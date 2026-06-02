# Copyright (c) 2026, manufacturing_addon contributors

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	# This custom field is a simple Link (Production Plan -> Order Sheet).
	# Do NOT set `fetch_from` on the Link field itself; Frappe validates
	# and rejects self-referential expressions like "custom_order_sheet.customer"
	# (where the source part equals the same fieldname).
	existing = frappe.get_value(
		"Custom Field",
		{"dt": "Production Plan", "fieldname": "custom_order_sheet"},
		"name",
	)

	if existing:
		# If an earlier deploy added an invalid `fetch_from`, clean it up so
		# this patch can be safely re-run.
		cf = frappe.get_doc("Custom Field", existing)
		if cf.get("fetch_from") or cf.get("fetch_if_empty"):
			cf.fetch_from = ""
			cf.fetch_if_empty = 0
			cf.save(ignore_permissions=True)
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
		},
	)
