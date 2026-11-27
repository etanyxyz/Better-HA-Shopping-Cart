/**
 * Better Shopping Cart panel - templates & history views (M8).
 *
 * Pure HTML builders for the templates screen (create from scratch or from
 * the current list, edit, apply, delete), the template editor (item rows
 * with name/section/quantity, reordered locally, committed on Done) and the
 * history screen (recently checked items with one-tap re-add, repeat last
 * shop). The host injects the returned strings into its shadow root.
 */

const VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const { esc } = await import(`./panel-view.js?v=${VERSION}`);
const { storeTabs } = await import(`./panel-store-view.js?v=${VERSION}`);

/** Small circular icon button used in row action clusters. */
function iconBtn(action, icon, label, disabled = false, danger = false) {
  return `<button type="button" class="icon-btn${danger ? " danger" : ""}" data-action="${action}"${disabled ? " disabled" : ""} aria-label="${label}">
    <ha-icon icon="${icon}"></ha-icon>
  </button>`;
}

/**
 * Templates screen: create row (new template / save current list) and one
 * row per template.
 *
 * ctx: { templates }
 */
export function templatesScreen(ctx) {
  const rows = ctx.templates
    .map((template) => {
      const n = esc(template.name);
      const count = template.items.length;
      return `
      <div class="store-row" data-template-id="${template.id}">
        <ha-icon icon="mdi:content-copy" class="row-icon"></ha-icon>
        <span class="row-name">${n}${count ? ` <span class="badge count">${count}</span>` : ""}</span>
        <div class="row-actions">
          ${iconBtn("template-edit", "mdi:pencil-outline", `Edit ${n}`)}
          ${iconBtn("template-apply", "mdi:play", `Apply ${n} to the active list`)}
          ${iconBtn("template-delete", "mdi:delete-outline", `Delete ${n}`, false, true)}
        </div>
      </div>
    `;
    })
    .join("");
  return `
    ${storeTabs("templates")}
    <p class="hint">A template is a reusable set of items. Apply it to the active list - items land in their sections.</p>
    <div class="addrow">
      <input type="text" class="add-input store-add-input" placeholder="New template" aria-label="New template name" autocomplete="off">
      <button type="button" class="icon-btn" data-action="template-add" aria-label="New template" title="New template">
        <ha-icon icon="mdi:plus"></ha-icon>
      </button>
      <button type="button" class="icon-btn" data-action="template-save-list" aria-label="Save the active list as a template" title="Save the active list as a template">
        <ha-icon icon="mdi:content-save-outline"></ha-icon>
      </button>
    </div>
    <div class="store-list">
      ${rows}
    </div>
  `;
}

/**
 * One editable item row of the template editor. Rows are local DOM state;
 * the whole list is committed when the editor is saved. Rows are reordered
 * by pointer drag.
 *
 * item: null for a fresh row, else { name, section_id, quantity }.
 * sections: store sections in store order (each { id, name }).
 * dragId: unique id for the pointer drag helper.
 */
export function templateItemRow(item, sections, dragId) {
  const options = sections
    .map(
      (section) =>
        `<option value="${section.id}"${
          item && item.section_id === section.id ? " selected" : ""
        }>${esc(section.name)}</option>`
    )
    .join("");
  const name = item ? esc(item.name) : "";
  const qty = item && item.quantity != null ? String(item.quantity) : "";
  return `
    <div class="store-row template-item-row" data-drag-row data-drag-id="${dragId}">
      <div class="template-item-main">
        <button type="button" class="icon-btn drag-handle" data-drag-handle aria-label="Drag to reorder item">
          <ha-icon icon="mdi:menu-vertical"></ha-icon>
        </button>
        <input type="text" class="template-item-name" value="${name}" aria-label="Item name" placeholder="Item" autocomplete="off">
        <input type="number" min="0" step="any" class="template-item-qty" value="${qty}" aria-label="Quantity" placeholder="Qty" autocomplete="off">
      </div>
      <div class="template-item-sub">
        <select class="template-item-section" aria-label="Section">${options}</select>
        <div class="row-actions">
          ${iconBtn("template-item-delete", "mdi:delete-outline", "Remove item", false, true)}
        </div>
      </div>
    </div>
  `;
}

/**
 * Template editor: rename, add/remove/reorder item rows, then Done commits
 * name + full item list to `templates/update`.
 *
 * template: the template being edited.
 * ctx: { sections (in store order) }
 */
export function templateEditor(template, ctx) {
  const rows = template.items
    .map((item, index) => templateItemRow(item, ctx.sections, `item-${index}`))
    .join("");
  const n = esc(template.name);
  return `
    ${storeTabs("templates")}
    <div class="layout-editor template-editor" data-template-id="${template.id}">
      <div class="edit-row">
        <label>Name
          <input type="text" class="template-name-input" value="${n}" aria-label="Template name" autocomplete="off">
        </label>
        <button type="button" class="primary-btn" data-action="template-done">Done</button>
      </div>
      <h2 class="shead"><ha-icon icon="mdi:cart-outline"></ha-icon><span>Items</span></h2>
      <div class="store-list">${rows}</div>
      <button type="button" class="primary-btn" data-action="template-item-add">
        <ha-icon icon="mdi:plus"></ha-icon><span>Add item</span>
      </button>
      <button type="button" class="primary-btn done-btn" data-action="template-done">Done - save template</button>
    </div>
  `;
}

/**
 * History screen: recently checked item names (most recent first) with a
 * one-tap re-add, plus the repeat-last-shop button.
 *
 * ctx: { recent (item names) }
 */
export function historyScreen(ctx) {
  const rows = ctx.recent
    .map(
      (name) => `
      <div class="store-row" data-history-item="${esc(name)}">
        <ha-icon icon="mdi:check-circle-outline" class="row-icon"></ha-icon>
        <span class="row-name">${esc(name)}</span>
        <div class="row-actions">
          ${iconBtn("history-readd", "mdi:plus", `Re-add ${name} to the active list`)}
        </div>
      </div>`
    )
    .join("");
  return `
    ${storeTabs("history")}
    <p class="hint">Items you have ticked off, most recent first - one tap re-adds them to the active list.</p>
    <button type="button" class="primary-btn done-btn" data-action="history-repeat">
      <ha-icon icon="mdi:repeat"></ha-icon><span>Repeat last shop</span>
    </button>
    ${
      ctx.recent.length
        ? `<div class="store-list">${rows}</div>`
        : `<p class="hint">Nothing bought yet - check items off to build the history.</p>`
    }
  `;
}
