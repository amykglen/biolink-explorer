// Behavior for the custom searchable multi-select (.bl-ms-wrapper), which replaces
// dcc.Dropdown / dcc.Checklist (both virtualize their option list, which caused the
// popup-height bug). Options are plain clickable rows; the selection lives in a dcc.Store
// (id = the wrapper's data-store). This handles open/close, type-to-filter, click-outside,
// and toggling a row's selection into the Store. The trigger text + row checkmarks are
// synced from the Store by a clientside callback (see register_callbacks).
(function () {
    function closeAll(except) {
        document.querySelectorAll(".bl-ms-wrapper.bl-ms-open").forEach(function (w) {
            if (w !== except) w.classList.remove("bl-ms-open");
        });
    }

    // dcc.Input renders the class on a container div with the real <input> inside it.
    function searchInput(wrapper) {
        var el = wrapper.querySelector(".bl-ms-search");
        if (!el) return null;
        return el.tagName === "INPUT" ? el : el.querySelector("input");
    }

    function applyFilter(wrapper) {
        var input = searchInput(wrapper);
        var q = (input ? input.value : "").trim().toLowerCase();
        wrapper.querySelectorAll(".bl-ms-option").forEach(function (row) {
            var hit = !q || (row.getAttribute("data-value") || "").toLowerCase().indexOf(q) >= 0;
            row.classList.toggle("bl-ms-hidden", !hit);
        });
    }

    // On open, float the currently-selected rows to the top (each group keeps its order)
    // so they're easy to find / uncheck — matching the old dropdown's behavior.
    function sortSelectedToTop(wrapper) {
        var container = wrapper.querySelector(".bl-ms-options");
        if (!container) return;
        var rows = Array.prototype.slice.call(container.querySelectorAll(".bl-ms-option"));
        var selected = rows.filter(function (r) { return r.classList.contains("bl-ms-selected"); });
        var rest = rows.filter(function (r) { return !r.classList.contains("bl-ms-selected"); });
        selected.concat(rest).forEach(function (r) { container.appendChild(r); });
    }

    function openWrapper(wrapper) {
        closeAll(wrapper);
        wrapper.classList.add("bl-ms-open");
        sortSelectedToTop(wrapper);
        var input = searchInput(wrapper);
        if (input) {
            // dcc.Input is React-controlled, so clear it through the native setter.
            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
            setter.call(input, "");
            input.dispatchEvent(new Event("input", { bubbles: true }));
            applyFilter(wrapper);
            setTimeout(function () { input.focus(); }, 0);
        }
        var opts = wrapper.querySelector(".bl-ms-options");
        if (opts) opts.scrollTop = 0;
    }

    function setStore(storeId, data) {
        if (storeId && window.dash_clientside && window.dash_clientside.set_props) {
            window.dash_clientside.set_props(storeId, { data: data });
        }
    }

    function toggleOption(row) {
        var wrapper = row.closest(".bl-ms-wrapper");
        if (!wrapper) return;
        var storeId = wrapper.getAttribute("data-store");
        if (wrapper.classList.contains("bl-ms-single")) {
            // Single-select: pick just this one and close.
            wrapper.querySelectorAll(".bl-ms-option").forEach(function (r) { r.classList.remove("bl-ms-selected"); });
            row.classList.add("bl-ms-selected");
            setStore(storeId, row.getAttribute("data-value"));
            wrapper.classList.remove("bl-ms-open");
            return;
        }
        row.classList.toggle("bl-ms-selected");  // optimistic; the callback re-syncs
        var selected = Array.prototype.map.call(
            wrapper.querySelectorAll(".bl-ms-option.bl-ms-selected"),
            function (r) { return r.getAttribute("data-value"); });
        setStore(storeId, selected);
    }

    function clearWrapper(wrapper) {
        wrapper.querySelectorAll(".bl-ms-option.bl-ms-selected").forEach(function (r) {
            r.classList.remove("bl-ms-selected");
        });
        wrapper.classList.remove("bl-ms-has-value");
        setStore(wrapper.getAttribute("data-store"), wrapper.classList.contains("bl-ms-single") ? null : []);
    }

    document.addEventListener("click", function (e) {
        // "Clear filters" banner button: clear every listed Store at once.
        var bannerClear = e.target.closest && e.target.closest(".bl-filter-clear");
        if (bannerClear) {
            (bannerClear.getAttribute("data-clear") || "").split(",").filter(Boolean).forEach(function (sid) {
                var w = document.querySelector('[data-store="' + sid + '"]');
                if (w) clearWrapper(w); else setStore(sid, []);
            });
            return;
        }
        // Clear "×" lives inside the control, so check it first (don't open the popup).
        var clear = e.target.closest && e.target.closest(".bl-ms-clear");
        if (clear) {
            var w0 = clear.closest(".bl-ms-wrapper");
            if (w0) clearWrapper(w0);
            return;
        }
        var control = e.target.closest && e.target.closest(".bl-ms-control");
        if (control) {
            var w = control.closest(".bl-ms-wrapper");
            if (w) { w.classList.contains("bl-ms-open") ? w.classList.remove("bl-ms-open") : openWrapper(w); }
            return;
        }
        var row = e.target.closest && e.target.closest(".bl-ms-option");
        if (row) { toggleOption(row); return; }
    });

    // A press anywhere outside an open multi-select closes it (mousedown so it fires even
    // when starting to pan/drag the graph, not only on a clean click).
    document.addEventListener("mousedown", function (e) {
        var inside = e.target.closest && e.target.closest(".bl-ms-wrapper");
        if (!inside) closeAll(null);
    }, true);

    document.addEventListener("input", function (e) {
        if (e.target.closest && e.target.closest(".bl-ms-search")) {
            var wrapper = e.target.closest(".bl-ms-wrapper");
            if (wrapper) applyFilter(wrapper);
        }
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeAll(null);
    });
})();
