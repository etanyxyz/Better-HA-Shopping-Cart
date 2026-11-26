# Better HA Shopping Cart

An improved Home Assistant supermarket shopping cart: a mobile-friendly shopping
list custom integration with store sections, named layouts per supermarket,
tick boxes, list templates, and native Home Assistant to-do entities (so it
works with dashboards, the built-in to-do card, and Assist voice).

> **Status:** under active development (v0.1.0 milestone M0). The integration
> currently loads with a config entry; the UI, commands and to-do entities
> arrive in the upcoming milestones.

## Features (v1)

- **Sections** — create supermarket sections/groups and reorder them to match
  a real store.
- **Named layouts** — save a layout per supermarket (e.g. "Tesco", "Costco")
  and switch between them.
- **Tick boxes** — check items off while walking the store.
- **List templates** — quickly add regular items to the list.
- **Quantity & units** per item (e.g. `2 kg potatoes`).
- **Notes** per item (e.g. "the green ones").
- **Quick re-add from history** — re-add recent items or repeat the last shop.
- **Multiple named lists** at once (Weekly, Party, BBQ).
- **Native HA to-do entity** + Assist voice ("add milk to shopping list").
- **Smart auto-categorisation** of new items into sections (a keyword
  dictionary that learns your corrections).
- **Household notifications** when items are added.

## Installation

### HACS

1. In Home Assistant, go to **Settings → Add-ons → HACS**.
2. Open HACS and choose **Integrations**.
3. Search for **Better Shopping Cart** and click **Download**.
4. Restart Home Assistant.

### Manual

1. Clone or download this repository.
2. Copy the `custom_components/better_shopping_cart` folder into your
   Home Assistant configuration directory (next to `configuration.yaml`).
3. Restart Home Assistant.

## Configuration

Go to **Settings → Devices & Services → Add Integration** and select
**Better Shopping Cart**. No credentials are required — optionally give the
entry a name.

## Limitations

- Single list per list entity (one to-do entity per named list).
- English only.
- No offline/PWA support.

## Repository notes

`PLAN.md`, `AGENTS.md` and `.env` are local development files and are
git-ignored by design.

## License

MIT — see [LICENSE](LICENSE).
