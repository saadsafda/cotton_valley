"""
Drafts a rep saves in the mobile app are stored as draft Sales Orders, marked
with `custom_app_draft_id`.

A customer's shopping cart is also a draft Sales Order, and the cart code finds
it as "the customer's draft for this company". Without excluding app drafts,
the cart would pick one up (and overwrite or delete it), a rep's several drafts
for one customer would collapse into one, and the abandoned-cart email would go
to the customer for a draft their rep saved. Every cart lookup must therefore
filter with `cart_filters` / `NOT_APP_DRAFT`.
"""

NOT_APP_DRAFT = ["is", "not set"]


def cart_filters(customer_id, company):
    """Filters that find a customer's shopping cart and never an app draft."""
    return {
        "customer": customer_id,
        "docstatus": 0,
        "company": company,
        "custom_app_draft_id": NOT_APP_DRAFT,
    }
