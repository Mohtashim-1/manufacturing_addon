# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import cstr, flt

from manufacturing_addon.manufacturing_addon.utils.subassembly_bom import (
	apply_subassembly_contractor_qty,
	resolve_subassembly_unit_qty,
	subassembly_material_type,
)


ITEM_STYLE_TABLES = (
	"custom_cutting_style",
	"custom_stitching_style",
	"custom_packing",
)

OPERATION_CONFIG = {
	"Cutting": {
		"item_style_field": "custom_cutting_style",
		"operation": "Cutting",
	},
	"Stitching": {
		"item_style_field": "custom_stitching_style",
		"operation": "Stitching",
	},
	"Packing": {
		"item_style_field": "custom_packing",
		"operation": "Packing",
	},
	"Checking": {
		"item_style_field": None,
		"operation": "Checking",
	},
	"Quality": {
		"item_style_field": "custom_stitching_style",
		"operation": "Quality",
	},
}

ITEM_STITCHING_STYLE_FIELD = OPERATION_CONFIG["Stitching"]["item_style_field"]
ITEM_STITCHING_STYLE_DOCTYPE = "Stitching Style"


def item_style_unit_amount(style_row):
	"""Per finished-unit amount from Item style tab (rate × qty or amount field)."""
	if flt(style_row.get("amount")):
		return flt(style_row.amount)
	rate = flt(style_row.get("rate"))
	qty = flt(style_row.get("qty") or 1) or 1
	return rate * qty


def billing_amount_for_work(style_row, work_qty):
	work_qty = flt(work_qty)
	if work_qty <= 0:
		return 0
	return work_qty * item_style_unit_amount(style_row)


def _normalize(value):
	return cstr(value or "").strip()


def _style_row_matches_report_line(style_row, so_item, combo_item, article):
	"""Match Item style row to a report CT line."""
	combo_code = _normalize(combo_item)
	article_text = _normalize(article)
	style_article = _normalize(style_row.get("combo_item"))
	component = _normalize(style_row.get("stitching_component"))

	if not combo_code and not article_text:
		return True

	if component and component == combo_code:
		return True

	if style_article and article_text and style_article.upper() == article_text.upper():
		return True

	if style_article and combo_code and frappe.db.exists("Item", combo_code):
		item_name = frappe.db.get_value("Item", combo_code, "item_name") or ""
		if style_article.upper() in (_normalize(item_name).upper(), combo_code.upper()):
			return True

	if not style_article and not component:
		return True

	return False


def _iter_item_style_rows(item, operation):
	"""Yield style rows for a report operation.

	- Rows from the operation's own style table are always included.
	- Rows marked Subassembly on any style table are included in every report.
	- Checking has no own table, so it only receives subassembly rows.
	"""
	config = OPERATION_CONFIG.get(operation)
	if not config:
		return

	own_field = config.get("item_style_field")
	seen = set()

	for table_field in ITEM_STYLE_TABLES:
		for row in item.get(table_field) or []:
			if not row.get("style"):
				continue

			row_key = row.name or f"{table_field}:{row.idx}:{row.style}"
			if row_key in seen:
				continue

			is_subassembly = bool(row.get("is_subassembly"))
			is_own_table = table_field == own_field

			if own_field and is_own_table:
				pass
			elif is_subassembly:
				pass
			else:
				continue

			seen.add(row_key)
			yield row


def get_item_styles(item_code, operation="Stitching", combo_item=None, article=None, mandatory_only=False):
	config = OPERATION_CONFIG.get(operation)
	if not config:
		return []

	if not item_code or not frappe.db.exists("Item", item_code):
		return []

	item = frappe.get_doc("Item", item_code)
	out = []
	for row in _iter_item_style_rows(item, operation):
		if mandatory_only and not row.get("is_mandatory"):
			continue
		if not _style_row_matches_report_line(row, item_code, combo_item, article):
			continue
		out.append(row)
	return out


def get_item_stitching_styles(item_code, combo_item=None, article=None, mandatory_only=False):
	return get_item_styles(
		item_code, operation="Stitching", combo_item=combo_item, article=article, mandatory_only=mandatory_only
	)


def _is_subassembly_style(style_row):
	return bool(style_row.get("is_subassembly")) or bool(subassembly_material_type(style_row.get("style")))


def build_style_contractor_rows(
	item_code,
	operation="Stitching",
	combo_item=None,
	article=None,
	mandatory_only=False,
	work_qty=0,
):
	config = OPERATION_CONFIG.get(operation)
	if not config:
		return []

	rows = []
	work_qty_f = flt(work_qty)
	for style_row in get_item_styles(
		item_code,
		operation=operation,
		combo_item=combo_item,
		article=article,
		mandatory_only=mandatory_only,
	):
		is_subassembly = _is_subassembly_style(style_row)
		if is_subassembly:
			unit_qty = resolve_subassembly_unit_qty(item_code, style_row)
			qty = work_qty_f * unit_qty if work_qty_f > 0 else unit_qty
		else:
			unit_qty = flt(style_row.get("qty") or 1) or 1
			qty = unit_qty
		rate = flt(style_row.get("rate"))
		rows.append(
			{
				"style": style_row.style,
				"contractor": "",
				"split_qty": work_qty_f if work_qty_f > 0 else 0,
				"qty": qty,
				"unit_qty": unit_qty if is_subassembly else 0,
				"rate": rate,
				"amount": rate * qty,
				"is_mandatory": 1 if style_row.get("is_mandatory") else 0,
				"is_subassembly": 1 if is_subassembly else 0,
				"operation": config["operation"],
				"combo_item": style_row.get("combo_item"),
				"item_style_row": style_row.name,
			}
		)
	return rows


def append_style_contractors(
	ct_row,
	item_code,
	operation="Stitching",
	combo_item=None,
	article=None,
	mandatory_only=False,
	work_qty_field=None,
):
	"""Populate nested style_contractors on a report CT row."""
	config = OPERATION_CONFIG.get(operation) or {}
	work_qty = flt(getattr(ct_row, work_qty_field, None)) if work_qty_field else 0
	ct_row.style_contractors = []
	for row_data in build_style_contractor_rows(
		item_code,
		operation=operation,
		combo_item=combo_item,
		article=article,
		mandatory_only=mandatory_only,
		work_qty=work_qty,
	):
		ct_row.append("style_contractors", row_data)
	if work_qty_field:
		apply_subassembly_contractor_qty(ct_row, work_qty_field)


def validate_mandatory_contractors(report_rows, qty_field="stitching_qty", report_label="Stitching Report"):
	"""Ensure mandatory style rows have a contractor when parent qty is entered."""
	from manufacturing_addon.manufacturing_addon.utils.style_contractor_split import (
		validate_style_contractor_splits,
	)

	validate_style_contractor_splits(report_rows, qty_field, report_label)

	for row in report_rows or []:
		if flt(row.get(qty_field)) <= 0:
			continue
		missing = []
		for sc in row.get("style_contractors") or []:
			if sc.get("is_mandatory") and not sc.get("contractor"):
				missing.append(sc.get("style") or _("Style"))
		if missing:
			frappe.throw(
				frappe._(
					"Row {0}: assign contractor for mandatory style(s): {1}"
				).format(row.idx, ", ".join(missing)),
				title=frappe._("{0} — Style Contractors").format(report_label),
			)
