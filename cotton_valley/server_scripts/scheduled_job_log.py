import frappe
from frappe import _


def after_save(doc, method):
    if doc.status == "Failed":
        # Define recipients
        recipients = [
            "hammad.saleem@cottonvalley.net", 
            "sher.muhammad@cottonvalley.net", 
            "info@cottonvalley.net"
        ]
        
        # Construct the message
        subject = f"CRITICAL: Job {doc.method} Failed"
        message = f"""
        <h3>Job Failure Alert</h3>
        <p><b>Job Method:</b> {doc.scheduled_job_type}</p>
        <p><b>Error Details:</b></p>
        <pre>{doc.details}</pre>
        """
        
        # Send the email
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message
        )
