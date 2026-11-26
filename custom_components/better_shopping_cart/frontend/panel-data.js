/**
 * Better Shopping Cart panel - data layer mixin (M6).
 *
 * Owns the local store copy: WS calls, refresh after each mutation and the
 * live subscription to the backend update stream, plus the derived view
 * data (sections in layout order, items grouped by section). Mixed into the
 * host element; expects the state fields initialised in its constructor and
 * the host's `_renderContent()`/`_showError()`.
 *
 * The stream is consumed with `hass.connection.subscribeMessage(callback,
 * message)`: the callback receives the streamed event string and the promise
 * resolves to an unsubscribe function. (`subscribeEvents` only listens to
 * core EventBus events, not to custom event messages.)
 */

const WS = "better_shopping_cart/";

export const dataMixin = (base) =>
  class extends base {
    _ws(type, payload = {}) {
      return this._hass.callWS({ type: WS + type, ...payload });
    }

    /** Run a mutation on the active list, then refresh the local copy. */
    async _mutate(type, payload = {}) {
      await this._ws(type, { list_id: this._activeListId, ...payload });
      await this._refresh();
    }

    /** Re-fetch all store data and the active list's items. */
    async _refresh() {
      if (this._refreshing) {
        this._refreshQueued = true;
        return;
      }
      this._refreshing = true;
      try {
        const [lists, sections, layouts, settings] = await Promise.all([
          this._ws("lists/list"),
          this._ws("sections/list"),
          this._ws("layouts/list"),
          this._ws("settings/get"),
        ]);
        this._lists = lists.lists;
        this._sections = sections.sections;
        this._layouts = layouts.layouts;
        this._settings = settings.settings;
        if (!this._lists.some((l) => l.id === this._activeListId)) {
          const active = this._settings.active_list_id;
          this._activeListId =
            active && this._lists.some((l) => l.id === active)
              ? active
              : this._lists.length
                ? this._lists[0].id
                : null;
        }
        await this._loadItems();
        await this._ensureSubscription();
        this._renderContent();
      } catch (err) {
        this._showError(err);
      } finally {
        this._refreshing = false;
        if (this._refreshQueued) {
          this._refreshQueued = false;
          this._refresh();
        }
      }
    }

    async _loadItems() {
      if (!this._activeListId) {
        this._items = [];
        return;
      }
      const { items } = await this._ws("items/list", {
        list_id: this._activeListId,
      });
      this._items = items;
    }

    /**
     * Subscribe to the store-update stream once the first list exists. The
     * backend streams an event on every commit (any list), so one
     * subscription covers all lists.
     */
    async _ensureSubscription() {
      if (this._unsubscribe || !this._activeListId) {
        return;
      }
      this._unsubscribe = await this._hass.connection.subscribeMessage(
        () => this._refresh(),
        { type: WS + "subscribe", list_id: this._activeListId }
      );
    }

    _teardownSubscription() {
      if (this._unsubscribe) {
        this._unsubscribe();
        this._unsubscribe = null;
      }
    }

    /** Sections of the active list's layout, in walking order. */
    _viewSections() {
      const list = this._lists.find((l) => l.id === this._activeListId);
      const layout =
        list && list.layout_id
          ? this._layouts.find((l) => l.id === list.layout_id)
          : null;
      const byId = new Map(this._sections.map((s) => [s.id, s]));
      const ordered = layout
        ? layout.section_order.map((id) => byId.get(id)).filter(Boolean)
        : [...this._sections].sort((a, b) => a.order - b.order);
      const hidden = layout ? new Set(layout.hidden_sections) : new Set();
      return ordered.filter((s) => !hidden.has(s.id));
    }

    /** Items grouped by section, each group in stored order. */
    _groupItems() {
      const groups = new Map();
      const sorted = [...this._items].sort((a, b) => a.order - b.order);
      for (const item of sorted) {
        if (!groups.has(item.section_id)) {
          groups.set(item.section_id, []);
        }
        groups.get(item.section_id).push(item);
      }
      return groups;
    }
  };
