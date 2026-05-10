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
	frappe.log_error("sales_order_dashboard")
	try:
		frappe.log_error("[Manufacturing Addon] get_data called for Sales Order dashboard override")
		if data:
			frappe.log_error(f"[Manufacturing Addon] Incoming data keys: {list(data.keys())}")
	except Exception as e:
		frappe.log_error(f"Sales Order dashboard logging failed: {e}", "Manufacturing Addon Dashboard Log Error")
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
	out = frappe_get_open_count(doctype, name, cleaned)

	order_sheet_names = frappe.get_all(
		"Order Sheet",
		filters={"sales_order": name},
		pluck="name",
	)

	for linked_doctype in items:
		if linked_doctype not in INDIRECT_VIA_ORDER_SHEET:
			continue

		if not order_sheet_names:
			out["count"]["internal_links_found"].append(
				{"doctype": linked_doctype, "count": 0, "open_count": 0, "names": []}
			)
			continue

		names = frappe.get_all(
			linked_doctype,
			filters={"order_sheet": ["in", order_sheet_names]},
			pluck="name",
			limit=100,
			distinct=True,
			order_by=None,
		)
		out["count"]["internal_links_found"].append(
			{
				"doctype": linked_doctype,
				"count": len(names),
				"open_count": 0,
				"names": names,
			}
		)

	return out
