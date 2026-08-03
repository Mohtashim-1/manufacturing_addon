# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

"""BOM-based quantity helpers for button/zip sub-assembly styles."""

import re

import frappe
from frappe import _
from frappe.utils import cstr, flt

from erpnext.stock.get_item_details import get_default_bom

MATERIAL_KEYWORDS = {
	"button": ("BUTTON",),
	"zip": ("ZIP",),
}

# Dedicated zip/button *making* styles only — not product styles like
# "QUILT COVER BUTTON MF (ST)" / "QUILT COVER WITH ZIP (CK)".
_BUTTON_MAKING_RE = re.compile(
	r"(REB+E?T\s+BUTTON|RIB+E?T\s+BUTTON|BUTTON\s+SET|SET\s+BUTTON|^BUTTON$)",
	re.I,
)
_ZIP_MAKING_RE = re.compile(
	r"((BASIC\s+)?ZIP\s*(CUTTING|MAKING)|SET\s+ZIP|ZIP\s+SET|^ZIP$)",
	re.I,
)


def subassembly_material_type(style_name):
	"""Infer button/zip material type for dedicated making styles only.

	Uses Style.is_subassembly when the Style master exists. Falls back to
	strict name patterns (REBET BUTTON SET, BASIC ZIP CUTTING, etc.).
	Product styles that only mention zip/button in the name are ignored.
	"""
	name = cstr(style_name).strip()
	if not name:
		return None

	is_sub = frappe.db.get_value("Style", name, "is_subassembly")
	if is_sub is not None:
		if not int(is_sub or 0):
			return None
		upper = name.upper()
		if "BUTTON" in upper:
			return "button"
		if "ZIP" in upper:
			return "zip"
		return None

	if _BUTTON_MAKING_RE.search(name):
		return "button"
	if _ZIP_MAKING_RE.search(name):
		return "zip"
	return None


def _material_like_values(material_type):
	"""Return LIKE values and matching SQL OR clauses for button/zip BOM items."""
	keywords = MATERIAL_KEYWORDS.get(material_type) or ()
	clauses = []
	values = []
	for keyword in keywords:
		like_value = f"%{keyword}%"
		clauses.extend(
			[
				"UPPER(IFNULL(i.item_group, '')) LIKE %s",
				"UPPER(IFNULL(i.custom_item_category, '')) LIKE %s",
				"UPPER(IFNULL(bi.item_code, '')) LIKE %s",
				"UPPER(IFNULL(bi.item_name, '')) LIKE %s",
			]
		)
		values.extend([like_value, like_value, like_value, like_value])
	return clauses, values


def get_bom_qty_per_finished_unit(item_code, material_type, bom_name=None):
	"""Return BOM material qty per one finished unit for button or zip."""
	if not item_code or not material_type:
		return 0

	bom_name = bom_name or get_default_bom(item_code)
	if not bom_name:
		return 0

	clauses, like_values = _material_like_values(material_type)
	if not clauses:
		return 0

	bom_qty = flt(frappe.db.get_value("BOM", bom_name, "quantity")) or 1
	rows = frappe.db.sql(
		f"""
		SELECT SUM(bi.qty) AS total_qty
		FROM `tabBOM Item` bi
		LEFT JOIN `tabItem` i ON i.name = bi.item_code
		WHERE bi.parent = %s
		  AND ({' OR '.join(clauses)})
		""",
		tuple([bom_name] + like_values),
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


def finished_work_qty(row, work_qty):
	"""Convert report line work qty to finished-product pieces.

	Cutting/stitching lines for combo components (e.g. PILLOW pcs=2) store
	component pieces in cutting_qty; BOM math and order caps use finished pcs.
	"""
	work_qty = flt(work_qty)
	pcs = flt(row.get("pcs") if hasattr(row, "get") else getattr(row, "pcs", None)) or 1
	return work_qty / pcs if pcs else work_qty


def set_sc_value(sc, fieldname, value):
	"""Set a field on a style-contractor row (dict, _dict, or Document)."""
	if sc is None:
		return
	if isinstance(sc, dict):
		sc[fieldname] = value
		return
	try:
		sc.set(fieldname, value)
	except Exception:
		setattr(sc, fieldname, value)


def apply_subassembly_contractor_qty(ct_row, work_qty_field):
	"""Set style qty from finished product qty × BOM zip/button per unit.

	Example: finished products = 12, BOM zip qty = 2 → style qty = 24.
	Always recalculates so users only enter finished product qty.
	Work qty on combo lines may be component pieces — convert via pcs.
	"""
	raw_work_qty = flt(getattr(ct_row, work_qty_field, None))
	work_qty = finished_work_qty(ct_row, raw_work_qty)
	item_code = getattr(ct_row, "so_item", None)
	if not item_code:
		return

	by_style = {}
	for sc in getattr(ct_row, "style_contractors", None) or []:
		style_name = sc.get("style") if hasattr(sc, "get") else getattr(sc, "style", None)
		if not style_name:
			continue
		by_style.setdefault(style_name, []).append(sc)

	for _style, rows in by_style.items():
		# Keep split_qty in the same units as the report work field (component pcs).
		# Convert to finished only when applying BOM unit qty.
		if len(rows) == 1 and raw_work_qty > 0:
			set_sc_value(rows[0], "split_qty", raw_work_qty)

		for sc in rows:
			style_name = sc.get("style") if hasattr(sc, "get") else getattr(sc, "style", None)
			is_sub = bool(sc.get("is_subassembly") if hasattr(sc, "get") else getattr(sc, "is_subassembly", 0)) or bool(
				subassembly_material_type(style_name)
			)
			if not is_sub:
				continue
			set_sc_value(sc, "is_subassembly", 1)
			unit_qty = get_subassembly_unit_qty(
				item_code,
				style_name,
				(sc.get("unit_qty") if hasattr(sc, "get") else None) or (sc.get("qty") if hasattr(sc, "get") else None),
			)
			set_sc_value(sc, "unit_qty", unit_qty)
			split_raw = flt(sc.get("split_qty") if hasattr(sc, "get") else getattr(sc, "split_qty", 0)) or raw_work_qty
			if raw_work_qty > 0 and not flt(sc.get("split_qty") if hasattr(sc, "get") else getattr(sc, "split_qty", 0)):
				set_sc_value(sc, "split_qty", raw_work_qty)
				split_raw = raw_work_qty
			split_finished = finished_work_qty(ct_row, split_raw)
			qty = split_finished * unit_qty if split_finished > 0 else unit_qty
			set_sc_value(sc, "qty", qty)
			rate = flt(sc.get("rate") if hasattr(sc, "get") else getattr(sc, "rate", 0))
			set_sc_value(sc, "amount", rate * flt(qty))


def _report_configs():
	return (
		("Cutting Report", "Cutting Report CT", "cutting_qty"),
		("Stitching Report", "Stitching Report CT", "stitching_qty"),
		("Packing Report", "Packing Report CT", "packaging_qty"),
		("Checking Report", "Checking Report CT", "checking_qty"),
		("Sub Assembly Report", "Sub Assembly Report CT", "sub_assembly_qty"),
	)


def _subassembly_styles_for_item(item_code):
	from manufacturing_addon.manufacturing_addon.utils.report_style_contractor import (
		_iter_item_style_rows,
	)

	if not item_code or not frappe.db.exists("Item", item_code):
		return []

	item = frappe.get_doc("Item", item_code)
	styles = {}
	for operation in ("Cutting", "Stitching", "Packing", "Checking", "Sub Assembly"):
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

		ct_fields = ["name", qty_field]
		# pcs exists on manufacturing report CT doctypes (combo component lines)
		if frappe.get_meta(child_doctype).has_field("pcs"):
			ct_fields.append("pcs")

		ct_rows = frappe.get_all(
			child_doctype,
			filters={"parent": ["in", reports], "so_item": so_item},
			fields=ct_fields,
		)
		if not ct_rows:
			continue

		ct_names = [r.name for r in ct_rows if flt(getattr(r, qty_field)) > 0]
		if not ct_names:
			continue

		work_by_ct = {
			r.name: finished_work_qty(r, getattr(r, qty_field)) for r in ct_rows
		}
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


def validate_subassembly_qty_caps(doc, child_table_field, work_qty_field, report_label, throw=True):
	"""Ensure finished qty × BOM does not exceed order qty × BOM unit qty.

	Returns list of warning messages. Throws on first breach when throw=True.
	"""
	order_sheet = doc.get("order_sheet")
	warnings = []
	if not order_sheet:
		return warnings

	for row in doc.get(child_table_field) or []:
		raw_work_qty = flt(row.get(work_qty_field))
		if raw_work_qty <= 0 or not row.get("so_item"):
			continue

		# Combo component lines (pillow pcs=2 etc.) store component pieces
		work_qty = finished_work_qty(row, raw_work_qty)

		order_qty = flt(row.get("order_qty"))
		planned_qty = flt(row.get("planned_qty"))
		# Allow cutting up to planned when plan exceeds order (over-plan booking)
		qty_ceiling = max(order_qty, planned_qty)
		if qty_ceiling <= 0:
			continue

		if work_qty > qty_ceiling + 1e-9:
			msg = _(
				"Row {0}: Finished Product Qty {1} cannot exceed Order/Plan Qty {2}."
			).format(row.idx, work_qty, qty_ceiling)
			if throw:
				frappe.throw(msg, title=_("{0} — Qty Limit").format(report_label))
			warnings.append(msg)
			continue

		style_rows = _subassembly_styles_for_item(row.so_item)
		if not style_rows:
			continue

		for style_row in style_rows:
			unit_qty = resolve_subassembly_unit_qty(row.so_item, style_row)
			max_total = qty_ceiling * unit_qty
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
				msg = _(
					"Row {0}: {1} style qty cannot exceed order/plan limit. "
					"Finished Product Qty {2} × BOM {3} = {4}, but max is {5} "
					"({6} pcs × {3} per pc). Already used {7}."
				).format(
					row.idx,
					style_row.style,
					work_qty,
					unit_qty,
					current,
					max_total,
					qty_ceiling,
					used,
				)
				if throw:
					frappe.throw(msg, title=_("{0} — Sub-Assembly Limit").format(report_label))
				warnings.append(msg)

	return warnings
