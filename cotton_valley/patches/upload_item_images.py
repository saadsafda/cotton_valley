import frappe
import pandas as pd
import requests
import os

def execute():
    # Load Excel (Option 1: one row per image)
    df = pd.read_csv("product.csv")

    for _, row in df.iterrows():
        print(row)
        item_code = row["Product Code"]
        image_url = row["Image"]

        if pd.notna(image_url):
            file_url = upload_image(item_code, image_url)
            if file_url:
                add_to_child_table(item_code, file_url)


def upload_image(item_code, image_url):
    try:
        file_name = os.path.basename(image_url)
        existing = frappe.db.get_value("File", {"file_name": file_name}, "file_url")
        if existing:
            return existing 
        response = requests.get(image_url, timeout=10)
        if response.status_code == 200:
            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": file_name,
                "is_private": 0,
                "attached_to_doctype": "Item",
                "attached_to_name": item_code,
                "content": response.content
            })
            file_doc.save()
            frappe.db.commit()
            return file_doc.file_url
        else:
            print(f"❌ Failed {image_url} for {item_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error uploading {image_url} for {item_code}: {e}")
        return None


def add_to_child_table(item_code, file_url):
    try:
        item = frappe.get_doc("Item", item_code)
        item.append("custom_product_images", {
            "list_index": len(item.custom_product_images) + 1,
            "image": file_url   # fieldname in Item Image child table
        })
        item.save()
        frappe.db.commit()
        print(f"✅ Added image {file_url} to {item_code}")
    except Exception as e:
        print(f"⚠️ Error updating child table for {item_code}: {e}")
