# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

"""BOM-based quantity helpers for button/zip sub-assembly styles."""

import frappe
from frappe import _
from frappe.utils import cstr, flt

from erpnext.stock.get_item_details import get_default_bom

MATERIAL_KEYWORDS = {
	"button": ("BUTTON",),
	"zip": ("ZIP",),
}


def subassembly_material_type(style_name):
	"""Infer button/zip material type from Style name."""
	name = cstr(style_name).upper()
	if "BUTTON" in name:
		return "button"
	if "ZIP" in name:
		return "zip"
	return None


def _material_sql_patterns(material_type):
	keywords = MATERIAL_KEYWORDS.get(material_type) or ()
	patterns = []
	for keyword in keywords:
		patterns.extend(
			[
				f"UPPER(IFNULL(i.item_group, '')) LIKE '%{keyword}%'",
				f"UPPER(IFNULL(i.custom_item_category, '')) LIKE '%{keyword}%'",
				f"UPPER(IFNULL(bi.item_code, '')) LIKE '%{keyword}%'",
				f"UPPER(IFNULL(bi.item_name, '')) LIKE '%{keyword}%'",
			]
		)
	return patterns


def get_bom_qty_per_finished_unit(item_code, material_type, bom_name=None):
	"""Return BOM material qty per one finished unit for button or zip."""
	if not item_code or not material_type:
		return 0

	bom_name = bom_name or get_default_bom(item_code)
	if not bom_name:
		return 0

	patterns = _material_sql_patterns(material_type)
	if not patterns:
		return 0

	bom_qty = flt(frappe.db.get_value("BOM", bom_name, "quantity")) or 1
	rows = frappe.db.sql(
		f"""
		SELECT SUM(bi.qty) AS total_qty
		FROM `tabBOM Item` bi
		LEFT JOIN `tabItem` i ON i.name = bi.item_code
		WHERE bi.parent = %s
		  AND ({' OR '.join(patterns)})
		""",
		bom_name,
		as_dict=True,
	)
	total = flt(rows[0].total_qty if rows else 0)
	if total <= 0:
		return 0
	return total / bom_qty if bom_qty else total


def get_subassembly_unit_qty(item_code, style_name, style_row_qty=None):
	"""Per-finished-unit qty for a sub-assembly style (BOM first, then Item Style qty)."""
	material_type = subassembly_material_type(style_name)
	if not material_type:
		return flt(style_row_qty or 1) or 1

	bom_qty = get_bom_qty_per_finished_unit(item_code, material_type)
	if bom_qty > 0:
		return bom_qty
	return flt(style_row_qty or 1) or 1


def resolve_subassembly_unit_qty(item_code, style_row):
	"""Unit qty for one finished piece from an Item style child row."""
	style_name = style_row.get("style")
	if not style_row.get("is_subassembly") and not subassembly_material_type(style_name):
		return flt(style_row.get("qty") or 1) or 1
	return get_subassembly_unit_qty(item_code, style_name, style_row.get("qty"))


@frappe.whitelist()
def get_subassembly_bom_qty(item_code, style_name):
	"""API: BOM qty per finished unit for a sub-assembly style."""
	material_type = subassembly_material_type(style_name)
	if not material_type:
		return {"material_type": None, "qty_per_unit": 0, "bom": get_default_bom(item_code)}
	qty = get_bom_qty_per_finished_unit(item_code, material_type)
	return {
		"material_type": material_type,
		"qty_per_unit": qty,
		"bom": get_default_bom(item_code),
	}


def sync_item_subassembly_qty_from_bom(item_code):
	"""Update sub-assembly style rows on Item from default BOM button/zip qty."""
	from manufacturing_addon.manufacturing_addon.utils.report_style_contractor import ITEM_STYLE_TABLES

	if not item_code or not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} not found").format(item_code))

	item = frappe.get_doc("Item", item_code)
	updated = []

	for table_field in ITEM_STYLE_TABLES:
		for row in item.get(table_field) or []:
			if not row.get("style"):
				continue
			if not row.get("is_subassembly") and not subassembly_material_type(row.style):
				continue

			unit_qty = get_subassembly_unit_qty(item_code, row.style, row.qty)
			if flt(row.qty) != unit_qty:
				row.qty = unit_qty
				row.amount = flt(row.rate) * unit_qty
				updated.append({"style": row.style, "table": table_field, "qty": unit_qty})

	if updated:
		item.save(ignore_permissions=True)

	return {"updated": updated, "count": len(updated)}


def apply_subassembly_contractor_qty(ct_row, work_qty_field):
	"""Set calculated total qty on sub-assembly style contractor rows."""
	work_qty = flt(getattr(ct_row, work_qty_field, None))
	item_code = getattr(ct_row, "so_item", None)
	if not item_code:
		return

	for sc in ct_row.get("style_contractors") or []:
		if not sc.get("is_subassembly"):
			continue
		unit_qty = flt(sc.get("unit_qty"))
		if unit_qty <= 0:
			unit_qty = get_subassembly_unit_qty(item_code, sc.get("style"), sc.get("qty"))
			sc.unit_qty = unit_qty
		split_work = flt(sc.get("split_qty")) or work_qty
		if not sc.get("split_qty") and work_qty > 0:
			sc.split_qty = work_qty
		total_qty = split_work * unit_qty if split_work > 0 else unit_qty
		sc.qty = total_qty
		sc.amount = flt(sc.get("rate")) * total_qty


def _report_configs():
	return (
		("Cutting Report", "Cutting Report CT", "cutting_qty"),
		("Stitching Report", "Stitching Report CT", "stitching_qty"),
		("Packing Report", "Packing Report CT", "packaging_qty"),
		("Checking Report", "Checking Report CT", "checking_qty"),
	)


def _subassembly_styles_for_item(item_code):
	from manufacturing_addon.manufacturing_addon.utils.report_style_contractor import (
		_iter_item_style_rows,
	)

	if not item_code or not frappe.db.exists("Item", item_code):
		return []

	item = frappe.get_doc("Item", item_code)
	styles = {}
	for operation in ("Cutting", "Stitching", "Packing", "Checking"):
		for row in _iter_item_style_rows(item, operation):
			if not row.get("is_subassembly") and not subassembly_material_type(row.style):
				continue
			key = row.name or row.style
			if key not in styles:
				styles[key] = row
	return list(styles.values())


def get_subassembly_qty_used(order_sheet, so_item, style, unit_qty, exclude_parent=None, exclude_parenttype=None):
	"""Sum calculated sub-assembly qty already entered on submitted reports."""
	if not order_sheet or not so_item or not style or unit_qty <= 0:
		return 0

	total = 0
	for parent_doctype, child_doctype, qty_field in _report_configs():
		parent_filters = {"order_sheet": order_sheet, "docstatus": 1}
		if exclude_parent and exclude_parenttype == parent_doctype:
			parent_filters["name"] = ("!=", exclude_parent)

		reports = frappe.get_all(parent_doctype, filters=parent_filters, pluck="name")
		if not reports:
			continue

		ct_rows = frappe.get_all(
			child_doctype,
			filters={"parent": ["in", reports], "so_item": so_item},
			fields=["name", qty_field],
		)
		if not ct_rows:
			continue

		ct_names = [r.name for r in ct_rows if flt(getattr(r, qty_field)) > 0]
		if not ct_names:
			continue

		work_by_ct = {r.name: flt(getattr(r, qty_field)) for r in ct_rows}
		sc_rows = frappe.get_all(
			"Report Style Contractor",
			filters={
				"parent": ["in", ct_names],
				"parenttype": child_doctype,
				"style": style,
			},
			fields=["parent", "qty", "unit_qty", "is_subassembly"],
		)
		for sc in sc_rows:
			work_qty = work_by_ct.get(sc.parent, 0)
			if work_qty <= 0:
				continue
			unit = flt(sc.unit_qty) or unit_qty
			if sc.is_subassembly:
				total += work_qty * unit
			else:
				total += flt(sc.qty)

	return total


def validate_subassembly_qty_caps(doc, child_table_field, work_qty_field, report_label):
	"""Ensure sub-assembly totals do not exceed order qty × BOM unit qty."""
	order_sheet = doc.get("order_sheet")
	if not order_sheet:
		return

	for row in doc.get(child_table_field) or []:
		work_qty = flt(row.get(work_qty_field))
		if work_qty <= 0 or not row.get("so_item"):
			continue

		order_qty = flt(row.get("order_qty"))
		if order_qty <= 0:
			continue

		style_rows = _subassembly_styles_for_item(row.so_item)
		if not style_rows:
			continue

		for style_row in style_rows:
			unit_qty = resolve_subassembly_unit_qty(row.so_item, style_row)
			max_total = order_qty * unit_qty
			used = get_subassembly_qty_used(
				order_sheet,
				row.so_item,
				style_row.style,
				unit_qty,
				exclude_parent=doc.name if doc.name else None,
				exclude_parenttype=doc.doctype,
			)
			current = work_qty * unit_qty
			if used + current > max_total + 1e-9:
				frappe.throw(
					_(
						"Row {0}: {1} quantity cannot exceed order limit. "
						"Max {2} ({3} pcs × {4} per pc), already used {5}, this entry adds {6}."
					).format(
						row.idx,
						style_row.style,
						max_total,
						order_qty,
						unit_qty,
						used,
						current,
					),
					title=_("{0} — Sub-Assembly Limit").format(report_label),
				)
