/**
 * Better Shopping Cart panel - settings screen actions (M9).
 *
 * The mutations behind the settings screen: default layout, hide-checked
 * default, notify service and notify-on-add. `settings/update` is global
 * (no `list_id`), so `_ws` is called directly rather than `_mutate`.
 * Expects the data mixin's `_ws`/`_refresh` and the host's
 * `_renderContent()`, plus `_view` and `_notifyServices` initialised in
 * the host's constructor.
 */

const VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const settingsView = await import(`./panel-settings-view.js?v=${VERSION}`);

export const settingsActionsMixin = (base) =>
  class extends base {
    /** Render the settings screen. */
    _renderSettingsContent() {
      const content = this._root.querySelector(".content");
      if (!content) {
        return;
      }
      content.innerHTML = settingsView.settingsScreen({
        settings: this._settings,
        layouts: this._layouts,
        notifyServices: this._notifyServices,
      });
    }

    /**
     * Populate the notify service picker from HA's service registry
     * (the core `get_services` command, filtered to the `notify` domain).
     */
    async _loadNotifyServices() {
      const services = await this._hass.callWS({ type: "get_services" });
      this._notifyServices = Object.keys(services.notify || {}).sort();
      // The screen rendered once on view entry with an empty list; paint it
      // again now the picker can be populated.
      if (this._view === "settings") {
        this._renderContent();
      }
    }

    /** Handle change events from the settings controls. */
    async _onSettingsChange(el) {
      const action = el.dataset.action;
      if (action === "settings-default-layout") {
        // Empty value = no default (lists follow their own layout).
        await this._saveSetting({ default_layout_id: el.value || null });
      } else if (action === "settings-hide-checked") {
        await this._saveSetting({ hide_checked: el.checked });
      } else if (action === "settings-notify-on-add") {
        await this._saveSetting({ notify_on_add: el.checked });
      } else if (action === "settings-notify-service") {
        await this._saveSetting({ notify_service: el.value });
      }
    }

    /** Persist one settings key and refresh the local copy. */
    async _saveSetting(values) {
      await this._ws("settings/update", values);
      await this._refresh();
    }
  };
