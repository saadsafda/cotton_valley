frappe.listview_settings['Item'] = {
    onload(listview) {
        console.log("item list js loaded", frappe.get_route());

        if (frappe.get_route()[2] === 'Report' && !frappe.get_route()[3]) {
            frappe.set_route('item', 'view', 'report', 'Product Report');
        }
        // Hide sidebar
        $('.layout-side-section').hide();
        // Add "Product" button
        listview.page.add_inner_button('Customer', () => {
            frappe.set_route("List", "Customer");  // Opens Product (Item) list
        });

        // Add "Sales Reps" button
        listview.page.add_inner_button('Sales Reps', () => {
            frappe.set_route("List", "Sales Person");  // Opens Sales Reps list
        });
    }
};

