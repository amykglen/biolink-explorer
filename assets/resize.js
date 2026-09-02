// Makes the right-hand detail panel width draggable. The panel width is the CSS
// variable --bl-panel-width (read by detail_panel_style in styles.py); dragging the
// handle on the panel's left edge updates it, clamped to a sensible range. The value
// persists for the session via localStorage. Uses event delegation so it keeps working
// across Dash re-renders / tab switches (the handle is recreated each time).
(function () {
    var MIN = 300, MAX = 680, KEY = "bl-panel-width";

    // Restore a previously chosen width.
    try {
        var saved = parseInt(localStorage.getItem(KEY), 10);
        if (saved >= MIN && saved <= MAX) {
            document.documentElement.style.setProperty("--bl-panel-width", saved + "px");
        }
    } catch (e) { /* ignore */ }

    var dragging = false;

    function onMove(e) {
        if (!dragging) return;
        // Panel is anchored to the right edge; width grows as the cursor moves left.
        var w = window.innerWidth - e.clientX;
        w = Math.max(MIN, Math.min(MAX, w));
        document.documentElement.style.setProperty("--bl-panel-width", w + "px");
        e.preventDefault();
    }

    function onUp() {
        if (!dragging) return;
        dragging = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        var cur = getComputedStyle(document.documentElement).getPropertyValue("--bl-panel-width").trim();
        var px = parseInt(cur, 10);
        if (px) { try { localStorage.setItem(KEY, px); } catch (e) { /* ignore */ } }
    }

    document.addEventListener("mousedown", function (e) {
        var handle = e.target.closest && e.target.closest(".panel-resize-handle");
        if (!handle) return;
        dragging = true;
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";  // don't select text while dragging
        e.preventDefault();
    });
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
})();
