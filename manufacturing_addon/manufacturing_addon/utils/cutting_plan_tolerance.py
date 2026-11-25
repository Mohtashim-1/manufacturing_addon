# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

"""Planned vs cutting quantity tolerance (configurable allowance %)."""

import frappe
from frappe import _
from frappe.utils import cint, flt

DEFAULT_CUTTING_QTY_TOLERANCE_PERCENT = 10
SETTING_DOCTYPE = "Manufacturing Addon Setting"


def _setting_value(fieldname, default=None):
	"""Read a Manufacturing Addon Setting value; use default when never saved in Singles.

	Frappe returns 0 for unset Check/Float singles, which would wrongly disable
	enforcement / treat allowance as 0%. Prefer the field default when the row
	is missing from tabSingles.
	"""
	try:
		if not frappe.db.exists(
			"Singles", {"doctype": SETTING_DOCTYPE, "field": fieldname}
		):
			return default
		return frappe.db.get_single_value(SETTING_DOCTYPE, fieldname)
	except Exception:
		return default


def get_cutting_qty_tolerance_percent():
	"""Allowance % from Manufacturing Addon Setting (fallback 10)."""
	pct = _setting_value(
		"cutting_qty_tolerance_percent", DEFAULT_CUTTING_QTY_TOLERANCE_PERCENT
	)
	if pct is None or pct == "":
		return flt(DEFAULT_CUTTING_QTY_TOLERANCE_PERCENT)
	return flt(pct)


def is_cutting_plan_tolerance_enforced():
	"""Default ON when the setting has never been saved."""
	val = _setting_value("enforce_cutting_plan_tolerance", 1)
	if val is None or val == "":
		return True
	return bool(cint(val))


def should_block_under_plan_cutting():
	val = _setting_value("block_under_plan_cutting", 0)
	return bool(cint(val or 0))

def tolerance_ratio():
	return get_cutting_qty_tolerance_percent() / 100


@frappe.whitelist()
def get_cutting_allowance_settings():
	"""Client helper: allowance % and whether over-plan cutting is blocked."""
	return {
		"enforce": is_cutting_plan_tolerance_enforced(),
		"tolerance_percent": get_cutting_qty_tolerance_percent(),
		"block_under": should_block_under_plan_cutting(),
	}


def cutting_qty_limits(planned_qty):
	"""Return min_allowed, max_allowed, planned for finished-piece qty."""
	planned = flt(planned_qty)
	if planned <= 0:
		return 0, 0, 0
	delta = planned * tolerance_ratio()
	return planned - delta, planned + delta, planned


def finished_cutting_pieces(ct_row):
	"""Convert cumulative cutting qty on a report line to finished pieces."""
	return finished_report_pieces(
		ct_row,
		qty_field="cutting_qty",
		finished_field="finished_cutting_qty",
	)


def finished_report_pieces(ct_row, qty_field, finished_field):
	"""Convert cumulative report qty on a line to finished pieces (÷ pcs)."""
	pcs = flt(getattr(ct_row, "pcs", None)) or 1
	total = flt(getattr(ct_row, finished_field, None)) + flt(
		getattr(ct_row, qty_field, None)
	)
	if total <= 0:
		total = flt(getattr(ct_row, "total_copy1", None))
	return total / pcs if pcs else total


def tolerance_status(planned_qty, actual_pieces):
	min_allowed, max_allowed, planned = cutting_qty_limits(planned_qty)
	actual = flt(actual_pieces)
	pct = get_cutting_qty_tolerance_percent()
	base = {
		"planned_qty": planned,
		"min_allowed": min_allowed,
		"max_allowed": max_allowed,
		"actual_pieces": actual,
		"tolerance_pct": pct,
	}
	if planned <= 0:
		return {
			**base,
			"status": "No Plan",
			"planned_qty": 0,
			"min_allowed": 0,
			"max_allowed": 0,
			"variance": 0,
			"variance_pct": 0,
		}
	if actual < min_allowed:
		return {
			**base,
			"status": "Under",
			"variance": actual - planned,
			"variance_pct": ((actual - planned) / planned) * 100,
		}
	if actual > max_allowed:
		return {
			**base,
			"status": "Over",
			"variance": actual - planned,
			"variance_pct": ((actual - planned) / planned) * 100,
		}
	return {
		**base,
		"status": "Within",
		"variance": actual - planned,
		"variance_pct": ((actual - planned) / planned) * 100 if planned else 0,
	}


def _tolerance_error_message(row, actual, info, qty_label=None):
	item_label = row.so_item or _("Item")
	combo = (row.combo_item or "").strip()
	if combo:
		item_label = f"{item_label} / {combo}"
	pct = info.get("tolerance_pct", get_cutting_qty_tolerance_percent())
	qty_label = qty_label or _("qty")
	if info.get("status") == "Over":
		return _(
			"Row {0} ({1}): {2} {3} cannot exceed planned qty + allowance "
			"({4} + {5}% = max {6})."
		).format(
			row.idx,
			item_label,
			qty_label,
			frappe.format_value(actual, {"fieldtype": "Float"}),
			frappe.format_value(info["planned_qty"], {"fieldtype": "Float"}),
			frappe.format_value(pct, {"fieldtype": "Float"}),
			frappe.format_value(info["max_allowed"], {"fieldtype": "Float"}),
		)
	return _(
		"Row {0} ({1}): total {2} {3} is outside the allowed range "
		"{4} – {5} (planned {6} ± {7}%)."
	).format(
		row.idx,
		item_label,
		qty_label,
		frappe.format_value(actual, {"fieldtype": "Float"}),
		frappe.format_value(info["min_allowed"], {"fieldtype": "Float"}),
		frappe.format_value(info["max_allowed"], {"fieldtype": "Float"}),
		frappe.format_value(info["planned_qty"], {"fieldtype": "Float"}),
		frappe.format_value(pct, {"fieldtype": "Float"}),
	)


def validate_report_plan_tolerance(
	doc,
	child_table,
	qty_field,
	finished_field,
	report_label,
	qty_label=None,
):
	"""Block save when report qty exceeds planned qty + allowance %.

	By default only over-plan is blocked so progressive (partial) entry works.
	Under-plan blocking is optional via Manufacturing Addon Setting.
	"""
	if not is_cutting_plan_tolerance_enforced():
		return

	block_under = should_block_under_plan_cutting()
	blocked = {"Over"}
	if block_under:
		blocked.add("Under")

	for row in doc.get(child_table) or []:
		# Plan Qty on CT is component pieces (finished plan × pcs). Tolerance uses finished units.
		pcs = flt(getattr(row, "pcs", None)) or 1
		planned_component = flt(row.planned_qty)
		planned = planned_component / pcs if pcs else planned_component
		if planned <= 0:
			continue
		if flt(getattr(row, qty_field, None)) <= 0 and flt(
			getattr(row, finished_field, None)
		) <= 0:
			continue

		actual = finished_report_pieces(row, qty_field, finished_field)
		info = tolerance_status(planned, actual)
		if info["status"] not in blocked:
			continue

		frappe.throw(
			_tolerance_error_message(row, actual, info, qty_label=qty_label),
			title=_("{0} — Plan Tolerance").format(report_label),
		)


def validate_cutting_report_tolerance(doc):
	"""Block save when cutting qty is outside the configured plan band."""
	validate_report_plan_tolerance(
		doc,
		child_table="cutting_report_ct",
		qty_field="cutting_qty",
		finished_field="finished_cutting_qty",
		report_label=_("Cutting Report"),
		qty_label=_("cutting qty"),
	)


def validate_sub_assembly_report_tolerance(doc):
	"""Block save when sub-assembly qty exceeds planned qty + allowance %."""
	validate_report_plan_tolerance(
		doc,
		child_table="sub_assembly_report_ct",
		qty_field="sub_assembly_qty",
		finished_field="finished_sub_assembly_qty",
		report_label=_("Sub Assembly Report"),
		qty_label=_("sub assembly qty"),
	)


def _cutting_component_pieces(order_sheet, exclude_report=None):
	"""Map (so_item, combo_item) -> finished pieces cut from submitted reports."""
	filters = {"order_sheet": order_sheet, "docstatus": 1}
	if exclude_report:
		filters["name"] = ("!=", exclude_report)

	reports = frappe.get_all("Cutting Report", filters=filters, pluck="name")
	if not reports:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT
			crct.so_item,
			IFNULL(crct.combo_item, '') AS combo_item,
			SUM(IFNULL(crct.cutting_qty, 0)) AS cutting_qty
		FROM `tabCutting Report CT` crct
		WHERE crct.parent IN %(parents)s
		GROUP BY crct.so_item, IFNULL(crct.combo_item, '')
		""",
		{"parents": reports},
		as_dict=True,
	)
	out = {}
	for row in rows:
		key = (row.so_item, row.combo_item or "")
		out[key] = flt(row.cutting_qty)
	return out


def _component_pcs_map(so_item):
	pcs_map = {"": 1}
	try:
		item = frappe.get_doc("Item", so_item)
		for combo_row in getattr(item, "custom_product_combo_item", []) or []:
			if combo_row.item:
				pcs_map[combo_row.item] = flt(combo_row.pcs) or 1
	except Exception:
		pass
	return pcs_map


def actual_cutting_pieces_for_order_line(order_sheet, so_item, component_pieces=None):
	"""Best estimate of finished pieces cut for one Order Sheet item."""
	component_pieces = component_pieces or _cutting_component_pieces(order_sheet)
	pcs_map = _component_pcs_map(so_item)

	keys = [k for k in component_pieces if k[0] == so_item]
	if not keys:
		return 0

	piece_counts = []
	for _so_item, combo_item in keys:
		raw = flt(component_pieces.get((_so_item, combo_item)))
		if raw <= 0:
			continue
		pcs = flt(pcs_map.get(combo_item)) or 1
		piece_counts.append(raw / pcs)

	if not piece_counts:
		return 0
	# Combo set completion is limited by the slowest component.
	return min(piece_counts) if len(piece_counts) > 1 else piece_counts[0]


@frappe.whitelist()
def get_cutting_plan_tolerance_dashboard(
	customer=None,
	order_sheet=None,
	status=None,
	sales_order=None,
):
	"""Dashboard rows: planned qty vs cutting with configurable ±% band."""
	tolerance_pct = get_cutting_qty_tolerance_percent()
	conditions = ["os.docstatus < 2", "IFNULL(osct.planned_qty, 0) > 0"]
	params = {}

	if customer:
		conditions.append("os.customer = %(customer)s")
		params["customer"] = customer
	if order_sheet:
		conditions.append("os.name = %(order_sheet)s")
		params["order_sheet"] = order_sheet
	if sales_order:
		conditions.append("os.sales_order = %(sales_order)s")
		params["sales_order"] = sales_order

	os_rows = frappe.db.sql(
		f"""
		SELECT
			os.name AS order_sheet,
			os.customer,
			os.sales_order,
			osct.so_item,
			IFNULL(osct.colour, '') AS colour,
			IFNULL(osct.size, '') AS size,
			IFNULL(osct.planned_qty, 0) AS planned_qty,
			IFNULL(osct.order_qty, 0) AS order_qty
		FROM `tabOrder Sheet` os
		INNER JOIN `tabOrder Sheet CT` osct ON osct.parent = os.name
		WHERE {' AND '.join(conditions)}
		ORDER BY os.name, osct.idx
		""",
		params,
		as_dict=True,
	)

	# Preload cutting totals per order sheet
	cutting_cache = {}
	result = []
	summary = {"total": 0, "within": 0, "over": 0, "under": 0, "no_cutting": 0}

	for row in os_rows:
		os_name = row.order_sheet
		if os_name not in cutting_cache:
			cutting_cache[os_name] = _cutting_component_pieces(os_name)

		actual = actual_cutting_pieces_for_order_line(
			os_name, row.so_item, cutting_cache[os_name]
		)
		info = tolerance_status(row.planned_qty, actual)
		status_value = info["status"]
		if actual <= 0 and status_value == "Within":
			status_value = "No Cutting"

		entry = {
			"order_sheet": os_name,
			"customer": row.customer,
			"sales_order": row.sales_order,
			"so_item": row.so_item,
			"colour": row.colour,
			"size": row.size,
			"order_qty": flt(row.order_qty),
			"planned_qty": info["planned_qty"],
			"min_allowed": info["min_allowed"],
			"max_allowed": info["max_allowed"],
			"actual_cutting_pieces": info["actual_pieces"],
			"variance": info["variance"],
			"variance_pct": round(info["variance_pct"], 2),
			"status": status_value,
			"tolerance_pct": tolerance_pct,
		}
		if status and status != "All" and entry["status"] != status:
			continue
		result.append(entry)

		summary["total"] += 1
		if status_value == "Within":
			summary["within"] += 1
		elif status_value == "Over":
			summary["over"] += 1
		elif status_value == "Under":
			summary["under"] += 1
		elif status_value == "No Cutting":
			summary["no_cutting"] += 1

	return {
		"rows": result,
		"summary": summary,
		"tolerance_pct": tolerance_pct,
	}
