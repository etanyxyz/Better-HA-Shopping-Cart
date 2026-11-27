/**
 * Smartcart panel - user actions mixin (M6).
 *
 * The mutations behind the view: list selection and creation, add, inline
 * edit (cleared unit/note submitted as empty strings, since the frozen §5
 * contract maps null to "leave unchanged"), delete, and drag reordering.
 * NOTES: Shopping Cart View adds the list actions (clear list, clear
 * completed, delete with confirmation) and the cross-section drag commit.
 * Expects the data mixin's methods (`_ws`, `_mutate`, `_refresh`,
 * `_groupItems`, `_viewSections`) and the host's `_renderContent()`.
 */

const VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const view = await import(`./panel-view.js?v=${VERSION}`);

export const actionsMixin = (base) =>
  class extends base {
    async _onAction(action, el) {
      switch (action) {
        case "new-list":
          this._showNewListForm();
          break;
        case "cancel-new-list": {
          const form = el.closest(".new-list-form");
          if (form) {
            form.remove();
          }
          break;
        }
        case "save-new-list":
          await this._saveNewList(
            el.closest(".new-list-form").querySelector(".new-list-input")
          );
          break;
        case "add-item":
          await this._addItem();
          break;
        case "edit-item": {
          const row = el.closest("[data-item-id]");
          if (row) {
            this._editingItemId = row.dataset.itemId;
            this._renderContent();
          }
          break;
        }
        case "cancel-edit":
          this._cancelEdit();
          break;
        case "save-item":
          await this._saveItem(el.closest("[data-item-id]"));
          break;
        case "delete-item":
          await this._mutate("items/delete", {
            item_id: el.closest("[data-item-id]").dataset.itemId,
          });
          break;
        // NOTES: Shopping Cart View - list actions menu.
        case "list-menu":
          this._listMenuOpen = !this._listMenuOpen;
          this._renderContent();
          break;
        case "clear-list":
          this._listMenuOpen = false;
          await this._mutate("lists/clear", {});
          break;
        case "clear-completed":
          this._listMenuOpen = false;
          await this._mutate("lists/clear_completed", {});
          break;
        case "delete-list":
          this._listMenuOpen = false;
          this._confirmDeleteList = true;
          this._renderContent();
          break;
        case "confirm-cancel":
          this._confirmDeleteList = false;
          this._renderContent();
          break;
        case "confirm-delete":
          this._confirmDeleteList = false;
          await this._mutate("lists/delete", {});
          break;
      }
    }

    _cancelEdit() {
      this._editingItemId = null;
      const form = this._root.querySelector(".new-list-form");
      if (form) {
        form.remove();
      }
      this._renderContent();
    }

    /** Insert the inline new-list form under the list bar (or at the top
     * in the no-lists state). */
    _showNewListForm() {
      const content = this._root.querySelector(".content");
      if (!content || content.querySelector(".new-list-form")) {
        return;
      }
      const form = document.createElement("div");
      form.innerHTML = view.newListForm();
      const el = form.firstElementChild;
      const listbar = content.querySelector(".listbar");
      if (listbar) {
        listbar.after(el);
      } else {
        content.prepend(el);
      }
      el.querySelector(".new-list-input").focus();
    }

    async _selectList(listId) {
      this._activeListId = listId;
      this._editingItemId = null;
      await this._ws("settings/update", { active_list_id: listId });
      await this._refresh();
    }

    async _toggleHideChecked(checked) {
      // `settings/update` is global (no list_id), so skip `_mutate`.
      await this._ws("settings/update", { hide_checked: checked });
      await this._refresh();
    }

    async _saveNewList(input) {
      const name = input.value.trim();
      if (!name) {
        return;
      }
      const payload = { name };
      const defaultLayoutId = this._settings.default_layout_id;
      if (
        defaultLayoutId &&
        this._layouts.some((l) => l.id === defaultLayoutId)
      ) {
        payload.layout_id = defaultLayoutId;
      }
      const { list } = await this._ws("lists/create", payload);
      this._activeListId = list.id;
      await this._refresh();
    }

    async _addItem() {
      const input = this._root.querySelector(".add-input");
      if (!input || !this._activeListId) {
        return;
      }
      const name = input.value.trim();
      if (name) {
        // No section_id: the backend auto-categorises (PLAN.md section 5).
        await this._mutate("items/add", { name });
      }
    }

    async _saveItem(row) {
      if (!row) {
        return;
      }
      const name = row.querySelector(".edit-name").value.trim();
      const qty = row.querySelector(".edit-qty").value;
      const unit = row.querySelector(".edit-unit").value.trim();
      const note = row.querySelector(".edit-note").value.trim();
      const payload = { item_id: row.dataset.itemId };
      if (name) {
        payload.name = name;
      }
      payload.section_id = row.querySelector(".edit-section").value;
      if (qty !== "") {
        payload.quantity = Number(qty);
      }
      // The frozen §5 contract maps null to "leave unchanged", so a cleared
      // field is submitted as an empty string (falsy, renders nothing).
      payload.unit = unit;
      payload.note = note;
      await this._mutate("items/update", payload);
      this._editingItemId = null;
    }

    /**
     * Commit a pointer drag of item rows (NOTES: Shopping Cart View).
     * `ids` is the new DOM order of all visible rows, across sections.
     * Rows that landed in a different section are first moved there via
     * `items/update` (which also teaches the learned category map, the
     * frozen §5 behaviour for moving an item), then the complete new
     * display order goes to `items/reorder`. Rows not in the DOM (checked
     * while hidden, the item being edited) keep their stored order at the
     * end of the submitted list.
     */
    async _commitItemDrag(ids) {
      const content = this._root.querySelector(".content");
      if (!content || !this._activeListId) {
        return;
      }
      const byId = new Map(this._items.map((i) => [i.id, i]));
      const moved = [];
      for (const row of content.querySelectorAll("[data-drag-row]")) {
        const item = byId.get(row.dataset.dragId);
        const sectionId = row.closest(".sblock")?.dataset.sectionId;
        if (item && sectionId && item.section_id !== sectionId) {
          moved.push({ id: item.id, sectionId });
        }
      }
      for (const { id, sectionId } of moved) {
        await this._mutate("items/update", { item_id: id, section_id: sectionId });
      }
      const seen = new Set(ids);
      const hidden = [...this._items]
        .sort((a, b) => a.order - b.order)
        .filter((i) => !seen.has(i.id))
        .map((i) => i.id);
      await this._mutate("items/reorder", { ordered_ids: [...ids, ...hidden] });
    }
  };
