/**
 * Better Shopping Cart panel - store management actions (M7).
 *
 * The mutations behind the sections and layouts screens: create, rename,
 * delete, reorder (pointer drag, layouts only), hidden sections, default
 * layout, and the shopping view's layout switch. The default sections are
 * immutable (NOTES: Sections tab); custom sections keep their creation
 * order.
 * Expects the data mixin's methods (`_ws`, `_refresh`) and the host's
 * `_renderContent()`, plus the state fields `_view`, `_editingSectionId`
 * and `_editingLayoutId` initialised in the host's constructor.
 *
 * `settings/update` is global (no `list_id`), so the default-layout toggle
 * calls `_ws` directly rather than `_mutate`.
 */

const VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const storeView = await import(`./panel-store-view.js?v=${VERSION}`);

export const storeActionsMixin = (base) =>
  class extends base {
    /** Render the active store screen (sections, or layouts + editor). */
    _renderStoreContent() {
      const content = this._root.querySelector(".content");
      if (!content) {
        return;
      }
      if (this._view === "sections") {
        const sorted = [...this._sections].sort((a, b) => a.order - b.order);
        content.innerHTML = storeView.sectionsScreen({
          defaultSections: sorted.filter(storeView.isDefaultSection),
          customSections: sorted.filter((s) => !storeView.isDefaultSection(s)),
          editingId: this._editingSectionId,
        });
        this._focusStoreInput(".section-name-input");
        return;
      }
      const layout = this._editingLayoutId
        ? this._layouts.find((l) => l.id === this._editingLayoutId)
        : null;
      content.innerHTML = layout
        ? storeView.layoutEditor(layout, {
            order: this._layoutOrder(layout),
            hidden: layout.hidden_sections || [],
          })
        : storeView.layoutsScreen({
            layouts: this._layouts,
            defaultId: this._settings.default_layout_id,
          });
      this._focusStoreInput(".layout-name-input");
    }

    /** Focus the first editable input of a freshly rendered edit form. */
    _focusStoreInput(selector) {
      const input = this._root.querySelector(selector);
      if (input) {
        input.focus();
      }
    }

    /** Effective section order of a layout (stored + missing sections). */
    _layoutOrder(layout) {
      const byId = new Map(this._sections.map((s) => [s.id, s]));
      const order = (layout.section_order || [])
        .map((id) => byId.get(id))
        .filter(Boolean);
      const known = new Set(order.map((s) => s.id));
      for (const s of [...this._sections].sort((a, b) => a.order - b.order)) {
        if (!known.has(s.id)) {
          order.push(s);
        }
      }
      return order;
    }

    async _onStoreAction(action, el) {
      switch (action) {
        case "store-tab":
          this._editingSectionId = null;
          this._editingLayoutId = null;
          this._gotoView(el.dataset.tab);
          break;
        case "section-add":
          await this._saveNewSection();
          break;
        case "section-edit":
          this._editingSectionId =
            el.closest("[data-section-id]").dataset.sectionId;
          this._renderContent();
          break;
        case "section-save":
          await this._saveSection(el.closest("[data-section-id]"));
          break;
        case "section-cancel":
          this._editingSectionId = null;
          this._renderContent();
          break;
        case "section-delete":
          await this._ws("sections/delete", {
            section_id: el.closest("[data-section-id]").dataset.sectionId,
          });
          await this._refresh();
          break;
        case "layout-add":
          await this._saveNewLayout();
          break;
        case "layout-edit":
          this._editingLayoutId = el.closest("[data-layout-id]").dataset.layoutId;
          this._renderContent();
          break;
        case "layout-done":
          this._editingLayoutId = null;
          this._renderContent();
          break;
        case "layout-save-name":
          await this._saveLayoutName(el.closest("[data-layout-id]"));
          break;
        case "layout-default": {
          const layoutId = el.closest("[data-layout-id]").dataset.layoutId;
          const isDefault = this._settings.default_layout_id === layoutId;
          await this._ws("settings/update", {
            default_layout_id: isDefault ? null : layoutId,
          });
          await this._refresh();
          break;
        }
        case "layout-delete":
          this._editingLayoutId = null;
          await this._ws("layouts/delete", {
            layout_id: el.closest("[data-layout-id]").dataset.layoutId,
          });
          await this._refresh();
          break;
        case "layout-section-up":
        case "layout-section-down":
          await this._reorderLayoutSection(
            el,
            action === "layout-section-up" ? -1 : 1
          );
          break;
      }
    }

    async _onStoreChange(el) {
      const action = el.dataset.action;
      if (action === "select-layout") {
        // Explicit null clears the list's layout (follow the store default).
        await this._ws("lists/update", {
          list_id: this._activeListId,
          layout_id: el.value || null,
        });
        await this._refresh();
      } else if (action === "layout-hide") {
        const container = el.closest("[data-layout-id]");
        if (!container) {
          return;
        }
        const hidden = Array.from(
          container.querySelectorAll('input[data-action="layout-hide"]')
        )
          .filter((input) => input.checked)
          .map(
            (input) => input.closest("[data-section-id]").dataset.sectionId
          );
        await this._ws("layouts/update", {
          layout_id: container.dataset.layoutId,
          hidden_sections: hidden,
        });
        await this._refresh();
      }
    }

    async _onStoreKeydown(event) {
      const t = event.target;
      const cls = t.classList;
      if (event.key === "Enter" && cls.contains("store-add-input")) {
        event.preventDefault();
        if (this._view === "sections") {
          await this._saveNewSection();
        } else {
          await this._saveNewLayout();
        }
      } else if (
        event.key === "Enter" &&
        cls.contains("section-name-input")
      ) {
        event.preventDefault();
        await this._saveSection(t.closest("[data-section-id]"));
      } else if (event.key === "Enter" && cls.contains("layout-name-input")) {
        event.preventDefault();
        await this._saveLayoutName(t.closest("[data-layout-id]"));
      } else if (event.key === "Escape" && t.closest(".row-edit")) {
        this._editingSectionId = null;
        this._renderContent();
      }
    }

    /** Drag reorder committed by the pointer drag helper (layout editor). */
    async _onDragReorder(ids) {
      if (this._view === "layouts" && this._editingLayoutId) {
        const layout = this._layouts.find((l) => l.id === this._editingLayoutId);
        if (!layout) {
          return;
        }
        const known = new Set(this._sections.map((s) => s.id));
        const order = ids.filter((id) => known.has(id));
        for (const s of this._layoutOrder(layout)) {
          if (!order.includes(s.id)) {
            order.push(s.id);
          }
        }
        await this._ws("layouts/update", {
          layout_id: layout.id,
          section_order: order,
        });
        await this._refresh();
      }
    }

    async _saveNewSection() {
      const input = this._root.querySelector(".store-add-input");
      const name = input.value.trim();
      if (!name) {
        return;
      }
      await this._ws("sections/create", { name });
      await this._refresh();
    }

    async _saveSection(row) {
      if (!row) {
        return;
      }
      const name = row.querySelector(".section-name-input").value.trim();
      if (!name) {
        return;
      }
      this._editingSectionId = null;
      await this._ws("sections/update", {
        section_id: row.dataset.sectionId,
        name,
      });
      await this._refresh();
    }

    async _saveNewLayout() {
      const input = this._root.querySelector(".store-add-input");
      const name = input.value.trim();
      if (!name) {
        return;
      }
      const { layout } = await this._ws("layouts/create", { name });
      this._editingLayoutId = layout.id;
      await this._refresh();
    }

    async _saveLayoutName(container) {
      if (!container) {
        return;
      }
      const name = container.querySelector(".layout-name-input").value.trim();
      if (!name) {
        return;
      }
      await this._ws("layouts/update", {
        layout_id: container.dataset.layoutId,
        name,
      });
      await this._refresh();
    }

    async _reorderLayoutSection(el, delta) {
      const container = el.closest("[data-layout-id]");
      const layout = this._layouts.find((l) => l.id === container.dataset.layoutId);
      if (!layout) {
        return;
      }
      const order = this._layoutOrder(layout).map((s) => s.id);
      const index = order.indexOf(el.closest("[data-section-id]").dataset.sectionId);
      const target = index + delta;
      if (index < 0 || target < 0 || target >= order.length) {
        return;
      }
      [order[index], order[target]] = [order[target], order[index]];
      await this._ws("layouts/update", {
        layout_id: layout.id,
        section_order: order,
      });
      await this._refresh();
    }
  };
