/**
 * Better Shopping Cart panel - shopping view (M6).
 *
 * Registered as a custom panel: url /shopping-cart, module
 * bsc/better-shopping-cart-panel.js?v=<VERSION>. HA's wrapper
 * (ha-panel-custom) assigns `hass`, `panel`, `narrow` and `route` before
 * connect and may re-send them while connected, so all setters are
 * idempotent. Split by concern to keep each file small:
 *
 *   panel-view.js    pure HTML builders (no DOM access)
 *   panel-data.js    store copy: WS calls, refresh, live subscription
 *   panel-actions.js user actions: select/create, add, edit, delete, reorder
 *
 * The panel keeps a local copy of the store (lists, sections, layouts,
 * settings) plus the active list's items, refreshed after each mutation and
 * on every `better_shopping_cart/updated` event from the `subscribe` stream,
 * so edits from other clients (todo entities, other panels) appear live.
 */

const VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const view = await import(`./panel-view.js?v=${VERSION}`);
const { dataMixin } = await import(`./panel-data.js?v=${VERSION}`);
const { actionsMixin } = await import(`./panel-actions.js?v=${VERSION}`);

class BetterShoppingCartPanel extends dataMixin(actionsMixin(HTMLElement)) {
  constructor() {
    super();
    this._root = this.attachShadow({ mode: "open" });
    this._hass = null;
    this._panel = null;
    this._narrow = false;
    this._stylesReady = null;
    this._style = null;
    this._rendered = false;
    // Shopping view state (M6).
    this._lists = [];
    this._sections = [];
    this._layouts = [];
    this._settings = {};
    this._items = [];
    this._activeListId = null;
    this._editingItemId = null;
    this._refreshing = false;
    this._refreshQueued = false;
    this._unsubscribe = null;
  }

  /** Wrapper properties; setters are idempotent. */
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
    // Mirrors the app's sidebar state for the CSS [narrow] selector.
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
    // HA's ha-panel-custom creates this element inside the module script's
    // `load` callback and assigns `hass`/`panel`/`narrow` right away. This
    // module has top-level awaits (the sibling imports), so that callback can
    // run before customElements.define() below: the element is not upgraded
    // yet and the assignments land as plain own properties the real setters
    // never see. Re-apply any leftovers through the setters at upgrade time.
    for (const key of ["panel", "narrow", "hass"]) {
      if (Object.prototype.hasOwnProperty.call(this, key)) {
        const value = this[key];
        delete this[key];
        this[key] = value;
      }
    }
    this._boot();
  }

  disconnectedCallback() {
    this._hass = null;
    this._rendered = false;
    this._teardownSubscription();
  }

  /** First render once the wrapper has handed over `hass`. */
  _boot() {
    if (this._rendered || !this._hass) {
      return;
    }
    this._rendered = true;
    this._loadStyles().then(() => {
      this._render();
      this._refresh();
    });
  }

  /** Fetch panel.css and inject it into the shadow root. */
  _loadStyles() {
    if (!this._stylesReady) {
      const url = `${new URL(".", import.meta.url).href}panel.css?v=${VERSION}`;
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

  /** Build the static shell once; the shopping view goes into .content. */
  _render() {
    this._root.innerHTML = `
      <div class="appbar">
        <button type="button" class="menu-btn" aria-label="Open navigation menu">
          <ha-icon icon="mdi:menu"></ha-icon>
        </button>
        <h1 class="title">Shopping Cart</h1>
      </div>
      <div class="content"></div>
    `;
    // innerHTML resets wipe the injected <style>, so re-append it.
    if (this._style) {
      this._root.appendChild(this._style);
    }
    this._root.querySelector(".menu-btn").addEventListener("click", () => {
      // The app listens for this event on itself; bubbles + composed carry
      // it out of the shadow root. No detail: toggle the drawer.
      this.dispatchEvent(
        new Event("hass-toggle-menu", { bubbles: true, composed: true })
      );
    });
    this._bindContentEvents();
    this._renderContent();
  }

  // ------------------------------------------------------------ rendering

  _showError(err) {
    const content = this._root.querySelector(".content");
    if (content) {
      content.innerHTML = view.errorState(
        err && err.message ? err.message : err
      );
    }
  }

  _renderContent() {
    const content = this._root.querySelector(".content");
    if (!content) {
      return;
    }
    if (!this._lists.length) {
      content.innerHTML = view.noListsState();
      return;
    }
    const hideChecked = Boolean(this._settings.hide_checked);
    const groups = this._groupItems();
    const viewSections = this._viewSections();
    const sections = viewSections
      .map((section) => {
        const items = groups.get(section.id) || [];
        const visible = hideChecked
          ? items.filter((i) => !i.checked)
          : items;
        const remaining =
          items.length - items.filter((i) => i.checked).length;
        return { section, visible, remaining };
      })
      .filter((g) => g.visible.length);
    content.innerHTML = view.shoppingView({
      lists: this._lists,
      activeListId: this._activeListId,
      hideChecked,
      checked: this._items.filter((i) => i.checked).length,
      total: this._items.length,
      sections,
      viewSections,
      editingItemId: this._editingItemId,
    });
    if (this._editingItemId) {
      const name = content.querySelector(
        `[data-item-id="${this._editingItemId}"] .edit-name`
      );
      if (name) {
        name.focus();
      }
    }
  }

  // -------------------------------------------------------------- events

  _bindContentEvents() {
    const content = this._root.querySelector(".content");
    if (!content) {
      return;
    }
    const safe = (promise) =>
      Promise.resolve(promise).catch((err) => console.error(err));
    content.addEventListener("click", (event) => {
      const el = event.target.closest("[data-action]");
      if (!el || !content.contains(el)) {
        return;
      }
      safe(this._onAction(el.dataset.action, el));
    });
    content.addEventListener("change", (event) => {
      const el = event.target.closest("[data-action]");
      if (!el) {
        return;
      }
      if (el.dataset.action === "select-list") {
        safe(this._selectList(el.value));
      } else if (el.dataset.action === "check-item") {
        safe(
          this._mutate("items/check", {
            item_id: el.closest("[data-item-id]").dataset.itemId,
            checked: el.checked,
          })
        );
      } else if (el.dataset.action === "hide-checked") {
        safe(this._toggleHideChecked(el.checked));
      }
    });
    content.addEventListener("keydown", (event) => {
      const t = event.target;
      const cls = t.classList;
      if (event.key === "Enter" && cls.contains("add-input")) {
        event.preventDefault();
        safe(this._addItem());
      } else if (event.key === "Enter" && cls.contains("edit-name")) {
        event.preventDefault();
        safe(this._saveItem(t.closest("[data-item-id]")));
      } else if (event.key === "Enter" && cls.contains("new-list-input")) {
        event.preventDefault();
        safe(this._saveNewList(t));
      } else if (event.key === "Enter" && cls.contains("item-body")) {
        event.preventDefault();
        t.click();
      } else if (
        event.key === "Escape" &&
        t.closest(".item-edit, .new-list-form")
      ) {
        this._cancelEdit();
      }
    });
  }
}

// Guarded define: if a stale tab re-connects after an integration update,
// the module re-runs under a new ?v= URL; the first definition wins and the
// page simply needs a full reload to pick up the new code.
if (!customElements.get("better-shopping-cart-panel")) {
  customElements.define("better-shopping-cart-panel", BetterShoppingCartPanel);
}
