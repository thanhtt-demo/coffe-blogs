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


def describe_image(image_bytes: bytes, media_type: str, context: str = "") -> str:
    """Use LLM vision to describe an image and return a text summary.

    Args:
        image_bytes: raw bytes of the image file.
        media_type: MIME type, e.g. "image/jpeg", "image/png", "image/webp".
        context: optional hint (e.g. material name/description) to guide the
                 description.

    Returns:
        A Vietnamese text description of the image content, or empty string
        on failure.
    """
    prompt = (
        "Hãy trích xuất chính xác toàn bộ nội dung văn bản và thông tin có trong hình ảnh này. "
        "Chỉ ghi lại những gì thực sự xuất hiện trong ảnh — không thêm, không bớt, không diễn giải. "
        "Nếu ảnh chứa text, ghi lại nguyên văn. Nếu ảnh chứa biểu đồ/bảng, mô tả dữ liệu chính xác. "
        "Trả lời bằng tiếng Việt."
    )
    if context:
        prompt += f"\n\nNgữ cảnh: {context}"

    provider = _get_provider()
    try:
        if provider == "openai":
            result = _describe_image_openai(image_bytes, media_type, prompt)
        else:
            result = _describe_image_bedrock(image_bytes, media_type, prompt)
        print(f"[LLM] Image described: {len(result)} chars")
        return result
    except Exception as e:
        print(f"[LLM] Image description failed ({provider}): {type(e).__name__}: {e}")
        return ""


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


# ---------------------------------------------------------------------------
# Vision helpers
# ---------------------------------------------------------------------------

def _describe_image_bedrock(image_bytes: bytes, media_type: str, prompt: str) -> str:
    import base64
    import boto3

    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=_get_bedrock_model(),
        messages=[{
            "role": "user",
            "content": [
                {
                    "image": {
                        "format": media_type.split("/")[-1],  # jpeg, png, webp
                        "source": {"bytes": image_bytes},
                    }
                },
                {"text": prompt},
            ],
        }],
        inferenceConfig={"maxTokens": 2048, "temperature": 0.3},
    )
    return response["output"]["message"]["content"][0]["text"]


def _describe_image_openai(image_bytes: bytes, media_type: str, prompt: str) -> str:
    import base64
    from openai import OpenAI

    client = OpenAI()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{media_type};base64,{b64}"
    model = _get_openai_model()

    # Use Responses API with input_image format (works with gpt-5.x models)
    try:
        response = client.responses.create(
            model=model,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }],
        )
        return response.output_text or ""
    except Exception as e:
        print(f"[LLM] Responses API vision failed with {model}: {e}")
        # Fallback: Chat Completions API with gpt-4o
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }],
                max_completion_tokens=2048,
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception as e2:
            print(f"[LLM] Chat Completions fallback also failed: {e2}")
            raise
