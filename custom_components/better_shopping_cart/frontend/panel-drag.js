/**
 * Smartcart panel - pointer-event drag reorder helper (M7).
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
 * Auto-scroll: while the pointer is held inside `AUTO_SCROLL_ZONE` of the
 * top or bottom edge of the scrolling element (the container itself, or
 * its nearest scrollable ancestor), a requestAnimationFrame loop scrolls
 * that element away from the pointer - so a stationary pointer keeps the
 * list moving. The dragged row is re-positioned every frame, which keeps
 * it pinned to the pointer while the content scrolls under it and moves
 * the drop gap with the content.
 *
 * `onReorder(ids)` fires on pointer up/cancel with the rows'
 * `data-drag-id` values in their new DOM order. `getKey(row)` (default:
 * the `data-drag-id`) decides when a real change happened: the callback
 * fires only when the sequence of keys changed, so a cross-section move
 * that keeps the global id order identical still commits.
 */

const AUTO_SCROLL_ZONE = 64; // px of edge sensitivity
const AUTO_SCROLL_MAX = 16; // px per frame at full depth

export function attachDragReorder(
  container,
  rowSelector,
  onReorder,
  groupSelector = null,
  getKey = null
) {
  const keyOf = getKey || ((row) => row.dataset.dragId);
  let drag = null;
  let rafId = null;

  const rows = () => Array.from(container.querySelectorAll(rowSelector));

  /** The element auto-scroll will scroll, or null when nothing can. */
  function findScroller() {
    let el = container;
    while (el) {
      const oy = getComputedStyle(el).overflowY;
      if (
        (oy === "auto" || oy === "scroll" || oy === "overlay") &&
        el.scrollHeight > el.clientHeight
      ) {
        return el;
      }
      el = el.parentElement;
    }
    return null;
  }

  /**
   * Move the dragged row to the pointer's slot and pin it there. The
   * transform is a viewport delta, so it stays correct while the
   * scroller moves: the natural top is re-measured after every
   * (possible) re-insertion and the difference applied.
   */
  function update(clientY) {
    const { row, groups, startY, baseTop } = drag;
    // The group the pointer is over: the nearest one by vertical distance,
    // so drops on a section header or into an empty section land sensibly.
    let group = groups[0];
    let best = Infinity;
    for (const g of groups) {
      const rect = g.getBoundingClientRect();
      const d =
        clientY < rect.top
          ? rect.top - clientY
          : clientY > rect.bottom
            ? clientY - rect.bottom
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
      if (clientY < rect.top + rect.height / 2) {
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
    row.style.transform = `translateY(${
      clientY - startY + baseTop - row.getBoundingClientRect().top
    }px)`;
  }

  /**
   * One animation frame: auto-scroll the scroller away from the pointer's
   * edge (linear ramp: slow at the zone boundary, fastest at the edge),
   * then reposition the row. Repositioning only when the pointer moved or
   * the scroller scrolled keeps idle frames from churning the DOM.
   */
  function frame() {
    if (!drag) {
      rafId = null;
      return;
    }
    let scrolled = false;
    const scroller = drag.scroller;
    if (scroller) {
      const rect = scroller.getBoundingClientRect();
      const y = drag.clientY;
      let depth = 0;
      if (y < rect.top + AUTO_SCROLL_ZONE) {
        depth = (rect.top + AUTO_SCROLL_ZONE - y) / AUTO_SCROLL_ZONE;
        scroller.scrollTop -= Math.min(1, depth) * AUTO_SCROLL_MAX;
        scrolled = true;
      } else if (y > rect.bottom - AUTO_SCROLL_ZONE) {
        depth = (y - (rect.bottom - AUTO_SCROLL_ZONE)) / AUTO_SCROLL_ZONE;
        scroller.scrollTop += Math.min(1, depth) * AUTO_SCROLL_MAX;
        scrolled = true;
      }
    }
    if (scrolled || drag.clientY !== drag.lastY) {
      update(drag.clientY);
      drag.lastY = drag.clientY;
    }
    rafId = requestAnimationFrame(frame);
  }

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
      clientY: event.clientY,
      lastY: event.clientY,
      startY: event.clientY,
      baseTop: row.getBoundingClientRect().top,
      scroller: findScroller(),
      keys: rows().map(keyOf),
    };
    row.classList.add("dragging");
    rafId = requestAnimationFrame(frame);
  }

  function onPointerMove(event) {
    if (!drag) {
      return;
    }
    // The rAF loop applies the position and does the auto-scroll.
    drag.clientY = event.clientY;
  }

  function end() {
    if (!drag) {
      return;
    }
    const row = drag.row;
    const before = drag.keys;
    drag = null;
    if (rafId != null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
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
