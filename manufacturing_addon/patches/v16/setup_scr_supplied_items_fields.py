# Copyright (c) 2026, Manufacturing Addon and contributors

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _set_property(doctype, fieldname, prop, value, property_type):
	filters = {"doc_type": doctype, "field_name": fieldname, "property": prop}
	if frappe.db.exists("Property Setter", filters):
		frappe.db.set_value("Property Setter", filters, "value", value)
	else:
		frappe.make_property_setter(
			{
				"doctype": doctype,
				"doctype_or_field": "DocField",
				"fieldname": fieldname,
				"property": prop,
				"value": value,
				"property_type": property_type,
			},
			ignore_validate=True,
		)


def execute():
	create_custom_fields(
		{
			"Subcontracting Receipt Supplied Item": [
				{
					"fieldname": "custom_transferred_qty",
					"label": "Transferred Qty",
					"fieldtype": "Float",
					"insert_after": "available_qty_for_consumption",
					"read_only": 1,
					"in_list_view": 1,
					"columns": 1,
					"print_hide": 1,
					"description": "Qty actually transferred to supplier via Stock Entry for this FG + RM",
				}
			]
		},
		update=True,
	)

	# Keep the grid narrow enough to fit without horizontal scrolling: the footer
	# totals in scrollable_table only stay aligned while columns fit the container.
	compact_columns = {
		"main_item_code": "2",
		"rm_item_code": "3",
		"required_qty": "1",
		"consumed_qty": "1",
	}
	for fieldname, columns in compact_columns.items():
		_set_property("Subcontracting Receipt Supplied Item", fieldname, "in_list_view", "1", "Check")
		_set_property("Subcontracting Receipt Supplied Item", fieldname, "columns", columns, "Int")

	for fieldname in ("rate", "amount", "available_qty_for_consumption", "serial_and_batch_bundle"):
		_set_property("Subcontracting Receipt Supplied Item", fieldname, "in_list_view", "0", "Check")

	frappe.clear_cache(doctype="Subcontracting Receipt Supplied Item")
	frappe.clear_cache(doctype="Subcontracting Receipt")
