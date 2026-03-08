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
		{"label": _("Cutting Report"), "fieldname": "cutting_report", "fieldtype": "Link", "options": "Cutting Report", "width": 170},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
		{"label": _("Order Sheet"), "fieldname": "order_sheet", "fieldtype": "Link", "options": "Order Sheet", "width": 170},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
		{"label": _("SO Item"), "fieldname": "so_item", "fieldtype": "Link", "options": "Item", "width": 200},
		{"label": _("Combo Item"), "fieldname": "combo_item", "fieldtype": "Link", "options": "Item", "width": 170},
		{"label": _("Planned Qty"), "fieldname": "planned_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Cutting Qty"), "fieldname": "cutting_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Progress %"), "fieldname": "progress_pct", "fieldtype": "Percent", "width": 100},
	]


def get_details(filters):
	conditions = ["cr.docstatus = 1"]
	values = {}

	if filters.get("from_date"):
		conditions.append("cr.date >= %(from_date)s")
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions.append("cr.date <= %(to_date)s")
		values["to_date"] = filters.get("to_date")
	if filters.get("supplier"):
		conditions.append("cr.supplier = %(supplier)s")
		values["supplier"] = filters.get("supplier")
	if filters.get("customer"):
		conditions.append("cr.customer = %(customer)s")
		values["customer"] = filters.get("customer")
	if filters.get("order_sheet"):
		conditions.append("cr.order_sheet = %(order_sheet)s")
		values["order_sheet"] = filters.get("order_sheet")

	where_clause = " AND ".join(conditions)

	return frappe.db.sql(
		f"""
		SELECT
			cr.supplier,
			cr.name AS cutting_report,
			cr.date AS posting_date,
			cr.order_sheet,
			cr.customer,
			crct.so_item,
			crct.combo_item,
			IFNULL(crct.planned_qty, 0) AS planned_qty,
			IFNULL(crct.cutting_qty, 0) AS cutting_qty
		FROM `tabCutting Report` cr
		LEFT JOIN `tabCutting Report CT` crct ON crct.parent = cr.name
		WHERE {where_clause}
		ORDER BY cr.supplier, cr.date, cr.name, crct.idx
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
			supplier_totals[supplier] = {"planned_qty": 0.0, "cutting_qty": 0.0}
		supplier_totals[supplier]["planned_qty"] += flt(row.get("planned_qty"))
		supplier_totals[supplier]["cutting_qty"] += flt(row.get("cutting_qty"))

	data = []
	current_supplier = None

	for row in details:
		supplier = row.get("supplier") or _("Not Set")
		if supplier != current_supplier:
			totals = supplier_totals.get(supplier, {})
			total_planned = flt(totals.get("planned_qty"))
			total_cutting = flt(totals.get("cutting_qty"))
			data.append(
				{
					"supplier": supplier,
					"row_type": "Summary",
					"planned_qty": total_planned,
					"cutting_qty": total_cutting,
					"progress_pct": (total_cutting / total_planned * 100) if total_planned else 0,
				}
			)
			current_supplier = supplier

		planned_qty = flt(row.get("planned_qty"))
		cutting_qty = flt(row.get("cutting_qty"))
		data.append(
			{
				"supplier": supplier,
				"row_type": "Detail",
				"cutting_report": row.get("cutting_report"),
				"posting_date": row.get("posting_date"),
				"order_sheet": row.get("order_sheet"),
				"customer": row.get("customer"),
				"so_item": row.get("so_item"),
				"combo_item": row.get("combo_item"),
				"planned_qty": planned_qty,
				"cutting_qty": cutting_qty,
				"progress_pct": (cutting_qty / planned_qty * 100) if planned_qty else 0,
				"indent": 1,
			}
		)

	return data
