# Order · Aruba — Visual Brief (Picker Hub)

**Audience:** Forge / Muddy HTML rebuild  
**Owner assets:** Pixel  
**Date:** Mon 5 Oct 2026 (America/La_Paz)

## Goal
Make the order homepage feel like a **premium multi-restaurant picker** — four distinct brands, visually best-on-island, one kitchen cooking all. Food photo sells the tap; brand chrome confirms which kitchen.

## Research takeaways (3 patterns to steal)

1. **Photo-first 16:9-ish store tiles, chrome after** — DoorDash and Uber Eats put lifestyle/food hero at full card width (≈16:9 or 16:10), then name + meta in a tight block *under* the image. Food is the content; UI steps back.  
   Sources: [DoorDash DESIGN.md (awesome-ios-design-md)](https://github.com/Meliwat/awesome-ios-design-md/blob/main/design-md/food/doordash/DESIGN.md); [Uber Eats · DESIGN.md](https://www.webdesignhot.com/design.md/uber-eats/); [DoorDash · DESIGN.md](https://www.webdesignhot.com/design.md/doordash/).

2. **Food vs logo hierarchy** — Hero dish fills the tile; restaurant mark is a small overlay (DoorDash ≈56pt circular logo with white border). Never put the wordmark over the dish’s appetizing face. Leave breathing room so aggressive `object-fit: cover` crops still read.  
   Sources: same DoorDash notes; [FoodShot Uber Eats & DoorDash photo guide (2025)](https://foodshot.ai/blog/menu-photos-uber-eats-doordash-2025-guide) (centered subject, landscape export, no baked prices/ratings on the photo).

3. **Spacing & density** — Card stack with **12–18px gaps**, image edge-to-edge inside the radius, **12–14px** text padding below. Full-bleed media + short body beats padded “poster frames.” Our hub already uses `gap:16px`, `radius:20px`, media `780/360` — keep that rhythm; only upgrade the *pixels* inside `.card__media`.  
   Sources: DoorDash/Uber Eats store-card specs above. *(Mobbin restaurant-picker search blocked — paid plan; web design-system notes used instead.)*

## Page tokens (match / lightly improve `picker.css`)

| Token | Value | Notes |
| --- | --- | --- |
| Page bg | `#0C0D10` + soft radial `#1e2433` | Keep dark marketplace frame |
| Max width | `640px` | Phone-first hub |
| Card radius | `20px` | **Do not bake radius into images** |
| Rail gap | `16px` (18px ≥700px) | |
| H1 | `clamp(26px,7vw,34px)` / 700 Inter | Hero “Choose a kitchen” |
| Card name | `18px` → `20px` | `.card__name` |
| Card tagline | `14px` `#C9C2B6` | |
| CTA pill | `12px` uppercase, brand accent fill | `.card__cta` |
| Mark (HTML badge) | `56×56` → `64×64`, radius `16–18` | Bottom-left over media |
| Cuisine chip | top-right, blur pill | Can hide if micro-label on art feels redundant |

## Per-brand card chrome

| Brand | `.card__in` / body feel | Border / accent | Mark |
| --- | --- | --- | --- |
| **Dushi Wok** | Elev `#14161C`; accent Jade `#0F7B6C` | Top border 3px Jade | `shared/logos/dushi-wok-mark.webp` on white plate |
| **Taco Brava** | Same elev; accent Pink `#E6246E` | Top border Pink | `taco-brava-mark.webp` |
| **Smash Shack** | Body `#161616→#111`; Mustard `#FFC72C` | Mustard border; badge ring Mustard | Prefer `smash-shack-mark-light` / light mark on dark |
| **Nonna's Night In** | Body `#1a2018→#121610`; Sauce `#B23A2E` | Sauce border; cream name | `nonnas-night-in-mark.webp` |

Keep existing accent CSS in `picker.css` unless Forge intentionally restyles.

## Asset map

| Role | Path | Size |
| --- | --- | --- |
| Picker cover (hub card media) | `shared/picker/{brand}.webp` (+ `.png`, `@2x.png`) | **780×360** (master **1560×720**) |
| Circle-safe mark (card badge) | `shared/logos/{brand}-mark.webp` | Square; HTML sizes it |
| Wordmark (headers / optional) | `shared/logos/{brand}-wordmark.webp` / `.png` | Horizontal |
| Menu header covers (optional shared) | `shared/covers/{brand}.webp` + `.png` | **1400×800** atmosphere masters |
| Live brand page cover today | `{brand}/assets/cover.webp` | Unchanged by this drop — Forge may point to `shared/covers/` later |

**Brand filenames:** `dushi-wok` · `taco-brava` · `smash-shack` · `nonnas-night-in`

**Pixel archive:** `/workspace/pixel/order-site/hub/{brand}-picker-card-v2-780x360.png` and `-1560x720.png`  
Old atmosphere pickers (`*-picker-card-780x360.png`) kept as reference only.

## Hierarchy (on the card)

1. **Food photo** — signature dish, ~55–70% of media, center-right, soft left fade into brand field  
2. **Logo mark** — HTML `.card__badge` bottom-left (and small wordmark plate baked top-left on the art)  
3. **Short cuisine line** — baked micro-label on art (`Wok · Aruba` / `Birria · Street` / `Smash · Diner` / `Italian · Night In`); HTML `.card__cuisine` optional duplicate  

No prices, no fake ratings on the image.

## Composition notes (v2 pickers)

- **Dushi:** Moody jade/ink field → chicken fried rice bowl right; Rice plate + jade wordmark top-left; coral edge cue.  
- **Taco:** Pink→Chile gradient + lime flash; birria cheese-pull right; pink capsule wordmark (white keyed out).  
- **Smash:** Grill black + **checkered strip only on Smash**; mustard/ketchup bars; smash burger center-right.  
- **Nonna:** Basil linen + gold lamp glow; baked penne cheese-pull right; cream wordmark plate.

## Proposal (bold extra) — *proposal, not shipped*

Add a soft honesty/positioning line under the hero H1, muted 13–14px:

> **Four kitchens. One pass.**

Optional alternate: staggered 3px left accent bars on `.card` matching brand (in addition to current top border). Label both as proposal — Forge/Muddy decide.

## Honesty

Photos are **illustrative** until a real kitchen shoot. Keep the disclaimer in footer / menu copy — **never burn it onto the food image**.

## Build note

Compositor: `/workspace/pixel/order-site/src/build_picker_v2.py` (PIL; heroes + wordmarks composited). Re-run to regenerate pickers/covers.
