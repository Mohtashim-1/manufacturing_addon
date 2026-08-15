# Copyright (c) 2026, Manufacturing Addon and contributors
# For license information, please see license.txt

"""Container Loading portal — table entry from Packing Reports."""

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from manufacturing_addon.manufacturing_addon.doctype.shipment_loading.shipment_loading import (
	CONTAINER_SPECS,
	get_or_create_shipment_loading,
	get_order_sheet_cartons,
	sync_shipment_loading_for_order_sheet,
)


@frappe.whitelist()
def get_portal_board(order_sheet=None, packing_report=None, only_pending=0, container_no=None):
	"""Return carton table rows for the Container Loading portal."""
	if not order_sheet:
		frappe.throw(_("Select Order Sheet first."))

	payload = get_order_sheet_cartons(
		order_sheet=order_sheet,
		packing_report=packing_report or None,
		sync=1,
	)
	cartons = payload.get("cartons") or []
	if cint(only_pending):
		cartons = [row for row in cartons if not cint(row.get("is_loaded"))]

	container_filter = (container_no or "").strip()
	if container_filter:
		cartons = [
			row
			for row in cartons
			if container_filter.lower() in cstr(row.get("container_no")).lower()
		]

	rows = []
	for row in cartons:
		count = cint(row.get("carton_count")) or 1
		load_qty = cint(row.get("load_cartons"))
		if cint(row.get("is_loaded")) and load_qty <= 0:
			load_qty = count
		per_cbm = flt(row.get("per_carton_cbm"))
		if not per_cbm and count:
			per_cbm = flt(row.get("cbm")) / count
		rows.append(
			{
				"name": row.get("name"),
				"packing_report": row.get("packing_report"),
				"so_item": row.get("so_item"),
				"article": row.get("article"),
				"colour": row.get("colour"),
				"finished_size": row.get("finished_size"),
				"qty_in_carton": flt(row.get("qty_in_carton")),
				"carton_count": count,
				"load_cartons": load_qty,
				"total_pieces": flt(row.get("total_pieces")),
				"per_carton_cbm": per_cbm,
				"cbm": flt(row.get("cbm")) or (per_cbm * count),
				"carton_dimension": row.get("carton_dimension"),
				"is_loaded": cint(row.get("is_loaded")),
				"container_no": row.get("container_no") or "",
				"loading_tag": row.get("loading_tag") or "",
				"remarks": row.get("remarks") or "",
			}
		)

	summary = payload.get("summary") or {}
	return {
		"shipment_loading": payload.get("shipment_loading"),
		"rows": rows,
		"summary": {
			"total_cartons": cint(summary.get("total_cartons")),
			"loaded_cartons": cint(summary.get("loaded_cartons")),
			"pending_cartons": cint(summary.get("pending_cartons")),
			"total_pieces_ready": flt(summary.get("total_pieces_ready")),
			"status": summary.get("status") or "Pending",
			"container_type": summary.get("container_type") or "20ft FCL",
			"container_no": summary.get("container_no") or "",
			"total_cbm": flt(summary.get("total_cbm")),
			"loaded_cbm": flt(summary.get("loaded_cbm")),
			"shipment_loading": payload.get("shipment_loading"),
		},
		"container_types": list(CONTAINER_SPECS.keys()) + ["Truck", "LCL"],
		"container_nos": search_container_nos(txt="", limit=50),
	}


def cstr(value):
	return "" if value is None else str(value)


@frappe.whitelist()
def search_container_nos(txt=None, limit=20):
	"""Autocomplete source for Container No (from prior loadings)."""
	txt = (txt or "").strip()
	limit = cint(limit) or 20
	like = f"%{txt}%"
	rows = frappe.db.sql(
		"""
		select container_no, count(*) as uses
		from (
			select container_no from `tabShipment Loading`
			where ifnull(container_no, '') != ''
			union all
			select container_no from `tabShipment Loading Carton`
			where ifnull(container_no, '') != ''
		) t
		where %(txt)s = '' or container_no like %(like)s
		group by container_no
		order by uses desc, container_no asc
		limit %(limit)s
		""",
		{"txt": txt, "like": like, "limit": limit},
		as_dict=True,
	)
	return [r.container_no for r in rows if r.container_no]


@frappe.whitelist()
def save_portal_header(order_sheet, container_type=None, container_no=None):
	"""Save container header fields on Shipment Loading."""
	if not order_sheet:
		frappe.throw(_("Order Sheet is required."))
	sync_shipment_loading_for_order_sheet(order_sheet)
	doc = get_or_create_shipment_loading(order_sheet)
	if container_type:
		doc.container_type = container_type
	if container_no is not None:
		doc.container_no = container_no
	doc.update_totals()
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def save_portal_rows(order_sheet, rows=None, container_no=None, loading_tag=None):
	"""Mark selected carton rows loaded / unloaded from the portal table.

	rows: [{name, is_loaded, load_cartons, container_no, remarks}]
	"""
	if not order_sheet:
		frappe.throw(_("Order Sheet is required."))

	rows = frappe.parse_json(rows) if isinstance(rows, str) else (rows or [])
	if not rows:
		frappe.throw(_("Nothing to save."))

	doc = get_or_create_shipment_loading(order_sheet)
	by_name = {row.name: row for row in (doc.cartons or [])}
	updated = 0
	header_container = (container_no or doc.container_no or "").strip()

	for entry in rows:
		name = entry.get("name")
		if not name or name not in by_name:
			continue
		row = by_name[name]
		want_loaded = cint(entry.get("is_loaded"))
		was_loaded = cint(row.is_loaded)
		ready = cint(row.carton_count) or 1
		load_qty = cint(entry.get("load_cartons"))
		if want_loaded:
			if load_qty <= 0:
				load_qty = ready
			load_qty = min(max(load_qty, 0), ready)
		else:
			load_qty = 0

		row_container = (entry.get("container_no") or header_container or row.container_no or "").strip()

		changed = False
		if want_loaded and not was_loaded:
			row.is_loaded = 1
			row.load_cartons = load_qty
			row.loaded_by = frappe.session.user
			row.loaded_on = now_datetime()
			row.loading_tag = entry.get("loading_tag") or loading_tag or row.loading_tag or "Manual"
			row.container_no = row_container
			changed = True
		elif not want_loaded and was_loaded:
			row.is_loaded = 0
			row.load_cartons = 0
			row.loaded_by = None
			row.loaded_on = None
			row.position_row = None
			row.position_col = None
			row.position_layer = 0
			changed = True
		elif want_loaded and was_loaded:
			if cint(row.load_cartons) != load_qty:
				row.load_cartons = load_qty
				changed = True
			if row_container and row.container_no != row_container:
				row.container_no = row_container
				changed = True

		if entry.get("remarks") is not None and (row.remarks or "") != (entry.get("remarks") or ""):
			row.remarks = entry.get("remarks")
			changed = True

		if entry.get("container_no") is not None and not want_loaded:
			# allow updating container on pending rows too
			if (entry.get("container_no") or "") != (row.container_no or ""):
				row.container_no = entry.get("container_no") or ""
				changed = True

		if changed:
			updated += 1

	if container_no is not None:
		doc.container_no = container_no

	doc.update_totals()
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"updated": updated,
		"status": doc.status,
		"loaded_cartons": doc.loaded_cartons,
		"pending_cartons": doc.pending_cartons,
	}
