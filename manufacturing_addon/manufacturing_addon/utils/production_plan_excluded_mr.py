# Copyright (c) 2026, Manufacturing Addon and contributors
# License: MIT

"""Helpers for Production Plan Raw Materials exclusion / qty-change tracking."""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cstr, flt


QTY_TOLERANCE = 0.0001


def _row_as_dict(row):
	if isinstance(row, dict):
		src = row
	else:
		src = row.as_dict() if hasattr(row, "as_dict") else {}
	return {
		"item_code": cstr(src.get("item_code")),
		"item_name": cstr(src.get("item_name")),
		"quantity": flt(src.get("quantity") or src.get("required_bom_qty") or src.get("qty")),
		"uom": cstr(src.get("uom") or src.get("stock_uom")),
		"warehouse": cstr(src.get("warehouse")),
		"material_request_type": cstr(src.get("material_request_type")),
		"description": cstr(src.get("description")),
	}


def parse_json_list(raw):
	if not raw:
		return []
	if isinstance(raw, list):
		return raw
	try:
		data = json.loads(raw)
		return data if isinstance(data, list) else []
	except Exception:
		return []


def _aggregate_by_item(rows):
	"""Sum qty per item_code; keep first name/uom/warehouse."""
	agg = {}
	for row in rows or []:
		d = _row_as_dict(row)
		item = d["item_code"]
		if not item:
			continue
		if item not in agg:
			agg[item] = {
				"item_code": item,
				"item_name": d["item_name"],
				"quantity": 0.0,
				"uom": d["uom"],
				"warehouse": d["warehouse"],
			}
		agg[item]["quantity"] = flt(agg[item]["quantity"]) + flt(d["quantity"])
		if not agg[item]["item_name"] and d["item_name"]:
			agg[item]["item_name"] = d["item_name"]
		if not agg[item]["uom"] and d["uom"]:
			agg[item]["uom"] = d["uom"]
		if not agg[item]["warehouse"] and d["warehouse"]:
			agg[item]["warehouse"] = d["warehouse"]
	return agg


def get_mr_item_changes(fetched_rows, current_rows):
	"""Compare required vs current Raw Materials.

	Returns rows with change_type: Removed | Qty Reduced | Qty Increased | Added
	"""
	required = _aggregate_by_item(fetched_rows)
	current = _aggregate_by_item(current_rows)
	all_items = sorted(set(required.keys()) | set(current.keys()))

	changes = []
	for item in all_items:
		req_qty = flt(required.get(item, {}).get("quantity"))
		cur_qty = flt(current.get(item, {}).get("quantity"))
		meta = required.get(item) or current.get(item) or {}
		diff = flt(cur_qty - req_qty)

		if item in required and item not in current:
			change_type = "Removed"
		elif item not in required and item in current:
			change_type = "Added"
		elif abs(diff) <= QTY_TOLERANCE:
			continue
		elif diff < 0:
			change_type = "Qty Reduced"
		else:
			change_type = "Qty Increased"

		changes.append(
			{
				"item_code": item,
				"item_name": meta.get("item_name") or "",
				"uom": meta.get("uom") or "",
				"warehouse": meta.get("warehouse") or "",
				"required_qty": req_qty,
				"current_qty": cur_qty,
				"difference": diff,
				"quantity": req_qty if change_type == "Removed" else cur_qty,
				"change_type": change_type,
			}
		)

	order = {"Removed": 0, "Qty Reduced": 1, "Qty Increased": 2, "Added": 3}
	changes.sort(key=lambda r: (order.get(r["change_type"], 9), r["item_code"]))
	return changes


# Back-compat alias used by older callers
def get_excluded_mr_items(fetched_rows, current_rows):
	return [
		r
		for r in get_mr_item_changes(fetched_rows, current_rows)
		if r.get("change_type") == "Removed"
	]


def _change_badge(change_type):
	colors = {
		"Removed": "#f8d7da",
		"Qty Reduced": "#fff3cd",
		"Qty Increased": "#d1ecf1",
		"Added": "#d4edda",
	}
	bg = colors.get(change_type, "#eee")
	return (
		f'<span style="background:{bg};padding:2px 8px;border-radius:4px;'
		f'font-size:12px;white-space:nowrap;">{frappe.utils.escape_html(change_type)}</span>'
	)


def build_excluded_mr_items_html(change_rows, source_note=None):
	"""HTML table for removed / qty-changed purchase items."""
	note = source_note or _(
		"Compared required purchase items with current Raw Materials. "
		"Removed / reduced / increased quantities are listed for confirmation."
	)
	if not change_rows:
		return (
			'<div class="text-muted" style="padding:8px 0;">'
			+ _("No purchase-list changes. Required items and quantities match Raw Materials.")
			+ "</div>"
		)

	rows_html = []
	for i, row in enumerate(change_rows, start=1):
		rows_html.append(
			"<tr>"
			f"<td>{i}</td>"
			f"<td>{_change_badge(row.get('change_type') or '')}</td>"
			f"<td>{frappe.utils.escape_html(row.get('item_code') or '')}</td>"
			f"<td>{frappe.utils.escape_html(row.get('item_name') or '')}</td>"
			f"<td style='text-align:right'>{flt(row.get('required_qty'))}</td>"
			f"<td style='text-align:right'>{flt(row.get('current_qty'))}</td>"
			f"<td style='text-align:right'>{flt(row.get('difference'))}</td>"
			f"<td>{frappe.utils.escape_html(row.get('uom') or '')}</td>"
			f"<td>{frappe.utils.escape_html(row.get('warehouse') or '')}</td>"
			"</tr>"
		)

	return f"""
	<div class="alert alert-warning" style="margin-bottom:8px;">
		<strong>{_("Purchase list changes")}</strong><br>
		{note}
	</div>
	<div class="table-responsive">
		<table class="table table-bordered table-condensed" style="margin:0;">
			<thead>
				<tr>
					<th>#</th>
					<th>{_("Change")}</th>
					<th>{_("Item Code")}</th>
					<th>{_("Item Name")}</th>
					<th style="text-align:right">{_("Required Qty")}</th>
					<th style="text-align:right">{_("Current Qty")}</th>
					<th style="text-align:right">{_("Difference")}</th>
					<th>{_("UOM")}</th>
					<th>{_("Warehouse")}</th>
				</tr>
			</thead>
			<tbody>
				{''.join(rows_html)}
			</tbody>
		</table>
	</div>
	"""


def _fetch_required_mr_items(doc):
	"""Recompute full required purchase list (ignore stock netting for fair compare)."""
	from erpnext.manufacturing.doctype.production_plan.production_plan import (
		get_items_for_material_requests,
	)

	# ERPNext accesses doc.sub_assembly_items as attributes — needs frappe._dict
	raw = doc if isinstance(doc, dict) else doc.as_dict()
	doc_copy = frappe._dict(raw)
	doc_copy.ignore_existing_ordered_qty = 1
	doc_copy.mr_items = []
	# Child tables must remain list-like attribute access
	for key in ("po_items", "sub_assembly_items", "mr_items", "material_requests"):
		if key in doc_copy and isinstance(doc_copy[key], list):
			doc_copy[key] = [frappe._dict(r) if isinstance(r, dict) else r for r in doc_copy[key]]

	warehouses = []
	for_warehouse = doc_copy.get("for_warehouse")
	if for_warehouse:
		warehouses = [{"warehouse": for_warehouse}]

	try:
		items = get_items_for_material_requests(doc_copy, warehouses=warehouses) or []
	except Exception:
		frappe.log_error(frappe.get_traceback(), "PP excluded MR live fetch failed")
		return []

	return [_row_as_dict(row) for row in items]


def sync_excluded_mr_items_on_doc(doc):
	"""Update excluded/changed JSON on Production Plan from snapshot/live vs current mr_items."""
	if not doc.meta.has_field("custom_mr_items_fetched_json"):
		return []

	# Preserve current rows — live fetch clears mr_items on the dict
	current = list(doc.get("mr_items") or [])
	fetched = parse_json_list(doc.get("custom_mr_items_fetched_json"))
	if not fetched:
		fetched = _fetch_required_mr_items(doc)
		if fetched and doc.meta.has_field("custom_mr_items_fetched_json"):
			doc.custom_mr_items_fetched_json = json.dumps(fetched, default=str)

	changes = get_mr_item_changes(fetched, current)
	if doc.meta.has_field("custom_excluded_mr_items_json"):
		doc.custom_excluded_mr_items_json = json.dumps(changes, default=str)
	return changes


@frappe.whitelist()
def get_excluded_mr_items_preview(doc):
	"""Return purchase-list changes + HTML for the Production Plan form (always).

	Shows Removed, Qty Reduced, Qty Increased, and Added rows.
	Uses saved snapshot if present; otherwise recomputes required MR items live.
	"""
	if isinstance(doc, str):
		doc = frappe.parse_json(doc)

	# Copy current rows first — get_items_for_material_requests clears doc["mr_items"]
	current = list(doc.get("mr_items") or [])

	fetched = parse_json_list(doc.get("custom_mr_items_fetched_json"))
	used_live = False
	if not fetched:
		fetched = _fetch_required_mr_items(doc)
		used_live = True

	changes = get_mr_item_changes(fetched, current)

	name = doc.get("name")
	if used_live and fetched and name and frappe.db.exists("Production Plan", name):
		if frappe.get_meta("Production Plan").has_field("custom_mr_items_fetched_json"):
			frappe.db.set_value(
				"Production Plan",
				name,
				"custom_mr_items_fetched_json",
				json.dumps(fetched, default=str),
				update_modified=False,
			)
		if frappe.get_meta("Production Plan").has_field("custom_excluded_mr_items_json"):
			frappe.db.set_value(
				"Production Plan",
				name,
				"custom_excluded_mr_items_json",
				json.dumps(changes, default=str),
				update_modified=False,
			)

	note = _(
		"Compared required purchase qty with current Raw Materials. "
		"Removed = not purchasing; Qty Reduced / Increased = user changed qty; Added = extra row not in required list."
	)
	if used_live:
		note = _(
			"Live recalculation of required purchase items vs current Raw Materials (no earlier fetch snapshot). "
			"Removed / reduced / increased / added rows are listed for confirmation."
		)

	return {
		"excluded": changes,  # full change list (kept key name for JS)
		"html": build_excluded_mr_items_html(changes, source_note=note),
		"fetched_count": len(fetched),
		"used_live": used_live,
	}
