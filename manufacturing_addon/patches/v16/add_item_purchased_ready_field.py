# Copyright (c) 2026, manufacturing_addon contributors

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	if frappe.db.exists("Custom Field", {"dt": "Item", "fieldname": "custom_purchased_ready"}):
		return

	create_custom_field(
		"Item",
		{
			"fieldname": "custom_purchased_ready",
			"label": "Purchased Ready (Skip Production Check)",
			"fieldtype": "Check",
			"default": "0",
			"insert_after": "is_purchase_item",
			"description": "Item is bought as a finished product. Packing Report will not require "
			"Cutting/Stitching/Checking qty for it. Can be set on the SO item or on its combo item.",
		},
	)
