# Copyright (c) 2026, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	details = get_details(filters)
	data = build_supplier_summary_with_details(details)
	return columns, data


def get_columns():
	return [
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Manufacturing Contractor", "width": 220},
		{"label": _("Row Type"), "fieldname": "row_type", "fieldtype": "Data", "width": 95},
		{"label": _("Stitching Report"), "fieldname": "stitching_report", "fieldtype": "Link", "options": "Stitching Report", "width": 170},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
		{"label": _("Order Sheet"), "fieldname": "order_sheet", "fieldtype": "Link", "options": "Order Sheet", "width": 170},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
		{"label": _("SO Item"), "fieldname": "so_item", "fieldtype": "Link", "options": "Item", "width": 200},
		{"label": _("Combo Item"), "fieldname": "combo_item", "fieldtype": "Link", "options": "Item", "width": 170},
		{"label": _("Planned Qty"), "fieldname": "planned_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Stitching Qty"), "fieldname": "stitching_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Progress %"), "fieldname": "progress_pct", "fieldtype": "Percent", "width": 100},
	]


def get_details(filters):
	conditions = ["sr.docstatus = 1"]
	values = {}

	if filters.get("from_date"):
		conditions.append("sr.date >= %(from_date)s")
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions.append("sr.date <= %(to_date)s")
		values["to_date"] = filters.get("to_date")
	if filters.get("supplier"):
		conditions.append("sr.supplier = %(supplier)s")
		values["supplier"] = filters.get("supplier")
	if filters.get("customer"):
		conditions.append("sr.customer = %(customer)s")
		values["customer"] = filters.get("customer")
	if filters.get("order_sheet"):
		conditions.append("sr.order_sheet = %(order_sheet)s")
		values["order_sheet"] = filters.get("order_sheet")

	where_clause = " AND ".join(conditions)

	return frappe.db.sql(
		f"""
		SELECT
			sr.supplier,
			sr.name AS stitching_report,
			sr.date AS posting_date,
			sr.order_sheet,
			sr.customer,
			srct.so_item,
			srct.combo_item,
			IFNULL(srct.planned_qty, 0) AS planned_qty,
			IFNULL(srct.stitching_qty, 0) AS stitching_qty
		FROM `tabStitching Report` sr
		LEFT JOIN `tabStitching Report CT` srct ON srct.parent = sr.name
		WHERE {where_clause}
		ORDER BY sr.supplier, sr.date, sr.name, srct.idx
		""",
		values,
		as_dict=True,
	)


def build_supplier_summary_with_details(details):
	if not details:
		return []

	supplier_totals = {}
	for row in details:
		supplier = row.get("supplier") or _("Not Set")
		if supplier not in supplier_totals:
			supplier_totals[supplier] = {"planned_qty": 0.0, "stitching_qty": 0.0}
		supplier_totals[supplier]["planned_qty"] += flt(row.get("planned_qty"))
		supplier_totals[supplier]["stitching_qty"] += flt(row.get("stitching_qty"))

	data = []
	current_supplier = None

	for row in details:
		supplier = row.get("supplier") or _("Not Set")
		if supplier != current_supplier:
			totals = supplier_totals.get(supplier, {})
			total_planned = flt(totals.get("planned_qty"))
			total_stitching = flt(totals.get("stitching_qty"))
			data.append(
				{
					"supplier": supplier,
					"row_type": "Summary",
					"planned_qty": total_planned,
					"stitching_qty": total_stitching,
					"progress_pct": (total_stitching / total_planned * 100) if total_planned else 0,
				}
			)
			current_supplier = supplier

		planned_qty = flt(row.get("planned_qty"))
		stitching_qty = flt(row.get("stitching_qty"))
		data.append(
			{
				"supplier": supplier,
				"row_type": "Detail",
				"stitching_report": row.get("stitching_report"),
				"posting_date": row.get("posting_date"),
				"order_sheet": row.get("order_sheet"),
				"customer": row.get("customer"),
				"so_item": row.get("so_item"),
				"combo_item": row.get("combo_item"),
				"planned_qty": planned_qty,
				"stitching_qty": stitching_qty,
				"progress_pct": (stitching_qty / planned_qty * 100) if planned_qty else 0,
				"indent": 1,
			}
		)

	return data
