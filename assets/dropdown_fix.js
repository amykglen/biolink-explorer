// Workaround for a dcc.Dropdown (Dash 4) virtualization quirk.
//
// The option list is a react-window virtualized list whose height is fixed at mount to
// fit the CURRENTLY shown options. When you type to filter a dropdown and then pick an
// option, the typed filter text stays in the component's internal state. The next time
// you open that dropdown, the list mounts at the old *filtered* (short) height and never
// grows — so the menu opens tiny, showing only a few rows in a cramped scroll area, until
// you close and reopen it a second time.
//
// Fix: as soon as an option is chosen, clear the dropdown's search box. That returns the
// list to the full set of options (full height) before the menu is next closed, so it
// always reopens at the correct height. (Clearing an already-empty box is a no-op, so
// this is inert for dropdowns you never typed in.)
(function () {
    function clearDropdownSearch() {
        var search = document.querySelector(".dash-dropdown-search");
        if (search && search.value) {
            var setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, "value").set;
            setter.call(search, "");
            search.dispatchEvent(new Event("input", { bubbles: true }));
        }
    }

    // Capture phase so we run regardless of how the option handles the click; the
    // setTimeout lets Dash apply the selection first, then we reset the filter.
    document.addEventListener("click", function (e) {
        var opt = e.target.closest && e.target.closest(".dash-options-list-option");
        if (opt) setTimeout(clearDropdownSearch, 0);
    }, true);
})();
