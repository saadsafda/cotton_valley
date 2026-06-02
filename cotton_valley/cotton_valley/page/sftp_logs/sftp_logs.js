frappe.pages["sftp-logs"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "SFTP File Logs",
		single_column: true,
	});

	page.main.html(`
		<div class="sftp-logs-container" style="padding: 15px;">
			<!-- Filters -->
			<div class="sftp-filters" style="display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; align-items: flex-end;">
				<div>
					<label class="control-label" style="font-size: 11px; color: #8d99a6;">Event Type</label>
					<select id="sftp-filter-type" class="form-control input-sm" style="width: 150px;">
						<option value="ALL">All Events</option>
						<option value="CREATE">Created</option>
						<option value="MODIFY">Modified</option>
						<option value="DELETE">Deleted</option>
						<option value="MOVED">Moved</option>
					</select>
				</div>
				<div>
					<label class="control-label" style="font-size: 11px; color: #8d99a6;">Search Filename</label>
					<input type="text" id="sftp-search" class="form-control input-sm" placeholder="Search..." style="width: 200px;">
				</div>
				<div>
					<label class="control-label" style="font-size: 11px; color: #8d99a6;">Limit</label>
					<select id="sftp-limit" class="form-control input-sm" style="width: 100px;">
						<option value="100">100</option>
						<option value="200" selected>200</option>
						<option value="500">500</option>
						<option value="1000">1000</option>
					</select>
				</div>
				<button class="btn btn-primary btn-sm" id="sftp-refresh" style="height: 30px;">
					Refresh
				</button>
			</div>

			<!-- Tabs -->
			<ul class="nav nav-tabs" style="margin-bottom: 0;">
				<li class="active"><a data-toggle="tab" href="#file-changes" style="font-weight: 500;">File Changes</a></li>
				<li><a data-toggle="tab" href="#sftp-sessions" style="font-weight: 500;">SFTP Sessions</a></li>
			</ul>

			<!-- Tab Content -->
			<div class="tab-content" style="border: 1px solid #ddd; border-top: none; border-radius: 0 0 4px 4px;">
				<!-- File Changes Tab -->
				<div id="file-changes" class="tab-pane active">
					<div id="file-changes-summary" style="padding: 12px 15px; background: #f7f8fa; border-bottom: 1px solid #eee; font-size: 13px; color: #6c7680;"></div>
					<div id="file-changes-table" style="max-height: 600px; overflow-y: auto;"></div>
				</div>

				<!-- Sessions Tab -->
				<div id="sftp-sessions" class="tab-pane">
					<div id="sessions-table" style="max-height: 600px; overflow-y: auto;"></div>
				</div>
			</div>
		</div>
	`);

	// Event handlers
	$("#sftp-refresh").on("click", () => load_all());
	$("#sftp-filter-type").on("change", () => load_file_changes());
	$("#sftp-limit").on("change", () => load_file_changes());

	let search_timeout;
	$("#sftp-search").on("input", () => {
		clearTimeout(search_timeout);
		search_timeout = setTimeout(() => load_file_changes(), 400);
	});

	function load_all() {
		load_file_changes();
		load_sessions();
	}

	function load_file_changes() {
		const filter_type = $("#sftp-filter-type").val();
		const search = $("#sftp-search").val();
		const limit = $("#sftp-limit").val();

		$("#file-changes-table").html('<div style="padding: 30px; text-align: center; color: #8d99a6;">Loading...</div>');

		frappe.call({
			method: "cotton_valley.api.sftp_logs.get_file_change_logs",
			args: { limit, filter_type, search },
			callback: function (r) {
				if (!r.message) return;
				const data = r.message;

				$("#file-changes-summary").html(
					`Showing <strong>${data.entries.length}</strong> entries` +
					(data.total ? ` out of <strong>${data.total}</strong> total log lines` : "")
				);

				if (!data.entries.length) {
					$("#file-changes-table").html(
						'<div style="padding: 40px; text-align: center; color: #8d99a6;">' +
						'<i class="fa fa-check-circle" style="font-size: 24px; margin-bottom: 8px;"></i>' +
						"<br>No file changes found</div>"
					);
					return;
				}

				let html = '<table class="table table-hover" style="margin: 0; font-size: 13px;">';
				html += `<thead style="background: #f7f8fa; position: sticky; top: 0;">
					<tr>
						<th style="width: 160px;">Time</th>
						<th style="width: 100px;">Event</th>
						<th>File Name</th>
					</tr>
				</thead><tbody>`;

				data.entries.forEach((entry) => {
					const badge = get_event_badge(entry.event);
					html += `<tr>
						<td style="white-space: nowrap; color: #6c7680;">${entry.timestamp}</td>
						<td>${badge}</td>
						<td title="${entry.full_path}" style="word-break: break-all;">${entry.filename}</td>
					</tr>`;
				});

				html += "</tbody></table>";
				$("#file-changes-table").html(html);
			},
		});
	}

	function load_sessions() {
		$("#sessions-table").html('<div style="padding: 30px; text-align: center; color: #8d99a6;">Loading...</div>');

		frappe.call({
			method: "cotton_valley.api.sftp_logs.get_sftp_session_logs",
			args: { limit: 100 },
			callback: function (r) {
				if (!r.message) return;
				const data = r.message;

				if (!data.entries.length) {
					$("#sessions-table").html(
						'<div style="padding: 40px; text-align: center; color: #8d99a6;">' +
						'<i class="fa fa-check-circle" style="font-size: 24px; margin-bottom: 8px;"></i>' +
						"<br>No SFTP sessions found</div>"
					);
					return;
				}

				let html = '<table class="table table-hover" style="margin: 0; font-size: 13px;">';
				html += `<thead style="background: #f7f8fa; position: sticky; top: 0;">
					<tr>
						<th style="width: 160px;">Time</th>
						<th style="width: 120px;">Action</th>
						<th style="width: 140px;">IP Address</th>
						<th>Details</th>
					</tr>
				</thead><tbody>`;

				data.entries.forEach((entry) => {
					const badge = get_session_badge(entry.action, entry.status);
					html += `<tr>
						<td style="white-space: nowrap; color: #6c7680;">${entry.timestamp || ""}</td>
						<td>${badge}</td>
						<td><code>${entry.ip || "-"}</code></td>
						<td style="font-size: 12px; color: #8d99a6; word-break: break-all;">${sanitize(entry.raw || "")}</td>
					</tr>`;
				});

				html += "</tbody></table>";
				$("#sessions-table").html(html);
			},
		});
	}

	function get_event_badge(event) {
		const colors = {
			UPLOAD: { bg: "#e6f7ee", color: "#28a745", icon: "fa-cloud-upload" },
			CREATE: { bg: "#e6f7ee", color: "#28a745", icon: "fa-plus" },
			MODIFIED: { bg: "#fff8e1", color: "#f39c12", icon: "fa-pencil" },
			MODIFY: { bg: "#fff8e1", color: "#f39c12", icon: "fa-pencil" },
			DELETED: { bg: "#fce4e4", color: "#e74c3c", icon: "fa-trash" },
			DELETE: { bg: "#fce4e4", color: "#e74c3c", icon: "fa-trash" },
			MOVED_FROM: { bg: "#e8eaf6", color: "#5c6bc0", icon: "fa-arrow-left" },
			MOVED_TO: { bg: "#e8eaf6", color: "#5c6bc0", icon: "fa-arrow-right" },
		};
		const c = colors[event] || { bg: "#f0f0f0", color: "#666", icon: "fa-circle" };
		return `<span style="background:${c.bg}; color:${c.color}; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 600;">
			<i class="fa ${c.icon}" style="margin-right: 3px;"></i>${event}
		</span>`;
	}

	function get_session_badge(action, status) {
		const colors = {
			success: { bg: "#e6f7ee", color: "#28a745" },
			danger: { bg: "#fce4e4", color: "#e74c3c" },
			info: { bg: "#f0f0f0", color: "#6c7680" },
		};
		const c = colors[status] || colors.info;
		return `<span style="background:${c.bg}; color:${c.color}; padding: 2px 8px; border-radius: 3px; font-size: 11px; font-weight: 600;">${action}</span>`;
	}

	function sanitize(str) {
		const div = document.createElement("div");
		div.textContent = str;
		return div.innerHTML;
	}

	// Initial load
	load_all();
};
