/**
 * Smartcart panel - templates & history actions (M8).
 *
 * The mutations behind the templates and history screens: create a template
 * from scratch or from the active list, edit its item rows (local DOM state,
 * committed as the full list on Done), apply a template to the active list,
 * delete, and the history one-tap re-add / repeat-last-shop. Expects the
 * data mixin's methods (`_ws`, `_mutate`, `_refresh`) and the host's
 * `_renderContent()`, plus the state fields `_view`, `_templates`,
 * `_recentItems` and `_editingTemplateId` initialised in the host.
 *
 * Template item rows are edited locally in the DOM; "Done" reads every row
 * and sends the complete item list to `templates/update`, so partial edits
 * never half-commit.
 */

const VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const templateView = await import(`./panel-template-view.js?v=${VERSION}`);

export const templateActionsMixin = (base) =>
  class extends base {
    /** Render the active templates or history screen. */
    _renderTemplateContent() {
      const content = this._root.querySelector(".content");
      if (!content) {
        return;
      }
      if (this._view === "templates") {
        const template = this._editingTemplateId
          ? this._templates.find((t) => t.id === this._editingTemplateId)
          : null;
        content.innerHTML = template
          ? templateView.templateEditor(template, {
              sections: [...this._sections].sort((a, b) => a.order - b.order),
            })
          : templateView.templatesScreen({ templates: this._templates });
        // Rows added while the editor is open get ids after the last
        // rendered one, so drag ids stay unique in the current DOM.
        this._templateRowSeq = content.querySelectorAll(
          ".template-item-row"
        ).length;
        this._focusStoreInput(".template-name-input");
        return;
      }
      content.innerHTML = templateView.historyScreen({
        recent: this._recentItems,
      });
    }

    /** Name of the active list (for hints/placeholders). */
    _activeListName() {
      const list = this._lists.find((l) => l.id === this._activeListId);
      return list ? list.name : "";
    }

    async _onTemplateAction(action, el) {
      switch (action) {
        case "store-tab":
          this._editingTemplateId = null;
          this._gotoView(el.dataset.tab);
          break;
        case "template-add":
          await this._saveNewTemplate();
          break;
        case "template-save-list":
          await this._saveCurrentListAsTemplate();
          break;
        case "template-edit":
          this._editingTemplateId =
            el.closest("[data-template-id]").dataset.templateId;
          this._renderContent();
          break;
        case "template-done":
          await this._saveTemplateEditor();
          break;
        case "template-item-add":
          this._addTemplateItemRow();
          break;
        case "template-item-delete":
          this._removeTemplateItemRow(el);
          break;
        case "template-apply":
          await this._applyTemplate(
            el.closest("[data-template-id]").dataset.templateId
          );
          break;
        case "template-delete":
          await this._deleteTemplate(
            el.closest("[data-template-id]").dataset.templateId
          );
          break;
        case "history-readd":
          await this._mutate("items/add", {
            name: el.closest("[data-history-item]").dataset.historyItem,
          });
          break;
        case "history-repeat":
          await this._repeatLastShop();
          break;
      }
    }

    async _onTemplateKeydown(event) {
      const t = event.target;
      const cls = t.classList;
      if (event.key === "Enter" && cls.contains("store-add-input")) {
        event.preventDefault();
        await this._saveNewTemplate();
      } else if (
        event.key === "Enter" &&
        (cls.contains("template-name-input") ||
          cls.contains("template-item-name") ||
          cls.contains("template-item-qty"))
      ) {
        event.preventDefault();
        await this._saveTemplateEditor();
      } else if (event.key === "Escape" && t.closest(".template-editor")) {
        this._editingTemplateId = null;
        this._renderContent();
      }
    }

    // ------------------------------------------------------- load & commit

    /** Refresh the local template copy, then re-render if on the screen. */
    async _loadTemplates() {
      const { templates } = await this._ws("templates/list");
      this._templates = templates;
      if (this._view === "templates") {
        this._renderContent();
      }
    }

    /** Refresh the recent-history copy, then re-render if on the screen. */
    async _loadHistory() {
      const { items } = await this._ws("history/recent");
      this._recentItems = items;
      if (this._view === "history") {
        this._renderContent();
      }
    }

    async _saveNewTemplate() {
      const input = this._root.querySelector(".store-add-input");
      const name = input ? input.value.trim() : "";
      if (!name) {
        return;
      }
      const { template } = await this._ws("templates/create", {
        name,
        items: [],
      });
      this._templates = [...this._templates, template];
      this._editingTemplateId = template.id;
      this._renderContent();
    }

    async _saveCurrentListAsTemplate() {
      const input = this._root.querySelector(".store-add-input");
      const name =
        (input ? input.value.trim() : "") || `${this._activeListName()} template`;
      if (!name) {
        return;
      }
      const items = [...this._items]
        .sort((a, b) => a.order - b.order)
        .map((item) => {
          // `quantity: null` is rejected by the schema; omit it instead.
          const entry = {
            name: item.name,
            section_id: item.section_id,
            unit: item.unit || null,
            note: item.note || null,
          };
          if (item.quantity != null) {
            entry.quantity = item.quantity;
          }
          return entry;
        });
      const { template } = await this._ws("templates/create", { name, items });
      this._templates = [...this._templates, template];
      this._renderContent();
    }

    /** Read every item row and commit the full list, then close the editor. */
    async _saveTemplateEditor() {
      const editor = this._root.querySelector(".template-editor");
      if (!editor) {
        return;
      }
      const name = editor.querySelector(".template-name-input").value.trim();
      if (!name) {
        return;
      }
      const items = [];
      for (const row of editor.querySelectorAll(".template-item-row")) {
        const itemName = row.querySelector(".template-item-name").value.trim();
        if (!itemName) {
          continue;
        }
        const qtyRaw = row.querySelector(".template-item-qty").value.trim();
        const quantity = qtyRaw === "" ? null : Number(qtyRaw);
        // `quantity: null` is rejected by the schema; omit it instead.
        const entry = {
          name: itemName,
          section_id: row.querySelector(".template-item-section").value,
          unit: null,
          note: null,
        };
        if (quantity != null && !Number.isNaN(quantity)) {
          entry.quantity = quantity;
        }
        items.push(entry);
      }
      const { template } = await this._ws("templates/update", {
        template_id: editor.dataset.templateId,
        name,
        items,
      });
      this._templates = this._templates.map((t) =>
        t.id === template.id ? template : t
      );
      this._editingTemplateId = null;
      await this._refresh();
    }

    async _applyTemplate(templateId) {
      await this._ws("templates/apply", {
        template_id: templateId,
        list_id: this._activeListId,
      });
      await this._refresh();
      this._gotoView("shopping");
    }

    async _deleteTemplate(templateId) {
      await this._ws("templates/delete", { template_id: templateId });
      this._templates = this._templates.filter((t) => t.id !== templateId);
      await this._refresh();
    }

    async _repeatLastShop() {
      await this._ws("history/repeat_last", { list_id: this._activeListId });
      await this._refresh();
      this._gotoView("shopping");
    }

    // ------------------------------------------------- local item-row edits

    _addTemplateItemRow() {
      const editor = this._root.querySelector(".template-editor");
      if (!editor) {
        return;
      }
      const list = editor.querySelector(".store-list");
      const sections = [...this._sections].sort((a, b) => a.order - b.order);
      const dragId = `item-${this._templateRowSeq++}`;
      const wrap = document.createElement("div");
      wrap.innerHTML = templateView.templateItemRow(null, sections, dragId);
      list.appendChild(wrap.firstElementChild);
    }

    _removeTemplateItemRow(el) {
      const row = el.closest(".template-item-row");
      if (row) {
        row.remove();
      }
    }
  };
