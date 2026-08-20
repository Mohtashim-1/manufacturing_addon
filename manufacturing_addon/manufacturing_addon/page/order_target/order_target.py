# Copyright (c) 2026, mohtashim and contributors
# For license information, please see license.txt

"""Order Target page APIs — including assumption planner (does not write SO/OS)."""

import math
import re
import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, today


def _extract_ean(item_code):
	"""Pull trailing barcode/EAN from item code when present."""
	if not item_code:
		return ""
	match = re.search(r"(\d{8,14})$", str(item_code).strip())
	return match.group(1) if match else ""


def _stage_map(order_sheet, report_dt, ct_dt, qty_col):
	"""Sum stage qty per item.

	Returns exact keys (so_item, combo, colour) and a rollup by (so_item, colour)
	so FG Order Sheet rows (empty combo) still pick up component cutting/stitching.
	"""
	rows = frappe.db.sql(
		f"""
		SELECT
			IFNULL(crct.so_item, '') AS so_item,
			IFNULL(crct.combo_item, '') AS combo_item,
			IFNULL(crct.colour, '') AS colour,
			IFNULL(SUM(crct.{qty_col}), 0) AS qty,
			COUNT(DISTINCT cr.date) AS active_days
		FROM `tab{report_dt}` cr
		JOIN `tab{ct_dt}` crct ON crct.parent = cr.name
		WHERE cr.docstatus = 1 AND cr.order_sheet = %s
		GROUP BY crct.so_item, crct.combo_item, crct.colour
		""",
		(order_sheet,),
		as_dict=True,
	)
	exact = {}
	rollup = {}
	for r in rows:
		qty = flt(r.qty)
		days = max(cint(r.active_days) or 1, 1)
		ek = (r.so_item or "", r.combo_item or "", r.colour or "")
		exact[ek] = {"qty": qty, "days": days}
		rk = (r.so_item or "", r.colour or "")
		prev = rollup.get(rk, {"qty": 0, "days": 0})
		rollup[rk] = {"qty": prev["qty"] + qty, "days": max(prev["days"], days)}
	return {"exact": exact, "rollup": rollup}


def _stage_lookup(stage, so_item, combo_item, colour):
	"""Prefer exact combo match; if OS combo blank, use so_item+colour rollup."""
	empty = {"qty": 0, "days": 1}
	if not stage:
		return empty
	exact = stage.get("exact") or {}
	rollup = stage.get("rollup") or {}
	ek = (so_item or "", combo_item or "", colour or "")
	if ek in exact:
		return exact[ek]
	# FG OS lines often have empty combo while cut/stitch store components
	if not (combo_item or "").strip():
		return rollup.get((so_item or "", colour or ""), empty)
	return empty


@frappe.whitelist()
def get_assumption_board(order_sheet):
	"""Item board for delivery-date assumptions.

	Defaults assumption delivery from Order Sheet shipment_date, else Sales Order
	delivery_date. User may change dates; nothing is written back to OS/SO.
	Packed qty = SUM(packaging_qty) only (matches packing report).
	Pending / days use planned_qty (fallback order_qty).
	"""
	if not order_sheet:
		frappe.throw(_("Select Order Sheet first."))

	if not frappe.db.exists("Order Sheet", order_sheet):
		frappe.throw(_("Order Sheet {0} not found").format(order_sheet))

	os_meta = frappe.db.get_value(
		"Order Sheet",
		order_sheet,
		["name", "customer", "sales_order", "shipment_date", "docstatus"],
		as_dict=True,
	)

	# Default assumption delivery: Order Sheet shipment → Sales Order delivery (editable later)
	default_delivery = os_meta.shipment_date
	if not default_delivery and os_meta.sales_order:
		default_delivery = frappe.db.get_value("Sales Order", os_meta.sales_order, "delivery_date")
	default_delivery = str(default_delivery) if default_delivery else ""

	os_rows = frappe.db.sql(
		"""
		SELECT
			osct.name AS row_name,
			osct.idx,
			IFNULL(osct.so_item, '') AS so_item,
			IFNULL(osct.combo_item, '') AS combo_item,
			IFNULL(osct.colour, '') AS colour,
			IFNULL(osct.stitching_article_no, IFNULL(osct.design, '')) AS article,
			IFNULL(osct.size, '') AS size,
			IFNULL(osct.order_qty, 0) AS order_qty,
			IFNULL(osct.planned_qty, 0) AS planned_qty
		FROM `tabOrder Sheet CT` osct
		WHERE osct.parent = %s
		ORDER BY osct.idx
		""",
		(order_sheet,),
		as_dict=True,
	)

	cut_map = _stage_map(order_sheet, "Cutting Report", "Cutting Report CT", "cutting_qty")
	stitch_map = _stage_map(order_sheet, "Stitching Report", "Stitching Report CT", "stitching_qty")
	check_map = _stage_map(order_sheet, "Checking Report", "Checking Report CT", "checking_qty")
	pack_map = _stage_map(order_sheet, "Packing Report", "Packing Report CT", "packaging_qty")

	items = []
	for row in os_rows:
		oq = flt(row.order_qty)
		# Same rule as Order Sheet: planned drives production math; fallback to order qty
		pq = flt(row.planned_qty) if flt(row.planned_qty) else oq
		cut = _stage_lookup(cut_map, row.so_item, row.combo_item, row.colour)
		stitch = _stage_lookup(stitch_map, row.so_item, row.combo_item, row.colour)
		check = _stage_lookup(check_map, row.so_item, row.combo_item, row.colour)
		pack = _stage_lookup(pack_map, row.so_item, row.combo_item, row.colour)

		cut_done = flt(cut["qty"])
		stitch_done = flt(stitch["qty"])
		check_done = flt(check["qty"])
		pack_done = flt(pack["qty"])
		# Pending vs planned (packing complete when packed >= planned)
		pending = max(pq - pack_done, 0)
		# Historical packing avg (fallback suggestion)
		hist_daily = round(pack_done / pack["days"], 1) if pack_done > 0 else 0
		# Prefer rate needed to hit default delivery when still pending
		suggested_daily = hist_daily
		if pending > 0 and default_delivery:
			avail = date_diff(getdate(default_delivery), getdate(today()))
			if avail > 0:
				suggested_daily = round(pending / avail, 1) or hist_daily
		ean = _extract_ean(row.so_item) or _extract_ean(row.combo_item)

		items.append(
			{
				"row_name": row.row_name,
				"idx": row.idx,
				"so_item": row.so_item,
				"combo_item": row.combo_item,
				"colour": row.colour,
				"article": row.article,
				"size": row.size,
				"ean": ean,
				"order_qty": oq,
				"planned_qty": pq,
				"cut_done": cut_done,
				"stitch_done": stitch_done,
				"check_done": check_done,
				"pack_done": pack_done,
				"pending_qty": pending,
				"cut_pending": max(pq - cut_done, 0),
				"stitch_pending": max(pq - stitch_done, 0),
				"check_pending": max(pq - check_done, 0),
				"suggested_daily": suggested_daily if pending > 0 else "",
				# Default from OS/SO — user may change; not written back to documents
				"assumption_delivery_date": default_delivery,
				"assumed_daily_rate": suggested_daily if pending > 0 else "",
			}
		)

	return {
		"order_sheet": os_meta.name,
		"customer": os_meta.customer,
		"sales_order": os_meta.sales_order,
		"order_sheet_shipment_date": os_meta.shipment_date,
		"default_delivery_date": default_delivery,
		"as_of": today(),
		"items": items,
		"note": _(
			"Assumption planner only. Changing dates here does not update Sales Order or Order Sheet."
		),
	}


@frappe.whitelist()
def calculate_assumption_days(rows=None, as_of=None):
	"""Pure calculation helper for assumption planner (no document writes).

	Days Needed   = ceil(Pending ÷ Assumed Pcs/Day)   (0 when Pending = 0)
	Days Available = Assumption Delivery − As Of
	Buffer         = Days Available − Days Needed
	  - when Pending = 0 (Done): Buffer = 0 (ignore past/future delivery for risk)
	"""
	rows = frappe.parse_json(rows) if isinstance(rows, str) else (rows or [])
	as_of = getdate(as_of or today())
	out = []
	selected_needed = []
	selected_available = []

	for row in rows:
		pending = flt(row.get("pending_qty"))
		rate = flt(row.get("assumed_daily_rate"))
		delivery = row.get("assumption_delivery_date")
		days_needed = None
		days_available = None
		buffer_days = None
		status = "Set date & rate"
		is_done = pending <= 0

		if is_done:
			days_needed = 0
			status = "Done"
		elif rate > 0:
			days_needed = int(math.ceil(pending / rate))

		if delivery:
			days_available = date_diff(getdate(delivery), as_of)

		if is_done:
			# Finished vs planned — do not flag past delivery as risk
			buffer_days = 0
			status = "Done"
		elif days_needed is not None and days_available is not None:
			buffer_days = days_available - days_needed
			if days_available < 0:
				status = "Past date"
			elif buffer_days < 0:
				status = "Not enough days"
			elif buffer_days == 0:
				status = "Tight"
			else:
				status = "OK"
		elif delivery and days_needed is None:
			status = "Set daily rate"
		elif not delivery and days_needed is not None:
			status = "Set delivery date"

		out.append(
			{
				"row_name": row.get("row_name"),
				"days_needed": days_needed,
				"days_available": days_available,
				"buffer_days": buffer_days,
				"status": status,
			}
		)

		# Summary risk only from selected rows that still have pending work
		if cint(row.get("selected")) and not is_done:
			if days_needed is not None:
				selected_needed.append(days_needed)
			if days_available is not None:
				selected_available.append(days_available)

	summary = {
		"selected_count": sum(1 for r in rows if cint(r.get("selected"))),
		"pending_selected": sum(1 for r in rows if cint(r.get("selected")) and flt(r.get("pending_qty")) > 0),
		"max_days_needed": max(selected_needed) if selected_needed else 0 if any(
			cint(r.get("selected")) and flt(r.get("pending_qty")) <= 0 for r in rows
		) else None,
		"min_days_available": min(selected_available) if selected_available else None,
		"as_of": str(as_of),
	}
	# If everything selected is Done, show clean zeros
	if summary["pending_selected"] == 0 and summary["selected_count"] > 0:
		summary["max_days_needed"] = 0
		summary["min_days_available"] = None
		summary["buffer_days"] = 0
		summary["can_finish"] = True
	elif summary["max_days_needed"] is not None and summary["min_days_available"] is not None:
		summary["buffer_days"] = summary["min_days_available"] - summary["max_days_needed"]
		summary["can_finish"] = summary["buffer_days"] >= 0
	else:
		summary["buffer_days"] = None
		summary["can_finish"] = None

	return {"rows": out, "summary": summary}
