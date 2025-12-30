frappe.listview_settings['Lead'] = {
    onload: function(listview) {
        // 1. Sidebar Hide (Ye aapka pehle bhi chal raha tha)
        $('.layout-side-section').hide();

        // 2. Redirect Logic
        let route = frappe.get_route();

        // CONDITION CHECK: 
        // Agar Route 'List' hai, Doctype 'Lead' hai, 
        // LEKIN teesra parameter 'Report' NAHI hai...
        if (route[0] === 'List' && route[1] === 'Lead' && route[2] !== 'Report') {
            
            // ...To ab 'Default Lead Report' par redirect karo.
            frappe.set_route('List', 'Lead', 'Report', 'Default Lead Report');
        }
    }
};