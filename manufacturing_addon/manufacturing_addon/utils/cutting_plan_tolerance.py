# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

"""Planned vs cutting quantity tolerance (±10% by default)."""

import frappe
from frappe import _
from frappe.utils import flt

CUTTING_QTY_TOLERANCE_PERCENT = 10


def tolerance_ratio():
	return flt(CUTTING_QTY_TOLERANCE_PERCENT) / 100


def cutting_qty_limits(planned_qty):
	"""Return min_allowed, max_allowed, planned for finished-piece qty."""
	planned = flt(planned_qty)
	if planned <= 0:
		return 0, 0, 0
	delta = planned * tolerance_ratio()
	return planned - delta, planned + delta, planned


def finished_cutting_pieces(ct_row):
	"""Convert cumulative cutting qty on a report line to finished pieces."""
	pcs = flt(getattr(ct_row, "pcs", None)) or 1
	total = flt(getattr(ct_row, "finished_cutting_qty", None)) + flt(
		getattr(ct_row, "cutting_qty", None)
	)
	if total <= 0:
		total = flt(getattr(ct_row, "total_copy1", None))
	return total / pcs if pcs else total


def tolerance_status(planned_qty, actual_pieces):
	min_allowed, max_allowed, planned = cutting_qty_limits(planned_qty)
	actual = flt(actual_pieces)
	if planned <= 0:
		return {
			"status": "No Plan",
			"planned_qty": 0,
			"min_allowed": 0,
			"max_allowed": 0,
			"actual_pieces": actual,
			"variance": 0,
			"variance_pct": 0,
		}
	if actual < min_allowed:
		return {
			"status": "Under",
			"planned_qty": planned,
			"min_allowed": min_allowed,
			"max_allowed": max_allowed,
			"actual_pieces": actual,
			"variance": actual - planned,
			"variance_pct": ((actual - planned) / planned) * 100,
		}
	if actual > max_allowed:
		return {
			"status": "Over",
			"planned_qty": planned,
			"min_allowed": min_allowed,
			"max_allowed": max_allowed,
			"actual_pieces": actual,
			"variance": actual - planned,
			"variance_pct": ((actual - planned) / planned) * 100,
		}
	return {
		"status": "Within",
		"planned_qty": planned,
		"min_allowed": min_allowed,
		"max_allowed": max_allowed,
		"actual_pieces": actual,
		"variance": actual - planned,
		"variance_pct": ((actual - planned) / planned) * 100 if planned else 0,
	}


def validate_cutting_report_tolerance(doc):
	"""Block save when cumulative cutting exceeds planned qty ± tolerance."""
	for row in doc.get("cutting_report_ct") or []:
		planned = flt(row.planned_qty)
		if planned <= 0:
			continue
		if flt(row.cutting_qty) <= 0 and flt(row.finished_cutting_qty) <= 0:
			continue

		actual = finished_cutting_pieces(row)
		info = tolerance_status(planned, actual)
		if info["status"] in ("Over", "Under"):
			item_label = row.so_item or _("Item")
			combo = (row.combo_item or "").strip()
			if combo:
				item_label = f"{item_label} / {combo}"
			frappe.throw(
				_(
					"Row {0} ({1}): total cutting qty {2} is outside the allowed range "
					"{3} – {4} (planned {5} ± {6}%)."
				).format(
					row.idx,
					item_label,
					frappe.format_value(actual, {"fieldtype": "Float"}),
					frappe.format_value(info["min_allowed"], {"fieldtype": "Float"}),
					frappe.format_value(info["max_allowed"], {"fieldtype": "Float"}),
					frappe.format_value(planned, {"fieldtype": "Float"}),
					CUTTING_QTY_TOLERANCE_PERCENT,
				),
				title=_("Cutting Report — Plan Tolerance"),
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
	"""Dashboard rows: planned qty vs cutting with ±10% tolerance band."""
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
			"tolerance_pct": CUTTING_QTY_TOLERANCE_PERCENT,
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
		"tolerance_pct": CUTTING_QTY_TOLERANCE_PERCENT,
	}
