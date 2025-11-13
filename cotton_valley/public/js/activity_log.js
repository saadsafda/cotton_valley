
frappe.ui.form.on('Activity Log', {
    refresh: function (frm) {
        if (frm.doc.ip_address) {
            callExternalApi(frm);
        }
    }
});

function callExternalApi(frm) {
    const apiUrl = `http://ip-api.com/json/${frm.doc.ip_address}`;

    fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                const location = `${data.country || 'Unknown Country'}, ${data.city || 'Unknown City'}`;

                const htmlContent = `
                    <div style="
                        display: flex;
                        align-items: center;
                        padding: 8px;
                        border: 1px solid #C4D7ED;
                        border-radius: 6px;
                        background-color: #F8F9FE;
                        font-family: Arial, sans-serif;
                        gap: 6px;
                        font-size: 13px;
                    ">
                        <span style="color: #007BFF; font-weight: 600;">📍 Location:</span>
                        <span style="color: #343A40;">${location}</span>
                    </div>
                `;

                // Display nicely in the custom field
                if (frm.fields_dict.custom_country__city) {
                    frm.fields_dict.custom_country__city.$wrapper.html(htmlContent);
                }

                frm.set_value('custom_country__city', location);
                console.log(`Location found: ${location}`);
            } else {
                console.error(`API reported failure: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('There was a problem with the fetch operation:', error);
        });
}
