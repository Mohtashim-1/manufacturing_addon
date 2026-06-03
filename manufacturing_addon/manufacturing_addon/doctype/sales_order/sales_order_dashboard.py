# Copyright (c) 2025, manufacturing_addon contributors
# License: MIT. See LICENSE

import json

from frappe import _
import frappe
from frappe.desk.notifications import get_open_count as frappe_get_open_count


INDIRECT_VIA_ORDER_SHEET = (
	"Cutting Report",
	"Packing Report",
	"Stitching Report",
	"Daily Checking",
	"Inline Stitching",
	"Final Inspection",
)
MANUFACTURING_CONNECTION_ITEMS = ("Order Sheet",) + INDIRECT_VIA_ORDER_SHEET


def get_data(data=None):
	dashboard = {
		"fieldname": "sales_order",
		"non_standard_fieldnames": {
			"Delivery Note": "against_sales_order",
			"Journal Entry": "reference_name",
			"Payment Entry": "reference_name",
			"Payment Request": "reference_name",
			"Auto Repeat": "reference_document",
			"Maintenance Visit": "prevdoc_docname",
			"Stock Reservation Entry": "voucher_no",
		},
		"internal_links": {
			"Quotation": ["items", "prevdoc_docname"],
			"BOM": ["items", "bom_no"],
			"Blanket Order": ["items", "blanket_order"],
			"Production Plan": ["sales_orders", "sales_order"],
			"Material Request": ["items", "sales_order"],
			"Purchase Order": ["items", "sales_order"],
			"Purchase Receipt": ["items", "sales_order"],
			"Purchase Invoice": ["items", "sales_order"],
		},
		"transactions": [
			{
				"label": _("Fulfillment"),
				"items": ["Sales Invoice", "Pick List", "Delivery Note", "Maintenance Visit"],
			},
			{"label": _("Purchasing"), "items": ["Material Request", "Purchase Order", "Purchase Receipt", "Purchase Invoice"]},
			{"label": _("Projects"), "items": ["Project"]},
			{
				"label": _("Manufacturing"),
				"items": [
					"Work Order",
					"BOM",
					"Blanket Order",
					"Production Plan",
					"Order Sheet",
					"Cutting Report",
					"Stitching Report",
					"Packing Report",
					"Daily Checking",
					"Inline Stitching",
					"Final Inspection",
				],
			},
			{"label": _("Reference"), "items": ["Quotation", "Auto Repeat", "Stock Reservation Entry"]},
			{"label": _("Payment"), "items": ["Payment Entry", "Payment Request", "Journal Entry"]},
		],
	}
	dashboard["method"] = (
		"manufacturing_addon.manufacturing_addon.doctype.sales_order.sales_order_dashboard.get_open_count"
	)
	return dashboard


@frappe.whitelist()
@frappe.read_only()
def get_open_count(doctype: str, name: str, items=None):
	"""Keep direct links and add indirect manufacturing counts via Order Sheet."""
	if doctype != "Sales Order":
		return frappe_get_open_count(doctype, name, items)

	if isinstance(items, str):
		items = json.loads(items)

	doc = frappe.get_doc(doctype, name)
	doc.check_permission()

	meta = doc.meta
	links = meta.get_dashboard_data()

	if items is None:
		items = []
		for group in links.transactions:
			items.extend(group.get("items"))

	cleaned = [item for item in items if item not in INDIRECT_VIA_ORDER_SHEET]

	# Allow slower prod DB; default frappe desk timeout is 1s.
	frappe.db.set_execution_timeout(5)
	try:
		out = frappe_get_open_count(doctype, name, cleaned)
	finally:
		frappe.db.set_execution_timeout(0)

	count = out.setdefault("count", {})
	internal = count.setdefault("internal_links_found", [])
	external = count.setdefault("external_links_found", [])

	# Drop wrong external rows (filter sales_order on doctypes that only link via Order Sheet).
	count["external_links_found"] = [
		row for row in external if row.get("doctype") not in INDIRECT_VIA_ORDER_SHEET
	]
	internal_by_dt = {row.get("doctype"): row for row in internal if row.get("doctype")}

	order_sheet_names = frappe.get_all(
		"Order Sheet",
		filters={"sales_order": name},
		pluck="name",
	)

	for linked_doctype in items:
		if linked_doctype not in INDIRECT_VIA_ORDER_SHEET:
			continue
		if not frappe.db.exists("DocType", linked_doctype):
			continue

		if not order_sheet_names:
			row = {"doctype": linked_doctype, "count": 0, "open_count": 0, "names": []}
		else:
			filters = {"order_sheet": ["in", order_sheet_names]}
			total = frappe.db.count(linked_doctype, filters)
			names = frappe.get_all(
				linked_doctype,
				filters=filters,
				pluck="name",
				limit=500,
				distinct=True,
				order_by="modified desc",
			)
			row = {
				"doctype": linked_doctype,
				"count": total,
				"open_count": 0,
				"names": names,
			}

		internal_by_dt[linked_doctype] = row

	count["internal_links_found"] = list(internal_by_dt.values())
	return out
