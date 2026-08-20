# Copyright (c) 2026, Manufacturing Addon and contributors
# For license information, please see license.txt

"""Bulk Edit BOM portal — SO → default active BOMs → RM matrix → new BOM versions."""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from manufacturing_addon.manufacturing_addon.doctype.production_plan.production_plan import (
	get_default_active_bom,
)


def _parse(data):
	if isinstance(data, str):
		return frappe.parse_json(data) or {}
	return data or {}


@frappe.whitelist()
def get_bom_matrix(sales_order, item_template=None, variants_only=1):
	"""Load FG variant items from Sales Order + their default active BOM RM matrix.

	- Rows = unique SO variant items (Item.variant_of = Item Template)
	- Optional item_template filter limits to that template's variants on the SO
	- Same raw material shares one column across variants
	"""
	if not sales_order:
		frappe.throw(_("Select Sales Order first."))

	if not frappe.db.exists("Sales Order", sales_order):
		frappe.throw(_("Sales Order {0} not found").format(sales_order))

	so = frappe.db.get_value(
		"Sales Order",
		sales_order,
		["name", "customer", "company", "transaction_date", "docstatus", "status"],
		as_dict=True,
	)

	template_filter = (item_template or "").strip() or None
	only_variants = cint(variants_only)

	so_items = frappe.db.sql(
		"""
		SELECT
			soi.name AS so_detail,
			soi.idx,
			soi.item_code,
			soi.item_name,
			IFNULL(soi.qty, 0) AS so_qty,
			IFNULL(soi.bom_no, '') AS so_bom_no,
			IFNULL(soi.uom, '') AS uom,
			IFNULL(i.variant_of, '') AS item_template,
			IFNULL(i.has_variants, 0) AS has_variants,
			IFNULL(i.item_group, '') AS item_group
		FROM `tabSales Order Item` soi
		INNER JOIN `tabItem` i ON i.name = soi.item_code
		WHERE soi.parent = %s
		ORDER BY IFNULL(i.variant_of, ''), soi.idx
		""",
		(sales_order,),
		as_dict=True,
	)

	# Templates present on this SO (for UI filter)
	templates_on_so = []
	seen_templates = set()
	for line in so_items:
		t = (line.item_template or "").strip()
		if t and t not in seen_templates:
			seen_templates.add(t)
			templates_on_so.append(t)

	# One matrix row per unique variant/FG item; sum SO qty if repeated
	seen = {}
	rows = []
	rm_order = []
	rm_set = set()
	cells = {}

	for line in so_items:
		item_code = line.item_code
		if not item_code:
			continue

		template = (line.item_template or "").strip()
		is_template_item = cint(line.has_variants) == 1
		is_variant = bool(template) and not is_template_item

		# Default: only Item Template → Variant items (skip plain items & templates)
		if only_variants and not is_variant:
			continue

		if template_filter and template != template_filter:
			continue

		if item_code in seen:
			# Aggregate qty onto existing row
			idx = seen[item_code]
			rows[idx]["so_qty"] = flt(rows[idx]["so_qty"]) + flt(line.so_qty)
			continue

		bom_no = get_default_active_bom(item_code) or line.so_bom_no or ""
		bom_meta = None
		materials = []
		if bom_no and frappe.db.exists("BOM", bom_no):
			bom_meta = frappe.db.get_value(
				"BOM",
				bom_no,
				["name", "item", "quantity", "uom", "is_active", "is_default", "docstatus"],
				as_dict=True,
			)
			materials = frappe.db.sql(
				"""
				SELECT
					bi.name AS bom_item_name,
					bi.item_code,
					bi.item_name,
					IFNULL(bi.qty, 0) AS qty,
					IFNULL(bi.uom, '') AS uom,
					IFNULL(bi.stock_qty, 0) AS stock_qty,
					IFNULL(bi.rate, 0) AS rate
				FROM `tabBOM Item` bi
				WHERE bi.parent = %s
				ORDER BY bi.idx
				""",
				(bom_no,),
				as_dict=True,
			)

		attrs = _variant_attributes(item_code) if is_variant else {}

		row = {
			"item_code": item_code,
			"item_name": line.item_name,
			"item_template": template,
			"is_variant": 1 if is_variant else 0,
			"attributes": attrs,
			"attributes_label": ", ".join(f"{k}: {v}" for k, v in attrs.items()) if attrs else "",
			"so_detail": line.so_detail,
			"so_qty": flt(line.so_qty),
			"bom_no": bom_no or "",
			"bom_qty": flt(bom_meta.quantity) if bom_meta else 1,
			"bom_uom": (bom_meta.uom if bom_meta else line.uom) or "",
			"is_active": cint(bom_meta.is_active) if bom_meta else 0,
			"is_default": cint(bom_meta.is_default) if bom_meta else 0,
			"has_bom": 1 if bom_meta else 0,
			"dirty": 0,
		}
		seen[item_code] = len(rows)
		rows.append(row)

		for m in materials:
			rm = m.item_code
			if not rm:
				continue
			if rm not in rm_set:
				rm_set.add(rm)
				rm_order.append(
					{
						"item_code": rm,
						"item_name": m.item_name or rm,
						"uom": m.uom or "",
					}
				)
			cells[f"{item_code}::{rm}"] = {
				"qty": flt(m.qty),
				"uom": m.uom or "",
				"bom_item_name": m.bom_item_name,
			}

	return {
		"sales_order": so.name,
		"customer": so.customer,
		"company": so.company,
		"transaction_date": so.transaction_date,
		"item_template": template_filter,
		"templates": templates_on_so,
		"variants_only": only_variants,
		"rows": rows,
		"rm_columns": rm_order,
		"cells": cells,
		"note": _(
			"Loads Item Template variant items from the Sales Order. "
			"Same raw material shares one column. Edit qty, replace RM, fill-down, "
			"then Save to create new default BOM versions."
		),
	}


def _variant_attributes(item_code):
	"""Return ordered {attribute: value} for a variant item."""
	rows = frappe.db.sql(
		"""
		SELECT attribute, attribute_value
		FROM `tabItem Variant Attribute`
		WHERE parent = %s
		ORDER BY idx
		""",
		(item_code,),
		as_dict=True,
	)
	return {r.attribute: r.attribute_value for r in rows if r.attribute}


@frappe.whitelist()
def save_bom_matrix(sales_order, rows=None, rm_columns=None, cells=None, options=None):
	"""Create new default BOM versions from the edited matrix."""
	if not sales_order:
		frappe.throw(_("Sales Order is required."))

	rows = _parse(rows) if not isinstance(rows, list) else rows
	rm_columns = _parse(rm_columns) if not isinstance(rm_columns, list) else rm_columns
	cells = _parse(cells) if not isinstance(cells, dict) else cells
	options = _parse(options) if not isinstance(options, dict) else (options or {})

	update_so = cint(options.get("update_so_bom_no", 1))
	deactivate_old = cint(options.get("deactivate_old", 0))

	created = []
	skipped = []
	errors = []

	# Build RM column list
	rm_codes = []
	for col in rm_columns or []:
		code = col.get("item_code") if isinstance(col, dict) else col
		if code and code not in rm_codes:
			rm_codes.append(code)

	for row in rows or []:
		item_code = row.get("item_code")
		if not item_code:
			continue
		if not cint(row.get("dirty", 1)):
			# Still allow save-all when dirty flag missing — treat as dirty if option
			if not cint(options.get("save_all", 0)):
				skipped.append({"item_code": item_code, "reason": "not changed"})
				continue

		old_bom = row.get("bom_no") or get_default_active_bom(item_code)
		if not old_bom or not frappe.db.exists("BOM", old_bom):
			errors.append({"item_code": item_code, "error": _("No active BOM to base on")})
			continue

		# Collect materials for this FG from matrix
		materials = []
		for rm in rm_codes:
			cell = cells.get(f"{item_code}::{rm}") or {}
			qty = flt(cell.get("qty"))
			if qty <= 0:
				continue
			uom = cell.get("uom") or frappe.db.get_value("Item", rm, "stock_uom") or ""
			materials.append({"item_code": rm, "qty": qty, "uom": uom})

		if not materials:
			errors.append({"item_code": item_code, "error": _("No raw materials with qty > 0")})
			continue

		try:
			new_bom_name = _create_bom_version(
				old_bom=old_bom,
				materials=materials,
				bom_qty=flt(row.get("bom_qty")) or None,
				deactivate_old=deactivate_old,
			)
			if update_so:
				frappe.db.sql(
					"""
					UPDATE `tabSales Order Item`
					SET bom_no = %s
					WHERE parent = %s AND item_code = %s
					""",
					(new_bom_name, sales_order, item_code),
				)
			created.append(
				{
					"item_code": item_code,
					"old_bom": old_bom,
					"new_bom": new_bom_name,
				}
			)
		except Exception as e:
			frappe.log_error(title=f"BOM Bulk Edit failed: {item_code}")
			errors.append({"item_code": item_code, "error": str(e)})

	return {
		"created": created,
		"skipped": skipped,
		"errors": errors,
		"message": _("{0} BOM version(s) created").format(len(created)),
	}


def _create_bom_version(old_bom, materials, bom_qty=None, deactivate_old=0):
	"""Copy submitted BOM, rewrite items, submit as new default active."""
	src = frappe.get_doc("BOM", old_bom)
	new_bom = frappe.copy_doc(src)
	new_bom.name = None
	new_bom.docstatus = 0
	new_bom.amended_from = None
	new_bom.is_active = 1
	new_bom.is_default = 1
	if bom_qty and bom_qty > 0:
		new_bom.quantity = bom_qty

	new_bom.set("items", [])
	for m in materials:
		new_bom.append(
			"items",
			{
				"item_code": m["item_code"],
				"qty": flt(m["qty"]),
				"uom": m.get("uom") or None,
			},
		)

	# Avoid duplicate default conflict before submit — unset old default flag after submit via manage_default_bom
	new_bom.flags.ignore_permissions = False
	new_bom.insert(ignore_permissions=True)
	new_bom.submit()

	if deactivate_old and old_bom != new_bom.name:
		try:
			old = frappe.get_doc("BOM", old_bom)
			if cint(old.is_active):
				old.db_set("is_active", 0)
			if cint(old.is_default):
				old.db_set("is_default", 0)
		except Exception:
			pass

	return new_bom.name


@frappe.whitelist()
def get_item_uom(item_code):
	if not item_code:
		return ""
	return frappe.db.get_value("Item", item_code, "stock_uom") or ""
