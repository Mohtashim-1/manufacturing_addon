import frappe


def execute():
	"""Clear invalid fetch_from on Production Plan.custom_order_sheet.

	Older custom field definitions used:
		fetch_from = "custom_order_sheet.customer"
	which is invalid in Frappe because the source field equals the same fieldname.
	This breaks `bench migrate` during `sync_customizations()` validation.
	"""
	name = frappe.get_value(
		"Custom Field",
		{"dt": "Production Plan", "fieldname": "custom_order_sheet"},
		"name",
	)
	if not name:
		return

	cf = frappe.get_doc("Custom Field", name)
	fetch_from = (cf.get("fetch_from") or "").strip()
	if not fetch_from:
		return

	# If self-referential, clear.
	if "." in fetch_from and fetch_from.split(".", 1)[0].strip() == (cf.fieldname or "").strip():
		cf.fetch_from = ""
		cf.fetch_if_empty = 0
		cf.save(ignore_permissions=True)

