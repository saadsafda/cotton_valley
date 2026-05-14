/**
 * Multi-Site Website Search Tracking Script
 * ==========================================
 *
 * Tracks search queries on both:
 *   - universaldc.com   → Company: UDC
 *   - cottonvalley.net   → Company: Cotton Valley
 *
 * Logs data to the ERPNext backend at portal.cottonvalley.net.
 *
 * Both sites use identical search patterns:
 *   - URL: /search?search=QUERY
 *   - Results text: "Showing 1-100 of N results"
 *   - Next.js SPA with client-side routing
 *
 * INSTALLATION:
 * Add this script to each Next.js app layout with data-company attribute:
 *
 *   <Script
 *     src="https://portal.cottonvalley.net/assets/cotton_valley/js/search_tracker.js"
 *     strategy="afterInteractive"
 *     data-company="UDC"           // for universaldc.com
 *     data-company="Cotton Valley" // for cottonvalley.net
 *   />
 */

(function () {
    "use strict";

    // ── Configuration ────────────────────────────────────────────────
    var CONFIG = {
        // ERPNext backend API endpoint
        API_URL: "https://portal.cottonvalley.net/api/method/cotton_valley.api.search_log.log_website_search",

        // Debounce interval (ms) for live/AJAX searches
        DEBOUNCE_MS: 1500,

        // Minimum query length to track
        MIN_QUERY_LENGTH: 2,

        // LocalStorage key for guest session ID
        SESSION_KEY: "cv_guest_session_id",

        // Prevent duplicate logging of the same query within this window (ms)
        DEDUP_WINDOW_MS: 5000,
    };

    // ── Company Detection ─────────────────────────────────────────────
    // Reads the data-company attribute from the <script> tag.
    // This is the most reliable method — works on localhost and production.
    function getCompany() {
        // Method 1: Read data-company from this script tag
        var scripts = document.querySelectorAll('script[src*="search_tracker"]');
        for (var i = 0; i < scripts.length; i++) {
            var company = scripts[i].getAttribute('data-company');
            if (company) return company;
        }
        // Method 2: Detect from domain (production fallback)
        var host = window.location.hostname.toLowerCase();
        if (host.indexOf('universaldc') !== -1) return 'UDC';
        if (host.indexOf('cottonvalley') !== -1) return 'Cotton Valley';
        return '';
    }

    // ── Guest Session ID Management ──────────────────────────────────
    function getGuestSessionId() {
        var sessionId = null;

        try {
            sessionId = localStorage.getItem(CONFIG.SESSION_KEY);
        } catch (e) {
            // localStorage unavailable
        }

        if (!sessionId) {
            sessionId = generateUUID();
            try {
                localStorage.setItem(CONFIG.SESSION_KEY, sessionId);
            } catch (e) {
                // Fallback: use a cookie
                document.cookie = CONFIG.SESSION_KEY + "=" + sessionId + ";path=/;max-age=31536000;SameSite=Lax";
            }
        }

        return sessionId;
    }

    function generateUUID() {
        if (typeof crypto !== "undefined" && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
            var r = (Math.random() * 16) | 0;
            var v = c === "x" ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    // ── Deduplication ────────────────────────────────────────────────
    var _lastLoggedQuery = "";
    var _lastLoggedTime = 0;

    function isDuplicate(query) {
        var normalized = query.toLowerCase().trim();
        var now = Date.now();
        if (normalized === _lastLoggedQuery && now - _lastLoggedTime < CONFIG.DEDUP_WINDOW_MS) {
            return true;
        }
        _lastLoggedQuery = normalized;
        _lastLoggedTime = now;
        return false;
    }

    // ── API Logging ──────────────────────────────────────────────────
    function logSearch(searchQuery, resultsCount) {
        if (!searchQuery || typeof searchQuery !== "string") return;

        // Clean the query
        searchQuery = searchQuery.trim().replace(/\s+/g, " ");
        if (searchQuery.length < CONFIG.MIN_QUERY_LENGTH) return;

        // Prevent duplicate logging
        if (isDuplicate(searchQuery)) return;

        var payload = {
            search_query: searchQuery,
            page_url: window.location.href,
            referrer: document.referrer || "",
            results_count: resultsCount !== undefined && resultsCount !== null ? parseInt(resultsCount, 10) : 0,
            guest_session_id: getGuestSessionId(),
            origin: window.location.origin,
            company: getCompany(),
        };

        var body = new URLSearchParams();
        for (var key in payload) {
            if (payload.hasOwnProperty(key)) {
                body.append(key, payload[key]);
            }
        }

        // Use sendBeacon for reliability (fires even during page unload)
        if (navigator.sendBeacon) {
            var blob = new Blob([body.toString()], {
                type: "application/x-www-form-urlencoded",
            });
            var sent = navigator.sendBeacon(CONFIG.API_URL, blob);
            if (!sent) {
                sendViaFetch(body);
            }
        } else {
            sendViaFetch(body);
        }
    }

    function sendViaFetch(body) {
        try {
            fetch(CONFIG.API_URL, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Frappe-CSRF-Token": "None",
                },
                body: body.toString(),
                keepalive: true,
                credentials: "include",
            }).catch(function () {
                // Silently fail — search tracking should never block the user
            });
        } catch (e) {
            // Silently fail
        }
    }

    // ── Debounce Helper ──────────────────────────────────────────────
    function debounce(fn, delay) {
        var timer = null;
        return function () {
            var context = this;
            var args = arguments;
            if (timer) clearTimeout(timer);
            timer = setTimeout(function () {
                fn.apply(context, args);
            }, delay);
        };
    }

    // ── URL-Based Search Detection ───────────────────────────────────
    // Both universaldc.com and cottonvalley.net use /search?search=QUERY
    function getSearchQueryFromURL() {
        var params = new URLSearchParams(window.location.search);
        return params.get("search") || params.get("q") || params.get("query") || "";
    }

    function getResultsCountFromPage() {
        // Both sites show "Showing X-Y of Z results"
        var resultElements = document.querySelectorAll(
            'p, span, div, [class*="result"], [class*="count"], [class*="showing"]'
        );
        for (var i = 0; i < resultElements.length; i++) {
            var text = resultElements[i].textContent || "";
            var match = text.match(/of\s+([\d,]+)\s+results?/i);
            if (match) {
                return parseInt(match[1].replace(/,/g, ""), 10);
            }
            match = text.match(/([\d,]+)\s+results?\s+found/i);
            if (match) {
                return parseInt(match[1].replace(/,/g, ""), 10);
            }
        }
        return 0;
    }

    // ── Input Tracking ───────────────────────────────────────────────
    function attachToSearchInputs() {
        // Selectors that work on both universaldc.com and cottonvalley.net
        var selectors = [
            'input[type="search"]',
            'input[name="search"]',
            'input[name="q"]',
            'input[name="query"]',
            'input[placeholder*="Search"]',
            'input[placeholder*="search"]',
            'input[aria-label*="search" i]',
            '.search-input input',
            '.search-bar input',
            '#search-input',
            '#searchInput',
            '[data-testid="search-input"]',
        ];

        var allInputs = [];
        for (var i = 0; i < selectors.length; i++) {
            try {
                var found = document.querySelectorAll(selectors[i]);
                for (var j = 0; j < found.length; j++) {
                    if (allInputs.indexOf(found[j]) === -1) {
                        allInputs.push(found[j]);
                    }
                }
            } catch (e) {
                // Some selectors may not be valid in all browsers
            }
        }

        allInputs.forEach(function (input) {
            if (input._searchTrackerAttached) return;
            input._searchTrackerAttached = true;

            // Track form submission
            var form = input.closest("form");
            if (form && !form._searchTrackerAttached) {
                form._searchTrackerAttached = true;
                form.addEventListener("submit", function () {
                    var query = input.value;
                    if (query && query.trim().length >= CONFIG.MIN_QUERY_LENGTH) {
                        logSearch(query, 0);
                    }
                });
            }

            // Track Enter key press
            input.addEventListener("keydown", function (e) {
                if (e.key === "Enter" || e.keyCode === 13) {
                    var query = input.value;
                    if (query && query.trim().length >= CONFIG.MIN_QUERY_LENGTH) {
                        setTimeout(function () {
                            logSearch(query, 0);
                        }, 50);
                    }
                }
            });

            // Track button click near search input
            var searchBtn = form
                ? form.querySelector('button[type="submit"], button:not([type]), [class*="search-btn"], [class*="search-icon"]')
                : null;
            if (searchBtn && !searchBtn._searchTrackerAttached) {
                searchBtn._searchTrackerAttached = true;
                searchBtn.addEventListener("click", function () {
                    var query = input.value;
                    if (query && query.trim().length >= CONFIG.MIN_QUERY_LENGTH) {
                        logSearch(query, 0);
                    }
                });
            }
        });
    }

    // ── Next.js Route Change Detection ───────────────────────────────
    // Both sites are Next.js SPAs — detect client-side route changes
    function setupRouteChangeListener() {
        var lastHref = window.location.href;

        var originalPushState = history.pushState;
        var originalReplaceState = history.replaceState;

        function onRouteChange() {
            var currentHref = window.location.href;
            if (currentHref !== lastHref) {
                lastHref = currentHref;
                if (window.location.pathname === "/search" || window.location.pathname.indexOf("/search") !== -1) {
                    // Wait for DOM to render search results
                    setTimeout(function () {
                        var query = getSearchQueryFromURL();
                        if (query && query.trim().length >= CONFIG.MIN_QUERY_LENGTH) {
                            var resultsCount = getResultsCountFromPage();
                            logSearch(query, resultsCount);
                        }
                        attachToSearchInputs();
                    }, 1500);
                } else {
                    setTimeout(attachToSearchInputs, 500);
                }
            }
        }

        history.pushState = function () {
            originalPushState.apply(this, arguments);
            onRouteChange();
        };

        history.replaceState = function () {
            originalReplaceState.apply(this, arguments);
            onRouteChange();
        };

        window.addEventListener("popstate", onRouteChange);
    }

    // ── Initialization ───────────────────────────────────────────────
    function init() {
        // 1. If already on the search results page, log the current search
        if (window.location.pathname === "/search" || window.location.pathname.indexOf("/search") !== -1) {
            setTimeout(function () {
                var query = getSearchQueryFromURL();
                if (query && query.trim().length >= CONFIG.MIN_QUERY_LENGTH) {
                    var resultsCount = getResultsCountFromPage();
                    logSearch(query, resultsCount);
                }
            }, 2000);
        }

        // 2. Attach to existing search inputs
        attachToSearchInputs();

        // 3. Setup route change listener for SPA navigation
        setupRouteChangeListener();

        // 4. MutationObserver for dynamically added search inputs
        if (typeof MutationObserver !== "undefined") {
            var observer = new MutationObserver(
                debounce(function () {
                    attachToSearchInputs();
                }, 500)
            );
            observer.observe(document.body, {
                childList: true,
                subtree: true,
            });
        }
    }

    // ── Start ────────────────────────────────────────────────────────
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    // Expose globally for manual use
    window.cvLogSearch = logSearch;
})();
