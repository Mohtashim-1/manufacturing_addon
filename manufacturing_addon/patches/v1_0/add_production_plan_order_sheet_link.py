# Copyright (c) 2026, manufacturing_addon contributors

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	if frappe.db.exists("Custom Field", "Production Plan-custom_order_sheet"):
		return

	create_custom_field(
		"Production Plan",
		{
			"fieldname": "custom_order_sheet",
			"label": "Order Sheet",
			"fieldtype": "Link",
			"options": "Order Sheet",
			"insert_after": "customer",
			"in_list_view": 1,
			"in_standard_filter": 1,
			"in_global_search": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
			"search_index": 1,
			"description": "Order Sheet this production plan was created from",
			"fetch_from": "custom_order_sheet.customer",
			"fetch_if_empty": 1,
		},
	)
