import frappe
import os
import re
from datetime import datetime


@frappe.whitelist()
def get_file_change_logs(limit=200, filter_type=None, search=None):
    """Read SFTP file change logs. Admin only."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Not permitted", frappe.PermissionError)

    log_file = "/var/log/sftp-file-changes.log"
    entries = []

    if not os.path.exists(log_file):
        return {"entries": [], "total": 0, "message": "No log file found"}

    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
    except PermissionError:
        return {"entries": [], "total": 0, "message": "Permission denied reading log file"}

    for line in reversed(lines):
        line = line.strip()
        if not line or "[MONITOR]" in line or "Setting up watches" in line or "Watches established" in line:
            continue

        # Parse: 2026-05-23 11:54:13 [CREATE] /home/.../files/filename.txt
        match = re.match(
            r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+(?:,\w+)*)\] (.+)", line
        )
        if match:
            timestamp = match.group(1)
            event_type = match.group(2)
            file_path = match.group(3)

            # Extract just the filename from the full path
            filename = os.path.basename(file_path)

            # Apply filters
            if filter_type and filter_type != "ALL" and filter_type not in event_type:
                continue
            if search and search.lower() not in filename.lower():
                continue

            entries.append({
                "timestamp": timestamp,
                "event": event_type,
                "filename": filename,
                "full_path": file_path,
            })

            if len(entries) >= int(limit):
                break

    return {"entries": entries, "total": len(lines)}


@frappe.whitelist()
def get_sftp_session_logs(limit=100):
    """Read SFTP session/auth logs. Admin only."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Not permitted", frappe.PermissionError)

    log_file = "/var/log/auth.log"
    entries = []

    if not os.path.exists(log_file):
        return {"entries": [], "message": "No auth log found"}

    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
    except PermissionError:
        return {"entries": [], "message": "Permission denied reading log file"}

    for line in reversed(lines):
        if "sftpfiles" not in line:
            continue

        line = line.strip()
        entry = {"raw": line}

        # Extract IP address
        ip_match = re.search(r"from (\d+\.\d+\.\d+\.\d+)", line)
        if ip_match:
            entry["ip"] = ip_match.group(1)

        # Determine action
        if "Accepted publickey" in line:
            entry["action"] = "LOGIN"
            entry["status"] = "success"
        elif "session opened" in line:
            entry["action"] = "SESSION_START"
            entry["status"] = "success"
        elif "session closed" in line:
            entry["action"] = "SESSION_END"
            entry["status"] = "info"
        elif "not allowed" in line or "denied" in line:
            entry["action"] = "BLOCKED"
            entry["status"] = "danger"
        else:
            entry["action"] = "OTHER"
            entry["status"] = "info"

        # Extract timestamp
        ts_match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", line)
        if ts_match:
            entry["timestamp"] = ts_match.group(1).replace("T", " ")

        entries.append(entry)

        if len(entries) >= int(limit):
            break

    return {"entries": entries}
