/**
 * Better Shopping Cart panel - pointer-event drag reorder helper (M7).
 *
 * Container-level drag reorder for a vertical list of rows, touch-capable:
 * rows matching `rowSelector` are the movable elements and a
 * `[data-drag-handle]` element inside a row is the grab area (give it
 * `touch-action: none` in CSS so the browser does not start scrolling
 * instead of dragging). While dragging, the row visually follows the
 * pointer; crossing a sibling's midpoint re-inserts the row in the DOM,
 * so the final order is read straight from the children.
 *
 * Rows may be nested inside wrapper elements inside `container` (e.g. the
 * layout editor's `.store-list` div, or the shopping view's per-section
 * `.sblock .items` divs, passed as `groupSelector`). The pointer's group
 * is the group nearest to the pointer, so a drop on a section header or
 * into an empty section lands in the intended group; inside the group the
 * row goes before the first row whose midpoint the pointer is above.
 *
 * `onReorder(ids)` fires on pointer up/cancel with the rows'
 * `data-drag-id` values in their new DOM order. `getKey(row)` (default:
 * the `data-drag-id`) decides when a real change happened: the callback
 * fires only when the sequence of keys changed, so a cross-section move
 * that keeps the global id order identical still commits.
 */

export function attachDragReorder(
  container,
  rowSelector,
  onReorder,
  groupSelector = null,
  getKey = null
) {
  const keyOf = getKey || ((row) => row.dataset.dragId);
  let drag = null;

  const rows = () => Array.from(container.querySelectorAll(rowSelector));

  function onPointerDown(event) {
    const handle = event.target.closest("[data-drag-handle]");
    if (!handle || !container.contains(handle)) {
      return;
    }
    const row = handle.closest(rowSelector);
    if (!row || !rows().includes(row)) {
      return;
    }
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    // Groups the rows live in: the section item wrappers when
    // `groupSelector` matches anything in this view, otherwise the rows'
    // own parent (the layout editor's single list).
    const groups = groupSelector
      ? Array.from(container.querySelectorAll(groupSelector))
      : [];
    if (!groups.length) {
      groups.push(row.parentNode);
    }
    drag = {
      row,
      groups,
      startY: event.clientY,
      baseTop: row.getBoundingClientRect().top,
      keys: rows().map(keyOf),
    };
    row.classList.add("dragging");
  }

  function onPointerMove(event) {
    if (!drag) {
      return;
    }
    const { row, groups, startY, baseTop } = drag;
    const dy = event.clientY - startY;
    // The group the pointer is over: the nearest one by vertical distance,
    // so drops on a section header or into an empty section land sensibly.
    let group = groups[0];
    let best = Infinity;
    for (const g of groups) {
      const rect = g.getBoundingClientRect();
      const d =
        event.clientY < rect.top
          ? rect.top - event.clientY
          : event.clientY > rect.bottom
            ? event.clientY - rect.bottom
            : 0;
      if (d < best) {
        best = d;
        group = g;
      }
    }
    // Inside the group: before the first row whose midpoint the pointer is
    // above (or at the end of the group).
    const siblings = Array.from(group.querySelectorAll(rowSelector)).filter(
      (r) => r !== row
    );
    let target = siblings.length;
    for (let i = 0; i < siblings.length; i++) {
      const rect = siblings[i].getBoundingClientRect();
      if (event.clientY < rect.top + rect.height / 2) {
        target = i;
        break;
      }
    }
    if (target < siblings.length) {
      siblings[target].parentNode.insertBefore(row, siblings[target]);
    } else {
      group.appendChild(row);
    }
    // Keep the row under the pointer: measure its natural top after the
    // (possible) re-insertion and translate by the difference.
    row.style.transform = "";
    row.style.transform = `translateY(${dy + baseTop - row.getBoundingClientRect().top}px)`;
  }

  function end() {
    if (!drag) {
      return;
    }
    const row = drag.row;
    const before = drag.keys;
    drag = null;
    row.classList.remove("dragging");
    row.style.transform = "";
    // A plain tap on the handle moves nothing; only commit a real change.
    const keys = rows().map(keyOf);
    if (keys.join("|") !== before.join("|")) {
      onReorder(rows().map((r) => r.dataset.dragId));
    }
  }

  container.addEventListener("pointerdown", onPointerDown);
  container.addEventListener("pointermove", onPointerMove);
  container.addEventListener("pointerup", end);
  container.addEventListener("pointercancel", end);
}
