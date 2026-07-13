import json

import frappe


def execute():
	"""Remove duplicate status column from Sales Order List View Settings for v16."""
	fields_raw = frappe.db.get_value("List View Settings", "Sales Order", "fields")
	if not fields_raw:
		return

	fields = json.loads(fields_raw)
	cleaned = [field for field in fields if field.get("fieldname") != "status"]
	if len(cleaned) == len(fields):
		return

	frappe.db.set_value("List View Settings", "Sales Order", "fields", json.dumps(cleaned))

	# v16 uses the virtual Status indicator column; hide the raw status field from list columns.
	if frappe.db.exists(
		"Property Setter", {"doc_type": "Sales Order", "field_name": "status", "property": "in_list_view"}
	):
		frappe.db.set_value(
			"Property Setter",
			{"doc_type": "Sales Order", "field_name": "status", "property": "in_list_view"},
			"value",
			"0",
		)
	else:
		frappe.make_property_setter(
			{
				"doctype": "Sales Order",
				"doctype_or_field": "DocField",
				"fieldname": "status",
				"property": "in_list_view",
				"value": "0",
				"property_type": "Check",
			},
			ignore_validate=True,
		)

	frappe.clear_cache(doctype="Sales Order")
