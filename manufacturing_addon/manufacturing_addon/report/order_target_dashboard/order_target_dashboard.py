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
		{
			"label": _("Order Sheet"),
			"fieldname": "order_sheet",
			"fieldtype": "Link",
			"options": "Order Sheet",
			"width": 190,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 160,
		},
		{
			"label": _("Shipment Date"),
			"fieldname": "shipment_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Order Qty"),
			"fieldname": "order_qty",
			"fieldtype": "Float",
			"precision": "0",
			"width": 95,
		},
		{
			"label": _("Days Left"),
			"fieldname": "days_remaining",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Daily Target"),
			"fieldname": "daily_target",
			"fieldtype": "Float",
			"precision": "0",
			"width": 110,
		},
		{
			"label": _("Weekly Target"),
			"fieldname": "weekly_target",
			"fieldtype": "Float",
			"precision": "0",
			"width": 115,
		},
		# ── Cutting ──────────────────────────────────────
		{
			"label": _("Total Cut"),
			"fieldname": "total_cut",
			"fieldtype": "Float",
			"precision": "0",
			"width": 95,
		},
		{
			"label": _("Cut %"),
			"fieldname": "cut_pct",
			"fieldtype": "Percent",
			"width": 80,
		},
		{
			"label": _("Today Cut"),
			"fieldname": "today_cut",
			"fieldtype": "Float",
			"precision": "0",
			"width": 95,
		},
		# ── Stitching ─────────────────────────────────────
		{
			"label": _("Total Stitch"),
			"fieldname": "total_stitch",
			"fieldtype": "Float",
			"precision": "0",
			"width": 105,
		},
		{
			"label": _("Stitch %"),
			"fieldname": "stitch_pct",
			"fieldtype": "Percent",
			"width": 80,
		},
		{
			"label": _("Today Stitch"),
			"fieldname": "today_stitch",
			"fieldtype": "Float",
			"precision": "0",
			"width": 105,
		},
		# ── Checking ──────────────────────────────────────
		{
			"label": _("Total Check"),
			"fieldname": "total_check",
			"fieldtype": "Float",
			"precision": "0",
			"width": 100,
		},
		{
			"label": _("Check %"),
			"fieldname": "check_pct",
			"fieldtype": "Percent",
			"width": 80,
		},
		{
			"label": _("Today Check"),
			"fieldname": "today_check",
			"fieldtype": "Float",
			"precision": "0",
			"width": 105,
		},
		# ── Packing ───────────────────────────────────────
		{
			"label": _("Total Pack"),
			"fieldname": "total_pack",
			"fieldtype": "Float",
			"precision": "0",
			"width": 95,
		},
		{
			"label": _("Pack %"),
			"fieldname": "pack_pct",
			"fieldtype": "Percent",
			"width": 80,
		},
		{
			"label": _("Today Pack"),
			"fieldname": "today_pack",
			"fieldtype": "Float",
			"precision": "0",
			"width": 95,
		},
		# ── Status ────────────────────────────────────────
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 115,
		},
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
			os.total_order_qty AS order_qty
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

	# ── Helper: fetch production totals per order_sheet ───
	def get_totals(report_dt, ct_dt, qty_col, for_date=None):
		in_ph = "({})".format(", ".join(["%s"] * len(os_names)))
		date_cond = "AND cr.date = %s" if for_date else ""
		extra_val = (for_date,) if for_date else ()

		rows = frappe.db.sql(
			f"""
			SELECT cr.order_sheet, IFNULL(SUM(crct.{qty_col}), 0) AS qty
			FROM `tab{report_dt}` cr
			JOIN `tab{ct_dt}` crct ON crct.parent = cr.name
			WHERE cr.docstatus = 1
			  AND cr.order_sheet IN {in_ph}
			  {date_cond}
			GROUP BY cr.order_sheet
			""",
			tuple(os_names) + extra_val,
			as_dict=True,
		)
		return {r.order_sheet: flt(r.qty) for r in rows}

	# Cumulative totals (all submitted reports)
	cut_total    = get_totals("Cutting Report",   "Cutting Report CT",   "cutting_qty")
	stitch_total = get_totals("Stitching Report", "Stitching Report CT", "stitching_qty")
	check_total  = get_totals("Checking Report",  "Checking Report CT",  "checking_qty")
	pack_total   = get_totals("Packing Report",   "Packing Report CT",   "packaging_qty")

	# Today's production (reports whose date = report_date)
	cut_today    = get_totals("Cutting Report",   "Cutting Report CT",   "cutting_qty",    report_date)
	stitch_today = get_totals("Stitching Report", "Stitching Report CT", "stitching_qty",  report_date)
	check_today  = get_totals("Checking Report",  "Checking Report CT",  "checking_qty",   report_date)
	pack_today   = get_totals("Packing Report",   "Packing Report CT",   "packaging_qty",  report_date)

	# ── Build result rows ─────────────────────────────────
	status_filter = filters.get("status") or "All"
	data = []

	for row in order_sheets:
		os_name     = row.order_sheet
		order_qty   = flt(row.order_qty)
		shipment_date = row.shipment_date

		days_remaining = date_diff(shipment_date, report_date)

		tc  = flt(cut_total.get(os_name, 0))
		ts  = flt(stitch_total.get(os_name, 0))
		tch = flt(check_total.get(os_name, 0))
		tp  = flt(pack_total.get(os_name, 0))

		cut_pct    = (tc  / order_qty * 100) if order_qty else 0
		stitch_pct = (ts  / order_qty * 100) if order_qty else 0
		check_pct  = (tch / order_qty * 100) if order_qty else 0
		pack_pct   = (tp  / order_qty * 100) if order_qty else 0

		# Daily / weekly target based on remaining packing qty
		remaining_to_pack = max(order_qty - tp, 0)
		if days_remaining > 0:
			daily_target = remaining_to_pack / days_remaining
		elif days_remaining == 0:
			daily_target = remaining_to_pack
		else:
			daily_target = 0  # already overdue

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
			if order_qty > 0 and days_remaining > 0:
				cut_daily_needed = (order_qty - tc) / days_remaining
				# On Track if today produced >= 85 % of what's needed daily
				if today_cut_qty >= cut_daily_needed * 0.85:
					status = "On Track"
				else:
					status = "Behind"
			else:
				status = "On Track"

		# Apply status filter
		if status_filter not in ("All", "") and status != status_filter:
			continue

		data.append({
			"order_sheet":   os_name,
			"customer":      row.customer,
			"shipment_date": shipment_date,
			"order_qty":     order_qty,
			"days_remaining": days_remaining,
			"daily_target":  daily_target,
			"weekly_target": weekly_target,
			# Cutting
			"total_cut":   tc,
			"cut_pct":     cut_pct,
			"today_cut":   flt(cut_today.get(os_name, 0)),
			# Stitching
			"total_stitch":  ts,
			"stitch_pct":    stitch_pct,
			"today_stitch":  flt(stitch_today.get(os_name, 0)),
			# Checking
			"total_check":  tch,
			"check_pct":    check_pct,
			"today_check":  flt(check_today.get(os_name, 0)),
			# Packing
			"total_pack":  tp,
			"pack_pct":    pack_pct,
			"today_pack":  flt(pack_today.get(os_name, 0)),
			# Status
			"status": status,
		})

	return data
