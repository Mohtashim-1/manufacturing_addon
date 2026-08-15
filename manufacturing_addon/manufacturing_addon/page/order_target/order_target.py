# Copyright (c) 2026, mohtashim and contributors
# For license information, please see license.txt

"""Order Target page APIs — including assumption planner (does not write SO/OS)."""

import math

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, today


@frappe.whitelist()
def get_order_drill_down(order_sheet):
	"""Return item/combo-level production breakdown for one Order Sheet."""

	def get_production_by_combo(report_dt, ct_dt, qty_col):
		rows = frappe.db.sql(
			f"""
			SELECT
				IFNULL(crct.combo_item, '')     AS combo_item,
				IFNULL(crct.colour, '')          AS colour,
				IFNULL(crct.article, '')         AS article,
				IFNULL(SUM(crct.{qty_col}), 0)  AS qty,
				COUNT(DISTINCT cr.date)          AS active_days
			FROM `tab{report_dt}` cr
			JOIN `tab{ct_dt}` crct ON crct.parent = cr.name
			WHERE cr.docstatus = 1
			  AND cr.order_sheet = %s
			GROUP BY crct.combo_item, crct.colour, crct.article
			ORDER BY crct.combo_item, crct.colour
			""",
			(order_sheet,),
			as_dict=True,
		)
		return {
			(r.combo_item, r.colour): {
				"qty": flt(r.qty),
				"days": max(int(r.active_days or 1), 1),
				"article": r.article,
			}
			for r in rows
		}, set(rows and [(r.combo_item, r.colour) for r in rows] or [])

	cut_map, cut_keys = get_production_by_combo("Cutting Report", "Cutting Report CT", "cutting_qty")
	stitch_map, stitch_keys = get_production_by_combo(
		"Stitching Report", "Stitching Report CT", "stitching_qty"
	)
	check_map, check_keys = get_production_by_combo(
		"Checking Report", "Checking Report CT", "checking_qty"
	)
	pack_map, pack_keys = get_production_by_combo("Packing Report", "Packing Report CT", "packaging_qty")

	all_keys = cut_keys | stitch_keys | check_keys | pack_keys

	os_items = frappe.db.sql(
		"""
		SELECT
			IFNULL(osct.combo_item, '')     AS combo_item,
			IFNULL(osct.colour, '')         AS colour,
			IFNULL(SUM(osct.order_qty), 0)  AS order_qty
		FROM `tabOrder Sheet CT` osct
		WHERE osct.parent = %s
		GROUP BY osct.combo_item, osct.colour
		""",
		(order_sheet,),
		as_dict=True,
	)
	order_map = {(r.combo_item, r.colour): flt(r.order_qty) for r in os_items}
	all_keys |= set(order_map.keys())

	def pct(done, total):
		return round(done / total * 100, 1) if total > 0 else 0

	result = []
	for key in sorted(all_keys):
		combo_item, colour = key
		oq = order_map.get(key, 0)

		cut_d = cut_map.get(key, {"qty": 0, "days": 1, "article": ""})
		stitch_d = stitch_map.get(key, {"qty": 0, "days": 1, "article": ""})
		check_d = check_map.get(key, {"qty": 0, "days": 1, "article": ""})
		pack_d = pack_map.get(key, {"qty": 0, "days": 1, "article": ""})

		article = cut_d["article"] or stitch_d["article"] or check_d["article"] or pack_d["article"]

		tc = cut_d["qty"]
		ts = stitch_d["qty"]
		tch = check_d["qty"]
		tp = pack_d["qty"]
		ref_qty = oq if oq > 0 else max(tc, ts, tch, tp)

		result.append(
			{
				"combo_item": combo_item or "—",
				"colour": colour or "—",
				"article": article,
				"order_qty": oq,
				"cut_done": tc,
				"cut_pending": max(ref_qty - tc, 0) if ref_qty > 0 else 0,
				"cut_pct": pct(tc, ref_qty),
				"cut_avg_d": round(tc / cut_d["days"], 1) if tc > 0 else 0,
				"stitch_done": ts,
				"stitch_pending": max(ref_qty - ts, 0) if ref_qty > 0 else 0,
				"stitch_pct": pct(ts, ref_qty),
				"stitch_avg_d": round(ts / stitch_d["days"], 1) if ts > 0 else 0,
				"check_done": tch,
				"check_pending": max(ref_qty - tch, 0) if ref_qty > 0 else 0,
				"check_pct": pct(tch, ref_qty),
				"check_avg_d": round(tch / check_d["days"], 1) if tch > 0 else 0,
				"pack_done": tp,
				"pack_pending": max(ref_qty - tp, 0) if ref_qty > 0 else 0,
				"pack_pct": pct(tp, ref_qty),
				"pack_avg_d": round(tp / pack_d["days"], 1) if tp > 0 else 0,
			}
		)

	return {"items": result}


def _stage_map(order_sheet, report_dt, ct_dt, qty_col):
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
	"""Item board for manual delivery-date assumptions.

	Never reads Sales Order delivery date into assumption fields.
	Does not write Order Sheet / Sales Order.
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

		items.append(
			{
				"row_name": row.row_name,
				"idx": row.idx,
				"so_item": row.so_item,
				"combo_item": row.combo_item,
				"colour": row.colour,
				"article": row.article,
				"size": row.size,
				"order_qty": oq,
				"pack_done": pack_done,
				"pending_qty": pending,
				"cut_done": flt(cut["qty"]),
				"stitch_done": flt(stitch["qty"]),
				"check_done": flt(check["qty"]),
				"suggested_daily": suggested_daily,
				# Blank on purpose — user fills assumption delivery date (not from SO)
				"assumption_delivery_date": "",
				"assumed_daily_rate": suggested_daily or "",
			}
		)

	return {
		"order_sheet": os_meta.name,
		"customer": os_meta.customer,
		"sales_order": os_meta.sales_order,
		# Reference only — not used as assumption default
		"order_sheet_shipment_date": os_meta.shipment_date,
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
