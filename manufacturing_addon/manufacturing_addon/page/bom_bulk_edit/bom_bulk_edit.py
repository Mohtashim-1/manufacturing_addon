# Copyright (c) 2026, Manufacturing Addon and contributors
# For license information, please see license.txt

"""Bulk Edit BOM portal — SO → default active BOMs → RM matrix → new BOM versions."""

import frappe
from frappe import _
from frappe.utils import cint, flt


def _get_default_active_bom(item_code):
	"""Lazy import — avoid heavy production_plan load on every request."""
	from manufacturing_addon.manufacturing_addon.doctype.production_plan.production_plan import (
		get_default_active_bom,
	)

	return get_default_active_bom(item_code)


def _parse(data):
	if isinstance(data, str):
		return frappe.parse_json(data) or {}
	return data or {}


@frappe.whitelist()
def get_bom_matrix(sales_order, item_template=None, variants_only=1):
	"""Load FG variant items from Sales Order + their default active BOM RM matrix.

	Batched queries (no per-item N+1) for fast load on large SOs.
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
			IFNULL(i.default_bom, '') AS default_bom
		FROM `tabSales Order Item` soi
		INNER JOIN `tabItem` i ON i.name = soi.item_code
		WHERE soi.parent = %s
		ORDER BY IFNULL(i.variant_of, ''), soi.idx
		""",
		(sales_order,),
		as_dict=True,
	)

	templates_on_so = []
	seen_templates = set()
	# Aggregate unique FG rows first
	seen = {}
	pending_rows = []

	for line in so_items:
		item_code = line.item_code
		if not item_code:
			continue

		template = (line.item_template or "").strip()
		is_template_item = cint(line.has_variants) == 1
		is_variant = bool(template) and not is_template_item

		if only_variants and not is_variant:
			continue
		if template_filter and template != template_filter:
			continue

		if template and template not in seen_templates:
			seen_templates.add(template)
			templates_on_so.append(template)

		if item_code in seen:
			pending_rows[seen[item_code]]["so_qty"] = flt(pending_rows[seen[item_code]]["so_qty"]) + flt(
				line.so_qty
			)
			continue

		seen[item_code] = len(pending_rows)
		pending_rows.append(
			{
				"item_code": item_code,
				"item_name": line.item_name,
				"item_template": template,
				"is_variant": 1 if is_variant else 0,
				"so_detail": line.so_detail,
				"so_qty": flt(line.so_qty),
				"so_bom_no": line.so_bom_no or "",
				"default_bom": line.default_bom or "",
				"uom": line.uom or "",
			}
		)

	item_codes = [r["item_code"] for r in pending_rows]
	payload = _assemble_matrix(pending_rows)
	payload.update(
		{
			"sales_order": so.name,
			"customer": so.customer,
			"company": so.company,
			"transaction_date": so.transaction_date,
			"item_template": template_filter,
			"templates": templates_on_so,
			"variants_only": only_variants,
			"load_mode": "sales_order",
			"note": _(
				"Loaded from Sales Order. Same raw material shares one column. "
				"Edit / fill-down / replace / add material, then Save new default BOM versions."
			),
		}
	)
	return payload


@frappe.whitelist()
def get_bom_matrix_for_item(item_query, include_siblings=0, limit=40):
	"""Load BOM matrix by Item search (no Sales Order required).

	Default path is single-item and intentionally minimal SQL for speed.
	"""
	import time

	t0 = time.time()
	q = (item_query or "").strip()
	if not q:
		frappe.throw(_("Type or select an Item to load."))

	resolved = _resolve_item_query(q)
	t_resolve = time.time() - t0
	if not resolved.get("item_code"):
		matches = resolved.get("matches") or []
		if matches:
			return {
				"sales_order": "",
				"load_mode": "item",
				"needs_pick": 1,
				"matches": matches,
				"rows": [],
				"rm_columns": [],
				"cells": {},
				"note": _("Multiple items matched — pick one."),
				"_timing": {"resolve_sec": round(t_resolve, 3)},
			}
		frappe.throw(_("No Item found matching: {0}").format(q))

	item_code = resolved["item_code"]
	include_siblings = cint(include_siblings)

	# Fast path: one item only
	if not include_siblings:
		payload = _fast_single_item_matrix(item_code)
		payload["_timing"] = {
			"resolve_sec": round(t_resolve, 3),
			"total_sec": round(time.time() - t0, 3),
			"mode": "single",
		}
		# Always log for debugging slow desk requests
		frappe.logger("bom_bulk_edit").info(
			f"single item ok query={q!r} item={item_code!r} timing={payload['_timing']}"
		)
		print(f"[bom_bulk_edit] single {payload['_timing']} item={item_code}")
		return payload

	limit = max(1, min(cint(limit) or 40, 100))
	meta = frappe.db.get_value(
		"Item",
		item_code,
		["name", "item_name", "variant_of", "has_variants", "default_bom", "stock_uom"],
		as_dict=True,
	)
	if not meta:
		frappe.throw(_("Item {0} not found").format(item_code))

	template = (meta.variant_of or "").strip()
	codes = [item_code]

	if template:
		siblings = frappe.db.sql(
			"""
			SELECT name
			FROM `tabItem`
			WHERE variant_of = %s AND disabled = 0 AND has_variants = 0
			ORDER BY CASE WHEN name = %s THEN 0 ELSE 1 END, name
			LIMIT %s
			""",
			(template, item_code, limit),
			as_list=True,
		)
		codes = [r[0] for r in siblings] or [item_code]
	elif cint(meta.has_variants):
		template = item_code
		siblings = frappe.db.sql(
			"""
			SELECT name FROM `tabItem`
			WHERE variant_of = %s AND disabled = 0
			ORDER BY name LIMIT %s
			""",
			(item_code, limit),
			as_list=True,
		)
		codes = [r[0] for r in siblings]
		if not codes:
			frappe.throw(_("Template {0} has no variant items").format(item_code))

	item_map = {
		r.name: r
		for r in frappe.db.sql(
			"""
			SELECT name, item_name, variant_of, has_variants, default_bom, stock_uom
			FROM `tabItem` WHERE name IN ({})
			""".format(",".join(["%s"] * len(codes))),
			tuple(codes),
			as_dict=True,
		)
	}

	pending_rows = []
	templates = []
	seen_t = set()
	for code in codes:
		it = item_map.get(code)
		if not it:
			continue
		t = (it.variant_of or "").strip()
		if t and t not in seen_t:
			seen_t.add(t)
			templates.append(t)
		pending_rows.append(
			{
				"item_code": code,
				"item_name": it.item_name,
				"item_template": t,
				"is_variant": 1 if t and not cint(it.has_variants) else 0,
				"so_detail": "",
				"so_qty": 0,
				"so_bom_no": "",
				"default_bom": it.default_bom or "",
				"uom": it.stock_uom or "",
			}
		)

	payload = _assemble_matrix(pending_rows)
	payload.update(
		{
			"sales_order": "",
			"customer": "",
			"company": "",
			"transaction_date": None,
			"item_template": template or "",
			"templates": templates,
			"variants_only": 1,
			"load_mode": "item",
			"resolved_item": item_code,
			"query": q,
			"note": _("Loaded template variants (slower). Uncheck for single-item speed."),
			"_timing": {
				"resolve_sec": round(t_resolve, 3),
				"total_sec": round(time.time() - t0, 3),
				"mode": "siblings",
				"items": len(pending_rows),
			},
		}
	)
	return payload


def _fast_single_item_matrix(item_code):
	"""Minimal queries for one FG item BOM — keep UI snappy."""
	meta = frappe.db.get_value(
		"Item",
		item_code,
		["name", "item_name", "variant_of", "has_variants", "default_bom", "stock_uom"],
		as_dict=True,
	)
	if not meta:
		frappe.throw(_("Item {0} not found").format(item_code))
	if cint(meta.has_variants):
		frappe.throw(
			_("“{0}” is an Item Template. Tick “All template variants” or pick a variant.").format(
				item_code
			)
		)

	bom_no = ""
	# 1) Item.default_bom if active submitted
	if meta.default_bom:
		st = frappe.db.get_value(
			"BOM", meta.default_bom, ["is_active", "docstatus", "quantity", "uom"], as_dict=True
		)
		if st and cint(st.is_active) == 1 and cint(st.docstatus) == 1:
			bom_no = meta.default_bom
			bom_qty = flt(st.quantity) or 1
			bom_uom = st.uom or meta.stock_uom or ""
			is_default = 1
		else:
			st = None
	else:
		st = None

	if not bom_no:
		row = frappe.db.sql(
			"""
			SELECT name, quantity, uom, is_default
			FROM `tabBOM`
			WHERE item = %s AND is_active = 1 AND docstatus = 1
			ORDER BY is_default DESC, modified DESC
			LIMIT 1
			""",
			(item_code,),
			as_dict=True,
		)
		if row:
			bom_no = row[0].name
			bom_qty = flt(row[0].quantity) or 1
			bom_uom = row[0].uom or meta.stock_uom or ""
			is_default = cint(row[0].is_default)
		else:
			bom_qty, bom_uom, is_default = 1, meta.stock_uom or "", 0

	materials = []
	if bom_no:
		materials = frappe.db.sql(
			"""
			SELECT item_code, item_name, IFNULL(qty, 0) AS qty, IFNULL(uom, '') AS uom, name AS bom_item_name
			FROM `tabBOM Item`
			WHERE parent = %s
			ORDER BY idx
			""",
			(bom_no,),
			as_dict=True,
		)

	# Skip attributes for speed — optional light fetch
	attrs = {}
	attrs_label = ""
	attr_rows = frappe.db.sql(
		"""
		SELECT attribute, attribute_value
		FROM `tabItem Variant Attribute`
		WHERE parent = %s
		ORDER BY idx
		LIMIT 12
		""",
		(item_code,),
		as_dict=True,
	)
	if attr_rows:
		attrs = {r.attribute: r.attribute_value for r in attr_rows if r.attribute}
		attrs_label = ", ".join(f"{k}: {v}" for k, v in attrs.items())

	rm_order = []
	cells = {}
	for m in materials:
		rm = m.item_code
		if not rm:
			continue
		rm_order.append({"item_code": rm, "item_name": m.item_name or rm, "uom": m.uom or ""})
		cells[f"{item_code}::{rm}"] = {
			"qty": flt(m.qty),
			"uom": m.uom or "",
			"bom_item_name": m.bom_item_name,
		}

	template = (meta.variant_of or "").strip()
	return {
		"sales_order": "",
		"customer": "",
		"company": "",
		"transaction_date": None,
		"item_template": template,
		"templates": [template] if template else [],
		"variants_only": 1,
		"load_mode": "item",
		"resolved_item": item_code,
		"rows": [
			{
				"item_code": item_code,
				"item_name": meta.item_name,
				"item_template": template,
				"is_variant": 1 if template else 0,
				"attributes": attrs,
				"attributes_label": attrs_label,
				"so_detail": "",
				"so_qty": 0,
				"bom_no": bom_no or "",
				"bom_qty": bom_qty,
				"bom_uom": bom_uom,
				"is_active": 1 if bom_no else 0,
				"is_default": is_default if bom_no else 0,
				"has_bom": 1 if bom_no else 0,
				"dirty": 0,
			}
		],
		"rm_columns": rm_order,
		"cells": cells,
		"note": _("Single item loaded (fast). Tick “All template variants” to edit siblings together."),
	}


def _resolve_item_query(q):
	"""Resolve item with indexed-friendly lookups (avoid slow leading-wildcard scans)."""
	import re

	candidates = [q]
	if "+" in q:
		candidates.append(q.replace("+", " "))
	if " " in q and "+" not in q:
		# common truncation / encoding swap
		candidates.append(q.replace(" ", "+", 1) if "X" in q else q)

	for c in candidates:
		if frappe.db.exists("Item", c):
			return {"item_code": c}

	# Prefix match (uses index better than %q%)
	for c in candidates:
		rows = frappe.db.sql(
			"""
			SELECT name, item_name, variant_of
			FROM `tabItem`
			WHERE disabled = 0 AND name LIKE %s
			ORDER BY name
			LIMIT 20
			""",
			(c + "%",),
			as_dict=True,
		)
		if len(rows) == 1:
			return {"item_code": rows[0].name}
		if len(rows) > 1:
			return {
				"matches": [
					{
						"item_code": r.name,
						"item_name": r.item_name,
						"item_template": r.variant_of or "",
					}
					for r in rows
				]
			}

	# Numeric token (EAN / barcode fragment) — last long digit run
	nums = re.findall(r"\d{8,}", q)
	if nums:
		token = nums[-1]
		rows = frappe.db.sql(
			"""
			SELECT name, item_name, variant_of
			FROM `tabItem`
			WHERE disabled = 0 AND name LIKE %s
			ORDER BY
				CASE WHEN name LIKE %s THEN 0 ELSE 1 END,
				name
			LIMIT 20
			""",
			(f"%{token}%", f"%{token}"),
			as_dict=True,
		)
		# Prefer non-sticker / exact-ish contains of original stem
		stem = q.split("-")[0] if q else ""
		if stem and len(rows) > 1:
			pref = [r for r in rows if cstr(r.name).startswith(stem)]
			if len(pref) == 1:
				return {"item_code": pref[0].name}
			if pref:
				rows = pref
		if len(rows) == 1:
			return {"item_code": rows[0].name}
		if rows:
			return {
				"matches": [
					{
						"item_code": r.name,
						"item_name": r.item_name,
						"item_template": r.variant_of or "",
					}
					for r in rows
				]
			}

	return {}


def cstr(v):
	return "" if v is None else str(v)


def _assemble_matrix(pending_rows):
	"""Shared BOM/RM matrix builder from pending FG rows."""
	item_codes = [r["item_code"] for r in pending_rows]
	if not item_codes:
		return {"rows": [], "rm_columns": [], "cells": {}}

	bom_by_item = _batch_default_boms(item_codes, pending_rows)
	bom_nos = list({b for b in bom_by_item.values() if b})
	bom_meta_map = {}
	if bom_nos:
		for b in frappe.db.sql(
			"""
			SELECT name, item, quantity, uom, is_active, is_default, docstatus
			FROM `tabBOM`
			WHERE name IN ({})
			""".format(",".join(["%s"] * len(bom_nos))),
			tuple(bom_nos),
			as_dict=True,
		):
			bom_meta_map[b.name] = b

	materials_by_bom = {b: [] for b in bom_nos}
	if bom_nos:
		for m in frappe.db.sql(
			"""
			SELECT
				bi.parent,
				bi.name AS bom_item_name,
				bi.item_code,
				bi.item_name,
				IFNULL(bi.qty, 0) AS qty,
				IFNULL(bi.uom, '') AS uom
			FROM `tabBOM Item` bi
			WHERE bi.parent IN ({})
			ORDER BY bi.parent, bi.idx
			""".format(",".join(["%s"] * len(bom_nos))),
			tuple(bom_nos),
			as_dict=True,
		):
			materials_by_bom.setdefault(m.parent, []).append(m)

	attrs_by_item = {c: {} for c in item_codes}
	for a in frappe.db.sql(
		"""
		SELECT parent, attribute, attribute_value, idx
		FROM `tabItem Variant Attribute`
		WHERE parent IN ({})
		ORDER BY parent, idx
		""".format(",".join(["%s"] * len(item_codes))),
		tuple(item_codes),
		as_dict=True,
	):
		if a.attribute:
			attrs_by_item.setdefault(a.parent, {})[a.attribute] = a.attribute_value

	rows = []
	rm_order = []
	rm_set = set()
	cells = {}

	for pr in pending_rows:
		item_code = pr["item_code"]
		bom_no = bom_by_item.get(item_code) or ""
		bom_meta = bom_meta_map.get(bom_no)
		materials = materials_by_bom.get(bom_no, []) if bom_no else []
		attrs = attrs_by_item.get(item_code) or {}

		rows.append(
			{
				"item_code": item_code,
				"item_name": pr.get("item_name"),
				"item_template": pr.get("item_template") or "",
				"is_variant": cint(pr.get("is_variant")),
				"attributes": attrs,
				"attributes_label": ", ".join(f"{k}: {v}" for k, v in attrs.items()) if attrs else "",
				"so_detail": pr.get("so_detail") or "",
				"so_qty": flt(pr.get("so_qty")),
				"bom_no": bom_no,
				"bom_qty": flt(bom_meta.quantity) if bom_meta else 1,
				"bom_uom": (bom_meta.uom if bom_meta else pr.get("uom")) or "",
				"is_active": cint(bom_meta.is_active) if bom_meta else 0,
				"is_default": cint(bom_meta.is_default) if bom_meta else 0,
				"has_bom": 1 if bom_meta else 0,
				"dirty": 0,
			}
		)

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

	return {"rows": rows, "rm_columns": rm_order, "cells": cells}


def _batch_default_boms(item_codes, pending_rows):
	"""Resolve default active BOM per item with few SQL round-trips."""
	result = {}
	# Prefer Item.default_bom when active+submitted
	default_map = {r["item_code"]: r.get("default_bom") or "" for r in pending_rows}
	so_bom_map = {r["item_code"]: r.get("so_bom_no") or "" for r in pending_rows}

	candidate_boms = list({b for b in default_map.values() if b} | {b for b in so_bom_map.values() if b})
	valid_defaults = set()
	if candidate_boms:
		for name, is_active, docstatus in frappe.db.sql(
			"""
			SELECT name, is_active, docstatus
			FROM `tabBOM`
			WHERE name IN ({})
			""".format(",".join(["%s"] * len(candidate_boms))),
			tuple(candidate_boms),
		):
			if cint(is_active) == 1 and cint(docstatus) == 1:
				valid_defaults.add(name)

	missing = []
	for code in item_codes:
		dbom = default_map.get(code) or ""
		if dbom and dbom in valid_defaults:
			result[code] = dbom
		else:
			missing.append(code)

	if missing:
		# Active default BOM per item (newest modified)
		rows = frappe.db.sql(
			"""
			SELECT b.item, b.name
			FROM `tabBOM` b
			INNER JOIN (
				SELECT item, MAX(modified) AS mx
				FROM `tabBOM`
				WHERE item IN ({0})
					AND is_active = 1 AND is_default = 1 AND docstatus = 1
				GROUP BY item
			) t ON t.item = b.item AND t.mx = b.modified
			WHERE b.is_active = 1 AND b.is_default = 1 AND b.docstatus = 1
			""".format(",".join(["%s"] * len(missing))),
			tuple(missing),
		)
		found = {item: name for item, name in rows}
		still = []
		for code in missing:
			if code in found:
				result[code] = found[code]
			else:
				still.append(code)

		if still:
			# Any active BOM (newest)
			rows = frappe.db.sql(
				"""
				SELECT b.item, b.name
				FROM `tabBOM` b
				INNER JOIN (
					SELECT item, MAX(modified) AS mx
					FROM `tabBOM`
					WHERE item IN ({0})
						AND is_active = 1 AND docstatus = 1
					GROUP BY item
				) t ON t.item = b.item AND t.mx = b.modified
				WHERE b.is_active = 1 AND b.docstatus = 1
				""".format(",".join(["%s"] * len(still))),
				tuple(still),
			)
			found2 = {item: name for item, name in rows}
			for code in still:
				if code in found2:
					result[code] = found2[code]
				else:
					# last resort: SO bom_no if valid
					sb = so_bom_map.get(code) or ""
					result[code] = sb if sb in valid_defaults else sb or ""

	return result


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
def save_bom_matrix(sales_order=None, rows=None, rm_columns=None, cells=None, options=None):
	"""Create new default BOM versions from the edited matrix."""
	rows = _parse(rows) if not isinstance(rows, list) else rows
	rm_columns = _parse(rm_columns) if not isinstance(rm_columns, list) else rm_columns
	cells = _parse(cells) if not isinstance(cells, dict) else cells
	options = _parse(options) if not isinstance(options, dict) else (options or {})

	sales_order = (sales_order or "").strip()
	update_so = cint(options.get("update_so_bom_no", 1)) if sales_order else 0
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

		old_bom = row.get("bom_no") or _get_default_active_bom(item_code)
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
def bom_bulk_edit_ping():
	"""Tiny health check so browser can measure network/server latency."""
	import time

	return {"ok": 1, "ts": time.time(), "site": frappe.local.site}


@frappe.whitelist()
def get_item_uom(item_code):
	if not item_code:
		return ""
	return frappe.db.get_value("Item", item_code, "stock_uom") or ""
