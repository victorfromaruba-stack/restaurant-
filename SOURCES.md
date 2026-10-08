## 8 Oct 2026 update
- Made with Google Gemini (gemini-3-pro-image), checked against each menu `desc`, saved at the same paths as before: Smash cheeseburger (`smash-shack/assets/dishes/sc-hero.webp`, `sc.webp`), Smash burger combo (`co.webp`), Ground beef street tacos (`taco-brava/assets/art/gt.webp`, a photo-style picture despite the folder name), Crispy shrimp tacos (`taco-brava/assets/dishes/st.webp`), Bitterballen (`oranje-snack/assets/art/bb.webp`). Illustrations, not kitchen photos: every menu says "Pictures are illustrations."

## 7 Oct 2026 update
- Oranje Snack dish pictures, Taco Brava `gt` and the three cans (`shared/drinks/`) are original drawings made for this site (sources + scripts in `build/art/`). No brand logos on the cans.
- Dushi Wok Family Table picture (`dushi-wok/assets/dishes/ft.webp`) is a composite of the fried rice, sweet & sour and lo mein photos (master in `build/photo-masters/dushi-wok/`).
- Oranje Snack logo: lettering in Fraunces (SIL OFL 1.1, outlined in the SVG).
- Home/cart type: Familjen Grotesk (SIL OFL 1.1, `shared/FAMILJEN-OFL.txt`). Oranje Snack headings: Fraunces (`oranje-snack/assets/FRAUNCES-OFL.txt`).
- Picker cards and atmosphere covers were retired; the home page and menu headers use the real dish pictures.

Menus from Atlas ghost_kitchen_model_v3.xlsx sheet Menus via build/extract_menus.py.
Brand palettes & fonts from /workspace/hype/ghost-kitchen-brand-pack.md.
Fonts: Fredoka, Nunito, Bungee, Work Sans, Anton, Inter (subset), Playfair Display, Lora — SIL Open Font License.

## Logos (shared/logos/) — all Pixel real files
- dushi-wok.svg — /workspace/pixel/dushi-wok/dushi-wok-wordmark-horizontal.svg (header)
- dushi-wok-mark.webp/.png/.svg — /workspace/pixel/dushi-wok/dushi-wok-logo-1000.* (picker mark)
- taco-brava.svg — /workspace/pixel/taco-brava/taco-brava-wordmark-horizontal.svg
- taco-brava-mark.* — /workspace/pixel/taco-brava/taco-brava-logo-1000.*
- smash-shack.svg — /workspace/pixel/smash-shack/smash-shack-wordmark-horizontal.svg
- smash-shack-mark.webp — from smash-shack-logo-1000-light.png (dark picker card body)
- nonnas-night-in.svg — /workspace/pixel/nonnas-night-in/nonnas-night-in-wordmark-horizontal.svg
- nonnas-night-in-mark.* — /workspace/pixel/nonnas-night-in/nonnas-night-in-logo-1000.*

## Picker cards (shared/picker/*.webp)
From /workspace/pixel/order-site/hub/*-picker-card-780x360.png → compressed WebP.

## Brand covers ({brand}/assets/cover.webp)
From /workspace/pixel/order-site/<brand>/*-cover-1400x800.png → compressed WebP.

## Signature heroes ({brand}/assets/dishes/{id}-hero.jpg + .webp)
Pixel photoreal illustrative JPGs (NOT a kitchen shoot). Honesty line on each menu.
- dushi-wok fr ← order-site/dushi-wok/dushi-wok-fr-chicken-fried-rice-1400x800.jpg
- taco-brava bt ← …/taco-brava-bt-birria-tacos-consomme-1400x800.jpg
- smash-shack sc ← …/smash-shack-sc-smash-cheeseburger-1400x800.jpg
- nonnas-night-in bp ← …/nonnas-night-in-bp-baked-penne-bolognese-1400x800.jpg
Live pages serve the WebP phone crop; JPG kept alongside for swap/archive.

## Other dish stills ({brand}/assets/dishes/*.webp)
Forge brand stills via build/images/generate_stills.py (SVG art direction). Graphic, not fake food photos.
Pixel order-site *.png dish stand-ins are NOT on the live site.
See build/images/DISH_ASSET_MAP.md for data-id → path swap map.
No real kitchen dish photos found on the box (frank* excluded).

## Full menu photoreal (Mon 5 Oct 2026)
All mains/sides from `/workspace/pixel/order-site/{brand}/*-1400x800.jpg` → `{brand}/assets/dishes/`.
Page uses phone JPG (`{id}.jpg` / `{id}-hero.jpg`); masters kept as `*-1400x800.jpg`. Phone WebP siblings under ~60 KB.
Drinks stay `cd.webp` brand stills. Covers/picker/logos unchanged.
Honesty: photos illustrative, not kitchen shoot — soft-launch only.


## Pixel v2 picker (food-filled) — Mon 5 Oct 2026
Food-filled picker cards supersede atmosphere-only `shared/picker/*.webp` (were ~6–7 KB empty frames; Smash was ~41 KB checkered).
- Masters: `shared/picker/{brand}@2x.png` (1560×720) + `shared/picker/{brand}.png` (780×360)
- Hub serve: `shared/picker/{brand}.webp` (780×360, q≈82)
- Archive: `/workspace/pixel/order-site/hub/{brand}-picker-card-v2-780x360.png` + `-1560x720.png`
- Heroes composited: dushi fr chicken fried rice; taco bt birria; smash sc cheeseburger; nonna bp baked penne
- Wordmarks from `shared/logos/*-wordmark.png`; brand atmosphere per Hype matrix (Smash checkered only)
- Covers refreshed into `shared/covers/{brand}.{png,webp}` at 1400×800 from `order-site/{brand}/*-cover-1400x800.png` (menu headers; picker aspect stays separate)
- Brief: `shared/VISUAL_BRIEF.md`
- Script: `/workspace/pixel/order-site/src/build_picker_v2.py`
Old hub atmosphere PNGs (`*-picker-card-780x360.png`) retained as reference only.
