import frappe
from frappe.utils.file_manager import save_file

@frappe.whitelist(allow_guest=True)
def guest_upload(file_name, file_data, doctype=None, docname=None, folder=None, is_private=0):
    # Decode base64 file data
    content = frappe.utils.base64.b64decode(file_data)

    # Save file
    file_doc = save_file(
        file_name,
        content,
        doctype,
        docname,
        folder or "Home/Attachments",
        is_private,
    )

    return {
        "file_url": file_doc.file_url,
        "file_name": file_doc.file_name,
        "success": True,
    }
