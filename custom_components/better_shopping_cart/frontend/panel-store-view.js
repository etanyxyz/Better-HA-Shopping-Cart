/**
 * Better Shopping Cart panel - store management views (M7).
 *
 * Pure HTML builders for the sections and layouts screens, no DOM access.
 * The host injects the returned strings into its shadow root. Layout editor
 * rows carry `data-drag-row`/`data-drag-id`/`data-drag-handle` attributes
 * for the pointer drag reorder helper (panel-drag.js); the sections screen
 * shows the immutable default group and the mutable custom group.
 */

const VERSION = new URL(import.meta.url).searchParams.get("v") || "dev";
const { esc } = await import(`./panel-view.js?v=${VERSION}`);

/** Small circular icon button used in row action clusters. */
function iconBtn(action, icon, label, disabled = false, danger = false) {
  return `<button type="button" class="icon-btn${danger ? " danger" : ""}" data-action="${action}"${disabled ? " disabled" : ""} aria-label="${label}">
    <ha-icon icon="${icon}"></ha-icon>
  </button>`;
}

/** Tab bar switching between the store management screens (M9: + settings). */
export function storeTabs(active) {
  const tab = (id, icon, label) => `
    <button type="button" class="tab${active === id ? " active" : ""}" data-action="store-tab" data-tab="${id}" aria-label="${label}">
      <ha-icon icon="${icon}"></ha-icon>
      <span>${label}</span>
    </button>`;
  return `
    <div class="tabs">
      ${tab("sections", "mdi:storefront", "Sections")}
      ${tab("layouts", "mdi:format-list-box", "Layouts")}
      ${tab("templates", "mdi:content-copy", "Templates")}
      ${tab("history", "mdi:history", "History")}
      ${tab("settings", "mdi:cog", "Settings")}
    </div>
  `;
}

/** Mirror of const.py's normalise_name for client-side classification. */
const normName = (name) => name.toLowerCase().replace(/\s+/g, " ").trim();

/** Normalised names of the immutable default sections (see const.py). */
const DEFAULT_SECTION_NAMES = [
  "produce",
  "dairy",
  "meat",
  "bakery",
  "frozen",
  "drinks",
  "household",
  "pantry",
  "other",
  "uncategorised",
];

/** Whether a section belongs to the immutable default group. */
export function isDefaultSection(section) {
  return DEFAULT_SECTION_NAMES.includes(normName(section.name));
}

/** One default section row: icon + name only (immutable). */
function defaultRow(section) {
  return `
    <div class="store-row" data-section-id="${section.id}">
      <ha-icon icon="${esc(section.icon)}" class="row-icon"></ha-icon>
      <span class="row-name">${esc(section.name)}</span>
    </div>
  `;
}

/** One custom section row, or the inline rename form while `editing`. */
function customRow(section, editing) {
  if (editing) {
    return `
      <div class="store-row row-edit" data-section-id="${section.id}">
        <input type="text" class="section-name-input" value="${esc(section.name)}" aria-label="Section name" autocomplete="off">
        <div class="edit-actions">
          <button type="button" class="primary-btn" data-action="section-save">Save</button>
          <button type="button" class="text-btn" data-action="section-cancel">Cancel</button>
        </div>
      </div>
    `;
  }
  const n = esc(section.name);
  return `
    <div class="store-row" data-section-id="${section.id}">
      <ha-icon icon="${esc(section.icon)}" class="row-icon"></ha-icon>
      <span class="row-name">${n}</span>
      <div class="row-actions">
        ${iconBtn("section-edit", "mdi:pencil-outline", `Edit ${n}`)}
        ${iconBtn("section-delete", "mdi:delete-outline", `Delete ${n}`, false, true)}
      </div>
    </div>
  `;
}

/**
 * Sections screen (NOTES: Sections tab): two groups - the immutable default
 * sections (icon + name only) and the mutable custom sections (rename and
 * delete, add form on top). Custom sections always use the cart icon and
 * keep their creation order.
 *
 * ctx: { defaultSections, customSections (each sorted by `order`),
 *        editingId }
 */
export function sectionsScreen(ctx) {
  const customRows = ctx.customSections.length
    ? ctx.customSections
        .map((section) => customRow(section, section.id === ctx.editingId))
        .join("")
    : '<p class="hint">No custom sections yet.</p>';
  return `
    ${storeTabs("sections")}
    <h2 class="shead"><ha-icon icon="mdi:storefront"></ha-icon><span>Default sections</span></h2>
    <p class="hint">Fixed sections, each with its own icon - they can't be edited, reordered or deleted.</p>
    <div class="store-list">
      ${ctx.defaultSections.map(defaultRow).join("")}
    </div>
    <h2 class="shead"><ha-icon icon="mdi:cart-variant"></ha-icon><span>Custom sections</span></h2>
    <p class="hint">Your own sections - they appear after the defaults and use the cart icon.</p>
    <div class="addrow">
      <input type="text" class="add-input store-add-input" placeholder="New section" aria-label="New section name" autocomplete="off">
      <button type="button" class="icon-btn" data-action="section-add" aria-label="Add section" title="Add section">
        <ha-icon icon="mdi:plus"></ha-icon>
      </button>
    </div>
    <div class="store-list">
      ${customRows}
    </div>
  `;
}

/**
 * Layouts screen: create form and one row per layout.
 *
 * ctx: { layouts, defaultId }
 */
export function layoutsScreen(ctx) {
  const rows = ctx.layouts
    .map((layout) => {
      const n = esc(layout.name);
      const isDefault = layout.id === ctx.defaultId;
      return `
      <div class="store-row" data-layout-id="${layout.id}">
        <ha-icon icon="mdi:format-list-box" class="row-icon"></ha-icon>
        <span class="row-name">${n}${isDefault ? '<span class="badge default">Default</span>' : ""}</span>
        <div class="row-actions">
          ${iconBtn("layout-edit", "mdi:pencil-outline", `Edit ${n}`)}
          ${iconBtn("layout-default", isDefault ? "mdi:star" : "mdi:star-outline", isDefault ? "Unset default layout" : `Make ${n} the default layout`)}
          ${iconBtn("layout-delete", "mdi:delete-outline", `Delete ${n}`, false, true)}
        </div>
      </div>
    `;
    })
    .join("");
  return `
    ${storeTabs("layouts")}
    <p class="hint">A layout fixes a section order and which sections are hidden. The default layout applies to lists without one of their own.</p>
    <div class="addrow">
      <input type="text" class="add-input store-add-input" placeholder="New layout" aria-label="New layout name" autocomplete="off">
      <button type="button" class="icon-btn" data-action="layout-add" aria-label="Add layout" title="Add layout">
        <ha-icon icon="mdi:plus"></ha-icon>
      </button>
    </div>
    <div class="store-list">
      ${rows}
    </div>
  `;
}

/**
 * Layout editor: rename, reorder the sections (up/down + drag) and toggle
 * which sections are hidden in the shopping view.
 *
 * layout: the layout being edited.
 * ctx: { order (sections in the layout's effective order),
 *        hidden (section ids hidden in the layout) }
 */
export function layoutEditor(layout, ctx) {
  const orderRows = ctx.order
    .map(
      (section, index) => `
        <div class="store-row" data-drag-row data-drag-id="${section.id}" data-section-id="${section.id}">
          <button type="button" class="icon-btn drag-handle" data-drag-handle aria-label="Drag to reorder ${esc(section.name)}">
            <ha-icon icon="mdi:menu-vertical"></ha-icon>
          </button>
          <ha-icon icon="${esc(section.icon)}" class="row-icon"></ha-icon>
          <span class="row-name">${esc(section.name)}</span>
          <div class="row-actions">
            ${iconBtn("layout-section-up", "mdi:arrow-up", `Move ${esc(section.name)} up`, index === 0)}
            ${iconBtn("layout-section-down", "mdi:arrow-down", `Move ${esc(section.name)} down`, index === ctx.order.length - 1)}
          </div>
        </div>`
    )
    .join("");
  const hideRows = ctx.order
    .map(
      (section) => `
      <div class="store-row hide-row" data-section-id="${section.id}">
        <ha-icon icon="${esc(section.icon)}" class="row-icon"></ha-icon>
        <span class="row-name">${esc(section.name)}</span>
        <label class="check" title="Hide ${esc(section.name)} in the shopping view">
          <input type="checkbox" data-action="layout-hide"${ctx.hidden.includes(section.id) ? " checked" : ""} aria-label="Hide ${esc(section.name)}">
          <ha-icon icon="mdi:check"></ha-icon>
        </label>
      </div>`
    )
    .join("");
  return `
    ${storeTabs("layouts")}
    <div class="layout-editor" data-layout-id="${layout.id}">
      <div class="edit-row">
        <label>Name
          <input type="text" class="layout-name-input" value="${esc(layout.name)}" aria-label="Layout name" autocomplete="off">
        </label>
        <button type="button" class="primary-btn" data-action="layout-save-name">Save</button>
      </div>
      <h2 class="shead"><ha-icon icon="mdi:arrow-up-down"></ha-icon><span>Section order</span></h2>
      <div class="store-list">${orderRows}</div>
      <h2 class="shead"><ha-icon icon="mdi:eye-off-outline"></ha-icon><span>Hidden sections</span></h2>
      <div class="store-list">${hideRows}</div>
      <button type="button" class="primary-btn done-btn" data-action="layout-done">Done</button>
    </div>
  `;
}
