# Copyright (c) 2026, Manufacturing Addon and contributors
# License: MIT

"""Simple BOM raw-material replace page — pick FG item → pick RM → replace → new default BOM."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt


def _get_default_active_bom(item_code):
	from manufacturing_addon.manufacturing_addon.doctype.production_plan.production_plan import (
		get_default_active_bom,
	)

	return get_default_active_bom(item_code)


@frappe.whitelist()
def search_fg_items(txt=None, limit=50):
	"""List finished / BOM items for the simple replace list."""
	txt = cstr(txt or "").strip()
	limit = min(cint(limit) or 50, 100)

	params = []
	where = [
		"i.disabled = 0",
		"i.has_variants = 0",
		"(IFNULL(i.default_bom, '') != '' OR EXISTS ("
		"  SELECT 1 FROM `tabBOM` b"
		"  WHERE b.item = i.name AND b.docstatus = 1 AND b.is_active = 1"
		"))",
	]
	if txt:
		where.append("(i.name LIKE %s OR i.item_name LIKE %s OR i.item_code LIKE %s)")
		like = f"%{txt}%"
		params.extend([like, like, like])

	params.append(limit)
	rows = frappe.db.sql(
		f"""
		SELECT
			i.name AS item_code,
			i.item_name,
			i.stock_uom,
			IFNULL(i.default_bom, '') AS default_bom,
			IFNULL(i.variant_of, '') AS variant_of
		FROM `tabItem` i
		WHERE {" AND ".join(where)}
		ORDER BY i.modified DESC
		LIMIT %s
		""",
		tuple(params),
		as_dict=True,
	)

	out = []
	for r in rows:
		bom = r.default_bom or _get_default_active_bom(r.item_code)
		if not bom:
			continue
		out.append(
			{
				"item_code": r.item_code,
				"item_name": r.item_name,
				"stock_uom": r.stock_uom,
				"default_bom": bom,
				"variant_of": r.variant_of or "",
			}
		)
	return out


@frappe.whitelist()
def get_item_bom_materials(item_code):
	"""Return default active BOM + raw material rows for an FG item."""
	item_code = cstr(item_code).strip()
	if not item_code:
		frappe.throw(_("Select an item"))

	if not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} not found").format(item_code))

	bom_no = _get_default_active_bom(item_code)
	if not bom_no:
		frappe.throw(_("No active default BOM for {0}").format(item_code))

	bom = frappe.db.get_value(
		"BOM",
		bom_no,
		["name", "item", "item_name", "quantity", "uom", "is_active", "is_default", "docstatus"],
		as_dict=True,
	)
	if not bom or cint(bom.docstatus) != 1:
		frappe.throw(_("BOM {0} is not submitted").format(bom_no))

	materials = frappe.db.sql(
		"""
		SELECT
			bi.name AS bom_item_name,
			bi.idx,
			bi.item_code,
			bi.item_name,
			IFNULL(bi.qty, 0) AS qty,
			IFNULL(bi.uom, '') AS uom,
			IFNULL(bi.stock_uom, '') AS stock_uom
		FROM `tabBOM Item` bi
		WHERE bi.parent = %s
		ORDER BY bi.idx
		""",
		(bom_no,),
		as_dict=True,
	)

	return {
		"item_code": item_code,
		"item_name": frappe.db.get_value("Item", item_code, "item_name") or item_code,
		"bom_no": bom.name,
		"bom_qty": flt(bom.quantity),
		"bom_uom": bom.uom or "",
		"materials": materials,
	}


@frappe.whitelist()
def replace_bom_material(
	item_code,
	old_rm_item,
	new_rm_item,
	new_qty=None,
	deactivate_old=0,
):
	"""Replace one raw material on the FG item's default BOM; create a new default BOM version."""
	item_code = cstr(item_code).strip()
	old_rm_item = cstr(old_rm_item).strip()
	new_rm_item = cstr(new_rm_item).strip()
	deactivate_old = cint(deactivate_old)

	if not item_code or not old_rm_item or not new_rm_item:
		frappe.throw(_("Item, current material, and new material are required"))

	if not frappe.db.exists("Item", new_rm_item):
		frappe.throw(_("New material {0} not found").format(new_rm_item))
	if cint(frappe.db.get_value("Item", new_rm_item, "disabled")):
		frappe.throw(_("New material {0} is disabled").format(new_rm_item))

	payload = get_item_bom_materials(item_code)
	old_bom = payload["bom_no"]
	materials = []
	replaced = False
	kept_qty = None

	for row in payload["materials"]:
		code = row.item_code
		qty = flt(row.qty)
		uom = row.uom or row.stock_uom or ""
		if code == old_rm_item:
			if replaced and new_rm_item == old_rm_item:
				# same RM appears twice — merge qty into first replace
				for m in materials:
					if m["item_code"] == new_rm_item:
						m["qty"] = flt(m["qty"]) + (
							flt(new_qty) if new_qty not in (None, "") else qty
						)
						break
				continue
			qty = flt(new_qty) if new_qty not in (None, "") else qty
			kept_qty = qty
			code = new_rm_item
			uom = frappe.db.get_value("Item", new_rm_item, "stock_uom") or uom
			replaced = True

		# merge duplicate RMs after replace
		found = None
		for m in materials:
			if m["item_code"] == code:
				found = m
				break
		if found:
			found["qty"] = flt(found["qty"]) + flt(qty)
		else:
			materials.append({"item_code": code, "qty": qty, "uom": uom})

	if not replaced:
		frappe.throw(
			_("Material {0} is not on BOM {1}").format(old_rm_item, old_bom)
		)

	if flt(kept_qty) <= 0:
		frappe.throw(_("Qty must be greater than zero"))

	from manufacturing_addon.manufacturing_addon.page.bom_bulk_edit.bom_bulk_edit import (
		_create_bom_version,
	)

	new_bom = _create_bom_version(
		old_bom=old_bom,
		materials=materials,
		bom_qty=flt(payload.get("bom_qty")) or None,
		deactivate_old=deactivate_old,
	)

	return {
		"item_code": item_code,
		"old_bom": old_bom,
		"new_bom": new_bom,
		"old_rm_item": old_rm_item,
		"new_rm_item": new_rm_item,
		"qty": kept_qty,
		"materials_count": len(materials),
	}
