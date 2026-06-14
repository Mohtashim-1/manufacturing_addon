# Copyright (c) 2026, manufacturing_addon contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.desk.notifications import get_open_count as frappe_get_open_count


PRODUCTION_CONNECTION_ITEMS = (
	"Order Sheet",
	"Cutting Report",
	"Stitching Report",
	"Checking Report",
	"Packing Report",
)

CHILD_TABLE_BY_DOCTYPE = {
	"Order Sheet": "Order Sheet CT",
	"Cutting Report": "Cutting Report CT",
	"Stitching Report": "Stitching Report CT",
	"Checking Report": "Checking Report CT",
	"Packing Report": "Packing Report CT",
}


def get_data(data=None):
	data = frappe._dict(data or {})
	label = _("Production")

	group = None
	for entry in data.get("transactions") or []:
		if _(entry.get("label")) == label:
			group = entry
			break

	if not group:
		group = {"label": label, "items": []}
		data.setdefault("transactions", []).append(group)

	for doctype in PRODUCTION_CONNECTION_ITEMS:
		if doctype not in group["items"]:
			group["items"].append(doctype)

	data["method"] = (
		"manufacturing_addon.manufacturing_addon.doctype.item.item_dashboard.get_open_count"
	)
	return data


@frappe.whitelist()
@frappe.read_only()
def get_open_count(doctype: str, name: str, items=None):
	"""Count Order Sheet / reports linked to an Item via child-table so_item."""
	if doctype != "Item":
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

	cleaned = [item for item in items if item not in PRODUCTION_CONNECTION_ITEMS]

	frappe.db.set_execution_timeout(5)
	try:
		out = frappe_get_open_count(doctype, name, cleaned)
	finally:
		frappe.db.set_execution_timeout(0)

	count = out.setdefault("count", {})
	internal = count.setdefault("internal_links_found", [])
	external = count.setdefault("external_links_found", [])

	count["external_links_found"] = [
		row for row in external if row.get("doctype") not in PRODUCTION_CONNECTION_ITEMS
	]
	internal_by_dt = {row.get("doctype"): row for row in internal if row.get("doctype")}

	for linked_doctype in items:
		if linked_doctype not in PRODUCTION_CONNECTION_ITEMS:
			continue
		if not frappe.db.exists("DocType", linked_doctype):
			continue

		child_doctype = CHILD_TABLE_BY_DOCTYPE.get(linked_doctype)
		names = _parent_docs_for_item(child_doctype, linked_doctype, name) if child_doctype else []
		internal_by_dt[linked_doctype] = {
			"doctype": linked_doctype,
			"count": len(names),
			"open_count": 0,
			"names": names,
		}

	count["internal_links_found"] = list(internal_by_dt.values())
	return out


def _parent_docs_for_item(child_doctype, parent_doctype, item_code):
	return frappe.get_all(
		child_doctype,
		filters={"so_item": item_code, "parenttype": parent_doctype},
		pluck="parent",
		distinct=True,
		limit=500,
		order_by="modified desc",
	)
