# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

import frappe
from frappe.model.document import Document
from frappe.utils import flt

# Frappe 16: child tables cannot host nested child tables via Document.append()
# (_table_fieldnames is empty for istable docs). Assign lists of _dict instead.
# as_dict() also skips nested tables on child docs — StyleContractorsChildMixin
# re-injects them so Desk receives Style Contractors on form load.


def _as_style_row(data):
	row = frappe._dict(data)
	row.doctype = row.get("doctype") or "Report Style Contractor"
	return row


def _style_row_to_client_dict(row):
	if isinstance(row, Document):
		return row.as_dict(convert_dates_to_str=True)
	out = {}
	for key, value in dict(row).items():
		if hasattr(value, "isoformat"):
			out[key] = str(value)
		else:
			out[key] = value
	out["doctype"] = out.get("doctype") or "Report Style Contractor"
	return out


class StyleContractorsChildMixin:
	"""Serialize nested style_contractors onto report CT rows for the Desk client."""

	def as_dict(self, *args, **kwargs):
		doc = super().as_dict(*args, **kwargs)
		style_rows = self.__dict__.get("style_contractors")
		if style_rows is None:
			style_rows = self.get("style_contractors")
		doc["style_contractors"] = [_style_row_to_client_dict(row) for row in (style_rows or [])]
		return doc


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

		row.set("style_contractors", [_as_style_row(sc) for sc in nested_rows])


def save_nested_style_contractors(doc, child_table_field, parenttype):
	"""Persist Report Style Contractor grandchildren for each CT row."""
	for ct_row in doc.get(child_table_field) or []:
		if not ct_row.name:
			continue
		_save_style_contractors_for_ct_row(ct_row, parenttype)


def _save_style_contractors_for_ct_row(ct_row, parenttype):
	style_rows = ct_row.get("style_contractors") or []
	# Desk posts nested rows as plain dict — normalize for consistent .get access.
	style_rows = [frappe._dict(row) if isinstance(row, dict) else row for row in style_rows]
	# Prefer attribute assign — frappe._dict.__getattr__("set") returns None
	if isinstance(ct_row, dict):
		ct_row["style_contractors"] = style_rows
	else:
		ct_row.style_contractors = style_rows
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
			frappe.db.set_value("Report Style Contractor", row.get("name"), values)
		else:
			doc = frappe.get_doc({"doctype": "Report Style Contractor", **values})
			doc.insert(ignore_permissions=True)
			row["name"] = doc.name
			row["__islocal"] = 0
