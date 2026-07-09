# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

"""Split contractor work qty across styles on production reports."""

import frappe
from frappe import _
from frappe.utils import flt

from manufacturing_addon.manufacturing_addon.utils.report_style_contractor import (
	billing_amount_for_work,
)
from manufacturing_addon.manufacturing_addon.utils.subassembly_bom import resolve_subassembly_unit_qty


def sc_matches_style(sc, style_row):
	if sc.get("item_style_row") and style_row.get("name"):
		return sc.get("item_style_row") == style_row.get("name")
	return (sc.get("style") or "") == (style_row.get("style") or "")


def style_contractors_for_style(sc_rows, style_row):
	return [sc for sc in (sc_rows or []) if sc_matches_style(sc, style_row)]


def is_subassembly_style(style_row):
	from manufacturing_addon.manufacturing_addon.utils.report_style_contractor import (
		_is_subassembly_style,
	)

	return _is_subassembly_style(style_row)


def billable_amount_for_split(so_item, style_row, split_work_qty, sc_row=None):
	"""Billing amount for one contractor's share of work qty."""
	split_work_qty = flt(split_work_qty)
	if split_work_qty <= 0:
		return 0, 0

	is_sub = is_subassembly_style(style_row)
	style_qty = resolve_subassembly_unit_qty(so_item, style_row) if is_sub else (
		flt(style_row.get("qty") or 1) or 1
	)
	rate = flt((sc_row or {}).get("rate")) or flt(style_row.get("rate"))

	if is_sub:
		billable_qty = split_work_qty * style_qty
		amount = billable_qty * rate
	else:
		billable_qty = split_work_qty * style_qty
		amount = billing_amount_for_work(style_row, split_work_qty)

	return billable_qty, amount


def resolve_style_splits(style_row, sc_rows, work_qty, default_contractor=""):
	"""Return [(contractor, split_work_qty, sc_row), ...] for one style."""
	matching = style_contractors_for_style(sc_rows, style_row)
	work_qty = flt(work_qty)
	if not matching:
		contractor = default_contractor or "Unassigned"
		return [(contractor, work_qty, None)] if work_qty > 0 else []

	explicit = [sc for sc in matching if flt(sc.get("split_qty")) > 0]
	if len(matching) == 1 and not explicit:
		sc = matching[0]
		contractor = sc.get("contractor") or default_contractor or "Unassigned"
		return [(contractor, work_qty, sc)] if work_qty > 0 else []

	out = []
	for sc in matching:
		split_qty = flt(sc.get("split_qty"))
		if split_qty <= 0:
			continue
		contractor = sc.get("contractor") or default_contractor or "Unassigned"
		out.append((contractor, split_qty, sc))
	return out


def apply_split_qty_defaults(ct_row, work_qty_field):
	"""Set split_qty to full work qty when only one contractor row exists per style."""
	work_qty = flt(getattr(ct_row, work_qty_field, None))
	if work_qty <= 0:
		return

	by_style = {}
	for sc in ct_row.get("style_contractors") or []:
		if not sc.get("style"):
			continue
		by_style.setdefault(sc.style, []).append(sc)

	for _style, rows in by_style.items():
		if len(rows) == 1 and not flt(rows[0].get("split_qty")):
			rows[0].split_qty = work_qty
			_update_sc_amounts_from_split(ct_row.so_item, rows[0], work_qty)


def _style_row_for_sc(so_item, sc_row):
	item_style_row = sc_row.get("item_style_row")
	if item_style_row and so_item:
		for child_doctype in ("Style CT", "Stitching Style", "Packing Style", "Checking Style"):
			if not frappe.db.table_exists(child_doctype):
				continue
			if not frappe.db.exists(child_doctype, item_style_row):
				continue
			row = frappe.db.get_value(
				child_doctype,
				item_style_row,
				["style", "rate", "qty", "amount", "is_subassembly"],
				as_dict=True,
			)
			if row:
				return row
	return {
		"style": sc_row.get("style"),
		"rate": sc_row.get("rate"),
		"qty": 1,
		"is_subassembly": sc_row.get("is_subassembly"),
	}


def _update_sc_amounts_from_split(so_item, sc_row, split_work_qty):
	"""Refresh qty/amount on a style contractor row from split work qty."""
	if sc_row.get("is_subassembly"):
		unit_qty = flt(sc_row.get("unit_qty")) or 1
		sc_row.qty = flt(split_work_qty) * unit_qty
		sc_row.amount = flt(sc_row.qty) * flt(sc_row.get("rate"))
		return

	style_row = _style_row_for_sc(so_item, sc_row)
	billable_qty, amount = billable_amount_for_split(so_item, style_row, split_work_qty, sc_row)
	sc_row.qty = billable_qty
	sc_row.amount = amount


def apply_all_style_contractor_amounts(ct_row, work_qty_field):
	"""Recalculate amounts for every style contractor row from split_qty."""
	work_qty = flt(getattr(ct_row, work_qty_field, None))
	so_item = getattr(ct_row, "so_item", None)
	if not so_item:
		return

	by_style = {}
	for sc in ct_row.get("style_contractors") or []:
		if not sc.get("style"):
			continue
		by_style.setdefault(sc.style, []).append(sc)

	for style, rows in by_style.items():
		if len(rows) == 1 and not flt(rows[0].get("split_qty")) and work_qty > 0:
			rows[0].split_qty = work_qty
		for sc in rows:
			split_wq = flt(sc.get("split_qty"))
			if split_wq > 0:
				_update_sc_amounts_from_split(so_item, sc, split_wq)


def validate_style_contractor_splits(report_rows, qty_field, report_label):
	"""Ensure split work qty per style equals the report line work qty."""
	for row in report_rows or []:
		work_qty = flt(row.get(qty_field))
		if work_qty <= 0:
			continue

		by_style = {}
		for sc in row.get("style_contractors") or []:
			if not sc.get("style"):
				continue
			by_style.setdefault(sc.style, []).append(sc)

		for style, sc_rows in by_style.items():
			if len(sc_rows) <= 1:
				sc = sc_rows[0]
				if sc.get("contractor") and not flt(sc.get("split_qty")):
					continue
				if len(sc_rows) == 1 and not sc.get("contractor"):
					continue
				if len(sc_rows) == 1:
					continue

			split_total = sum(flt(sc.get("split_qty")) for sc in sc_rows)
			if split_total <= 0:
				if any(sc.get("contractor") for sc in sc_rows):
					frappe.throw(
						_("Row {0}: enter Split Qty for style {1} contractors.").format(
							row.idx, style
						),
						title=_("{0} — Contractor Split").format(report_label),
					)
				continue

			if abs(split_total - work_qty) > 0.0001:
				frappe.throw(
					_(
						"Row {0}: style {1} split qty total {2} must equal line work qty {3}."
					).format(row.idx, style, split_total, work_qty),
					title=_("{0} — Contractor Split").format(report_label),
				)

			missing = [sc for sc in sc_rows if flt(sc.get("split_qty")) > 0 and not sc.get("contractor")]
			if missing:
				frappe.throw(
					_("Row {0}: assign contractor for all split rows on style {1}.").format(
						row.idx, style
					),
					title=_("{0} — Contractor Split").format(report_label),
				)


@frappe.whitelist()
def get_contractor_split_dashboard(
	from_date=None,
	to_date=None,
	operation=None,
	order_sheet=None,
	contractor=None,
):
	"""Dashboard: contractor billing split by process / style from submitted reports."""
	from frappe.utils import getdate

	from_date = getdate(from_date) if from_date else None
	to_date = getdate(to_date) if to_date else None

	report_sources = (
		("Cutting", "Cutting Report", "Cutting Report CT", "cutting_qty"),
		("Stitching", "Stitching Report", "Stitching Report CT", "stitching_qty"),
		("Packing", "Packing Report", "Packing Report CT", "packaging_qty"),
	)

	rows = []
	for op_name, report_dt, ct_dt, qty_field in report_sources:
		if operation and operation not in ("All", op_name):
			continue
		if not frappe.db.table_exists("Report Style Contractor"):
			continue

		filters = {"docstatus": 1}
		if from_date:
			filters["date"] = [">=", from_date]
		if to_date:
			if "date" in filters:
				filters["date"] = ["between", [from_date, to_date]]
			else:
				filters["date"] = ["<=", to_date]
		if order_sheet:
			filters["order_sheet"] = order_sheet

		reports = frappe.get_all(
			report_dt,
			filters=filters,
			fields=["name", "order_sheet", "date", "supplier"],
		)
		if not reports:
			continue

		report_map = {r.name: r for r in reports}
		ct_rows = frappe.get_all(
			ct_dt,
			filters={"parent": ["in", list(report_map)]},
			fields=["name", "parent", "so_item", "combo_item", "article"],
		)
		if not ct_rows:
			continue

		sc_rows = frappe.get_all(
			"Report Style Contractor",
			filters={
				"parent": ["in", [c.name for c in ct_rows]],
				"parenttype": ct_dt,
			},
			fields=[
				"parent",
				"style",
				"contractor",
				"split_qty",
				"qty",
				"rate",
				"amount",
				"is_subassembly",
				"operation",
			],
			order_by="parent asc, idx asc",
		)

		ct_map = {c.name: c for c in ct_rows}
		for sc in sc_rows:
			if contractor and sc.contractor != contractor:
				continue
			if not sc.contractor:
				continue
			ct = ct_map.get(sc.parent)
			if not ct:
				continue
			report = report_map.get(ct.parent)
			if not report:
				continue

			rows.append(
				{
					"operation": op_name,
					"report_name": report.name,
					"report_date": str(report.date) if report.date else "",
					"order_sheet": report.order_sheet,
					"so_item": ct.so_item,
					"combo_item": ct.combo_item or "",
					"style": sc.style,
					"contractor": sc.contractor,
					"split_qty": flt(sc.split_qty),
					"billable_qty": flt(sc.qty),
					"rate": flt(sc.rate),
					"amount": flt(sc.amount),
					"is_subassembly": sc.is_subassembly,
				}
			)

	rows.sort(
		key=lambda r: (
			r.get("report_date") or "",
			r.get("order_sheet") or "",
			r.get("operation") or "",
			r.get("style") or "",
		),
		reverse=True,
	)

	summary = {
		"rows": len(rows),
		"total_amount": sum(flt(r.get("amount")) for r in rows),
		"contractors": len({r.get("contractor") for r in rows if r.get("contractor")}),
	}

	return {"rows": rows, "summary": summary}
