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

	Dedicated making-style name patterns (BASIC ZIP CUTTING, REBET BUTTON SET, …)
	always win — even when Style.is_subassembly is unchecked — so SET zip/button
	qty is not blindly copied onto every duvet/pillow combo row.
	"""
	name = cstr(style_name).strip()
	if not name:
		return None

	# Name patterns first (source of truth for making styles)
	if _BUTTON_MAKING_RE.search(name):
		return "button"
	if _ZIP_MAKING_RE.search(name):
		return "zip"

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


def _style_component(style_row):
	"""Return stitching_component / combo_item from an Item style row."""
	if not style_row:
		return ""
	getter = style_row.get if hasattr(style_row, "get") else lambda k, d=None: getattr(style_row, k, d)
	return cstr(getter("stitching_component") or getter("combo_item") or "").strip()


def get_product_combo_pcs(so_item, combo_item):
	"""PCS for one Product Combo Item component on a SET item."""
	if not so_item or not combo_item:
		return None
	pcs = frappe.db.get_value(
		"Product Combo Item",
		{"parent": so_item, "parenttype": "Item", "item": combo_item},
		"pcs",
	)
	if pcs is None:
		# Some sites store combo rows without parenttype populated
		pcs = frappe.db.get_value(
			"Product Combo Item",
			{"parent": so_item, "item": combo_item},
			"pcs",
		)
	if pcs is None:
		return None
	return flt(pcs) or 1


def get_subassembly_unit_qty(item_code, style_name, style_row_qty=None, prefer_style_qty=False):
	"""Per-finished-unit qty for a sub-assembly style (BOM first, then Item Style qty).

	When prefer_style_qty=True (component-scoped duvet/pillow rows), Item Style /
	Product Combo qty wins over SET BOM totals so each combo line does not get
	the full SET zip/button qty.
	"""
	material_type = subassembly_material_type(style_name)
	if not material_type:
		return flt(style_row_qty or 1) or 1

	if prefer_style_qty and flt(style_row_qty or 0) > 0:
		return flt(style_row_qty)

	bom_qty = get_bom_qty_per_finished_unit(item_code, material_type)
	if bom_qty > 0:
		return bom_qty
	return flt(style_row_qty or 1) or 1


def resolve_subassembly_unit_qty(item_code, style_row):
	"""Unit qty for one finished piece from an Item style child row.

	Component-scoped zip/button styles (duvet/pillow via stitching_component)
	use the Item Style qty from Product Combo — not the SET BOM total.
	"""
	style_name = style_row.get("style") if hasattr(style_row, "get") else getattr(style_row, "style", None)
	style_qty = style_row.get("qty") if hasattr(style_row, "get") else getattr(style_row, "qty", None)
	if not style_row.get("is_subassembly") and not subassembly_material_type(style_name):
		return flt(style_qty or 1) or 1

	# Per-component style → keep combo pcs / manually set qty
	if _style_component(style_row):
		return get_subassembly_unit_qty(
			item_code, style_name, style_qty, prefer_style_qty=True
		)
	return get_subassembly_unit_qty(item_code, style_name, style_qty)


def resolve_unit_qty_for_ct_style(ct_row, style_name, fallback_qty=None):
	"""Resolve zip/button unit qty for a report CT line (SET or combo component).

	For combo lines (duvet/pillow), never apply the SET BOM total to every row.
	Prefer Product Combo pcs (source of truth for component qty), then the
	component-scoped Item Style qty when it is not a stale SET BOM overwrite.
	"""
	so_item = getattr(ct_row, "so_item", None) if not hasattr(ct_row, "get") else ct_row.get("so_item")
	combo_item = (
		getattr(ct_row, "combo_item", None) if not hasattr(ct_row, "get") else ct_row.get("combo_item")
	)
	combo_item = cstr(combo_item or "").strip()
	fallback = flt(fallback_qty or 0)

	if not so_item:
		return fallback or 1

	if combo_item:
		from manufacturing_addon.manufacturing_addon.utils.report_style_contractor import (
			get_item_styles,
		)

		material_type = subassembly_material_type(style_name)
		pcs = get_product_combo_pcs(so_item, combo_item)
		if pcs is None:
			# CT row already stores combo pcs from get_data1
			row_pcs = (
				ct_row.get("pcs") if hasattr(ct_row, "get") else getattr(ct_row, "pcs", None)
			)
			if flt(row_pcs or 0) > 0:
				pcs = flt(row_pcs)
		bom_total = (
			get_bom_qty_per_finished_unit(so_item, material_type) if material_type else 0
		)

		# Product Combo pcs is the source of truth for duvet/pillow zip/button qty.
		# SET style qty (e.g. BASIC ZIP CUTTING qty=3) is for the whole set — never
		# apply it separately on pillow AND duvet (that doubles everything).
		if material_type:
			return flt(pcs) or 1

		for style_row in get_item_styles(
			so_item, operation="Sub Assembly", combo_item=combo_item
		):
			row_style = style_row.get("style") if hasattr(style_row, "get") else style_row.style
			if row_style != style_name:
				continue
			# Component-scoped style row only
			if not _style_component(style_row):
				return flt(pcs) or 1
			style_q = flt(
				style_row.get("qty") if hasattr(style_row, "get") else getattr(style_row, "qty", 0)
			)
			# Ignore stale SET BOM total written onto the style row
			if style_q > 0 and bom_total > 0 and abs(style_q - bom_total) < 1e-9:
				return flt(pcs) or 1
			if style_q > 0:
				return style_q
			return resolve_subassembly_unit_qty(so_item, style_row)

		# Unscoped / unknown style on a combo line → component pcs only
		return flt(pcs) or 1

	return get_subassembly_unit_qty(so_item, style_name, fallback or None)


@frappe.whitelist()
def get_subassembly_bom_qty(item_code, style_name, combo_item=None):
	"""API: BOM / combo qty per finished unit for a sub-assembly style.

	When combo_item is passed (duvet/pillow line), returns that component's
	Item Style / Product Combo qty instead of the SET BOM total.
	"""
	material_type = subassembly_material_type(style_name)
	bom_name = get_default_bom(item_code)
	if not material_type:
		return {"material_type": None, "qty_per_unit": 0, "bom": bom_name}

	combo_item = cstr(combo_item or "").strip()
	if combo_item:
		ct_stub = frappe._dict(so_item=item_code, combo_item=combo_item)
		qty = resolve_unit_qty_for_ct_style(ct_stub, style_name)
		return {
			"material_type": material_type,
			"qty_per_unit": qty,
			"bom": bom_name,
			"source": "combo",
		}

	qty = get_bom_qty_per_finished_unit(item_code, material_type)
	return {
		"material_type": material_type,
		"qty_per_unit": qty,
		"bom": bom_name,
		"source": "bom",
	}


def sync_item_subassembly_qty_from_bom(item_code):
	"""Update sub-assembly style rows on Item from default BOM button/zip qty.

	Skips component-scoped rows (duvet/pillow) so Product Combo pcs are kept
	instead of overwriting every component with the SET BOM total.
	"""
	from manufacturing_addon.manufacturing_addon.utils.report_style_contractor import ITEM_STYLE_TABLES

	if not item_code or not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} not found").format(item_code))

	item = frappe.get_doc("Item", item_code)
	updated = []
	skipped = []

	for table_field in ITEM_STYLE_TABLES:
		for row in item.get(table_field) or []:
			if not row.get("style"):
				continue
			if not row.get("is_subassembly") and not subassembly_material_type(row.style):
				continue

			if _style_component(row):
				skipped.append(
					{
						"style": row.style,
						"table": table_field,
						"component": _style_component(row),
						"qty": flt(row.qty),
					}
				)
				continue

			unit_qty = get_subassembly_unit_qty(item_code, row.style, row.qty)
			if flt(row.qty) != unit_qty:
				row.qty = unit_qty
				row.amount = flt(row.rate) * unit_qty
				updated.append({"style": row.style, "table": table_field, "qty": unit_qty})

	if updated:
		item.save(ignore_permissions=True)

	return {"updated": updated, "count": len(updated), "skipped_component_rows": skipped}


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
	Combo lines (duvet/pillow) use that component's Item Style / Product Combo
	qty — not the SET BOM total on every row.
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
			fallback = (sc.get("unit_qty") if hasattr(sc, "get") else None) or (
				sc.get("qty") if hasattr(sc, "get") else None
			)
			unit_qty = resolve_unit_qty_for_ct_style(ct_row, style_name, fallback)
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
	"""Reports that book/count sub-assembly (zip/button) qty against plan.

	Cutting and Stitching are excluded — those reports no longer load or validate
	sub-assembly styles; caps are enforced on Sub Assembly Report only.
	"""
	return (
		("Sub Assembly Report", "Sub Assembly Report CT", "sub_assembly_qty"),
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
	for operation in ("Cutting", "Stitching", "Packing", "Checking", "Sub Assembly"):
		for row in _iter_item_style_rows(item, operation):
			if not row.get("is_subassembly") and not subassembly_material_type(row.style):
				continue
			key = row.name or row.style
			if key not in styles:
				styles[key] = row
	return list(styles.values())


def get_subassembly_qty_used(
	order_sheet,
	so_item,
	style,
	unit_qty,
	exclude_parent=None,
	exclude_parenttype=None,
	combo_item=None,
):
	"""Sum sub-assembly style qty already booked on submitted reports.

	When combo_item is set, only count that component line (DUVET/PILLOW) so
	zip booked on both combos is not double-charged against one row.
	"""
	if not order_sheet or not so_item or not style or unit_qty <= 0:
		return 0

	combo = cstr(combo_item or "").strip()
	total = 0
	for parent_doctype, child_doctype, qty_field in _report_configs():
		parent_filters = {"order_sheet": order_sheet, "docstatus": 1}
		if exclude_parent and exclude_parenttype == parent_doctype:
			parent_filters["name"] = ("!=", exclude_parent)

		reports = frappe.get_all(parent_doctype, filters=parent_filters, pluck="name")
		if not reports:
			continue

		ct_fields = ["name", qty_field, "combo_item"]
		if frappe.get_meta(child_doctype).has_field("pcs"):
			ct_fields.append("pcs")

		ct_filters = {"parent": ["in", reports], "so_item": so_item}
		if combo:
			ct_filters["combo_item"] = combo

		ct_rows = frappe.get_all(
			child_doctype,
			filters=ct_filters,
			fields=ct_fields,
		)
		if not ct_rows:
			continue

		# SET-level (no combo filter): include all component lines for this so_item
		if not combo:
			pass
		else:
			ct_rows = [
				r
				for r in ct_rows
				if cstr(getattr(r, "combo_item", None) or "").strip() == combo
			]

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
			# Prefer stored style qty (what was actually booked)
			booked = flt(sc.qty)
			if booked > 0:
				total += booked
				continue
			work_qty = work_by_ct.get(sc.parent, 0)
			if work_qty <= 0:
				continue
			unit = flt(sc.unit_qty) or unit_qty
			total += work_qty * unit

	return total


def get_production_flow_component_qty(order_sheet, so_item, combo_item=None):
	"""Upstream production qty for one SO item / combo line.

	Sub Assembly / Packing follow Cutting → Stitching → Checking: ceiling is the
	minimum of those stages that already have qty (empty stage ignored).

	When combo_item is blank (SET / packing finished line), returns finished-set
	equivalent = min(component_qty / pcs) across Product Combo components.
	"""
	if not order_sheet or not so_item:
		return 0.0

	combo = cstr(combo_item or "").strip()
	stages = (
		("Cutting Report", "Cutting Report CT", "cutting_qty"),
		("Stitching Report", "Stitching Report CT", "stitching_qty"),
		("Checking Report", "Checking Report CT", "checking_qty"),
	)

	if combo:
		positive = []
		for parent_dt, child_dt, qty_field in stages:
			row = frappe.db.sql(
				f"""
				SELECT SUM(ct.`{qty_field}`)
				FROM `tab{child_dt}` ct
				INNER JOIN `tab{parent_dt}` p ON p.name = ct.parent
				WHERE p.order_sheet = %s AND p.docstatus = 1
				  AND ct.so_item = %s AND ct.combo_item = %s
				""",
				(order_sheet, so_item, combo),
			)
			qty = flt(row[0][0] if row else 0)
			if qty > 0:
				positive.append(qty)
		return min(positive) if positive else 0.0

	# Finished / SET line — convert combo-component totals to set equivalents
	bundle_rows = frappe.get_all(
		"Product Combo Item",
		filters={"parent": so_item},
		fields=["item", "pcs"],
	)
	if not bundle_rows:
		# No combo map: sum lines with empty combo_item only
		positive = []
		for parent_dt, child_dt, qty_field in stages:
			row = frappe.db.sql(
				f"""
				SELECT SUM(ct.`{qty_field}`)
				FROM `tab{child_dt}` ct
				INNER JOIN `tab{parent_dt}` p ON p.name = ct.parent
				WHERE p.order_sheet = %s AND p.docstatus = 1
				  AND ct.so_item = %s
				  AND (ct.combo_item IS NULL OR ct.combo_item = '')
				""",
				(order_sheet, so_item),
			)
			qty = flt(row[0][0] if row else 0)
			if qty > 0:
				positive.append(qty)
		return min(positive) if positive else 0.0

	positive = []
	for parent_dt, child_dt, qty_field in stages:
		rows = frappe.db.sql(
			f"""
			SELECT ct.combo_item, SUM(ct.`{qty_field}`) AS total_qty
			FROM `tab{child_dt}` ct
			INNER JOIN `tab{parent_dt}` p ON p.name = ct.parent
			WHERE p.order_sheet = %s AND p.docstatus = 1
			  AND ct.so_item = %s
			  AND IFNULL(ct.combo_item, '') != ''
			GROUP BY ct.combo_item
			""",
			(order_sheet, so_item),
			as_dict=True,
		)
		total_map = {cstr(r.combo_item): flt(r.total_qty) for r in rows}
		normalized = []
		for b in bundle_rows:
			pcs = flt(b.pcs) or 1
			normalized.append(flt(total_map.get(cstr(b.item), 0)) / pcs)
		stage_qty = min(normalized) if normalized else 0
		if stage_qty > 0:
			positive.append(stage_qty)

	return min(positive) if positive else 0.0


def _subassembly_row_ceiling(doc, row, report_label):
	"""Finished-piece ceiling for product + style caps.

	Sub Assembly / Packing / Checking: Cutting→Stitching→Checking flow
	(may exceed order/plan when production over-cut).
	Other reports: max(order, plan) in finished pieces.
	"""
	order_qty = flt(row.get("order_qty"))
	planned_qty = flt(row.get("planned_qty"))
	pcs = flt(row.get("pcs") if hasattr(row, "get") else getattr(row, "pcs", None)) or 1
	# planned_qty on combo CT is usually component pieces
	plan_finished = planned_qty / pcs if pcs else planned_qty
	order_plan = max(order_qty, plan_finished)

	doctype = cstr(getattr(doc, "doctype", None) or "")
	label = cstr(report_label or "")
	flow_doctypes = {
		"Sub Assembly Report",
		"Packing Report",
		"Checking Report",
	}
	if doctype not in flow_doctypes and label not in flow_doctypes:
		return order_plan, "Order/Plan", order_plan

	# Prefer already-calculated upstream fields on Packing CT (SET-equivalent)
	if doctype == "Packing Report" or label == "Packing Report":
		positives = []
		for field in (
			"finished_cutting_qty",
			"finished_stitching_qty",
			"finished_quality_qty",
		):
			q = flt(row.get(field) if hasattr(row, "get") else getattr(row, field, 0))
			if q > 0:
				positives.append(q)
		if positives:
			flow_finished = min(positives)
			return flow_finished, "Cutting/Stitching/Checking", flow_finished * pcs

	combo_item = cstr(getattr(row, "combo_item", None) or "").strip()
	flow_component = get_production_flow_component_qty(
		doc.get("order_sheet"), row.get("so_item"), combo_item
	)
	flow_finished = flow_component / pcs if pcs else flow_component
	if flow_finished > 0:
		return flow_finished, "Cutting/Stitching/Checking", flow_component
	# No upstream yet — fall back to order/plan so empty lines still validate
	return order_plan, "Order/Plan", order_plan * pcs


def validate_subassembly_qty_caps(doc, child_table_field, work_qty_field, report_label, throw=True):
	"""Ensure finished qty × BOM does not exceed the allowed ceiling × BOM unit qty.

	Sub Assembly Report ceiling = Cutting/Stitching/Checking flow (not order/plan).
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

		qty_ceiling, ceiling_label, _flow_component = _subassembly_row_ceiling(
			doc, row, report_label
		)
		if qty_ceiling <= 0:
			continue

		if work_qty > qty_ceiling + 1e-9:
			msg = _(
				"Row {0}: Finished Product Qty {1} cannot exceed {2} Qty {3}."
			).format(row.idx, work_qty, ceiling_label, qty_ceiling)
			if throw:
				frappe.throw(msg, title=_("{0} — Qty Limit").format(report_label))
			warnings.append(msg)
			continue

		# Zip/button style caps belong only on Sub Assembly Report
		doctype = cstr(getattr(doc, "doctype", None) or "")
		if doctype != "Sub Assembly Report" and cstr(report_label) != "Sub Assembly Report":
			continue

		combo_item = cstr(getattr(row, "combo_item", None) or "").strip()
		style_rows = _subassembly_styles_for_item(row.so_item)
		if not style_rows:
			continue

		for style_row in style_rows:
			# On combo CT lines, only validate styles for that component
			component = _style_component(style_row)
			if combo_item and component and component != combo_item:
				continue

			unit_qty = (
				resolve_unit_qty_for_ct_style(row, style_row.style, style_row.get("qty"))
				if combo_item
				else resolve_subassembly_unit_qty(row.so_item, style_row)
			)
			# Unscoped SET zip (qty=2) booked on both DUVET+PILLOW at unit 1 each:
			# per combo line, treat unit as 1 and scope "used" to that combo.
			if combo_item and not component and flt(unit_qty) > 1:
				unit_qty = 1.0

			max_total = qty_ceiling * unit_qty
			used = get_subassembly_qty_used(
				order_sheet,
				row.so_item,
				style_row.style,
				unit_qty,
				exclude_parent=doc.name if doc.name else None,
				exclude_parenttype=doc.doctype,
				combo_item=combo_item or None,
			)
			current = work_qty * unit_qty
			if used + current > max_total + 1e-9:
				remaining = max(max_total - used, 0)
				msg = _(
					"Row {0}: {1} style qty cannot exceed {8} limit. "
					"Finished Product Qty {2} × BOM {3} = {4}, but max is {5} "
					"({6} pcs × {3} per pc). Already used {7}. Remaining {9}."
				).format(
					row.idx,
					style_row.style,
					work_qty,
					unit_qty,
					current,
					max_total,
					qty_ceiling,
					used,
					ceiling_label,
					remaining,
				)
				if throw:
					frappe.throw(msg, title=_("{0} — Sub-Assembly Limit").format(report_label))
				warnings.append(msg)

	return warnings
