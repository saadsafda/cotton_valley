import frappe

@frappe.whitelist(allow_guest=True)
def get_homepage_slides():
    # Get the first (or active) Homepage Banner Setting doc
    doc = frappe.get_single("Homepage Banner Setting")

    result = {
        "content": {
            "categories_image_list": {
                "title": doc.category_title,
                "category_ids": [d["product_category"] for d in doc.homepage_categories],
                "status": doc.show_categories
            },
            "slider_products": {
                "status": True,
                "product_slider_1": {
                    "title": doc.first_title,
                    "status": True,
                    "product_ids": [row.product for row in doc.slide_1_ids]
                },
                "product_slider_2": {
                    "title": doc.sec_title,
                    "status": True,
                    "product_ids": [row.product for row in doc.slide_2_ids]
                },
                "product_slider_3": {
                    "title": doc.third_title,
                    "status": True,
                    "product_ids": [row.product for row in doc.slide_3_ids]
                },
                "product_slider_4": {
                    "title": doc.forth_title,
                    "status": True,
                    "product_ids": [row.product for row in doc.slide_4_ids]
                },
            }
        }
    }

    return result
