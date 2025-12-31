import frappe
import requests

def get_location_from_ip(doc, method):
    # Field name check: Standard 'ip_address' ya Custom 'custom_ip_address'
    # Jo field aapke Customer form me hai, wo pehle priority lega
    ip_addr = getattr(doc, 'ip_address', None) or getattr(doc, 'custom_ip_address', None)
    
    # Agar IP nahi hai to function yahin rok dein
    if not ip_addr:
        return

    if doc.get('custom_country') and doc.get('custom_city'):
        return

    # API URL setup
    api_url = f"http://ip-api.com/json/{ip_addr}"

    try:
        # Request bhejein (Timeout 5 seconds rakha hai taake system hang na ho)
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get('status') == 'success':
            country = data.get('country', '')
            city = data.get('city', '')
            lat = data.get('lat')
            lon = data.get('lon')

            # --- Values Set Karna ---
            
            # Country aur City set karein
            if country:
                doc.custom_country = country
            if city:
                doc.custom_city = city
            
            # Lat & Long set karein (Format: "Lat, Long")
            # Check kar lein ki aapke Doctype me field ka naam 'custom_lat_long' hai ya kuch aur
            if lat and lon:
                if hasattr(doc, 'custom_lat_long'):
                    doc.custom_lat_long = f"{lat}, {lon}"
                elif hasattr(doc, 'lat_long'):
                    doc.lat_long = f"{lat}, {lon}"
                
                # Agar aapka field 'custom_latitude' aur 'custom_longitude' alag alag hain:
                if hasattr(doc, 'custom_latitude'):
                    doc.custom_latitude = lat
                if hasattr(doc, 'custom_longitude'):
                    doc.custom_longitude = lon

        else:
            # Agar API fail kare lekin crash na ho (jaise invalid IP)
            frappe.log_error(
                message=f"Message: {data.get('message')}",
                title=f"Customer IP Lookup Failed: {ip_addr}"
            )

    except Exception as e:
        # Koi technical error aaye to log karein
        frappe.log_error(
            message=frappe.get_traceback(),
            title=f"Customer IP API Error: {ip_addr}"
        )