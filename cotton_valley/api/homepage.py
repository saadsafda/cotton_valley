import frappe # type: ignore

@frappe.whitelist(allow_guest=True)
def get_homepage_slides(company="Cotton Valley"):
    # Get the first (or active) Homepage Banner Setting doc
    doctype = "Homepage Banner Setting"
    company = "Cotton Valley" if not company or company == "null" else company
    if company != "Cotton Valley":
        doctype = f"UDC Home Page"
    doc = frappe.get_single(doctype)
    first_row_product_ids = [row.product for row in sorted(doc.product_row_1, key=lambda x: x.idx)]
    sec_row_product_ids = [row.product for row in sorted(doc.product_row_2, key=lambda x: x.idx)]
    first_slide_product_ids = [row.product for row in sorted(doc.slide_1_ids, key=lambda x: x.idx)]
    sec_slide_product_ids = [row.product for row in sorted(doc.slide_2_ids, key=lambda x: x.idx)]
    third_slide_product_ids = [row.product for row in sorted(doc.slide_3_ids, key=lambda x: x.idx)]
    fourth_slide_product_ids = [row.product for row in sorted(doc.slide_4_ids, key=lambda x: x.idx)]
    all_product_ids = list(set(
        fourth_slide_product_ids +
        third_slide_product_ids +
        sec_slide_product_ids +
        first_slide_product_ids +
        sec_row_product_ids +
        first_row_product_ids
    ))

    home_banners = []
    for row in sorted(doc.home_banners, key=lambda x: x.idx):
        home_banners.append({
            "image_url": row.image,
            "redirect_link": {
                "link": row.link,
                "link_type": get_subbanner_link_type(row.link_type),
            }
        })

    promotion_link = ""
    if doc.link_type == "External Url":
        promotion_link = doc.external_url
    elif doc.link_type == "Category":
        promotion_link = doc.category
    else:
        promotion_link = doc.product

    subPromotion_link = ""
    if doc.sublink_type == "External Url":
        subPromotion_link = doc.subexternal_url
    elif doc.sublink_type == "Category":
        subPromotion_link = doc.subpromotion_category
    else:
        subPromotion_link = doc.sub_product

    result = {
        "content": {
            "home_banner": {
                "status": True,
                "main_banner": home_banners,
                "sub_banner_1": {
                    "image_url": doc.right_top,
                    "redirect_link": {
                        "link": doc.right_top_banner_link,
                        "link_type": get_subbanner_link_type(doc.right_top_banner_link_type),
                    }
                },
                "sub_banner_2": {
                    "image_url": doc.right_bottom,
                    "redirect_link": {
                        "link": doc.right_bottom_banner_link,
                        "link_type": get_subbanner_link_type(doc.right_bottom_banner_link_type),
                    }
                }
            },
            "categories_image_list": {
                "title": doc.category_title,
                "category_ids": [d.product_category for d in sorted(doc.homepage_categories, key=lambda x: x.idx)],
                "status": doc.show_categories
            },
            "products_list_1": {
                "title": doc.title,
                "description": doc.description,
                "product_ids": first_row_product_ids,
                "status": doc.show_products
            },
            "products_list_2": {
                "product_ids": sec_row_product_ids,
                "status": len(doc.product_row_2) > 0
            },
            "promotion_banner": {
                "status": doc.show_promotion_baners,
                "banner_1": {
                    "image_url": doc.promotion_banner,
                    "redirect_link": {
                        "link_type": get_subbanner_link_type(doc.link_type),
                        "link": promotion_link
                    }
                },
                "banner_2": {
                    "image_url": doc.promotion_subbanner,
                    "redirect_link": {
                        "link_type": get_subbanner_link_type(doc.sublink_type),
                        "link": subPromotion_link
                    }
                }
            },
            "slider_products": {
                "status": True,
                "product_slider_1": {
                    "title": doc.first_title,
                    "status": True,
                    "product_ids": first_slide_product_ids
                },
                "product_slider_2": {
                    "title": doc.sec_title,
                    "status": True,
                    "product_ids": sec_slide_product_ids
                },
                "product_slider_3": {
                    "title": doc.third_title,
                    "status": True,
                    "product_ids": third_slide_product_ids
                },
                "product_slider_4": {
                    "title": doc.forth_title,
                    "status": True,
                    "product_ids": fourth_slide_product_ids
                },
            },
            "news_letter": {
                "title": doc.news_title,
                "sub_title": doc.sub_title,
                "image_url": doc.newsletter_background,
                "status": doc.show_newsletter
            },
            "products_ids": all_product_ids
        }
    }

    return result


def get_subbanner_link_type(banner_settings):
    if banner_settings == "Product" or banner_settings == "Item":
        return "product"
    elif banner_settings == "Category" or banner_settings == "Product Category":
        return "collection"
    elif banner_settings == "External Url":
        return "external_url"
    else:
        return ""
