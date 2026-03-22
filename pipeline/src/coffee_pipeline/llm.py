"""
LLM abstraction — hỗ trợ AWS Bedrock và OpenAI.

Chọn provider qua env var:
  LLM_PROVIDER=bedrock   (default)  → dùng AWS Bedrock
  LLM_PROVIDER=openai               → dùng OpenAI API

Config Bedrock:
  BEDROCK_MODEL_ID=...              (default: global.anthropic.claude-sonnet-4-6)
  AWS_DEFAULT_REGION=...            (default: us-east-1)

Config OpenAI:
  OPENAI_API_KEY=sk-...             (required)
  OPENAI_MODEL_ID=gpt-5.4-mini      (default)
"""

import os


def get_model_label() -> str:
    """Trả về string mô tả model đang active để dùng trong log."""
    if _get_provider() == "openai":
        return f"openai/{_get_openai_model()}"
    return f"bedrock/{_get_bedrock_model()}"


def call_llm(
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> tuple[str, dict]:
    """
    Gọi LLM và trả về (text, usage).

    usage dict luôn có 2 keys:
      inputTokens  : int | "?"
      outputTokens : int | "?"
    """
    provider = _get_provider()
    if provider == "openai":
        return _call_openai(system, user, max_tokens, temperature)
    return _call_bedrock(system, user, max_tokens, temperature)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_provider() -> str:
    return os.getenv("LLM_PROVIDER", "bedrock").lower()


def _get_bedrock_model() -> str:
    return os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-6")


def _get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL_ID", "gpt-5.4-mini")


def _call_bedrock(system: str, user: str, max_tokens: int, temperature: float) -> tuple[str, dict]:
    import boto3  # lazy import — chỉ cần khi dùng Bedrock

    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=_get_bedrock_model(),
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    raw = response.get("usage", {})
    usage = {
        "inputTokens" : raw.get("inputTokens",  "?"),
        "outputTokens": raw.get("outputTokens", "?"),
    }
    text = response["output"]["message"]["content"][0]["text"]
    return text, usage


def _call_openai(system: str, user: str, max_tokens: int, temperature: float) -> tuple[str, dict]:
    from openai import OpenAI  # lazy import — chỉ cần khi dùng OpenAI

    client = OpenAI()  # tự đọc OPENAI_API_KEY từ env
    model = _get_openai_model()

    # Newer models (o-series, gpt-5.x) require max_completion_tokens; legacy
    # models use max_tokens. Try max_completion_tokens first and fall back.
    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_completion_tokens": max_tokens,
        "temperature": temperature,
    }
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as e:
        msg = str(e)
        if "max_completion_tokens" in msg and "not supported" in msg:
            # Fall back to legacy parameter
            kwargs["max_tokens"] = kwargs.pop("max_completion_tokens")
            response = client.chat.completions.create(**kwargs)
        else:
            raise

    u = response.usage
    usage = {
        "inputTokens" : u.prompt_tokens     if u else "?",
        "outputTokens": u.completion_tokens if u else "?",
    }
    text = response.choices[0].message.content or ""
    return text, usage
