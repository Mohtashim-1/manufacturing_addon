# Copyright (c) 2026, Manufacturing Addon and contributors
# License: MIT

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt


def _get_orders_from_scr(doc) -> list[str]:
	orders = []
	for row in doc.get("items") or []:
		order = row.get("subcontracting_order")
		if order and order not in orders:
			orders.append(order)
	return orders


@frappe.whitelist()
def get_transferred_raw_materials(subcontracting_orders=None, subcontracting_receipt=None):
	"""Return raw materials actually sent via Stock Entry for the given SCO(s)."""
	if isinstance(subcontracting_orders, str):
		subcontracting_orders = frappe.parse_json(subcontracting_orders)

	if not subcontracting_orders and subcontracting_receipt:
		doc = frappe.get_doc("Subcontracting Receipt", subcontracting_receipt)
		subcontracting_orders = _get_orders_from_scr(doc)

	if not subcontracting_orders:
		return {"rows": [], "aggregated": []}

	rows = frappe.db.sql(
		"""
		SELECT
			se.name AS stock_entry,
			se.posting_date,
			se.is_return,
			se.subcontracting_order,
			sed.subcontracted_item AS main_item_code,
			sed.item_code AS rm_item_code,
			sed.item_name,
			CASE
				WHEN se.purpose = 'Material Transfer' AND se.is_return = 1 THEN -1 * sed.qty
				ELSE sed.qty
			END AS qty,
			sed.basic_rate AS rate,
			CASE
				WHEN se.purpose = 'Material Transfer' AND se.is_return = 1 THEN -1 * sed.amount
				ELSE sed.amount
			END AS amount,
			sed.stock_uom,
			sed.original_item
		FROM `tabStock Entry` se
		INNER JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
		WHERE se.docstatus = 1
			AND se.subcontracting_order IN %(orders)s
			AND (
				se.purpose = 'Send to Subcontractor'
				OR (se.purpose = 'Material Transfer' AND se.is_return = 1)
			)
		ORDER BY se.posting_date, se.name, sed.idx
		""",
		{"orders": subcontracting_orders},
		as_dict=True,
	)

	agg_map = defaultdict(
		lambda: frappe._dict(
			main_item_code="",
			rm_item_code="",
			item_name="",
			stock_uom="",
			qty=0.0,
			amount=0.0,
			stock_entries=set(),
		)
	)

	for row in rows:
		key = (row.main_item_code, row.rm_item_code, row.subcontracting_order)
		bucket = agg_map[key]
		bucket.main_item_code = row.main_item_code
		bucket.rm_item_code = row.rm_item_code
		bucket.item_name = row.item_name
		bucket.stock_uom = row.stock_uom
		bucket.subcontracting_order = row.subcontracting_order
		bucket.qty += flt(row.qty)
		bucket.amount += flt(row.amount)
		bucket.stock_entries.add(row.stock_entry)

	aggregated = []
	for bucket in agg_map.values():
		aggregated.append(
			{
				"main_item_code": bucket.main_item_code,
				"rm_item_code": bucket.rm_item_code,
				"item_name": bucket.item_name,
				"stock_uom": bucket.stock_uom,
				"subcontracting_order": bucket.subcontracting_order,
				"qty": flt(bucket.qty),
				"amount": flt(bucket.amount),
				"stock_entries": sorted(bucket.stock_entries),
			}
		)

	aggregated.sort(key=lambda d: (d.get("main_item_code") or "", d.get("rm_item_code") or ""))
	return {"rows": rows, "aggregated": aggregated}


@frappe.whitelist()
def get_transferred_qty_map(subcontracting_orders=None, subcontracting_receipt=None):
	data = get_transferred_raw_materials(subcontracting_orders, subcontracting_receipt)
	qty_map = {}
	for row in data.get("aggregated") or []:
		key = f"{row.get('main_item_code')}::{row.get('rm_item_code')}"
		qty_map[key] = flt(row.get("qty"))
	return qty_map


def set_transferred_qty_on_supplied_items(doc, method=None):
	"""Fill custom_transferred_qty from Stock Entries against linked SCOs."""
	if not doc.get("supplied_items"):
		return

	meta = frappe.get_meta("Subcontracting Receipt Supplied Item")
	if not meta.has_field("custom_transferred_qty"):
		return

	orders = _get_orders_from_scr(doc)
	if not orders:
		return

	qty_map = get_transferred_qty_map(orders)
	for row in doc.supplied_items:
		key = f"{row.main_item_code}::{row.rm_item_code}"
		row.custom_transferred_qty = flt(qty_map.get(key))


@frappe.whitelist()
def load_supplied_items_from_transfers(doc):
	"""
	Rebuild supplied_items from actual Send-to-Subcontractor Stock Entries
	(same as Reset Raw Materials when backflush = Material Transferred),
	then stamp transferred qty on each row.
	"""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can reload supplied items from transfers"), frappe.PermissionError)

	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	if isinstance(doc, dict):
		doc = frappe.get_doc(doc)

	if cint(doc.docstatus) != 0:
		frappe.throw(_("Can only reload raw materials on a draft Subcontracting Receipt"))

	if not _get_orders_from_scr(doc):
		frappe.throw(_("No Subcontracting Order linked on Items"))

	doc.flags.reset_raw_materials = True
	doc.set("supplied_items", [])
	doc.create_raw_materials_supplied_or_received()
	set_transferred_qty_on_supplied_items(doc)
	return doc.as_dict()
