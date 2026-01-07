import frappe


@frappe.whitelist(allow_guest=True)
def get_brands(company=None):
    try:
        company = None if not company or company == "null" else company
        filters = {}
        if company:
            filters["company"] = company

        brands = frappe.get_all(
            "Brand",
            filters=filters,
            fields=["name", "image", "company"],
            order_by="name asc"
        )
        for brand in brands:
            brand["image"] = frappe.utils.get_full_url(brand["image"]) if brand["image"] else ""

        return {"status": "success", "data": brands}
    except Exception as e:
        return {"status": "error", "message": str(e)}