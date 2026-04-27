# Copyright (c) 2025, manufacturing_addon contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.desk.notifications import get_open_count as frappe_get_open_count

# Linked via Order Sheet → Sales Order (no direct sales_order field on these doctypes)
INDIRECT_VIA_ORDER_SHEET = ("Cutting Report", "Packing Report", "Stitching Report")

MANUFACTURING_CONNECTION_ITEMS = ("Order Sheet",) + INDIRECT_VIA_ORDER_SHEET


def get_data(data=None):
	"""Extend ERPNext Sales Order dashboard with Order Sheet and manufacturing reports."""
	if data is None:
		data = {}

	if "transactions" not in data:
		data["transactions"] = []

	mfg_group = None
	for transaction in data["transactions"]:
		if transaction.get("label") == _("Manufacturing"):
			mfg_group = transaction
			break

	if mfg_group:
		for dt in MANUFACTURING_CONNECTION_ITEMS:
			if dt not in mfg_group["items"]:
				mfg_group["items"].append(dt)
	else:
		data["transactions"].append(
			{"label": _("Manufacturing"), "items": list(MANUFACTURING_CONNECTION_ITEMS)}
		)

	data["method"] = (
		"manufacturing_addon.manufacturing_addon.doctype.sales_order.sales_order_dashboard.get_open_count"
	)

	return data


@frappe.whitelist()
@frappe.read_only()
def get_open_count(doctype: str, name: str, items=None):
	"""Resolve Cutting / Packing / Stitching counts via Order Sheet; delegate the rest to core."""
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

	cleaned = [i for i in items if i not in INDIRECT_VIA_ORDER_SHEET]
	out = frappe_get_open_count(doctype, name, cleaned)

	order_sheet_names = frappe.get_all(
		"Order Sheet",
		filters={"sales_order": name},
		pluck="name",
	)

	for d in items:
		if d not in INDIRECT_VIA_ORDER_SHEET:
			continue
		if not order_sheet_names:
			out["count"]["internal_links_found"].append(
				{"doctype": d, "count": 0, "open_count": 0, "names": []}
			)
			continue
		names = frappe.get_all(
			d,
			filters={"order_sheet": ["in", order_sheet_names]},
			pluck="name",
			limit=100,
			distinct=True,
			order_by=None,
		)
		out["count"]["internal_links_found"].append(
			{
				"doctype": d,
				"count": len(names),
				"open_count": 0,
				"names": names,
			}
		)

	return out
