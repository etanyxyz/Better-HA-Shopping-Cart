/**
 * Better Shopping Cart panel - shopping view (M6) + store management (M7).
 *
 * Registered as a custom panel: url /shopping-cart, module
 * bsc/better-shopping-cart-panel.js?v=<VERSION>. HA's wrapper
 * (ha-panel-custom) assigns `hass`, `panel`, `narrow` and `route` before
 * connect and may re-send them while connected, so all setters are
 * idempotent. Split by concern to keep each file small:
 *
 *   panel-view.js          pure HTML builders, shopping view (no DOM access)
 *   panel-store-view.js    pure HTML builders, sections + layouts screens
 *   panel-template-view.js pure HTML builders, templates + history screens
 *   panel-data.js          store copy: WS calls, refresh, live subscription
 *   panel-actions.js       shopping view actions: add, edit, delete, reorder
 *   panel-store-actions.js store management actions + drag reorder commit
 *   panel-template-actions.js template/history actions (M8)
 *   panel-drag.js          pointer-event drag reorder helper
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
const { storeActionsMixin } = await import(`./panel-store-actions.js?v=${VERSION}`);
const { templateActionsMixin } = await import(
  `./panel-template-actions.js?v=${VERSION}`
);
const { attachDragReorder } = await import(`./panel-drag.js?v=${VERSION}`);

class BetterShoppingCartPanel extends dataMixin(
  templateActionsMixin(storeActionsMixin(actionsMixin(HTMLElement)))
) {
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
    // Store management state (M7/M8):
    // "shopping" | "sections" | "layouts" | "templates" | "history".
    this._view = "shopping";
    this._editingSectionId = null;
    this._editingLayoutId = null;
    // Templates & history state (M8).
    this._templates = [];
    this._recentItems = [];
    this._editingTemplateId = null;
    this._templateRowSeq = 0;
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
        <button type="button" class="menu-btn" aria-label="Open navigation menu"><ha-icon icon="mdi:menu"></ha-icon></button>
        <button type="button" class="icon-btn back-btn" aria-label="Back to shopping view" hidden><ha-icon icon="mdi:arrow-left"></ha-icon></button>
        <h1 class="title">Shopping Cart</h1>
        <button type="button" class="icon-btn manage-btn" aria-label="Manage store (sections and layouts)" title="Manage store"><ha-icon icon="mdi:store"></ha-icon></button>
      </div>
      <div class="content"></div>
    `;
    // innerHTML resets wipe the injected <style>, so re-append it.
    if (this._style) {
      this._root.appendChild(this._style);
    }
    this._root.querySelector(".menu-btn").addEventListener("click", () => {
      // bubbles + composed carry the event out of the shadow root.
      this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
    });
    this._root.querySelector(".back-btn").onclick = () => this._gotoView("shopping");
    this._root.querySelector(".manage-btn").onclick = () => this._gotoView("sections");
    this._bindContentEvents();
    this._renderContent();
  }

  /** Switch between the shopping view and the store management screens. */
  _gotoView(viewName) {
    this._view = viewName;
    this._editingSectionId = null;
    this._editingLayoutId = null;
    this._editingTemplateId = null;
    this._root.querySelector(".back-btn").hidden = viewName === "shopping";
    this._root.querySelector(".manage-btn").hidden = viewName !== "shopping";
    this._root.querySelector(".title").textContent =
      {
        shopping: "Shopping Cart",
        sections: "Sections",
        layouts: "Layouts",
        templates: "Templates",
        history: "History",
      }[viewName];
    this._renderContent();
    // Templates and history are fetched on entry (small, rarely needed).
    if (viewName === "templates") {
      this._loadTemplates().catch((err) => this._showError(err));
    } else if (viewName === "history") {
      this._loadHistory().catch((err) => this._showError(err));
    }
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
    if (this._view === "templates" || this._view === "history") {
      return this._renderTemplateContent();
    }
    if (this._view !== "shopping") {
      return this._renderStoreContent();
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
        const visible = hideChecked ? items.filter((i) => !i.checked) : items;
        return { section, visible, remaining: items.length - items.filter((i) => i.checked).length };
      })
      .filter((g) => g.visible.length);
    const activeList = this._lists.find((l) => l.id === this._activeListId);
    content.innerHTML = view.shoppingView({
      lists: this._lists,
      activeListId: this._activeListId,
      activeLayoutId: activeList ? activeList.layout_id : null,
      defaultLayoutId: this._settings.default_layout_id,
      layouts: this._layouts.map((l) => ({ id: l.id, name: l.name, isDefault: l.id === this._settings.default_layout_id })),
      hideChecked,
      checked: this._items.filter((i) => i.checked).length,
      total: this._items.length,
      sections,
      viewSections,
      editingItemId: this._editingItemId,
    });
    if (this._editingItemId) {
      const name = content.querySelector(`[data-item-id="${this._editingItemId}"] .edit-name`);
      name?.focus();
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
      const handler =
        this._view === "shopping"
          ? this._onAction
          : this._view === "templates" || this._view === "history"
            ? this._onTemplateAction
            : this._onStoreAction;
      safe(handler.call(this, el.dataset.action, el));
    });
    content.addEventListener("change", (event) => {
      const el = event.target.closest("[data-action]");
      if (!el) {
        return;
      }
      if (this._view !== "shopping") {
        safe(this._onStoreChange(el));
        return;
      }
      if (el.dataset.action === "select-list") {
        safe(this._selectList(el.value));
      } else if (el.dataset.action === "select-layout") {
        safe(this._onStoreChange(el));
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
      if (this._view === "templates" || this._view === "history") {
        safe(this._onTemplateKeydown(event));
        return;
      }
      if (this._view !== "shopping") {
        safe(this._onStoreKeydown(event));
        return;
      }
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
    // Pointer drag reorder for the store screens' row lists (M7).
    attachDragReorder(content, "[data-drag-row]", (ids) => {
      safe(this._onDragReorder(ids));
    });
  }
}

// Guarded define: if a stale tab re-connects after an integration update,
// the module re-runs under a new ?v= URL; the first definition wins and the
// page simply needs a full reload to pick up the new code.
if (!customElements.get("better-shopping-cart-panel")) {
  customElements.define("better-shopping-cart-panel", BetterShoppingCartPanel);
}
