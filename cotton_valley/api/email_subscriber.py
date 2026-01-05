import frappe


@frappe.whitelist(allow_guest=True)
def subscribe_email(email, company=""):
    """Subscribe an email to the Email Subscriber list for a given company."""
    company = "Cotton Valley" if not company or company == "null" else company
    subscriber_list_name = f"{company} Email Group"

    email_exiests = frappe.get_all("Email Group Member", filters={"email": email})
    # Check if the Email Subscriber List exists; if not, create it
    if len(email_exiests) == 0:
        subscriber_list = frappe.get_doc({
            "doctype": "Email Group Member",
            "email_group": subscriber_list_name,
            "email": email
        })
        subscriber_list.insert(ignore_permissions=True)

        return {"message": "Subscription successful."}
    else:
        return {"message": "Email is already subscribed."}