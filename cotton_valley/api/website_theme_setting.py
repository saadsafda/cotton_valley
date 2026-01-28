import frappe # type: ignore
from cotton_valley.api.common import get_customer_from_token, check_customer_token
from cotton_valley.api.brand import get_brands

@frappe.whitelist(allow_guest=True)
def settings(company=None):
    company = "Cotton Valley" if not company or company == "null" else company
    doctype = "Website Theme Settings"
    if company == "UDC":
        doctype = f"UDC {doctype}"
    settings = frappe.get_single(doctype)
    mode_of_payment = frappe.get_all("Mode of Payment", filters={"enabled": 1}, fields=["name", "enabled as status"])
    if check_customer_token():
        current_customer = get_customer_from_token()
        if current_customer:
            customer_payment = frappe.db.get_value("customer", current_customer, "udc_mode_of_payment") if company == "UDC" else frappe.db.get_value(
                "Customer", current_customer, "mode_of_payment"
            )
            if customer_payment:
                mode_of_payment = frappe.get_all(
                    "Mode of Payment",
                    filters={"name": customer_payment, "enabled": 1},
                    fields=["name", "enabled as status"]
                )

    data = {
        "values": {
            "general": {
            "default_currency_id": 1,
            "default_currency": {
                "id": 1,
                "code": "USD",
                "symbol": "$",
                "no_of_decimal": 2,
                "exchange_rate": "1.00",
                "symbol_position": "before_price",
                "thousands_separator": "comma",
                "decimal_separator": "comma",
                "system_reserve": "1",
                "status": 1,
            },
            "min_order_amount": settings.min_order_amount,
            "min_order_free_shipping": settings.min_order_free_shipping,
            },
            "wallet_points": {
            "point_currency_ratio": 30
            },
            "delivery": {
            "default_delivery": 1,
            "default": {
                "title": "Standard Delivery",
                "description": "Approx 5 to 7 Days"
            },
            "same_day_delivery": True,
            "same_day": {
                "title": "Express Delivery",
                "description": "Schedule"
            },
            "same_day_intervals": [
                {
                "title": "Morning",
                "description": "8.00 AM - 12.00 AM"
                },
                {
                "title": "Noon",
                "description": "12.00 PM - 2.00 PM"
                },
                {
                "title": "Afternoon",
                "description": "02.00 PM - 05.00 PM"
                },
                {
                "title": "Evening",
                "description": "05.00 PM - 08.00 PM"
                }
            ]
            },
            "maintenance": {
            "title": "We'll be back Soon..",
            "maintenance_mode": False,
            "maintenance_image_id": 6,
            "description": "We are busy to updating our store for you.",
            "maintenance_image": {
                "id": 6,
                "collection_name": "attachment",
                "name": "maintainance",
                "file_name": "maintainance.jpg",
                "mime_type": "image/jpeg",
                "disk": "public",
                "conversions_disk": "public",
                "size": "111275",
                "created_by_id": "1",
                "created_at": "2023-08-24T08:16:03.000000Z",
                "updated_at": "2023-08-24T08:16:03.000000Z",
                "original_url": "https://react.pixelstrap.net/fastkart/assets/maintainance.jpg"
            }
            },
            "payment_methods": mode_of_payment
        }
        }
    return data

@frappe.whitelist(allow_guest=True)
def get_website_theme_settings(company=None):
    company = "Cotton Valley" if not company or company == "null" else company
    doctype = "Website Theme Settings"
    if company == "UDC":
        doctype = f"UDC {doctype}"
    settings = frappe.get_single(doctype)
    all_category_ids = frappe.get_all("Product Category", filters=[["company", "=", company]], pluck="name")
    all_event_pages = frappe.get_all("Event Page", filters=[["internal_page", "=", 0], ["company", "=", company]], pluck="name")
    brand_list = get_brands(company=company)

    result = {
        "id": 1,
        "options": {
            "general": {
                "site_title": settings.site_title,
                "site_tagline": settings.site_tagline,
                "cart_style": "cart_sidebar",
                "back_to_top_enable": True,
                "language_direction": "ltr",
                "primary_color": settings.primary_color,
                "mode": "light"
            },
            "logo": {
                "favicon_icon": get_file(settings.faveicon),
                "header_logo": get_file(settings.header_logo),
                "footer_logo": get_file(settings.footer_logo),
            },
            "header": {
                "sticky_header_enable": True,
                "header_options": "basic_header",
                "page_top_bar_enable": True,
                "top_bar_content": [
                    {
                        "content": settings.top_bar_content
                    }
                ],
                "company_name": settings.other_company_name,
                "company_link": settings.other_company_link,
                "page_top_bar_dark": False,
                "support_number": settings.support_number,
                "today_deals": [row.product for row in settings.products],
                "brands": brand_list.get("data", []),
                "category_ids": all_category_ids,
                "event_pages": all_event_pages
            },
            "footer": {
                "footer_style": "light_mode",
                "footer_copyright": settings.footer_copyright,
                "copyright_content": settings.copyright_content,
                "footer_about": settings.footer_about,
                "about_address": settings.about_address,
                "about_email": settings.about_email,
                "footer_categories": [row.product_category for row in settings.footer_categories],
                "help_center": [
                    {
                    "label": "My Account",
                    "link": "account/dashboard"
                    },
                    {
                    "label": "My Orders",
                    "link": "account/order"
                    },
                    {
                    "label": "Privacy Policy",
                    "link": "privacy-policy"
                    },
                    {
                    "label": "Shipping & Returns",
                    "link": "shipping-and-returns"
                    },
                    {
                    "label": "Contact Us",
                    "link": "contact-us"
                    }
                ],
                "useful_link": [
                    {
                    "label": "Home",
                    "link": "home"
                    },
                    {
                    "label": "Collections",
                    "link": "collections"
                    },
                    {
                    "label": "About",
                    "link": "about-us"
                    },
                    {
                    "label": "Search",
                    "link": "search"
                    },
                    {
                    "label": "Terms & Conditions",
                    "link": "terms-and-conditions"
                    }
                ],
                "support_number": settings.support_number,
                "support_email": settings.support_email,
                # "play_store_url": settings.play_store_url,
                # "app_store_url": settings.app_store_url,
                "social_media_enable": settings.social_media_enable,
                "facebook": settings.facebook_url,
                "instagram": settings.instagram_url,
                "twitter": settings.twitter_url,
                "pinterest": settings.pinterest_url
            },
            "collection": {
                "collection_layout": "collection_category_slider",
                "collection_banner_image_url": settings.collection_banner_image,
            },
            "product": {
                "product_layout": "product_thumbnail",
                "is_trending_product": True,
                "banner_enable": True,
                "banner_image_url": "https://react.pixelstrap.net/fastkart/assets/banner-1.png",
                "safe_checkout": True,
                "safe_checkout_image": "https://react.pixelstrap.net/fastkart/assets/payments.png",
                "secure_checkout": True,
                "secure_checkout_image": "https://react.pixelstrap.net/fastkart/assets/secure_payments.png",
                "encourage_order": True,
                "encourage_max_order_count": 50,
                "encourage_view": True,
                "encourage_max_view_count": 50,
                "sticky_checkout": True,
                "sticky_product": True,
                "social_share": True,
                "shipping_and_return": "<p>Shipping and Returns are integral parts of your shopping experience, and we aim to make them as smooth as possible. We prioritize efficient shipping, striving to deliver your orders promptly within the estimated delivery window, typically ranging from 5 to 7 days. We understand that sometimes your purchase may not meet your expectations, so we offer a straightforward return policy. If you find yourself unsatisfied with your order, eligible items can be returned within 30 days of purchase, ensuring you have ample time to make a decision. Our commitment is to ensure your satisfaction and convenience throughout your shopping journey with us, and we're here to assist you every step of the way.</p><p><strong>Our Shipping Commitment:</strong></p><ul><li>Timely and reliable delivery within 5-7 days.</li><li>Real-time tracking for your orders.</li><li>Exceptional packaging to ensure your items arrive in perfect condition.</li></ul><p>&nbsp;</p><p><strong>Our Hassle-Free Returns:</strong></p><ul><li>Eligible items can be returned within 30 days.</li><li>Easy return initiation through our website.</li><li>Prompt processing of returns for a hassle-free experience.</li></ul><p>&nbsp;</p><p>We understand that your shopping needs may vary, and we are here to accommodate them while providing exceptional service.</p>"
            },
            "blog": {
                "blog_style": "grid_view",
                "blog_sidebar_type": "left_sidebar",
                "blog_author_enable": True,
                "read_more_enable": True
            },
            "seller": {
            "about": {
                "status": True,
                "title": "Become a seller on Fastkart...",
                "description": "Ready to showcase your products to the world? Join our dynamic marketplace and become a seller at our thriving multipurpose store. With a diverse customer base and a wide range of categories including groceries, fashion, electronics, and more, you'll have the perfect platform to reach a vast audience.\n\nAs a seller, you'll benefit from our user-friendly interface, seamless payment processing, and dedicated support to ensure your products shine. Whether you're a local artisan or a growing brand, our store provides the visibility and tools you need to succeed.\n\nTap into our established customer traffic, set up your shop with ease, and let your products take center stage. Join us in creating a shopping experience that caters to every need and taste. Your journey to success starts here – become a seller at our multipurpose store today!",
                "image_url": "https://react.pixelstrap.net/fastkart/assets/banner-2.jpg"
            },
            "services": { 
                "status": True,
                "service_1": {
                "title": "Lowest Cost",
                "description": "Unlock quality at the lowest cost, exceeding expectations.",
                "image_url": "https://react.pixelstrap.net/fastkart/assets/service.png"
                },
                "service_2": {
                "title": "Lowest Cost",
                "description": "Unlock quality at the lowest cost, exceeding expectations.",
                "image_url": "https://react.pixelstrap.net/fastkart/assets/service-2.png"
                },
                "service_3": {
                "title": "Dedicated Pickup",
                "description": "Enjoy the convenience of dedicated pickup services for your orders.",
                "image_url": "https://react.pixelstrap.net/fastkart/assets/service-3.png"
                },
                "service_4": {
                "title": "Most Approachable",
                "description": "We take pride in being the most approachable choice for your needs.",
                "image_url": "https://react.pixelstrap.net/fastkart/assets/service-4.png"
                }
            },
            "steps": {
                "status": True,
                "title": "Doing Business on Fastkart is really easy",
                "step_1": {
                "title": "List Your Products & Get Support Provider",
                "description": "Elevate your business by listing your products with us. Experience dedicated support services for your growth."
                },
                "step_2": {
                "title": "Receive orders & Schedule a pickup",
                "description": "Effortlessly receive orders and schedule pickups for ultimate convenience. Your business is simplified."
                },
                "step_3": {
                "title": "Receive quick payment & grow your business",
                "description": "Receive swift payments, fuel the growth of your business seamlessly, and watch your ventures thrive."
                }
            },
            "start_selling": {
                "status": True,
                "title": "Start Selling",
                "description": "Fastkart marketplace is India's leading platform for selling online. Be it a manufacturer, vendor or supplier, simply sell your products online on Fastkart and become a top ecommerce player with minimum investment. Through a team of experts offering exclusive seller workshops, training, seller support and convenient seller portal, Fastkart focuses on educating and empowering sellers across India. Selling on Fastkart.com is easy and absolutely free. All you need is to register, list your catalogue and start selling your products."
            },
            "store_layout": "basic_store",
            "store_details": "basic_store_details"
            },
            "newsletter_modal": {
                "image": get_file(settings.half_banner),
                "description": settings.description,
            },
            "contact_us": {
            "contact_image_url": "https://react.pixelstrap.net/fastkart/assets/contact-us.png",
            "detail_1": {
                "label": "Phone",
                "icon": "ri-phone-line",
                "text": "(+1) 618 190 496"
            },
            "detail_2": {
                "label": "Email",
                "icon": "ri-mail-line",
                "text": "support@fastkart.com"
            },
            "detail_3": {
                "label": "London Office",
                "icon": "ri-map-pin-line",
                "text": "Cruce Casa de Postas 29"
            },
            "detail_4": {
                "label": "Bournemouth Office",
                "icon": "ri-building-line",
                "text": "Visitación de la Encina 22"
            }
            },
            "error_page": {
                "error_page_content": settings.error_page_content,
                "back_button_enable": settings.back_button_enable,
                "back_button_text": settings.back_button_text
            },
            "seo": {
                "meta_tags": settings.meta_tags,
                "meta_title": settings.meta_title,
                "meta_description": settings.meta_description,
                "og_title": settings.og_title,
                "og_description": settings.og_description,
                "og_image": get_file(settings.og_image),
            }
        }
        }
    
    return result
    

def get_file(file_url):
    """return file object with meta if available"""
    if not file_url:
        return {
            "id": "",
            "file_name": "",
            "mime_type": "",
            "original_url": "",
        }
    
    if file_url.startswith("http"):
        return {
            "id": file_url,
            "file_name": file_url,
            "mime_type": "internet",
            "original_url": file_url or "",
        }
    
    return {
        "id": file_url,
        "file_name": file_url,
        "mime_type": "internal",
        "original_url": frappe.utils.get_url(file_url) or "",
    }

def get_categories_from_string(category_string):
    """
    Convert a comma-separated category string into a clean list of categories.
    
    Args:
        category_string (str): e.g. "Shirts, Pants, Shoes"
    
    Returns:
        list: e.g. ["Shirts", "Pants", "Shoes"]
    """
    if not category_string:
        return []
    
    return [cat.strip() for cat in category_string.split(",") if cat.strip()]


