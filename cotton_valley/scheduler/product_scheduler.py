import frappe
import time
import requests
import uuid
from typing import List, Optional

ITEM_LOCK_KEY_CV = "cv_sync_items_lock"
ITEM_LOCK_KEY_UDC = "udc_sync_items_lock"
DEFAULT_BATCH_SIZE = 400
DEFAULT_MAX_BATCHES_PER_RUN = 10  # Max batches per scheduler invocation


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
        pass


def _acquire_lock(lock_key: str, ttl_seconds: int = 60 * 60) -> bool:
    """Prevents overlapping runs. Uses Redis."""
    cache = frappe.cache()
    if cache.get_value(lock_key):
        return False
    cache.set_value(lock_key, "1", expires_in_sec=ttl_seconds)
    return True


def _release_lock(lock_key: str):
    frappe.cache().delete_value(lock_key)


def _dispatch_item_sync(company: str, lock_key: str, cursor_key: str, sync_fn: str, task_prefix: str):
    """
    Generic dynamic item sync dispatcher.
    
    Strategy:
    1. First, find NEW items (never synced: available_stock is NULL/0 AND created recently)
       and items modified since last sync — these get priority.
    2. Then, continue cursor-based sync from where we left off for remaining items.
    3. When cursor reaches the end, reset it so next run starts fresh.
    4. Dynamic batch count: calculates based on total items & batch_size.
    """
    if not _get_cv_setting("is_enabled", 1):
        return f"{company} Item Sync is disabled."

    if not _acquire_lock(lock_key, ttl_seconds=60 * 60):
        return f"{company} Item Sync already running (lock exists)."

    try:
        batch_size = int(_get_cv_setting("batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE)
        max_batches = int(_get_cv_setting("max_batches_per_run", DEFAULT_MAX_BATCHES_PER_RUN) or DEFAULT_MAX_BATCHES_PER_RUN)
        max_items_per_run = batch_size * max_batches

        # --- Phase 1: Priority items (new / never synced) ---
        # Items with no available_stock (NULL or 0) are likely never synced from external API
        priority_items = frappe.db.sql("""
            SELECT name FROM `tabItem`
            WHERE company = %s
              AND (available_stock IS NULL OR available_stock = 0)
              AND disabled = 0
            ORDER BY creation DESC
            LIMIT %s
        """, (company, max_items_per_run), as_dict=True)
        priority_names = [d["name"] for d in priority_items]

        # --- Phase 2: Cursor-based items (regular sync cycle) ---
        last_item_code = _get_cv_setting(cursor_key, "") or ""
        remaining_slots = max_items_per_run - len(priority_names)

        cursor_names = []
        if remaining_slots > 0:
            filters = {"company": company}
            if last_item_code:
                filters["name"] = (">", last_item_code)

            cursor_items = frappe.get_all(
                "Item",
                filters=filters,
                fields=["name"],
                order_by="name asc",
                limit=remaining_slots
            )
            cursor_names = [d["name"] for d in cursor_items]

            if not cursor_names and not priority_names:
                # Cursor reached the end with no priority items either — reset cursor
                _set_cv_setting(cursor_key, "")
                return f"{company} Item Sync: reached end, cursor reset. Will restart next run."

            if not cursor_names:
                # Cursor reached end but we have priority items — reset for next run
                _set_cv_setting(cursor_key, "")
            elif len(cursor_names) < remaining_slots:
                # Fetched fewer items than slots = we've reached the end, reset
                _set_cv_setting(cursor_key, "")
            else:
                # Save cursor for next run
                _set_cv_setting(cursor_key, cursor_names[-1])

        # --- Merge & deduplicate (priority first, then cursor) ---
        seen = set()
        all_names = []
        for name in priority_names + cursor_names:
            if name not in seen:
                seen.add(name)
                all_names.append(name)

        if not all_names:
            return f"{company} Item Sync: No items to process."

        # --- Split into batches and enqueue ---
        batches = [all_names[i:i + batch_size] for i in range(0, len(all_names), batch_size)]

        task_id = f"{task_prefix}_{uuid.uuid4().hex[:8]}"
        total_items = len(all_names)
        total_batches = len(batches)

        frappe.cache().set_value(
            f"sync_task_{task_id}",
            {
                "task_id": task_id,
                "company": company,
                "sync_type": "item",
                "total_items": total_items,
                "total_batches": total_batches,
                "priority_count": len(priority_names),
                "cursor_count": len(cursor_names),
                "status": "running",
                "started_at": frappe.utils.now()
            },
            expires_in_sec=3600 * 2
        )

        items_before_batch = 0
        for idx, batch in enumerate(batches, start=1):
            frappe.enqueue(
                sync_fn,
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

        return {
            "success": True,
            "task_id": task_id,
            "message": (
                f"{company} Item Sync dispatched {total_batches} batches, {total_items} items "
                f"({len(priority_names)} priority + {len(cursor_names)} cursor)."
            ),
            "total_batches": total_batches,
            "total_items": total_items,
            "priority_count": len(priority_names),
            "cursor_count": len(cursor_names)
        }

    finally:
        _release_lock(lock_key)


@frappe.whitelist()
def scheduler_dispatch_cv_item_sync():
    """Scheduler-safe dispatcher for Cotton Valley item sync."""
    return _dispatch_item_sync(
        company="Cotton Valley",
        lock_key=ITEM_LOCK_KEY_CV,
        cursor_key="last_item_code_cv",
        sync_fn="cotton_valley.api.products.sync_cv_item_batch",
        task_prefix="cv_scheduler"
    )


@frappe.whitelist()
def scheduler_dispatch_udc_item_sync():
    """Scheduler-safe dispatcher for UDC item sync."""
    return _dispatch_item_sync(
        company="UDC",
        lock_key=ITEM_LOCK_KEY_UDC,
        cursor_key="last_item_code_udc",
        sync_fn="cotton_valley.api.products.sync_udc_item_batch",
        task_prefix="udc_scheduler"
    )


# ============ PRODUCT PRICES SCHEDULER ============

PRICE_LOCK_KEY_CV = "cv_sync_prices_lock"
PRICE_LOCK_KEY_UDC = "udc_sync_prices_lock"


def _dispatch_price_sync(company: str, lock_key: str, cursor_key: str, sync_fn: str, task_prefix: str):
    """
    Generic dynamic price sync dispatcher.

    Strategy (mirrors item sync):
    1. Priority: items whose Item Price was recently modified or items with
       no Item Price record yet get synced first.
    2. Cursor-based: continue from where we left off for remaining items.
    3. When cursor reaches the end, reset it so next run starts fresh.
    4. Dynamic batch count based on settings.
    """
    if not _get_cv_setting("is_enabled", 1):
        return f"{company} Price Sync is disabled."

    if not _acquire_lock(lock_key, ttl_seconds=60 * 60):
        return f"{company} Price Sync already running (lock exists)."

    try:
        batch_size = int(_get_cv_setting("batch_size", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE)
        max_batches = int(_get_cv_setting("max_batches_per_run", DEFAULT_MAX_BATCHES_PER_RUN) or DEFAULT_MAX_BATCHES_PER_RUN)
        max_items_per_run = batch_size * max_batches

        # --- Phase 1: Priority items (no Item Price records yet) ---
        priority_items = frappe.db.sql("""
            SELECT i.name
            FROM `tabItem` i
            LEFT JOIN `tabItem Price` ip ON ip.item_code = i.name
            WHERE i.company = %s
              AND i.disabled = 0
              AND ip.name IS NULL
            ORDER BY i.creation DESC
            LIMIT %s
        """, (company, max_items_per_run), as_dict=True)
        priority_names = [d["name"] for d in priority_items]

        # --- Phase 2: Cursor-based items (regular price sync cycle) ---
        last_price_item_code = _get_cv_setting(cursor_key, "") or ""
        remaining_slots = max_items_per_run - len(priority_names)

        cursor_names = []
        if remaining_slots > 0:
            filters = {"company": company}
            if last_price_item_code:
                filters["name"] = (">", last_price_item_code)

            cursor_items = frappe.get_all(
                "Item",
                filters=filters,
                fields=["name"],
                order_by="name asc",
                limit=remaining_slots
            )
            cursor_names = [d["name"] for d in cursor_items]

            if not cursor_names and not priority_names:
                _set_cv_setting(cursor_key, "")
                return f"{company} Price Sync: reached end, cursor reset. Will restart next run."

            if not cursor_names:
                _set_cv_setting(cursor_key, "")
            elif len(cursor_names) < remaining_slots:
                _set_cv_setting(cursor_key, "")
            else:
                _set_cv_setting(cursor_key, cursor_names[-1])

        # --- Merge & deduplicate (priority first, then cursor) ---
        seen = set()
        all_names = []
        for name in priority_names + cursor_names:
            if name not in seen:
                seen.add(name)
                all_names.append(name)

        if not all_names:
            return f"{company} Price Sync: No items to process."

        # --- Split into batches and enqueue ---
        batches = [all_names[i:i + batch_size] for i in range(0, len(all_names), batch_size)]

        task_id = f"{task_prefix}_{uuid.uuid4().hex[:8]}"
        total_items = len(all_names)
        total_batches = len(batches)

        frappe.cache().set_value(
            f"sync_task_{task_id}",
            {
                "task_id": task_id,
                "company": company,
                "sync_type": "price",
                "total_items": total_items,
                "total_batches": total_batches,
                "priority_count": len(priority_names),
                "cursor_count": len(cursor_names),
                "status": "running",
                "started_at": frappe.utils.now()
            },
            expires_in_sec=3600 * 2
        )

        items_before_batch = 0
        for idx, batch in enumerate(batches, start=1):
            frappe.enqueue(
                sync_fn,
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

        return {
            "success": True,
            "task_id": task_id,
            "message": (
                f"{company} Price Sync dispatched {total_batches} batches, {total_items} items "
                f"({len(priority_names)} priority + {len(cursor_names)} cursor)."
            ),
            "total_batches": total_batches,
            "total_items": total_items,
            "priority_count": len(priority_names),
            "cursor_count": len(cursor_names)
        }

    finally:
        _release_lock(lock_key)


@frappe.whitelist()
def scheduler_dispatch_cv_price_sync():
    """Scheduler-safe dispatcher for Cotton Valley price sync."""
    return _dispatch_price_sync(
        company="Cotton Valley",
        lock_key=PRICE_LOCK_KEY_CV,
        cursor_key="last_price_item_code_cv",
        sync_fn="cotton_valley.api.products.sync_cv_price_batch",
        task_prefix="cv_price_scheduler"
    )


@frappe.whitelist()
def scheduler_dispatch_udc_price_sync():
    """Scheduler-safe dispatcher for UDC price sync."""
    return _dispatch_price_sync(
        company="UDC",
        lock_key=PRICE_LOCK_KEY_UDC,
        cursor_key="last_price_item_code_udc",
        sync_fn="cotton_valley.api.products.sync_udc_price_batch",
        task_prefix="udc_price_scheduler"
    )
