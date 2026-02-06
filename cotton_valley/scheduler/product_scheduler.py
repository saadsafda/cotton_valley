import frappe
import time
import requests
import uuid
from typing import List, Optional

LOCK_KEY = "cv_sync_items_lock"
DEFAULT_BATCH_SIZE = 300
DEFAULT_MAX_BATCHES_PER_RUN = 10  # Not used anymore - all items processed in one go


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
    - Enqueues N batches with progress tracking
    - Releases lock
    """
    if not _get_cv_setting("is_enabled", 1):
        return "CV Sync is disabled."

    if not _acquire_lock(ttl_seconds=60 * 60):
        # Another run is in progress
        return "CV Sync already running (lock exists)."

    try:
        batch_size = int(_get_cv_setting("batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE)

        company = "Cotton Valley"

        # Fetch ALL items for company in one go
        items = frappe.get_all(
            "Item",
            filters={"company": company},
            fields=["name"],
            order_by="name asc"
        )

        if not items:
            return "CV Sync: No items found for Cotton Valley."

        names = [d["name"] for d in items]

        # Split into batches and enqueue each batch
        batches = [names[i:i + batch_size] for i in range(0, len(names), batch_size)]
        
        # Generate a task_id for progress tracking
        task_id = f"cv_scheduler_{uuid.uuid4().hex[:8]}"
        total_items = len(names)
        total_batches = len(batches)
        
        # Store task info in cache for progress page
        frappe.cache().set_value(
            f"sync_task_{task_id}",
            {
                "task_id": task_id,
                "company": company,
                "total_items": total_items,
                "total_batches": total_batches,
                "status": "running",
                "started_at": frappe.utils.now()
            },
            expires_in_sec=3600 * 2  # 2 hours
        )

        items_before_batch = 0
        for idx, batch in enumerate(batches, start=1):
            frappe.enqueue(
                "cotton_valley.api.products.sync_cv_item_batch",
                queue="long",
                timeout=1800,  # 30 minutes per batch (tune as needed)
                now=False,
                batch=batch,
                company=company,
                task_id=task_id,
                batch_number=idx,
                total_batches=total_batches,
                total_items=total_items,
                items_before_batch=items_before_batch
            )
            items_before_batch += len(batch)

        return {
            "success": True,
            "task_id": task_id,
            "message": f"CV Sync dispatched {len(batches)} batches, {len(names)} items total.",
            "total_batches": total_batches,
            "total_items": total_items
        }

    finally:
        _release_lock()



@frappe.whitelist()
def scheduler_dispatch_udc_item_sync():
    """
    Scheduler-safe dispatcher:
    - Acquires a lock
    - Reads cursor
    - Enqueues N batches with progress tracking
    - Releases lock
    """
    if not _get_cv_setting("is_enabled", 1):
        return "UDC Sync is disabled."

    if not _acquire_lock(ttl_seconds=60 * 60):
        # Another run is in progress
        return "UDC Sync already running (lock exists)."

    try:
        batch_size = int(_get_cv_setting("batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE)

        company = "UDC"

        # Fetch ALL items for company in one go
        items = frappe.get_all(
            "Item",
            filters={"company": company},
            fields=["name"],
            order_by="name asc"
        )

        if not items:
            return "UDC Sync: No items found for UDC."

        names = [d["name"] for d in items]

        # Split into batches and enqueue each batch
        batches = [names[i:i + batch_size] for i in range(0, len(names), batch_size)]
        
        # Generate a task_id for progress tracking
        task_id = f"udc_scheduler_{uuid.uuid4().hex[:8]}"
        total_items = len(names)
        total_batches = len(batches)
        
        # Store task info in cache for progress page
        frappe.cache().set_value(
            f"sync_task_{task_id}",
            {
                "task_id": task_id,
                "company": company,
                "total_items": total_items,
                "total_batches": total_batches,
                "status": "running",
                "started_at": frappe.utils.now()
            },
            expires_in_sec=3600 * 2  # 2 hours
        )

        items_before_batch = 0
        for idx, batch in enumerate(batches, start=1):
            frappe.enqueue(
                "cotton_valley.api.products.sync_udc_item_batch",
                queue="long",
                timeout=1800,  # 30 minutes per batch (tune as needed)
                now=False,
                batch=batch,
                company=company,
                task_id=task_id,
                batch_number=idx,
                total_batches=total_batches,
                total_items=total_items,
                items_before_batch=items_before_batch
            )
            items_before_batch += len(batch)

        return {
            "success": True,
            "task_id": task_id,
            "message": f"UDC Sync dispatched {len(batches)} batches, {len(names)} items total.",
            "total_batches": total_batches,
            "total_items": total_items
        }

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

        company = "Cotton Valley"
        
        # Calculate max_batches based on total products / batch_size
        total_products = frappe.db.count("Item", {"company": company})
        max_batches = (total_products + batch_size - 1) // batch_size  # Ceiling division
        
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
        
        # Generate a task_id for progress tracking
        task_id = f"cv_price_scheduler_{uuid.uuid4().hex[:8]}"
        total_items = len(names)
        total_batches = len(batches)
        
        # Store task info in cache for progress page
        frappe.cache().set_value(
            f"sync_task_{task_id}",
            {
                "task_id": task_id,
                "company": company,
                "sync_type": "price",
                "total_items": total_items,
                "total_batches": total_batches,
                "status": "running",
                "started_at": frappe.utils.now()
            },
            expires_in_sec=3600 * 2
        )

        items_before_batch = 0
        for idx, batch in enumerate(batches, start=1):
            frappe.enqueue(
                "cotton_valley.api.products.sync_cv_price_batch",
                queue="long",
                timeout=1800,
                now=False,
                batch=batch,
                company=company,
                task_id=task_id,
                batch_number=idx,
                total_batches=total_batches,
                total_items=total_items,
                items_before_batch=items_before_batch
            )
            items_before_batch += len(batch)

        _set_cv_setting("last_price_item_code_cv", names[-1])

        return {
            "success": True,
            "task_id": task_id,
            "message": f"CV Price Sync dispatched {len(batches)} batches, {len(names)} items. Cursor -> {names[-1]}",
            "total_batches": total_batches,
            "total_items": total_items
        }

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

        company = "UDC"
        
        # Calculate max_batches based on total products / batch_size
        total_products = frappe.db.count("Item", {"company": company})
        max_batches = (total_products + batch_size - 1) // batch_size  # Ceiling division
        
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
        
        # Generate a task_id for progress tracking
        task_id = f"udc_price_scheduler_{uuid.uuid4().hex[:8]}"
        total_items = len(names)
        total_batches = len(batches)
        
        # Store task info in cache for progress page
        frappe.cache().set_value(
            f"sync_task_{task_id}",
            {
                "task_id": task_id,
                "company": company,
                "sync_type": "price",
                "total_items": total_items,
                "total_batches": total_batches,
                "status": "running",
                "started_at": frappe.utils.now()
            },
            expires_in_sec=3600 * 2
        )

        items_before_batch = 0
        for idx, batch in enumerate(batches, start=1):
            frappe.enqueue(
                "cotton_valley.api.products.sync_udc_price_batch",
                queue="long",
                timeout=1800,
                now=False,
                batch=batch,
                company=company,
                task_id=task_id,
                batch_number=idx,
                total_batches=total_batches,
                total_items=total_items,
                items_before_batch=items_before_batch
            )
            items_before_batch += len(batch)

        _set_cv_setting("last_price_item_code_udc", names[-1])

        return {
            "success": True,
            "task_id": task_id,
            "message": f"UDC Price Sync dispatched {len(batches)} batches, {len(names)} items. Cursor -> {names[-1]}",
            "total_batches": total_batches,
            "total_items": total_items
        }

    finally:
        _release_price_lock(PRICE_LOCK_KEY_UDC)
