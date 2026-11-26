/**
 * Better Shopping Cart panel - mobile-first shell (M5).
 *
 * The integration registers this module as a custom panel:
 *   url         /shopping-cart
 *   module_url  bsc/better-shopping-cart-panel.js?v=<VERSION>
 *
 * HA's panel wrapper (ha-panel-custom) loads the module, creates
 * <better-shopping-cart-panel> and assigns the `panel`, `hass`, `narrow`
 * and `route` properties before the element connects. The element can also
 * receive property updates while connected, so all setters below are
 * idempotent.
 *
 * M5 renders the app shell (top app bar + content area). M6 renders the
 * shopping view inside `.content`, fed by the `better_shopping_cart/subscribe`
 * WebSocket stream.
 */

/** Cache-busting version: comes from the ?v= query on module_url. */
const VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";

class BetterShoppingCartPanel extends HTMLElement {
  constructor() {
    super();
    this._root = this.attachShadow({ mode: "open" });
    this._hass = null;
    this._panel = null;
    this._narrow = false;
    this._stylesReady = null;
    this._style = null;
    this._rendered = false;
  }

  /**
   * Properties set by HA's panel wrapper.
   *
   * @property {import("homeassistant").Hass} hass
   * @property {object} panel panel response (config lives in `panel.config`)
   * @property {boolean} narrow true when the app uses the drawer sidebar
   * @property {string} route unused by the shell (forward compatibility)
   */

  set hass(value) {
    this._hass = value;
    this._boot();
  }

  get hass() {
    return this._hass;
  }

  set panel(value) {
    this._panel = value;
    this._boot();
  }

  get panel() {
    return this._panel;
  }

  set narrow(value) {
    this._narrow = Boolean(value);
    // The CSS shows/hides the menu button based on this attribute so it
    // mirrors the app's sidebar state exactly (narrow == drawer sidebar).
    this.toggleAttribute("narrow", this._narrow);
    this._boot();
  }

  get narrow() {
    return this._narrow;
  }

  set route(_value) {
    // Accepted for forward compatibility; the shell has no routing.
  }

  connectedCallback() {
    this._boot();
  }

  disconnectedCallback() {
    this._hass = null;
    this._rendered = false;
  }

  /** First render once the wrapper has handed over `hass`. */
  _boot() {
    if (this._rendered || !this._hass) {
      return;
    }
    this._rendered = true;
    this._loadStyles().then(() => this._render());
  }

  /** Fetch panel.css and inject it into the shadow root. */
  _loadStyles() {
    if (!this._stylesReady) {
      const dir = new URL(".", import.meta.url).href;
      const url = `${dir}panel.css?v=${VERSION}`;
      this._stylesReady = fetch(url)
        .then((res) => (res.ok ? res.text() : ""))
        .catch(() => "")
        .then((css) => {
          const style = document.createElement("style");
          style.textContent = css;
          this._style = style;
          this._root.appendChild(style);
        });
    }
    return this._stylesReady;
  }

  _render() {
    this._root.innerHTML = `
      <div class="appbar">
        <button type="button" class="menu-btn"
                aria-label="Open navigation menu">
          <ha-icon icon="mdi:menu"></ha-icon>
        </button>
        <h1 class="title">Shopping Cart</h1>
      </div>
      <div class="content">
        <div class="empty">
          <ha-icon icon="mdi:cart-outline"></ha-icon>
          <p>Your shopping list will appear here.</p>
        </div>
      </div>
    `;
    // innerHTML resets wipe the injected <style>, so re-append it.
    if (this._style) {
      this._root.appendChild(this._style);
    }
    this._root.querySelector(".menu-btn").addEventListener("click", () => {
      // The app listens for this event on itself; bubbles + composed carry
      // the event out of the shadow root. No detail: toggle the drawer.
      this.dispatchEvent(
        new Event("hass-toggle-menu", { bubbles: true, composed: true })
      );
    });
  }
}

customElements.define("better-shopping-cart-panel", BetterShoppingCartPanel);
