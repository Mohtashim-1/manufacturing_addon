# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import cstr, flt


ITEM_STITCHING_STYLE_FIELD = "custom_stitching_style"
ITEM_STITCHING_STYLE_DOCTYPE = "Stitching Style"


def _normalize(value):
	return cstr(value or "").strip()


def _style_row_matches_report_line(style_row, so_item, combo_item, article):
	"""Match Item stitching style row to a report CT line."""
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


def get_item_stitching_styles(item_code, combo_item=None, article=None, mandatory_only=False):
	if not item_code or not frappe.db.exists("Item", item_code):
		return []

	item = frappe.get_doc("Item", item_code)
	out = []
	for row in item.get(ITEM_STITCHING_STYLE_FIELD) or []:
		if not row.get("style"):
			continue
		if mandatory_only and not row.get("is_mandatory"):
			continue
		if not _style_row_matches_report_line(row, item_code, combo_item, article):
			continue
		out.append(row)
	return out


def build_style_contractor_rows(item_code, combo_item=None, article=None, mandatory_only=False):
	rows = []
	for style_row in get_item_stitching_styles(
		item_code, combo_item=combo_item, article=article, mandatory_only=mandatory_only
	):
		qty = flt(style_row.get("qty") or 1) or 1
		rate = flt(style_row.get("rate"))
		rows.append(
			{
				"style": style_row.style,
				"contractor": "",
				"qty": qty,
				"rate": rate,
				"amount": rate * qty,
				"is_mandatory": 1 if style_row.get("is_mandatory") else 0,
				"operation": "Stitching",
				"combo_item": style_row.get("combo_item"),
				"item_style_row": style_row.name,
			}
		)
	return rows


def append_style_contractors(ct_row, item_code, combo_item=None, article=None, mandatory_only=False):
	"""Populate nested style_contractors on a Stitching Report CT row."""
	ct_row.style_contractors = []
	for row_data in build_style_contractor_rows(
		item_code, combo_item=combo_item, article=article, mandatory_only=mandatory_only
	):
		ct_row.append("style_contractors", row_data)


def validate_mandatory_contractors(report_rows, qty_field="stitching_qty", report_label="Stitching Report"):
	"""Ensure mandatory style rows have a contractor when parent qty is entered."""
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
