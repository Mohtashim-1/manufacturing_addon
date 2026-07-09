# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

import frappe
from frappe.utils import flt


def load_nested_style_contractors(doc, child_table_field, parenttype):
	"""Load Report Style Contractor grandchildren for each CT row."""
	for row in doc.get(child_table_field) or []:
		if not row.name:
			continue

		nested_rows = frappe.get_all(
			"Report Style Contractor",
			filters={
				"parent": row.name,
				"parenttype": parenttype,
				"parentfield": "style_contractors",
			},
			fields=["*"],
			order_by="idx asc",
		)

		row.set("style_contractors", [])
		for sc_data in nested_rows:
			row.append("style_contractors", sc_data)


def save_nested_style_contractors(doc, child_table_field, parenttype):
	"""Persist Report Style Contractor grandchildren for each CT row."""
	for ct_row in doc.get(child_table_field) or []:
		if not ct_row.name:
			continue
		_save_style_contractors_for_ct_row(ct_row, parenttype)


def _save_style_contractors_for_ct_row(ct_row, parenttype):
	style_rows = ct_row.get("style_contractors") or []
	parent_filters = {
		"parent": ct_row.name,
		"parenttype": parenttype,
		"parentfield": "style_contractors",
	}

	keep_names = [
		row.get("name")
		for row in style_rows
		if row.get("name") and not row.get("__islocal")
	]
	if keep_names:
		frappe.db.delete(
			"Report Style Contractor",
			{**parent_filters, "name": ("not in", keep_names)},
		)
	else:
		frappe.db.delete("Report Style Contractor", parent_filters)

	for idx, row in enumerate(style_rows, start=1):
		values = {
			"style": row.get("style"),
			"contractor": row.get("contractor"),
			"split_qty": flt(row.get("split_qty")),
			"qty": flt(row.get("qty") or 1) or 1,
			"unit_qty": flt(row.get("unit_qty")),
			"rate": flt(row.get("rate")),
			"amount": flt(row.get("amount")),
			"is_mandatory": 1 if row.get("is_mandatory") else 0,
			"is_subassembly": 1 if row.get("is_subassembly") else 0,
			"operation": row.get("operation"),
			"combo_item": row.get("combo_item"),
			"item_style_row": row.get("item_style_row"),
			"parent": ct_row.name,
			"parenttype": parenttype,
			"parentfield": "style_contractors",
			"idx": idx,
		}

		if row.get("name") and not row.get("__islocal"):
			frappe.db.set_value("Report Style Contractor", row.name, values)
		else:
			doc = frappe.get_doc({"doctype": "Report Style Contractor", **values})
			doc.insert(ignore_permissions=True)
			row.name = doc.name
			if hasattr(row, "__islocal"):
				row.__islocal = 0
