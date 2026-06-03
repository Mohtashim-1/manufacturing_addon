# Copyright (c) 2026, manufacturing_addon contributors
# License: MIT

import frappe
from frappe import _


@frappe.whitelist()
def get_sales_order_connection_dashboard(sales_order):
	"""Manufacturing progress + linked docs for Sales Order Connection Dashboard tab."""
	if not sales_order:
		frappe.throw(_("Sales Order is required"))

	if not frappe.db.exists("Sales Order", sales_order):
		frappe.throw(_("Sales Order {0} not found").format(sales_order))

	frappe.has_permission("Sales Order", doc=sales_order, ptype="read", throw=True)

	from manufacturing_addon.manufacturing_addon.page.order_tracking.order_tracking import (
		get_dashboard_data,
	)

	tracking = get_dashboard_data(sales_order=sales_order) or {}
	summary = tracking.get("summary") or {}

	related = {
		"order_sheets_count": 0,
		"order_sheet_rows": [],
		"cutting_reports_count": 0,
		"cutting_report_rows": [],
		"stitching_reports_count": 0,
		"stitching_report_rows": [],
		"packing_reports_count": 0,
		"packing_report_rows": [],
	}

	try:
		from production_plan_addon.api import get_related_via_production_plan

		related = get_related_via_production_plan(sales_order) or related
	except Exception:
		related.update(_manufacturing_doc_rows(sales_order))

	return {
		"sales_order": sales_order,
		"summary": summary,
		**{k: related.get(k) for k in related if k.endswith("_count") or k.endswith("_rows")},
	}


def _manufacturing_doc_rows(sales_order):
	"""Fallback when production_plan_addon API is unavailable."""
	os_names = frappe.get_all("Order Sheet", filters={"sales_order": sales_order}, pluck="name")
	out = {
		"order_sheets_count": len(os_names),
		"order_sheet_rows": [],
		"cutting_reports_count": 0,
		"cutting_report_rows": [],
		"stitching_reports_count": 0,
		"stitching_report_rows": [],
		"packing_reports_count": 0,
		"packing_report_rows": [],
	}
	if not os_names:
		return out

	out["order_sheet_rows"] = frappe.get_all(
		"Order Sheet",
		filters={"name": ["in", os_names]},
		fields=["name", "customer", "posting_date_and_time", "shipment_date"],
		order_by="modified desc",
		limit=50,
	)

	for dt, count_key, rows_key in (
		("Cutting Report", "cutting_reports_count", "cutting_report_rows"),
		("Stitching Report", "stitching_reports_count", "stitching_report_rows"),
		("Packing Report", "packing_reports_count", "packing_report_rows"),
	):
		if not frappe.db.exists("DocType", dt):
			continue
		rows = frappe.get_all(
			dt,
			filters={"order_sheet": ["in", os_names]},
			fields=["name", "date", "order_sheet", "customer", "supplier"],
			order_by="modified desc",
			limit=50,
		)
		out[count_key] = frappe.db.count(dt, {"order_sheet": ["in", os_names]})
		out[rows_key] = rows

	return out
