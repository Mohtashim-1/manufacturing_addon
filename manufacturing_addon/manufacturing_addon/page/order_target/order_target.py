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
	"""Sum stage qty per item. For packing use packaging_qty only (finished_* is cumulative)."""
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
	out = {}
	for r in rows:
		key = (r.so_item or "", r.combo_item or "", r.colour or "")
		out[key] = {"qty": flt(r.qty), "days": max(cint(r.active_days) or 1, 1)}
	return out


@frappe.whitelist()
def get_assumption_board(order_sheet):
	"""Item board for delivery-date assumptions.

	Defaults assumption delivery from Order Sheet shipment_date, else Sales Order
	delivery_date. User may change dates; nothing is written back to OS/SO.
	Packed qty = SUM(packaging_qty) only (matches packing report).
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
			IFNULL(osct.order_qty, 0) AS order_qty
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
		key = (row.so_item or "", row.combo_item or "", row.colour or "")
		oq = flt(row.order_qty)
		cut = cut_map.get(key, {"qty": 0, "days": 1})
		stitch = stitch_map.get(key, {"qty": 0, "days": 1})
		check = check_map.get(key, {"qty": 0, "days": 1})
		pack = pack_map.get(key, {"qty": 0, "days": 1})

		pack_done = flt(pack["qty"])
		pending = max(oq - pack_done, 0)
		# Suggested daily rate from historical packing avg (assumption default only)
		suggested_daily = round(pack_done / pack["days"], 1) if pack_done > 0 else 0
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
				"pack_done": pack_done,
				"pending_qty": pending,
				"cut_done": flt(cut["qty"]),
				"stitch_done": flt(stitch["qty"]),
				"check_done": flt(check["qty"]),
				"suggested_daily": suggested_daily,
				# Default from OS/SO — user may change; not written back to documents
				"assumption_delivery_date": default_delivery,
				"assumed_daily_rate": suggested_daily or "",
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

	rows: [{pending_qty, assumed_daily_rate, assumption_delivery_date, selected}]
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

		if rate > 0 and pending > 0:
			days_needed = int(math.ceil(pending / rate))
		elif pending <= 0:
			days_needed = 0
			status = "Done"

		if delivery:
			days_available = date_diff(getdate(delivery), as_of)
			if days_needed is not None:
				buffer_days = days_available - days_needed
				if pending <= 0:
					status = "Done"
				elif days_available < 0:
					status = "Past date"
				elif buffer_days < 0:
					status = "Not enough days"
				elif buffer_days == 0:
					status = "Tight"
				else:
					status = "OK"
			else:
				status = "Set daily rate"

		out.append(
			{
				"row_name": row.get("row_name"),
				"days_needed": days_needed,
				"days_available": days_available,
				"buffer_days": buffer_days,
				"status": status,
			}
		)

		if cint(row.get("selected")):
			if days_needed is not None:
				selected_needed.append(days_needed)
			if days_available is not None:
				selected_available.append(days_available)

	summary = {
		"selected_count": sum(1 for r in rows if cint(r.get("selected"))),
		"max_days_needed": max(selected_needed) if selected_needed else None,
		"min_days_available": min(selected_available) if selected_available else None,
		"as_of": str(as_of),
	}
	if summary["max_days_needed"] is not None and summary["min_days_available"] is not None:
		summary["buffer_days"] = summary["min_days_available"] - summary["max_days_needed"]
		summary["can_finish"] = summary["buffer_days"] >= 0
	else:
		summary["buffer_days"] = None
		summary["can_finish"] = None

	return {"rows": out, "summary": summary}
