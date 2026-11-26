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
 * Rows may be nested inside a wrapper inside `container` (e.g. a
 * `.store-list` div); the helper finds them with `querySelectorAll` and
 * re-inserts them into their own parent node.
 *
 * `onReorder(ids)` fires on pointer up/cancel with the rows'
 * `data-drag-id` values in their new DOM order.
 */

export function attachDragReorder(container, rowSelector, onReorder) {
  let drag = null;

  const rows = () => Array.from(container.querySelectorAll(rowSelector));

  function onPointerDown(event) {
    const handle = event.target.closest("[data-drag-handle]");
    if (!handle || !container.contains(handle)) {
      return;
    }
    const row = handle.closest(rowSelector);
    if (!row) {
      return;
    }
    const list = rows();
    const start = list.indexOf(row);
    if (start < 0) {
      return;
    }
    // Distance between adjacent rows (height + gap), for the transform
    // compensation after DOM re-insertion.
    const step =
      list.length > 1
        ? list[1].getBoundingClientRect().top - list[0].getBoundingClientRect().top
        : row.getBoundingClientRect().height;
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    drag = { row, list, start, step, startY: event.clientY, ids: list.map((r) => r.dataset.dragId) };
    row.classList.add("dragging");
  }

  function onPointerMove(event) {
    if (!drag) {
      return;
    }
    const { row, list, start, step, startY } = drag;
    const dy = event.clientY - startY;
    // Sibling rows keep their relative DOM order throughout the drag, so
    // the insertion index is read among them: before the first sibling
    // whose midpoint the pointer is above (or after all of them). That
    // index is also the row's final index among all rows.
    const others = list.filter((r) => r !== row);
    let target = others.length;
    for (let i = 0; i < others.length; i++) {
      const rect = others[i].getBoundingClientRect();
      if (event.clientY < rect.top + rect.height / 2) {
        target = i;
        break;
      }
    }
    const allRows = rows();
    const current = allRows.indexOf(row);
    if (target !== current) {
      // Insert into the row's own parent, which may be a wrapper inside
      // `container` (inserting relative to a non-child of `container`
      // throws NotFoundError).
      const parent = row.parentNode;
      if (target < current) {
        parent.insertBefore(row, allRows[target]);
      } else {
        const next = allRows[target + 1];
        if (next) {
          parent.insertBefore(row, next);
        } else {
          parent.appendChild(row);
        }
      }
    }
    // The layout position shifted by (target - start) * step after the
    // re-insertion; compensate so the row stays under the pointer.
    row.style.transform = `translateY(${dy - (target - start) * step}px)`;
  }

  function end() {
    if (!drag) {
      return;
    }
    const row = drag.row;
    const before = drag.ids;
    drag = null;
    row.classList.remove("dragging");
    row.style.transform = "";
    // A plain tap on the handle moves nothing; only commit a real reorder.
    const ids = rows().map((r) => r.dataset.dragId);
    if (ids.join("|") !== before.join("|")) {
      onReorder(ids);
    }
  }

  container.addEventListener("pointerdown", onPointerDown);
  container.addEventListener("pointermove", onPointerMove);
  container.addEventListener("pointerup", end);
  container.addEventListener("pointercancel", end);
}
