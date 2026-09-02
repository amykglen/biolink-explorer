// Wires the "About" info modal: open on the header info button, close on the ✕
// button, on a backdrop click, or on Escape. The modal content is static, so this
// just toggles its visibility (no Dash callbacks needed).
(function () {
    function setup() {
        var btn = document.getElementById("info-btn");
        var modal = document.getElementById("info-modal");
        if (!btn || !modal) return false;
        if (modal._wired) return true;
        modal._wired = true;

        var closeBtn = document.getElementById("info-close");
        function open() { modal.style.display = "flex"; }
        function hide() { modal.style.display = "none"; }

        btn.addEventListener("click", open);
        if (closeBtn) closeBtn.addEventListener("click", hide);
        modal.addEventListener("click", function (e) { if (e.target === modal) hide(); });
        document.addEventListener("keydown", function (e) { if (e.key === "Escape") hide(); });
        return true;
    }

    var iv = setInterval(function () { if (setup()) clearInterval(iv); }, 250);
})();
