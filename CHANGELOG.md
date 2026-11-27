# Changelog

## v1.1 — Smartcart (2026-11-27)

The repository was renamed to **Smartcart** (`etanyxyz/Smartcart`) and the
integration's display name is now **Smartcart**.

### New

- **Auto-scroll while dragging** — while reordering an item, hold the pointer
  near the top or bottom edge of the screen and the list scrolls away on its
  own (linear ramp over the outer 64px, up to ~16px/frame right at the edge).
  Works in the shopping view, layout editor and template editor.
- **Marketplace brand icon** — the HACS / HA Marketplace card now shows the
  Smartcart icon (`brand/icon.png` 256×256 and `brand/icon@2x.png` 512×512).
- **Rebrand** — display name changed from "Better Shopping Cart" to
  "Smartcart" (HA UI, store card, setup flow); documentation and issue
  tracker links point at the new repository.

### Changed

- **Up/down arrow buttons removed** — the drag grip is the only reorder path
  (shopping view items, layout sections, template items).

### Notes

- The internal domain stays `better_shopping_cart`, so existing installs
  keep working; the repository rename is handled by GitHub's redirect.

## v1.0

First release:

- Shopping cart view with multiple lists: add/check/delete items, hide
  checked items, list actions
- Store manager: default (immutable) and custom sections, per-store layouts
  with a section order
- Templates: save the active list as a template, edit and apply templates
- List history
- Settings screen
- Drag-and-drop reordering (plus up/down arrows, removed in v1.1)
- 146 automated tests; installable via HACS
