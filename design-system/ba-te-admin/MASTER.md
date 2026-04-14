# Design System — Ba Tê Admin

> **LOGIC:** When building a specific page, first check `design-system/ba-te-admin/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Ba Tê Admin
**Updated:** 2026-04-08
**Style:** Minimalism & Swiss Style (admin panel variant)

---

## Design Philosophy

- Admin-first: tối giản, tập trung vào chức năng, không marketing
- Single-user tool: không cần onboarding, social proof, hay landing page
- Tái sử dụng Tailwind CSS có sẵn trong Astro project
- Vanilla JS + fetch API, không thêm framework JS
- Tiếng Việt toàn bộ UI labels
- Desktop-first, responsive mobile

---

## Color Palette

| Role       | Hex       | Tailwind     | Usage                                 |
| ---------- | --------- | ------------ | ------------------------------------- |
| Primary    | `#18181B` | `zinc-900`   | Headers, primary text, nav            |
| Secondary  | `#3F3F46` | `zinc-700`   | Secondary text, borders               |
| Muted      | `#71717A` | `zinc-500`   | Placeholder, timestamps               |
| CTA/Accent | `#2563EB` | `blue-600`   | Primary buttons, links, active states |
| Danger     | `#DC2626` | `red-600`    | Delete buttons, error states          |
| Success    | `#16A34A` | `green-600`  | Success toast, completed status       |
| Warning    | `#CA8A04` | `yellow-600` | Draft badges, pending status          |
| Background | `#FAFAFA` | `zinc-50`    | Page background                       |
| Surface    | `#FFFFFF` | `white`      | Cards, modals, inputs                 |
| Border     | `#E4E4E7` | `zinc-200`   | Card borders, dividers, input borders |
| Text       | `#09090B` | `zinc-950`   | Body text                             |

**Rationale:** Editorial black palette (zinc scale) giữ tông chuyên nghiệp. Blue accent thay vì pink — phù hợp hơn cho admin tool. Status colors (green/yellow/red) cho pipeline job states.

---

## Typography

**Font:** Inter (single family, weight variations)
**Category:** Minimal Swiss — clean, functional, neutral
**Best for:** Dashboards, admin panels, documentation

**Tailwind config:** Project đã có `@fontsource-variable/inter` trong dependencies, dùng trực tiếp.

| Element         | Size            | Weight | Tailwind                |
| --------------- | --------------- | ------ | ----------------------- |
| Page title      | 24px / 1.5rem   | 700    | `text-2xl font-bold`    |
| Section heading | 18px / 1.125rem | 600    | `text-lg font-semibold` |
| Card title      | 16px / 1rem     | 500    | `text-base font-medium` |
| Body text       | 14px / 0.875rem | 400    | `text-sm`               |
| Small/meta      | 12px / 0.75rem  | 400    | `text-xs`               |
| Mono (editor)   | 14px / 0.875rem | 400    | `text-sm font-mono`     |

---

## Spacing

Dùng Tailwind spacing scale, base unit 4px:

| Token          | Value   | Usage                            |
| -------------- | ------- | -------------------------------- |
| `gap-1`        | 4px     | Icon-text gaps                   |
| `gap-2`        | 8px     | Inline spacing, badge padding    |
| `p-4`          | 16px    | Card padding, form field spacing |
| `p-6`          | 24px    | Section padding                  |
| `py-6 md:py-8` | 24-32px | Page content padding             |
| `px-4 md:px-8` | 16-32px | Responsive horizontal padding    |
| `space-y-4`    | 16px    | Vertical stack spacing           |
| `space-y-6`    | 24px    | Section spacing                  |

---

## Layout

| Property                | Value      | Tailwind            |
| ----------------------- | ---------- | ------------------- |
| Max width               | 1152px     | `max-w-6xl mx-auto` |
| Page padding            | responsive | `px-4 py-6 md:px-8` |
| Border radius (cards)   | 8px        | `rounded-lg`        |
| Border radius (buttons) | 6px        | `rounded-md`        |
| Border radius (badges)  | 9999px     | `rounded-full`      |
| Border radius (inputs)  | 6px        | `rounded-md`        |

---

## Components

### Buttons

```
Primary:    bg-blue-600 text-white px-4 py-2 rounded-md font-medium
            hover:bg-blue-700 transition-colors duration-200 cursor-pointer
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2

Secondary:  bg-white text-zinc-700 border border-zinc-300 px-4 py-2 rounded-md font-medium
            hover:bg-zinc-50 transition-colors duration-200 cursor-pointer

Danger:     bg-red-600 text-white px-4 py-2 rounded-md font-medium
            hover:bg-red-700 transition-colors duration-200 cursor-pointer

Ghost:      text-zinc-600 px-3 py-1.5 rounded-md
            hover:bg-zinc-100 transition-colors duration-200 cursor-pointer
```

### Cards

```
Default:    bg-white border border-zinc-200 rounded-lg p-4
            (no shadow by default — minimalist)

Hover card: bg-white border border-zinc-200 rounded-lg p-4
            hover:border-zinc-300 transition-colors duration-200 cursor-pointer
```

### Inputs

```
Text:       w-full px-3 py-2 border border-zinc-300 rounded-md text-sm
            focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
            placeholder:text-zinc-400

Select:     Same as text input + appearance-none

Textarea:   Same as text input + min-h-[400px] font-mono (for markdown editor)
```

### Status Badges

```
Pending:    bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded-full text-xs font-medium
Running:    bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full text-xs font-medium
Completed:  bg-green-100 text-green-800 px-2 py-0.5 rounded-full text-xs font-medium
Failed:     bg-red-100 text-red-800 px-2 py-0.5 rounded-full text-xs font-medium
Draft:      bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded-full text-xs font-medium
Published:  bg-green-100 text-green-800 px-2 py-0.5 rounded-full text-xs font-medium
```

### Toast Notifications

```
Position:   fixed top-4 right-4 z-50
Container:  px-4 py-3 rounded-lg border shadow-sm max-w-sm
Success:    bg-green-50 border-green-200 text-green-800
Error:      bg-red-50 border-red-200 text-red-800
Info:       bg-blue-50 border-blue-200 text-blue-800
Behavior:   Auto-dismiss after 5 seconds, close button (X)
```

### Modal / Confirm Dialog

```
Overlay:    fixed inset-0 bg-black/50 z-40
Container:  bg-white rounded-lg p-6 max-w-md w-[90%] shadow-lg
            centered with flex items-center justify-center
Actions:    flex justify-end gap-3 mt-6
```

### Table

```
Container:  w-full border border-zinc-200 rounded-lg overflow-hidden
Header:     bg-zinc-50 text-xs font-medium text-zinc-500 uppercase tracking-wider
Row:        border-t border-zinc-200 hover:bg-zinc-50 transition-colors cursor-pointer
Cell:       px-4 py-3 text-sm
```

### Progress Indicator (Pipeline Steps)

```
Step done:      w-3 h-3 rounded-full bg-green-500
Step active:    w-3 h-3 rounded-full bg-blue-500 animate-pulse
Step pending:   w-3 h-3 rounded-full bg-zinc-200
Connector:      h-0.5 bg-zinc-200 (done: bg-green-500)
Label:          text-xs text-zinc-500 (active: text-blue-600 font-medium)
```

---

## Icons

Use Tabler icons via `astro-icon` (already installed in project):

```astro
<Icon name="tabler:edit" class="w-4 h-4" />
```

Key icons:
| Action | Icon |
|--------|------|
| Edit | `tabler:edit` |
| Delete | `tabler:trash` |
| Publish | `tabler:send` |
| Back | `tabler:arrow-left` |
| Logout | `tabler:logout` |
| Article | `tabler:file-text` |
| Search | `tabler:search` |
| Filter | `tabler:filter` |
| Close | `tabler:x` |
| Check | `tabler:check` |
| Alert | `tabler:alert-circle` |

---

## Transitions & Animation

| Property         | Duration | Easing        |
| ---------------- | -------- | ------------- |
| Color changes    | 200ms    | `ease`        |
| Border changes   | 200ms    | `ease`        |
| Opacity          | 150ms    | `ease-in-out` |
| Toast enter/exit | 300ms    | `ease-out`    |

**No layout-shifting animations.** No scale transforms on hover.
Respect `prefers-reduced-motion`: disable all animations.

---

## Responsive Breakpoints

| Breakpoint | Width   | Behavior                                                    |
| ---------- | ------- | ----------------------------------------------------------- |
| Mobile     | < 768px | Stack layout, card list instead of table, full-width inputs |
| Tablet     | 768px+  | Table layout, side-by-side form fields                      |
| Desktop    | 1024px+ | Full layout, max-w-6xl centered                             |

---

## Anti-Patterns (AVOID)

- No emojis as UI icons (use Tabler SVG icons)
- No scale transforms on hover (causes layout shift)
- No box-shadow heavy design (keep flat/minimal)
- No ornate decorations or gradients
- No instant state changes (always use transitions)
- No invisible focus states
- No low contrast text (4.5:1 minimum)

---

## Pre-Delivery Checklist

- [ ] No emojis used as icons (use Tabler SVG icons)
- [ ] All icons from `@iconify-json/tabler` (already installed)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (200ms)
- [ ] Text contrast 4.5:1 minimum (zinc-950 on zinc-50 = pass)
- [ ] Focus states visible (ring-2 ring-blue-500)
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px
- [ ] No content hidden behind fixed elements
- [ ] No horizontal scroll on mobile
- [ ] Vietnamese text renders correctly (UTF-8)
