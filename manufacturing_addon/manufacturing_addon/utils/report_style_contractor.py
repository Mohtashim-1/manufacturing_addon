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
	"Sub Assembly": {
		"item_style_field": None,
		"operation": "Sub Assembly",
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
	"""Match Item style row to a report CT line.

	Unscoped styles (no stitching_component / combo_item) must not fan out onto
	every duvet/pillow combo line — that duplicated SET BOM zip qty on each row.
	"""
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

	# Combo-specific report line: unscoped *product* styles must not fan out.
	# Unscoped zip/button still attach on Sub Assembly / Checking (Cutting/Stitching
	# never receive those styles from _iter_item_style_rows anymore).
	if combo_code and not style_article and not component:
		return _is_subassembly_style(style_row)

	if not style_article and not component:
		return True

	return False


# Product reports: fabric/product styles only. Zip/button live on Sub Assembly Report.
_PRODUCT_OPERATIONS = frozenset({"Cutting", "Stitching", "Packing", "Quality"})
_SUBASSEMBLY_OPERATIONS = frozenset({"Sub Assembly", "Checking"})


def _iter_item_style_rows(item, operation):
	"""Yield style rows for a report operation.

	- Cutting / Stitching / Packing: only that operation's own style table, and
	  never zip/button sub-assembly styles (those are Sub Assembly Report only).
	- Sub Assembly / Checking: only sub-assembly styles (checkbox or zip/button name).
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

			is_subassembly = _is_subassembly_style(row)
			is_own_table = bool(own_field) and table_field == own_field

			if operation in _PRODUCT_OPERATIONS:
				if not is_own_table or is_subassembly:
					continue
			elif operation in _SUBASSEMBLY_OPERATIONS:
				if not is_subassembly:
					continue
			else:
				# Unknown operation: keep previous own-table OR subassembly rule
				if is_own_table:
					pass
				elif is_subassembly:
					pass
				else:
					continue

			seen.add(row_key)
			yield row


def strip_subassembly_style_contractors(report_rows):
	"""Drop zip/button sub-assembly style lines from Cutting/Stitching CT rows."""
	for row in report_rows or []:
		styles = row.get("style_contractors") or []
		if not styles:
			continue
		kept = []
		for sc in styles:
			sc = frappe._dict(sc) if isinstance(sc, dict) else sc
			style_name = sc.get("style") if hasattr(sc, "get") else getattr(sc, "style", None)
			is_sub = bool(
				(sc.get("is_subassembly") if hasattr(sc, "get") else getattr(sc, "is_subassembly", 0))
				or subassembly_material_type(style_name)
			)
			if is_sub:
				continue
			kept.append(sc)
		if isinstance(row, dict):
			row["style_contractors"] = kept
		else:
			row.style_contractors = kept


def _is_subassembly_style(style_row):
	return bool(style_row.get("is_subassembly")) or bool(subassembly_material_type(style_row.get("style")))


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
	rows = build_style_contractor_rows(
		item_code,
		operation=operation,
		combo_item=combo_item,
		article=article,
		mandatory_only=mandatory_only,
		work_qty=work_qty,
	)
	if not rows:
		return

	# Frappe 16 blocks Document.append on nested tables of child docs; assign _dicts.
	ct_row.set("style_contractors", [frappe._dict(row_data) for row_data in rows])

	if work_qty_field:
		apply_subassembly_contractor_qty(ct_row, work_qty_field)


def _normalize_style_contractors(report_rows):
	"""Ensure nested style_contractors are frappe._dict (Desk often posts plain dict)."""
	for row in report_rows or []:
		styles = row.get("style_contractors")
		if not styles:
			continue
		normalized = [frappe._dict(sc) if isinstance(sc, dict) else sc for sc in styles]
		# Prefer attribute assign — frappe._dict.__getattr__("set") returns None
		if isinstance(row, dict):
			row["style_contractors"] = normalized
		else:
			row.style_contractors = normalized


def validate_mandatory_contractors(report_rows, qty_field="stitching_qty", report_label="Stitching Report"):
	"""Ensure mandatory style rows have a contractor when parent qty is entered."""
	from manufacturing_addon.manufacturing_addon.utils.style_contractor_split import (
		validate_style_contractor_splits,
	)

	_normalize_style_contractors(report_rows)
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
