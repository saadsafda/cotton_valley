app_name = "cotton_valley"
app_title = "Cotton Valley"
app_publisher = "Saad"
app_description = "This app for custom changes for cotton valley"
app_email = "muhammadsaadsafdar2005@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

fixtures = [
	{
		"doctype":"Custom Field",
		"filters":[
			[
				"module", "=", "Cotton Valley"
			]
		]
	},
    {
		"doctype":"Property Setter",
		"filters":[
			[
				"module", "=", "Cotton Valley"
			]
		]
	},
    {
		"doctype":"Client Script",
		"filters":[
			[
				"module", "=", "Cotton Valley"
			]
		]
	},
    {
		"doctype":"Report",
		"filters":[
			[
				"module", "=", "Cotton Valley"
			]
		]
	},
]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "cotton_valley",
# 		"logo": "/assets/cotton_valley/logo.png",
# 		"title": "Cotton Valley",
# 		"route": "/cotton_valley",
# 		"has_permission": "cotton_valley.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/cotton_valley/css/cotton_valley.css"
# app_include_js = "/assets/cotton_valley/js/cotton_valley.js"
app_include_js = "/assets/cotton_valley/js/workspace_filter.js"

# include js, css files in header of web template
# web_include_css = "/assets/cotton_valley/css/cotton_valley.css"
# web_include_js = "/assets/cotton_valley/js/cotton_valley.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "cotton_valley/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Item" : "public/js/item.js", 
    "Customer" : "public/js/customer.js",
    "Sales Order" : "public/js/sales_order.js",
    "Sales Invoice" : "public/js/sales_invoice.js",
	"Activity Log": "public/js/activity_log.js",
	"Tag": "public/js/tag.js"
}
doctype_list_js = {"Customer" : "public/js/customer_list.js", "Item" : "public/js/item_list.js", "Sales Order" : "public/js/sales_order_list.js", "Lead": "public/js/lead_list.js"}
# doctype_image_js = {"Item" : "public/js/item_image.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "cotton_valley/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "cotton_valley.utils.jinja_methods",
# 	"filters": "cotton_valley.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "cotton_valley.install.before_install"
# after_install = "cotton_valley.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "cotton_valley.uninstall.before_uninstall"
# after_uninstall = "cotton_valley.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "cotton_valley.utils.before_app_install"
# after_app_install = "cotton_valley.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "cotton_valley.utils.before_app_uninstall"
# after_app_uninstall = "cotton_valley.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "cotton_valley.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Item": "cotton_valley.overrides.item.CustomItem"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	# "Stock Ledger Entry": {
	# 	"on_submit": "cotton_valley.server_scripts.stock_ledger.on_submit",
	# 	# "on_cancel": "method",
	# 	# "on_trash": "method"
	# },
    "Sales Order": {
		"on_submit": [
            "cotton_valley.server_scripts.sales_order.update_customer_order_summary",
            # "cotton_valley.server_scripts.sales_order.notify_customer_on_status_change"
        ],
		"on_update_after_submit": "cotton_valley.server_scripts.sales_order.notify_customer_on_status_change",
        "before_cancel": "cotton_valley.server_scripts.sales_order.order_cancel",
        "on_cancel": "cotton_valley.server_scripts.sales_order.increase_stock_on_cancel",
	},
	"Activity Log": {
        "before_save": "cotton_valley.server_scripts.activity_log.get_location_from_ip"
    },
    "Customer": {
        "before_save": "cotton_valley.server_scripts.customer.get_location_from_ip"
    },
	"Item": {
		"validate": "cotton_valley.server_scripts.item.validate",
		"before_save": "cotton_valley.server_scripts.item.before_save"
	},
    "Scheduled Job Log": {
		"after_save": "cotton_valley.server_scripts.scheduled_job_log.after_save"
	},
    "Item Price": {
        "before_save": "cotton_valley.server_scripts.item_price.before_save"
    },
    "File": {
		"after_insert": "cotton_valley.server_scripts.file.after_save",
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"all": [
		"cotton_valley.api.customer.deactivate_inactive_customers"
	],
	"cron": {
		"0 14 * * *": [
			# "cotton_valley.scheduler.product_scheduler.scheduler_dispatch_cv_price_sync",
			# "cotton_valley.scheduler.product_scheduler.scheduler_dispatch_udc_price_sync",
			"cotton_valley.server_scripts.sales_order.send_abandoned_cart_emails",
			"cotton_valley.api.sales_order.mark_orders_as_invoiced",
			# "cotton_valley.scheduler.product_scheduler.scheduler_dispatch_cv_item_sync",
			# "cotton_valley.scheduler.product_scheduler.scheduler_dispatch_udc_item_sync"
		]
	},
# 	"hourly": [
# 		"cotton_valley.tasks.hourly"
# 	],
	"weekly": [
		"cotton_valley.api.products.delete_all_item_value_updates"
	],
# 	"monthly": [
# 		"cotton_valley.tasks.monthly"
# 	],
}

# Testing
# -------

# before_tests = "cotton_valley.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "cotton_valley.event.get_events"
# }

override_whitelisted_methods = {
	"frappe.desk.desktop.get_workspace_sidebar_items": "cotton_valley.api.workspace_api.get_workspace_sidebar_items",
	"frappe.desk.desktop.get_desktop_page": "cotton_valley.api.workspace_api.get_desktop_page"
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "cotton_valley.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["cotton_valley.utils.before_request"]
# after_request = ["cotton_valley.utils.after_request"]

# Job Events
# ----------
# before_job = ["cotton_valley.utils.before_job"]
# after_job = ["cotton_valley.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"cotton_valley.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

