/**
 * Smartcart panel - settings screen (M9).
 *
 * Pure HTML builder for the settings screen, no DOM access. The host
 * injects the returned string into its shadow root. Controls carry
 * `data-action` attributes handled by panel-settings-actions.js.
 */

const VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const { esc } = await import(`./panel-view.js?v=${VERSION}`);
const { storeTabs } = await import(`./panel-store-view.js?v=${VERSION}`);

/**
 * Settings screen: store-wide defaults and notification behaviour.
 *
 * ctx: { settings, layouts, notifyServices (sorted service names, no domain) }
 */
export function settingsScreen(ctx) {
  const settings = ctx.settings;
  const layoutOptions = [
    '<option value="">Store default</option>',
    ...ctx.layouts.map(
      (layout) =>
        `<option value="${esc(layout.id)}"${layout.id === settings.default_layout_id ? " selected" : ""}>${esc(layout.name)}</option>`
    ),
  ].join("");
  const hasNotify = ctx.notifyServices.length > 0;
  const notifyOptions = hasNotify
    ? ctx.notifyServices
        .map((name) => {
          const value = `notify.${name}`;
          return `<option value="${esc(value)}"${value === settings.notify_service ? " selected" : ""}>${esc(name)}</option>`;
        })
        .join("")
    : '<option value="">No notify services available</option>';
  return `
    ${storeTabs("settings")}
    <p class="hint">Store-wide defaults. Changes apply to every list.</p>
    <div class="store-list">
      <div class="store-row settings-row">
        <ha-icon icon="mdi:format-list-box" class="row-icon"></ha-icon>
        <span class="row-name">Default layout</span>
        <select data-action="settings-default-layout" class="settings-select" aria-label="Default layout">
          ${layoutOptions}
        </select>
      </div>
      <div class="store-row settings-row">
        <ha-icon icon="mdi:eye-off-outline" class="row-icon"></ha-icon>
        <span class="row-name">Hide checked by default</span>
        <label class="check" title="Start the shopping view with checked items hidden">
          <input type="checkbox" data-action="settings-hide-checked"${settings.hide_checked ? " checked" : ""} aria-label="Hide checked items by default">
          <ha-icon icon="mdi:check"></ha-icon>
        </label>
      </div>
      <h2 class="shead settings-shead"><ha-icon icon="mdi:bell-outline"></ha-icon><span>Notifications</span></h2>
      <div class="store-row settings-row">
        <ha-icon icon="mdi:bell-ring-outline" class="row-icon"></ha-icon>
        <span class="row-name">Notify on add</span>
        <label class="check" title="Send a notification when an item is added">
          <input type="checkbox" data-action="settings-notify-on-add"${settings.notify_on_add ? " checked" : ""} aria-label="Notify when an item is added">
          <ha-icon icon="mdi:check"></ha-icon>
        </label>
      </div>
      <div class="store-row settings-row">
        <ha-icon icon="mdi:bell-outline" class="row-icon"></ha-icon>
        <span class="row-name">Notify service</span>
        <select data-action="settings-notify-service" class="settings-select"${hasNotify ? "" : " disabled"} aria-label="Notification service">
          ${notifyOptions}
        </select>
      </div>
    </div>
    ${hasNotify ? "" : '<p class="hint">Set up a notification integration (for example your phone via "Mobile App") to enable notifications.</p>'}
  `;
}
