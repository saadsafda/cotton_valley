import frappe

def split_name_ext(fname: str):
    fname = (fname or "").strip()
    if "." in fname:
        base, ext = fname.rsplit(".", 1)   # split from right only once
        return base, "." + ext.lower()
    return fname, ""  # no extension

def normalize_base(fname: str, cut_last: int = 5):
    base, ext = split_name_ext(fname)
    if len(base) > cut_last:
        base = base[:-cut_last]
    return base, ext

def after_save(doc, method):

    current_base, current_ext = normalize_base(doc.file_name, cut_last=5)
    
    files = frappe.get_all(
        "File",
        filters={
            "file_name": ["in", [doc.file_name, current_base]]
        },
        fields=["name", "file_url", "file_name", "creation"],
        order_by="creation desc"
    )

    seen = set()
    for f in files:
        key = (f.file_url, current_base)
        if key in seen:
            frappe.delete_doc("File", f.name, ignore_permissions=True)
        else:
            seen.add(key)
