# Copyright (c) 2026, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, today, date_diff


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Order Sheet"),    "fieldname": "order_sheet",    "fieldtype": "Link",    "options": "Order Sheet", "width": 190},
		{"label": _("Customer"),       "fieldname": "customer",       "fieldtype": "Link",    "options": "Customer",    "width": 160},
		{"label": _("Shipment Date"),  "fieldname": "shipment_date",  "fieldtype": "Date",    "width": 110},
		{"label": _("Order Qty"),      "fieldname": "order_qty",      "fieldtype": "Float",   "precision": "0", "width": 95},
		{"label": _("Days Left"),      "fieldname": "days_remaining", "fieldtype": "Int",     "width": 80},
		{"label": _("Delayed Days"),   "fieldname": "delayed_days",   "fieldtype": "Int",     "width": 100},
		{"label": _("Daily Target"),   "fieldname": "daily_target",   "fieldtype": "Float",   "precision": "0", "width": 110},
		{"label": _("Weekly Target"),  "fieldname": "weekly_target",  "fieldtype": "Float",   "precision": "0", "width": 115},
		# ── Cutting ──────────────────────────────────────
		{"label": _("Total Cut"),        "fieldname": "total_cut",         "fieldtype": "Float", "precision": "0", "width": 95},
		{"label": _("Pending Cut"),      "fieldname": "pending_cut",       "fieldtype": "Float", "precision": "0", "width": 95},
		{"label": _("Cut %"),            "fieldname": "cut_pct",           "fieldtype": "Percent", "width": 75},
		{"label": _("Cut Avg/Day"),      "fieldname": "avg_daily_cut",     "fieldtype": "Float", "precision": "0", "width": 95},
		{"label": _("Cut Need/Day"),     "fieldname": "needed_daily_cut",  "fieldtype": "Float", "precision": "0", "width": 100},
		{"label": _("Today Cut"),        "fieldname": "today_cut",         "fieldtype": "Float", "precision": "0", "width": 90},
		# ── Stitching ─────────────────────────────────────
		{"label": _("Total Stitch"),     "fieldname": "total_stitch",      "fieldtype": "Float", "precision": "0", "width": 100},
		{"label": _("Pending Stitch"),   "fieldname": "pending_stitch",    "fieldtype": "Float", "precision": "0", "width": 105},
		{"label": _("Stitch %"),         "fieldname": "stitch_pct",        "fieldtype": "Percent", "width": 75},
		{"label": _("Stitch Avg/Day"),   "fieldname": "avg_daily_stitch",  "fieldtype": "Float", "precision": "0", "width": 105},
		{"label": _("Stitch Need/Day"),  "fieldname": "needed_daily_stitch", "fieldtype": "Float", "precision": "0", "width": 110},
		{"label": _("Today Stitch"),     "fieldname": "today_stitch",      "fieldtype": "Float", "precision": "0", "width": 100},
		# ── Checking ──────────────────────────────────────
		{"label": _("Total Check"),      "fieldname": "total_check",       "fieldtype": "Float", "precision": "0", "width": 100},
		{"label": _("Pending Check"),    "fieldname": "pending_check",     "fieldtype": "Float", "precision": "0", "width": 105},
		{"label": _("Check %"),          "fieldname": "check_pct",         "fieldtype": "Percent", "width": 75},
		{"label": _("Check Avg/Day"),    "fieldname": "avg_daily_check",   "fieldtype": "Float", "precision": "0", "width": 105},
		{"label": _("Check Need/Day"),   "fieldname": "needed_daily_check", "fieldtype": "Float", "precision": "0", "width": 110},
		{"label": _("Today Check"),      "fieldname": "today_check",       "fieldtype": "Float", "precision": "0", "width": 100},
		# ── Packing ───────────────────────────────────────
		{"label": _("Total Pack"),       "fieldname": "total_pack",        "fieldtype": "Float", "precision": "0", "width": 95},
		{"label": _("Pending Pack"),     "fieldname": "pending_pack",      "fieldtype": "Float", "precision": "0", "width": 100},
		{"label": _("Pack %"),           "fieldname": "pack_pct",          "fieldtype": "Percent", "width": 75},
		{"label": _("Pack Avg/Day"),     "fieldname": "avg_daily_pack",    "fieldtype": "Float", "precision": "0", "width": 100},
		{"label": _("Pack Need/Day"),    "fieldname": "needed_daily_pack", "fieldtype": "Float", "precision": "0", "width": 105},
		{"label": _("Today Pack"),       "fieldname": "today_pack",        "fieldtype": "Float", "precision": "0", "width": 90},
		# ── Status ────────────────────────────────────────
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 115},
	]


def get_data(filters):
	report_date = filters.get("report_date") or today()

	# ── Build order sheet query ───────────────────────────
	conditions = ["os.docstatus = 1"]
	os_values = {}

	if filters.get("from_shipment"):
		conditions.append("os.shipment_date >= %(from_shipment)s")
		os_values["from_shipment"] = filters["from_shipment"]
	if filters.get("to_shipment"):
		conditions.append("os.shipment_date <= %(to_shipment)s")
		os_values["to_shipment"] = filters["to_shipment"]
	if filters.get("customer"):
		conditions.append("os.customer = %(customer)s")
		os_values["customer"] = filters["customer"]
	if filters.get("order_sheet"):
		conditions.append("os.name = %(order_sheet)s")
		os_values["order_sheet"] = filters["order_sheet"]

	where = " AND ".join(conditions)

	order_sheets = frappe.db.sql(
		f"""
		SELECT
			os.name        AS order_sheet,
			os.customer,
			os.shipment_date,
			IFNULL(NULLIF(os.total_order_qty, 0), os.total_quantity) AS order_qty
		FROM `tabOrder Sheet` os
		WHERE {where}
		ORDER BY os.shipment_date ASC, os.name
		""",
		os_values,
		as_dict=True,
	)

	if not order_sheets:
		return []

	os_names = [row.order_sheet for row in order_sheets]
	in_ph = "({})".format(", ".join(["%s"] * len(os_names)))

	# ── Helper: cumulative totals + active days per order_sheet ──
	def get_stage_stats(report_dt, ct_dt, qty_col):
		rows = frappe.db.sql(
			f"""
			SELECT
				cr.order_sheet,
				IFNULL(SUM(crct.{qty_col}), 0)  AS total_qty,
				COUNT(DISTINCT cr.date)           AS active_days
			FROM `tab{report_dt}` cr
			JOIN `tab{ct_dt}` crct ON crct.parent = cr.name
			WHERE cr.docstatus = 1
			  AND cr.order_sheet IN {in_ph}
			GROUP BY cr.order_sheet
			""",
			tuple(os_names),
			as_dict=True,
		)
		return {
			r.order_sheet: {
				"total": flt(r.total_qty),
				"days":  max(int(r.active_days or 1), 1),
			}
			for r in rows
		}

	# ── Helper: today's production ────────────────────────
	def get_today_qty(report_dt, ct_dt, qty_col):
		rows = frappe.db.sql(
			f"""
			SELECT cr.order_sheet, IFNULL(SUM(crct.{qty_col}), 0) AS qty
			FROM `tab{report_dt}` cr
			JOIN `tab{ct_dt}` crct ON crct.parent = cr.name
			WHERE cr.docstatus = 1
			  AND cr.order_sheet IN {in_ph}
			  AND cr.date = %s
			GROUP BY cr.order_sheet
			""",
			tuple(os_names) + (report_date,),
			as_dict=True,
		)
		return {r.order_sheet: flt(r.qty) for r in rows}

	# Cumulative stage stats
	cut_stats    = get_stage_stats("Cutting Report",   "Cutting Report CT",   "cutting_qty")
	stitch_stats = get_stage_stats("Stitching Report", "Stitching Report CT", "stitching_qty")
	check_stats  = get_stage_stats("Checking Report",  "Checking Report CT",  "checking_qty")
	pack_stats   = get_stage_stats("Packing Report",   "Packing Report CT",   "packaging_qty")

	# Today's production
	cut_today    = get_today_qty("Cutting Report",   "Cutting Report CT",   "cutting_qty")
	stitch_today = get_today_qty("Stitching Report", "Stitching Report CT", "stitching_qty")
	check_today  = get_today_qty("Checking Report",  "Checking Report CT",  "checking_qty")
	pack_today   = get_today_qty("Packing Report",   "Packing Report CT",   "packaging_qty")

	# ── Build result rows ─────────────────────────────────
	status_filter = filters.get("status") or "All"
	data = []

	for row in order_sheets:
		os_name       = row.order_sheet
		order_qty     = flt(row.order_qty)
		shipment_date = row.shipment_date

		days_remaining = date_diff(shipment_date, report_date)
		delayed_days   = max(0, -days_remaining)

		# Per-stage cumulative totals
		cs = cut_stats.get(os_name,    {"total": 0, "days": 1})
		ss = stitch_stats.get(os_name, {"total": 0, "days": 1})
		chs = check_stats.get(os_name, {"total": 0, "days": 1})
		ps = pack_stats.get(os_name,   {"total": 0, "days": 1})

		tc  = cs["total"]
		ts  = ss["total"]
		tch = chs["total"]
		tp  = ps["total"]

		# Pending per stage
		pending_cut    = max(order_qty - tc,  0)
		pending_stitch = max(order_qty - ts,  0)
		pending_check  = max(order_qty - tch, 0)
		pending_pack   = max(order_qty - tp,  0)

		# Percentage per stage
		def pct(done, total):
			return (done / total * 100) if total > 0 else 0

		cut_pct    = pct(tc,  order_qty)
		stitch_pct = pct(ts,  order_qty)
		check_pct  = pct(tch, order_qty)
		pack_pct   = pct(tp,  order_qty)

		# Historical average daily rate per stage
		avg_daily_cut    = round(tc  / cs["days"],  1) if tc  > 0 else 0
		avg_daily_stitch = round(ts  / ss["days"],  1) if ts  > 0 else 0
		avg_daily_check  = round(tch / chs["days"], 1) if tch > 0 else 0
		avg_daily_pack   = round(tp  / ps["days"],  1) if tp  > 0 else 0

		# Needed daily rate per stage to finish on time
		def needed_rate(pending, days_left):
			if days_left > 0:
				return round(pending / days_left, 1)
			elif days_left == 0:
				return pending
			else:
				return 0  # already overdue

		needed_daily_cut    = needed_rate(pending_cut,    days_remaining)
		needed_daily_stitch = needed_rate(pending_stitch, days_remaining)
		needed_daily_check  = needed_rate(pending_check,  days_remaining)
		needed_daily_pack   = needed_rate(pending_pack,   days_remaining)

		# Packing-based overall daily / weekly target
		if days_remaining > 0:
			daily_target = needed_daily_pack
		elif days_remaining == 0:
			daily_target = pending_pack
		else:
			daily_target = 0

		weekly_target = daily_target * 7

		# ── Status logic ──────────────────────────────────
		if pack_pct >= 100:
			status = "Completed"
		elif days_remaining < 0:
			status = "Overdue"
		elif tc == 0 and ts == 0 and tch == 0 and tp == 0:
			status = "Not Started"
		else:
			today_cut_qty = flt(cut_today.get(os_name, 0))
			if order_qty > 0 and days_remaining > 0 and needed_daily_cut > 0:
				status = "On Track" if today_cut_qty >= needed_daily_cut * 0.85 else "Behind"
			else:
				status = "On Track"

		if status_filter not in ("All", "") and status != status_filter:
			continue

		data.append({
			"order_sheet":   os_name,
			"customer":      row.customer,
			"shipment_date": shipment_date,
			"order_qty":     order_qty,
			"days_remaining": days_remaining,
			"delayed_days":  delayed_days,
			"daily_target":  daily_target,
			"weekly_target": weekly_target,
			# Cutting
			"total_cut":          tc,
			"pending_cut":        pending_cut,
			"cut_pct":            cut_pct,
			"avg_daily_cut":      avg_daily_cut,
			"needed_daily_cut":   needed_daily_cut,
			"today_cut":          flt(cut_today.get(os_name, 0)),
			# Stitching
			"total_stitch":         ts,
			"pending_stitch":       pending_stitch,
			"stitch_pct":           stitch_pct,
			"avg_daily_stitch":     avg_daily_stitch,
			"needed_daily_stitch":  needed_daily_stitch,
			"today_stitch":         flt(stitch_today.get(os_name, 0)),
			# Checking
			"total_check":        tch,
			"pending_check":      pending_check,
			"check_pct":          check_pct,
			"avg_daily_check":    avg_daily_check,
			"needed_daily_check": needed_daily_check,
			"today_check":        flt(check_today.get(os_name, 0)),
			# Packing
			"total_pack":        tp,
			"pending_pack":      pending_pack,
			"pack_pct":          pack_pct,
			"avg_daily_pack":    avg_daily_pack,
			"needed_daily_pack": needed_daily_pack,
			"today_pack":        flt(pack_today.get(os_name, 0)),
			# Status
			"status": status,
		})

	return data
