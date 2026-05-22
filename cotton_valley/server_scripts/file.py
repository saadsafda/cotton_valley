import os
import frappe

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".avif"}


def _is_image(value: str | None) -> bool:
    if not value:
        return False
    _, ext = os.path.splitext(value.lower().strip())
    return ext in IMAGE_EXTENSIONS


def _cleanup_same_name_item_files(item_code: str, file_name: str) -> tuple[int, str | None]:
    """Keep the newest File row for same Item+file_name, delete older duplicates."""
    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Item",
            "attached_to_name": item_code,
            "file_name": file_name,
        },
        fields=["name", "file_url", "creation"],
        order_by="creation desc, name desc",
    )

    if not files:
        return 0, None

    newest = files[0]
    deleted = 0

    for old in files[1:]:
        try:
            # Keep filesystem file if shared elsewhere; remove duplicate File rows.
            frappe.delete_doc("File", old.name, ignore_permissions=True)
            deleted += 1
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"File duplicate cleanup failed: {old.name}")

    return deleted, newest.get("file_url")


def after_save(doc, method=None):
    """Ensure latest uploaded image is used for Item and prevent duplicate File rows."""
    if doc.attached_to_doctype != "Item" or not doc.attached_to_name:
        return

    if not (_is_image(doc.file_name) or _is_image(doc.file_url)):
        return

    deleted, newest_file_url = _cleanup_same_name_item_files(doc.attached_to_name, doc.file_name)

    # Always point Item image to latest same-name file for predictable behavior.
    if newest_file_url:
        frappe.db.set_value("Item", doc.attached_to_name, "image", newest_file_url, update_modified=False)

    if deleted:
        frappe.db.commit()


def cleanup_existing_item_file_duplicates() -> dict:
    """One-time maintenance: remove duplicate Item file rows by file_name and fix item.image."""
    groups = frappe.db.sql(
        """
        SELECT attached_to_name, file_name
        FROM `tabFile`
        WHERE attached_to_doctype='Item' AND IFNULL(file_name,'')<>''
        GROUP BY attached_to_name, file_name
        HAVING COUNT(*) > 1
        """,
        as_dict=True,
    )

    deleted_total = 0
    updated_items = 0

    for g in groups:
        item_code = g.attached_to_name
        file_name = g.file_name

        files = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "Item",
                "attached_to_name": item_code,
                "file_name": file_name,
            },
            fields=["name", "file_url", "creation"],
            order_by="creation desc, name desc",
        )

        if not files:
            continue

        newest = files[0]
        older = files[1:]

        if older and newest.get("file_url"):
            older_urls = {r.get("file_url") for r in older if r.get("file_url")}
            current_image = frappe.db.get_value("Item", item_code, "image")
            if current_image in older_urls:
                frappe.db.set_value("Item", item_code, "image", newest.file_url, update_modified=False)
                updated_items += 1

        for old in older:
            try:
                frappe.delete_doc("File", old.name, ignore_permissions=True)
                deleted_total += 1
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Bulk file duplicate cleanup failed: {old.name}"
                )

    frappe.db.commit()
    return {
        "duplicate_groups": len(groups),
        "deleted_rows": deleted_total,
        "updated_items": updated_items,
    }
