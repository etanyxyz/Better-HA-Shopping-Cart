/**
 * Better Shopping Cart panel - pure view builders (M6).
 *
 * No DOM access: each function returns an HTML string for the panel module
 * to inject into its shadow root. The panel imports this file with an
 * explicit `?v=<VERSION>` query so HA's 7-day static cache is busted on
 * every release.
 */

/** Escape a value for safe interpolation into HTML. */
export function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );
}

/** `<option>` for the list/section selects. */
export function option(value, selected, label) {
  return `<option value="${value}"${value === selected ? " selected" : ""}>${esc(label)}</option>`;
}

/** Empty state shown when the store has no shopping lists. */
export function noListsState() {
  return `
    <div class="empty">
      <ha-icon icon="mdi:cart-outline"></ha-icon>
      <p>No shopping lists yet.</p>
      <button type="button" class="primary-btn" data-action="new-list">Create a list</button>
    </div>
  `;
}

/** Error state shown when a data fetch fails. */
export function errorState(message) {
  return `
    <div class="empty">
      <ha-icon icon="mdi:alert-circle-outline"></ha-icon>
      <p>Could not load data: ${esc(message)}</p>
    </div>
  `;
}

/**
 * The shopping view: list bar (list selector, list actions, layout
 * selector, progress, hide-checked toggle), add row and the section blocks.
 *
 * NOTES: Shopping Cart View - the layout's sections always render, empty
 * ones included (the toggle hides only items, not sections), and item rows
 * carry `data-drag-row`/`data-drag-id` plus a `[data-drag-handle]` grip so
 * items can be dragged between sections.
 *
 * ctx: { lists, activeListId, activeLayoutId, defaultLayoutId,
 *        layouts: [{ id, name, isDefault }],
 *        hideChecked, checked, total,
 *        sections: [{ section, visible, remaining }],
 *        viewSections, editingItemId,
 *        listMenuOpen, confirm, checkedCount }
 */
export function shoppingView(ctx) {
  const { lists, activeListId, hideChecked, checked, total, sections } = ctx;
  const activeList = lists.find((l) => l.id === activeListId);
  const layoutOptions = [
    option(
      "",
      ctx.activeLayoutId ? null : "",
      ctx.defaultLayoutId ? "Follow default layout" : "Default section order"
    ),
    ...ctx.layouts.map((l) =>
      option(l.id, ctx.activeLayoutId, l.isDefault ? `${l.name} •` : l.name)
    ),
  ].join("");
  let html = `
    <div class="listbar">
      <select class="list-select" data-action="select-list" aria-label="Active shopping list">
        ${lists.map((l) => option(l.id, activeListId, l.name)).join("")}
      </select>
      <button type="button" class="icon-btn" data-action="list-menu" aria-label="List actions" title="List actions">
        <ha-icon icon="mdi:dots-vertical"></ha-icon>
      </button>
      <button type="button" class="icon-btn" data-action="new-list" aria-label="Create new list" title="Create new list">
        <ha-icon icon="mdi:plus"></ha-icon>
      </button>
      <span class="progress" aria-label="${checked} of ${total} items checked">${checked}/${total}</span>
      <label class="hidechecked" title="Hide checked items">
        <input type="checkbox" data-action="hide-checked" aria-label="Hide checked items"${hideChecked ? " checked" : ""}>
        <ha-icon icon="mdi:eye-off-outline"></ha-icon>
      </label>
      <select class="list-select layout-select" data-action="select-layout" aria-label="Store layout (section order)">
        ${layoutOptions}
      </select>
    </div>
  `;
  if (ctx.listMenuOpen && activeList) {
    html += listMenuHtml({ name: activeList.name, checked: ctx.checkedCount });
  }
  if (ctx.confirm && activeList) {
    html += confirmDeleteListHtml({ name: activeList.name });
  }
  html += `
    <div class="addrow">
      <input type="text" class="add-input" placeholder="Add an item" aria-label="Add an item" autocomplete="off">
      <button type="button" class="icon-btn" data-action="add-item" aria-label="Add item" title="Add item">
        <ha-icon icon="mdi:plus"></ha-icon>
      </button>
    </div>
    <div class="sections">
  `;
  for (const { section, visible, remaining } of sections) {
    html += `
      <section class="sblock" data-section-id="${section.id}">
        <h2 class="shead">
          <ha-icon icon="${esc(section.icon)}"></ha-icon>
          <span>${esc(section.name)}</span>
          ${remaining ? `<span class="scount">${remaining}</span>` : ""}
        </h2>
        <div class="items">${visible.map((i) => itemHtml(i, ctx)).join("")}</div>
      </section>
    `;
  }
  html += "</div>";
  if (!sections.length || total === 0) {
    html += `<p class="hint">No items yet - add your first one above.</p>`;
  }
  return html;
}

/**
 * List actions menu (NOTES: Shopping Cart View): delete the list, clear
 * all its items, or clear only the checked ones.
 *
 * ctx: { name, checked (number of checked items) }
 */
export function listMenuHtml(ctx) {
  const n = esc(ctx.name);
  return `
    <div class="list-menu">
      <button type="button" class="menu-item" data-action="clear-list">Clear ${n}</button>
      <button type="button" class="menu-item" data-action="clear-completed"${
        ctx.checked ? "" : " disabled"
      }>Clear completed items${ctx.checked ? ` (${ctx.checked})` : ""}</button>
      <button type="button" class="menu-item danger" data-action="delete-list">Delete ${n}</button>
    </div>
  `;
}

/**
 * Confirmation card for deleting the active list (the only destructive
 * action that asks first; the clear actions run immediately).
 *
 * ctx: { name }
 */
export function confirmDeleteListHtml(ctx) {
  return `
    <div class="confirm">
      <p>Delete <strong>${esc(ctx.name)}</strong>? Its items will be removed too.</p>
      <div class="confirm-actions">
        <button type="button" class="text-btn" data-action="confirm-cancel">Cancel</button>
        <button type="button" class="primary-btn danger" data-action="confirm-delete">Delete</button>
      </div>
    </div>
  `;
}

/**
 * One item row, or the inline edit form while `editingItemId` matches.
 * NOTES: Shopping Cart View - rows carry `data-drag-row`/`data-drag-id`
 * plus a `[data-drag-handle]` grip so they can be dragged between
 * sections; the up/down buttons remain as the keyboard alternative.
 */
export function itemHtml(item, ctx) {
  if (item.id === ctx.editingItemId) {
    const sectionOptions = ctx.viewSections
      .map((s) => option(s.id, item.section_id, s.name))
      .join("");
    return editFormHtml(item, sectionOptions);
  }
  const n = esc(item.name);
  const badge =
    item.quantity != null
      ? `<span class="badge">${esc(item.quantity)}${item.unit ? " " + esc(item.unit) : ""}</span>`
      : "";
  const note = item.note ? `<div class="item-note">${esc(item.note)}</div>` : "";
  const btn = (action, icon, label, danger) =>
    `<button type="button" class="icon-btn${danger ? " danger" : ""}" data-action="${action}" aria-label="${label}">
      <ha-icon icon="${icon}"></ha-icon>
    </button>`;
  return `
    <div class="item${item.checked ? " checked" : ""}" data-item-id="${item.id}" data-drag-row data-drag-id="${item.id}">
      <label class="check">
        <input type="checkbox" data-action="check-item"${item.checked ? " checked" : ""} aria-label="Mark ${n} as done">
        <ha-icon icon="mdi:check"></ha-icon>
      </label>
      <div class="item-body" data-action="edit-item" role="button" tabindex="0">
        <div class="item-name">${n}${badge}</div>
        ${note}
      </div>
      <div class="item-actions">
        <button type="button" class="icon-btn drag-handle" data-drag-handle aria-label="Drag to reposition ${n}" title="Drag to reposition">
          <ha-icon icon="mdi:dots-vertical"></ha-icon>
        </button>
        ${btn("move-up", "mdi:arrow-up", `Move ${n} up`)}
        ${btn("move-down", "mdi:arrow-down", `Move ${n} down`)}
        ${btn("edit-item", "mdi:pencil-outline", `Edit ${n}`)}
        ${btn("delete-item", "mdi:delete-outline", `Delete ${n}`, true)}
      </div>
    </div>
  `;
}

/** Inline edit form for one item (section options as an HTML string). */
export function editFormHtml(item, sectionOptions) {
  return `
    <div class="item-edit" data-item-id="${item.id}">
      <input type="text" class="edit-name" value="${esc(item.name)}" aria-label="Item name" autocomplete="off">
      <div class="edit-row">
        <label>Section
          <select class="edit-section" aria-label="Section">${sectionOptions}</select>
        </label>
        <label>Qty
          <input type="number" min="0" step="any" class="edit-qty" value="${item.quantity != null ? item.quantity : ""}" aria-label="Quantity">
        </label>
        <label>Unit
          <input type="text" class="edit-unit" value="${esc(item.unit || "")}" aria-label="Unit" placeholder="x, kg, L">
        </label>
      </div>
      <input type="text" class="edit-note" value="${esc(item.note || "")}" aria-label="Note" placeholder="Note">
      <div class="edit-actions">
        <button type="button" class="primary-btn" data-action="save-item">Save</button>
        <button type="button" class="text-btn" data-action="cancel-edit">Cancel</button>
      </div>
    </div>
  `;
}

/** Inline new-list form (inserted under the list bar). */
export function newListForm() {
  return `
    <div class="new-list-form">
      <input type="text" class="new-list-input" placeholder="List name" aria-label="New list name" autocomplete="off">
      <button type="button" class="primary-btn" data-action="save-new-list">Add</button>
      <button type="button" class="text-btn" data-action="cancel-new-list">Cancel</button>
    </div>
  `;
}
