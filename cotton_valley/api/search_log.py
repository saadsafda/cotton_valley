# Copyright (c) 2026, Saad and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime, cint
import re
import time


# ── Domain → Company Mapping ──────────────────────────────────────────────
# Maps website domains to their corresponding ERPNext Company names.
# Both www and non-www variants are included.
DOMAIN_COMPANY_MAP = {
    "universaldc.com": "UDC",
    "www.universaldc.com": "UDC",
    "cottonvalley.net": "Cotton Valley",
    "www.cottonvalley.net": "Cotton Valley",
}


# ── Rate Limiting ──────────────────────────────────────────────────────────
_rate_limit_cache = {}
RATE_LIMIT_WINDOW = 60       # seconds
RATE_LIMIT_MAX_REQUESTS = 30 # max searches per window per IP


def _check_rate_limit(ip_address):
    """
    Check if the IP has exceeded the rate limit.
    Returns True if rate-limited (should block), False otherwise.
    """
    if not ip_address:
        return False

    now = time.time()
    key = f"search_log:{ip_address}"

    # Try Redis-based rate limiting first (works across workers)
    try:
        cache_key = f"search_rate_limit:{ip_address}"
        count = frappe.cache().get_value(cache_key)
        if count is None:
            frappe.cache().set_value(cache_key, 1, expires_in_sec=RATE_LIMIT_WINDOW)
            return False
        count = cint(count)
        if count >= RATE_LIMIT_MAX_REQUESTS:
            return True
        frappe.cache().set_value(cache_key, count + 1, expires_in_sec=RATE_LIMIT_WINDOW)
        return False
    except Exception:
        # Fallback to in-memory rate limiting if Redis is unavailable
        if key in _rate_limit_cache:
            window_start, count = _rate_limit_cache[key]
            if now - window_start < RATE_LIMIT_WINDOW:
                if count >= RATE_LIMIT_MAX_REQUESTS:
                    return True
                _rate_limit_cache[key] = (window_start, count + 1)
                return False

        _rate_limit_cache[key] = (now, 1)
        return False


# ── Input Sanitization ────────────────────────────────────────────────────
def _sanitize_string(value, max_length=140):
    """
    Sanitize a string input:
    - Convert to string
    - Strip whitespace
    - Remove HTML tags
    - Truncate to max_length
    """
    if not value:
        return ""
    value = str(value).strip()
    # Remove HTML tags
    value = re.sub(r'<[^>]+>', '', value)
    # Remove potential script injections
    value = re.sub(r'(?i)(javascript|on\w+\s*=)', '', value)
    # Truncate
    if len(value) > max_length:
        value = value[:max_length]
    return value


def _sanitize_url(value, max_length=500):
    """Sanitize a URL value."""
    if not value:
        return ""
    value = str(value).strip()
    # Only allow http/https URLs or relative paths
    if value and not re.match(r'^(https?://|/)', value):
        return ""
    # Remove potential XSS in URLs
    value = re.sub(r'(?i)javascript:', '', value)
    if len(value) > max_length:
        value = value[:max_length]
    return value


def _extract_domain(url):
    """
    Extract the hostname/domain from a URL.
    e.g. 'https://www.universaldc.com/search?q=test' → 'www.universaldc.com'
    """
    if not url:
        return ""
    try:
        # Simple regex extraction — avoids importing urllib
        match = re.match(r'https?://([^/:]+)', url)
        if match:
            return match.group(1).lower()
    except Exception:
        pass
    return ""


def _resolve_company(page_url, referrer, origin):
    """
    Determine the ERPNext Company based on the domain of the request.
    Checks page_url first, then referrer, then explicit origin param.
    Falls back to the system default company.
    """
    # Try page_url domain first
    domain = _extract_domain(page_url)
    if domain and domain in DOMAIN_COMPANY_MAP:
        return DOMAIN_COMPANY_MAP[domain]

    # Try referrer domain
    domain = _extract_domain(referrer)
    if domain and domain in DOMAIN_COMPANY_MAP:
        return DOMAIN_COMPANY_MAP[domain]

    # Try explicit origin parameter (sent by the frontend JS)
    if origin:
        origin_clean = str(origin).strip().lower()
        # origin might be a full URL like 'https://universaldc.com'
        origin_domain = _extract_domain(origin_clean) or origin_clean
        if origin_domain in DOMAIN_COMPANY_MAP:
            return DOMAIN_COMPANY_MAP[origin_domain]

    # Fallback: try the HTTP Origin / Referer headers
    try:
        if hasattr(frappe.local, 'request') and frappe.local.request:
            http_origin = frappe.local.request.headers.get("Origin", "")
            if http_origin:
                origin_domain = _extract_domain(http_origin)
                if origin_domain and origin_domain in DOMAIN_COMPANY_MAP:
                    return DOMAIN_COMPANY_MAP[origin_domain]

            http_referer = frappe.local.request.headers.get("Referer", "")
            if http_referer:
                ref_domain = _extract_domain(http_referer)
                if ref_domain and ref_domain in DOMAIN_COMPANY_MAP:
                    return DOMAIN_COMPANY_MAP[ref_domain]
    except Exception:
        pass

    # Final fallback: system default
    try:
        return frappe.db.get_default("company") or ""
    except Exception:
        return ""


# ── Main API Method ───────────────────────────────────────────────────────
@frappe.whitelist(allow_guest=True)
def log_website_search(
    search_query=None,
    page_url=None,
    referrer=None,
    results_count=None,
    guest_session_id=None,
    origin=None
):
    """
    Log a website search query into the Website Search Log DocType.

    This method is accessible by guest users and logged-in users.
    All inputs are sanitized and validated before insertion.
    Rate limiting is applied per IP address.

    Supports multiple websites:
    - universaldc.com  → Company = "UDC"
    - cottonvalley.net → Company = "Cotton Valley"

    Args:
        search_query (str): The search term entered by the user.
        page_url (str): The URL of the page where the search was performed.
        referrer (str): The HTTP referrer URL.
        results_count (int/str): Number of search results returned.
        guest_session_id (str): UUID for tracking guest sessions.
        origin (str): The website origin domain (e.g. 'https://universaldc.com').

    Returns:
        dict: Status of the operation with success/ignored/error.
    """
    try:
        # ── Sanitize inputs ───────────────────────────────────────────
        search_query = _sanitize_string(search_query, max_length=500)
        page_url = _sanitize_url(page_url, max_length=500)
        referrer = _sanitize_url(referrer, max_length=500)
        guest_session_id = _sanitize_string(guest_session_id, max_length=140)
        origin = _sanitize_string(origin, max_length=200)

        # ── Validate search query ─────────────────────────────────────
        if not search_query:
            return {"status": "ignored", "reason": "Empty search query"}

        # Trim extra spaces (collapse multiple spaces)
        search_query = re.sub(r'\s+', ' ', search_query).strip()

        if len(search_query) < 2:
            return {"status": "ignored", "reason": "Search query too short (minimum 2 characters)"}

        # ── Rate limiting ─────────────────────────────────────────────
        ip_address = frappe.local.request_ip if hasattr(frappe.local, 'request_ip') else ""
        if _check_rate_limit(ip_address):
            return {"status": "error", "reason": "Rate limit exceeded. Please try again later."}

        # ── Normalize query ───────────────────────────────────────────
        normalized_query = search_query.lower().strip()

        # ── Detect user type ──────────────────────────────────────────
        session_user = frappe.session.user if frappe.session else "Guest"

        if session_user == "Guest":
            user_type = "Guest"
            user = ""
        else:
            user_type = "Logged In"
            user = session_user

        # ── Get request metadata ──────────────────────────────────────
        user_agent = ""
        if hasattr(frappe.local, 'request') and frappe.local.request:
            user_agent = _sanitize_string(
                frappe.local.request.headers.get("User-Agent", ""),
                max_length=500
            )

        # ── Parse results count ───────────────────────────────────────
        try:
            results_count = cint(results_count) if results_count else 0
            # Prevent absurdly large numbers
            if results_count < 0:
                results_count = 0
            if results_count > 999999:
                results_count = 999999
        except (ValueError, TypeError):
            results_count = 0

        # ── Resolve company from domain ───────────────────────────────
        company = _resolve_company(page_url, referrer, origin)

        # ── Create log entry ──────────────────────────────────────────
        log = frappe.get_doc({
            "doctype": "Website Search Log",
            "search_query": search_query,
            "normalized_query": normalized_query,
            "user_type": user_type,
            "user": user,
            "guest_session_id": guest_session_id if user_type == "Guest" else "",
            "ip_address": ip_address,
            "user_agent": user_agent,
            "page_url": page_url,
            "referrer": referrer,
            "results_count": results_count,
            "searched_on": now_datetime(),
            "company": company,
        })

        log.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Search logged successfully",
            "name": log.name,
            "company": company
        }

    except Exception as e:
        frappe.log_error(
            title="Website Search Log Error",
            message=frappe.get_traceback()
        )
        return {"status": "error", "reason": "Internal error while logging search"}
