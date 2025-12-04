import frappe

@frappe.whitelist()
def get_tag_info():

  tag_list = frappe.db.get_all(
        "Tag",
        fields=["name", "description"],

  )

  for tag in tag_list:
        # Fetch data from the Child Table
        # Replace 'Tag Product' with the actual Name of your Child Table DocType
        tag.products = frappe.db.get_all(
            "Recommended Products", 
            filters={
                "parent": tag.name,       # Links child to the specific tag
                "parenttype": "Tag",      # Ensures it belongs to the Tag doctype
                "parentfield": "products" # The fieldname in the Tag form
            },
            fields=["product_name"], # Replace with your actual column names
            pluck="product_name"
        )
  return tag_list