/**
 * Client-side workspace filter for "In house SR" role.
 * Supplements server-side filtering as a safety net.
 */
(function () {
    var ROLE = "In house SR";
    var ALLOWED_SIDEBAR = ["Home", "Dashboard V1", "Reports"];
    var ALLOWED_SHORTCUTS = [
        "CV Customer", "CV Sales Order", "CV Sales Invoice",
        "UDC Customer", "UDC Sales Order", "UDC Sales Invoice"
    ];

    function hasRole() {
        if (!frappe.user_roles) return false;
        // Never filter Administrator or System Manager users
        if (frappe.session.user === "Administrator") return false;
        if (frappe.user_roles.indexOf("System Manager") !== -1) return false;
        return frappe.user_roles.indexOf(ROLE) !== -1;
    }

    function filterSidebar() {
        if (!hasRole()) return;
        document.querySelectorAll(".sidebar-menu .standard-sidebar-item").forEach(function (el) {
            var lbl = el.querySelector(".sidebar-item-label");
            if (lbl && ALLOWED_SIDEBAR.indexOf(lbl.textContent.trim()) === -1) {
                el.style.display = "none";
            }
        });
    }

    function filterHome() {
        if (!hasRole()) return;
        if (window.location.pathname.toLowerCase() !== "/app/home") return;

        document.querySelectorAll(".shortcut-widget-box, .widget.shortcut-widget-box").forEach(function (w) {
            var lbl = w.querySelector(".widget-label") || w.querySelector(".ellipsis");
            if (lbl && ALLOWED_SHORTCUTS.indexOf(lbl.textContent.trim()) === -1) {
                var col = w.closest("[class*=col]");
                if (col) col.style.display = "none";
                else w.style.display = "none";
            }
        });

        // Hide empty section headers
        document.querySelectorAll(".widget.header-widget-box, .ce-header").forEach(function (h) {
            var next = h.closest("[class*=col]") ? h.closest("[class*=col]").nextElementSibling : h.nextElementSibling;
            if (next && next.style && next.style.display === "none") {
                var hCol = h.closest("[class*=col]");
                if (hCol) hCol.style.display = "none";
                else h.style.display = "none";
            }
        });
    }

    function run() {
        if (!hasRole()) return;
        filterSidebar();
        filterHome();
    }

    // Run on page load and SPA navigation
    document.addEventListener("DOMContentLoaded", function () { setTimeout(run, 500); });

    if (typeof MutationObserver !== "undefined") {
        var timer;
        var obs = new MutationObserver(function () {
            if (!hasRole()) return;
            clearTimeout(timer);
            timer = setTimeout(run, 250);
        });
        var startObs = function () {
            if (document.body) obs.observe(document.body, { childList: true, subtree: true });
        };
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", startObs);
        } else {
            startObs();
        }
    }
})();
