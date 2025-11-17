import frappe
import requests

def get_location_from_ip(doc, method):
    
    if not doc.ip_address:

        return

    # Use the same external API as the JavaScript
    api_url = f"http://ip-api.com/json/{doc.ip_address}"
    


    try:
        # Make the external HTTP request
        response = requests.get(api_url, timeout=5) # Set a timeout for safety
       
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        data = response.json()
        
        if data.get('status') == 'success':
            # Update the separate country and city fields
            country = data.get('country', 'N/A')
            city = data.get('city', 'N/A')
           
            if country and city:
                doc.custom_country = country
                doc.custom_city = city
               
                
                try:
                    doc.db_set()
                    frappe.log_error(
                        title='IP Location Update Success',
                        message=f"IP: {doc.ip_address}, Location: {city}, {country}"
                    )
                except Exception as db_error:
                    frappe.log_error(
                        title='IP Location DB Update Failed',
                        message=f"IP: {doc.ip_address}, Error: {db_error}"
                    )
            else:
                frappe.log_error(
                    title='IP Location API Invalid Response',
                    message=f"IP: {doc.ip_address}, Missing country or city in response"
                )

        else:
            # Log the API failure message
            frappe.log_error(
                title='IP Location API Failure',
                message=f"IP: {doc.ip_address}, API Message: {data.get('message')}"
            )
            return
            
    except requests.exceptions.RequestException as e:
        # Log any error that occurs during the HTTP request (network, timeout, status code)
        frappe.log_error(
            title='IP Location API Error',
            message=f"IP: {doc.ip_address}, Error: {e}"
        )
    except Exception as e:
        # Catch any other unexpected errors
        frappe.log_error(
            title='General IP Location Error',
            message=f"IP: {doc.ip_address}, Error: {e}"
        )
