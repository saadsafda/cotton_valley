import frappe
import time
import requests
from typing import List, Optional

LOCK_KEY = "cv_sync_items_lock"
DEFAULT_BATCH_SIZE = 200
DEFAULT_MAX_BATCHES_PER_RUN = 10  # 10 * 200 = 2000 items per scheduler run


def _get_cv_setting(fieldname: str, default=None):
    """Reads from Single doctype CV Sync Settings. Falls back to default if missing."""
    try:
        val = frappe.db.get_single_value("CV Sync Settings", fieldname)
        return val if val not in (None, "") else default
    except Exception:
        return default


def _set_cv_setting(fieldname: str, value):
    try:
        frappe.db.set_single_value("CV Sync Settings", fieldname, value)
    except Exception:
        # If settings doctype doesn't exist, ignore (or change to cache-based storage)
        pass


def _acquire_lock(ttl_seconds: int = 60 * 60) -> bool:
    """Prevents overlapping runs. Uses Redis."""
    cache = frappe.cache()
    # Check if lock exists
    if cache.get_value(LOCK_KEY):
        return False
    # Set lock with expiration
    cache.set_value(LOCK_KEY, "1", expires_in_sec=ttl_seconds)
    return True


def _release_lock():
    frappe.cache().delete_value(LOCK_KEY)


@frappe.whitelist()
def scheduler_dispatch_cv_item_sync():
    """
    Scheduler-safe dispatcher:
    - Acquires a lock
    - Reads cursor
    - Enqueues N batches
    - Releases lock
    """
    if not _get_cv_setting("is_enabled", 1):
        return "CV Sync is disabled."

    if not _acquire_lock(ttl_seconds=60 * 60):
        # Another run is in progress
        return "CV Sync already running (lock exists)."

    try:
        batch_size = int(_get_cv_setting("batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE)
        max_batches = int(_get_cv_setting("max_batches_per_run", DEFAULT_MAX_BATCHES_PER_RUN) or DEFAULT_MAX_BATCHES_PER_RUN)

        company = "Cotton Valley"
        last_item_code = _get_cv_setting("last_item_code", "") or ""

        # Fetch items in stable order, continuing after last_item_code
        # (This avoids loading all 4000 into memory)
        filters = {"company": company}
        if last_item_code:
            filters["name"] = (">", last_item_code)

        items = frappe.get_all(
            "Item",
            filters=filters,
            fields=["name"],
            order_by="name asc",
            limit=batch_size * max_batches
        )

        if not items:
            # We reached the end — reset cursor so next run starts from beginning
            _set_cv_setting("last_item_code", "")
            return "CV Sync: reached end, cursor reset."

        names = [d["name"] for d in items]

        # Split into batches and enqueue each batch
        batches = [names[i:i + batch_size] for i in range(0, len(names), batch_size)]

        for idx, batch in enumerate(batches, start=1):
            frappe.enqueue(
                "cotton_valley.api.products.sync_cv_item_batch",
                queue="long",
                timeout=1800,  # 30 minutes per batch (tune as needed)
                now=False,
                batch=batch,
                company=company
            )

        # Update cursor to last item we dispatched (not processed) so next scheduler continues
        _set_cv_setting("last_item_code", names[-1])

        return f"CV Sync dispatched {len(batches)} batches, {len(names)} items. Cursor -> {names[-1]}"

    finally:
        _release_lock()



@frappe.whitelist()
def scheduler_dispatch_udc_item_sync():
    """
    Scheduler-safe dispatcher:
    - Acquires a lock
    - Reads cursor
    - Enqueues N batches
    - Releases lock
    """
    if not _get_cv_setting("is_enabled", 1):
        return "UDC Sync is disabled."

    if not _acquire_lock(ttl_seconds=60 * 60):
        # Another run is in progress
        return "UDC Sync already running (lock exists)."

    try:
        batch_size = int(_get_cv_setting("batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE)
        max_batches = int(_get_cv_setting("max_batches_per_run", DEFAULT_MAX_BATCHES_PER_RUN) or DEFAULT_MAX_BATCHES_PER_RUN)

        company = "UDC"
        last_item_code = _get_cv_setting("last_item_code", "") or ""

        # Fetch items in stable order, continuing after last_item_code
        # (This avoids loading all 4000 into memory)
        filters = {"company": company}
        if last_item_code:
            filters["name"] = (">", last_item_code)

        items = frappe.get_all(
            "Item",
            filters=filters,
            fields=["name"],
            order_by="name asc",
            limit=batch_size * max_batches
        )

        if not items:
            # We reached the end — reset cursor so next run starts from beginning
            _set_cv_setting("last_item_code", "")
            return "UDC Sync: reached end, cursor reset."

        names = [d["name"] for d in items]

        # Split into batches and enqueue each batch
        batches = [names[i:i + batch_size] for i in range(0, len(names), batch_size)]

        for idx, batch in enumerate(batches, start=1):
            frappe.enqueue(
                "cotton_valley.api.products.sync_udc_item_batch",
                queue="long",
                timeout=1800,  # 30 minutes per batch (tune as needed)
                now=False,
                batch=batch,
                company=company
            )

        # Update cursor to last item we dispatched (not processed) so next scheduler continues
        _set_cv_setting("last_item_code", names[-1])

        return f"UDC Sync dispatched {len(batches)} batches, {len(names)} items. Cursor -> {names[-1]}"

    finally:
        _release_lock()


# ============ PRODUCT PRICES SCHEDULER ============

PRICE_LOCK_KEY_CV = "cv_sync_prices_lock"
PRICE_LOCK_KEY_UDC = "udc_sync_prices_lock"


def _acquire_price_lock(lock_key: str, ttl_seconds: int = 60 * 60) -> bool:
    """Prevents overlapping runs. Uses Redis."""
    cache = frappe.cache()
    if cache.get_value(lock_key):
        return False
    cache.set_value(lock_key, "1", expires_in_sec=ttl_seconds)
    return True


def _release_price_lock(lock_key: str):
    frappe.cache().delete_value(lock_key)


@frappe.whitelist()
def scheduler_dispatch_cv_price_sync():
    """
    Scheduler-safe dispatcher for Cotton Valley prices:
    - Acquires a lock
    - Reads cursor
    - Enqueues N batches
    - Releases lock
    """
    if not _get_cv_setting("is_enabled", 1):
        return "CV Price Sync is disabled."

    if not _acquire_price_lock(PRICE_LOCK_KEY_CV, ttl_seconds=60 * 60):
        return "CV Price Sync already running (lock exists)."

    try:
        batch_size = int(_get_cv_setting("batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE)
        max_batches = int(_get_cv_setting("max_batches_per_run", DEFAULT_MAX_BATCHES_PER_RUN) or DEFAULT_MAX_BATCHES_PER_RUN)

        company = "Cotton Valley"
        last_price_item_code = _get_cv_setting("last_price_item_code_cv", "") or ""

        filters = {"company": company}
        if last_price_item_code:
            filters["name"] = (">", last_price_item_code)

        items = frappe.get_all(
            "Item",
            filters=filters,
            fields=["name"],
            order_by="name asc",
            limit=batch_size * max_batches
        )

        if not items:
            _set_cv_setting("last_price_item_code_cv", "")
            return "CV Price Sync: reached end, cursor reset."

        names = [d["name"] for d in items]
        batches = [names[i:i + batch_size] for i in range(0, len(names), batch_size)]

        for idx, batch in enumerate(batches, start=1):
            frappe.enqueue(
                "cotton_valley.api.products.sync_cv_price_batch",
                queue="long",
                timeout=1800,
                now=False,
                batch=batch,
                company=company
            )

        _set_cv_setting("last_price_item_code_cv", names[-1])

        return f"CV Price Sync dispatched {len(batches)} batches, {len(names)} items. Cursor -> {names[-1]}"

    finally:
        _release_price_lock(PRICE_LOCK_KEY_CV)


@frappe.whitelist()
def scheduler_dispatch_udc_price_sync():
    """
    Scheduler-safe dispatcher for UDC prices:
    - Acquires a lock
    - Reads cursor
    - Enqueues N batches
    - Releases lock
    """
    if not _get_cv_setting("is_enabled", 1):
        return "UDC Price Sync is disabled."

    if not _acquire_price_lock(PRICE_LOCK_KEY_UDC, ttl_seconds=60 * 60):
        return "UDC Price Sync already running (lock exists)."

    try:
        batch_size = int(_get_cv_setting("batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE)
        max_batches = int(_get_cv_setting("max_batches_per_run", DEFAULT_MAX_BATCHES_PER_RUN) or DEFAULT_MAX_BATCHES_PER_RUN)

        company = "UDC"
        last_price_item_code = _get_cv_setting("last_price_item_code_udc", "") or ""

        filters = {"company": company}
        if last_price_item_code:
            filters["name"] = (">", last_price_item_code)

        items = frappe.get_all(
            "Item",
            filters=filters,
            fields=["name"],
            order_by="name asc",
            limit=batch_size * max_batches
        )

        if not items:
            _set_cv_setting("last_price_item_code_udc", "")
            return "UDC Price Sync: reached end, cursor reset."

        names = [d["name"] for d in items]
        batches = [names[i:i + batch_size] for i in range(0, len(names), batch_size)]

        for idx, batch in enumerate(batches, start=1):
            frappe.enqueue(
                "cotton_valley.api.products.sync_udc_price_batch",
                queue="long",
                timeout=1800,
                now=False,
                batch=batch,
                company=company
            )

        _set_cv_setting("last_price_item_code_udc", names[-1])

        return f"UDC Price Sync dispatched {len(batches)} batches, {len(names)} items. Cursor -> {names[-1]}"

    finally:
        _release_price_lock(PRICE_LOCK_KEY_UDC)
