# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

"""Component Plan Qty = Order Sheet finished plan × Pcs per Set (pillow pcs=2 → double)."""

from __future__ import annotations

import frappe
from frappe.utils import flt


def component_plan_qty(finished_plan_qty, pcs) -> float:
	"""Return plan qty in component pieces."""
	return flt(finished_plan_qty) * (flt(pcs) or 1)


def refresh_component_planned_qty(rows, order_sheet: str | None):
	"""
	Set each combo line's planned_qty (and qty mirror) to finished_plan × pcs.

	Safe on save/validate for existing drafts that still store finished-level plan.
	"""
	if not rows:
		return

	plan_by_so = {}
	if order_sheet:
		plan_by_so = {
			r.so_item: flt(r.planned_qty)
			for r in frappe.get_all(
				"Order Sheet CT",
				filters={"parent": order_sheet},
				fields=["so_item", "planned_qty"],
			)
			if r.so_item
		}

	for row in rows:
		so_item = getattr(row, "so_item", None) or (row.get("so_item") if hasattr(row, "get") else None)
		if not so_item:
			continue
		pcs = flt(getattr(row, "pcs", None) if not hasattr(row, "get") else row.get("pcs")) or 1
		finished_plan = plan_by_so.get(so_item)
		if finished_plan is None:
			current = flt(getattr(row, "planned_qty", None) if not hasattr(row, "get") else row.get("planned_qty"))
			# If current already looks component-scaled, keep via /pcs then *pcs
			finished_plan = current / pcs if pcs else current
		component_plan = component_plan_qty(finished_plan, pcs)
		setter = getattr(row, "set", None)
		if callable(setter):
			setter("planned_qty", component_plan)
			try:
				setter("qty", component_plan)
			except Exception:
				if hasattr(row, "qty"):
					row.qty = component_plan
		else:
			row.planned_qty = component_plan
			if hasattr(row, "qty"):
				row.qty = component_plan
