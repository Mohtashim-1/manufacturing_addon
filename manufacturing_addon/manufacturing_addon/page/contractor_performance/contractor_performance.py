# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def _date_range(from_date=None, to_date=None):
	from_date = from_date or nowdate()
	to_date = to_date or from_date
	try:
		from_date = getdate(from_date)
		to_date = getdate(to_date)
	except Exception:
		frappe.throw(_("Invalid from/to date"))
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date"))
	return from_date, to_date


def _contractor_display_name(mc_name: str | None) -> str:
	if not mc_name:
		return ""
	try:
		supplier_link = frappe.get_cached_value("Manufacturing Contractor", mc_name, "supplier")
		if supplier_link:
			n = frappe.get_cached_value("Supplier", supplier_link, "supplier_name")
			return n or supplier_link
	except Exception:
		pass
	return mc_name


def _item_label(so_item, combo_item, article, design, colour) -> str:
	code = so_item or combo_item
	if code:
		name = frappe.db.get_value("Item", code, "item_name")
		return name or code
	parts = [p for p in (article, design, colour) if p]
	return " / ".join(parts) if parts else _("Unknown item")


def _collect_item_codes(*row_lists):
	codes = set()
	for lst in row_lists:
		for r in lst:
			if r.get("so_item"):
				codes.add(r["so_item"])
			if r.get("combo_item"):
				codes.add(r["combo_item"])
	return codes


def _item_name_map(codes):
	m = {}
	for c in codes:
		m[c] = frappe.db.get_value("Item", c, "item_name") or c
	return m


def _rich_item_fields(row, item_names: dict) -> dict:
	"""Labels for product-combo rows: show combo component vs SO parent clearly."""
	so_item = (row.get("so_item") or "").strip()
	combo_item = (row.get("combo_item") or "").strip()
	article = row.get("article")
	design = row.get("design")
	colour = row.get("colour")

	so_label = item_names.get(so_item, so_item) if so_item else ""
	co_label = item_names.get(combo_item, combo_item) if combo_item else ""

	if combo_item and so_item:
		primary = co_label or combo_item
		detail = _("SO item: {0}").format(so_label or so_item)
	elif combo_item:
		primary = co_label or combo_item
		detail = ""
	elif so_item:
		primary = so_label or so_item
		detail = ""
	else:
		primary = _item_label(None, None, article, design, colour)
		detail = ""

	return {
		"item_label": primary,
		"combo_detail": detail,
		"so_item": so_item or None,
		"combo_item": combo_item or None,
		"so_item_label": so_label,
		"combo_item_label": co_label,
		"is_combo": bool(combo_item and so_item),
	}


def _cutting_agg(from_date, to_date, customer=None, so_item=None, combo_item=None, supplier=None):
	conditions = ["cr.docstatus = 1", "cr.date >= %(from_date)s", "cr.date <= %(to_date)s"]
	values = {"from_date": from_date, "to_date": to_date}
	if customer:
		conditions.append("cr.customer = %(customer)s")
		values["customer"] = customer
	if so_item:
		conditions.append("NULLIF(TRIM(crct.so_item), '') = %(so_item)s")
		values["so_item"] = so_item
	if combo_item:
		conditions.append("NULLIF(TRIM(crct.combo_item), '') = %(combo_item)s")
		values["combo_item"] = combo_item
	if supplier:
		conditions.append("cr.supplier = %(supplier)s")
		values["supplier"] = supplier
	where_clause = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			COALESCE(
				NULLIF(TRIM(crct.so_item), ''),
				NULLIF(TRIM(crct.combo_item), ''),
				CONCAT(
					'ATTR:',
					IFNULL(crct.article, ''),
					'|',
					IFNULL(crct.design, ''),
					'|',
					IFNULL(crct.colour, '')
				)
			) AS item_key,
			MAX(crct.so_item) AS so_item,
			MAX(crct.combo_item) AS combo_item,
			MAX(crct.article) AS article,
			MAX(crct.design) AS design,
			MAX(crct.colour) AS colour,
			cr.supplier AS contractor,
			SUM(IFNULL(crct.cutting_qty, 0)) AS qty,
			COUNT(DISTINCT cr.name) AS report_count,
			GROUP_CONCAT(DISTINCT cr.name ORDER BY cr.name SEPARATOR ',') AS reports
		FROM `tabCutting Report` cr
		INNER JOIN `tabCutting Report CT` crct ON crct.parent = cr.name
		WHERE {where_clause}
		GROUP BY item_key, cr.supplier
		HAVING SUM(IFNULL(crct.cutting_qty, 0)) <> 0
		ORDER BY item_key, cr.supplier
		""",
		values,
		as_dict=True,
	)


def _stitching_agg(from_date, to_date, customer=None, so_item=None, combo_item=None, supplier=None):
	conditions = ["sr.docstatus = 1", "sr.date >= %(from_date)s", "sr.date <= %(to_date)s"]
	values = {"from_date": from_date, "to_date": to_date}
	if customer:
		conditions.append("sr.customer = %(customer)s")
		values["customer"] = customer
	if so_item:
		conditions.append("NULLIF(TRIM(srct.so_item), '') = %(so_item)s")
		values["so_item"] = so_item
	if combo_item:
		conditions.append("NULLIF(TRIM(srct.combo_item), '') = %(combo_item)s")
		values["combo_item"] = combo_item
	if supplier:
		conditions.append("sr.supplier = %(supplier)s")
		values["supplier"] = supplier
	where_clause = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			COALESCE(
				NULLIF(TRIM(srct.so_item), ''),
				NULLIF(TRIM(srct.combo_item), ''),
				CONCAT(
					'ATTR:',
					IFNULL(srct.article, ''),
					'|',
					IFNULL(srct.design, ''),
					'|',
					IFNULL(srct.colour, '')
				)
			) AS item_key,
			MAX(srct.so_item) AS so_item,
			MAX(srct.combo_item) AS combo_item,
			MAX(srct.article) AS article,
			MAX(srct.design) AS design,
			MAX(srct.colour) AS colour,
			sr.supplier AS contractor,
			SUM(IFNULL(srct.stitching_qty, 0)) AS qty,
			COUNT(DISTINCT sr.name) AS report_count,
			GROUP_CONCAT(DISTINCT sr.name ORDER BY sr.name SEPARATOR ',') AS reports
		FROM `tabStitching Report` sr
		INNER JOIN `tabStitching Report CT` srct ON srct.parent = sr.name
		WHERE {where_clause}
		GROUP BY item_key, sr.supplier
		HAVING SUM(IFNULL(srct.stitching_qty, 0)) <> 0
		ORDER BY item_key, sr.supplier
		""",
		values,
		as_dict=True,
	)


def _packing_agg(from_date, to_date, customer=None, so_item=None, combo_item=None, supplier=None):
	conditions = ["pr.docstatus = 1", "pr.date >= %(from_date)s", "pr.date <= %(to_date)s"]
	values = {"from_date": from_date, "to_date": to_date}
	if customer:
		conditions.append("pr.customer = %(customer)s")
		values["customer"] = customer
	if so_item:
		conditions.append("NULLIF(TRIM(prct.so_item), '') = %(so_item)s")
		values["so_item"] = so_item
	if combo_item:
		conditions.append("NULLIF(TRIM(prct.combo_item), '') = %(combo_item)s")
		values["combo_item"] = combo_item
	if supplier:
		conditions.append("pr.supplier = %(supplier)s")
		values["supplier"] = supplier
	where_clause = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			COALESCE(
				NULLIF(TRIM(prct.so_item), ''),
				NULLIF(TRIM(prct.combo_item), ''),
				CONCAT(
					'ATTR:',
					IFNULL(prct.article, ''),
					'|',
					IFNULL(prct.design, ''),
					'|',
					IFNULL(prct.colour, '')
				)
			) AS item_key,
			MAX(prct.so_item) AS so_item,
			MAX(prct.combo_item) AS combo_item,
			MAX(prct.article) AS article,
			MAX(prct.design) AS design,
			MAX(prct.colour) AS colour,
			pr.supplier AS contractor,
			SUM(IFNULL(prct.packaging_qty, 0)) AS qty,
			COUNT(DISTINCT pr.name) AS report_count,
			GROUP_CONCAT(DISTINCT pr.name ORDER BY pr.name SEPARATOR ',') AS reports
		FROM `tabPacking Report` pr
		INNER JOIN `tabPacking Report CT` prct ON prct.parent = pr.name
		WHERE {where_clause}
		GROUP BY item_key, pr.supplier
		HAVING SUM(IFNULL(prct.packaging_qty, 0)) <> 0
		ORDER BY item_key, pr.supplier
		""",
		values,
		as_dict=True,
	)


def _drop_zero_qty_rows(rows: list) -> list:
	"""Safety net: hide contractor lines with zero aggregated qty."""
	return [r for r in rows if flt(r.get("qty")) != 0]


def _rows_for_stage(raw_rows, stage_label: str, item_names: dict):
	out = []
	for row in raw_rows:
		reports = (row.get("reports") or "").split(",") if row.get("reports") else []
		reports = [r for r in reports if r][:15]
		rich = _rich_item_fields(row, item_names)
		out.append(
			{
				"stage": stage_label,
				"item_key": row.get("item_key"),
				"item_label": rich["item_label"],
				"combo_detail": rich["combo_detail"],
				"so_item": rich["so_item"],
				"combo_item": rich["combo_item"],
				"so_item_label": rich["so_item_label"],
				"combo_item_label": rich["combo_item_label"],
				"is_combo": rich["is_combo"],
				"contractor": row.get("contractor"),
				"contractor_name": _contractor_display_name(row.get("contractor")),
				"qty": flt(row.get("qty")),
				"report_count": int(row.get("report_count") or 0),
				"reports": reports,
			}
		)
	return out


def _matrix_meta_for_key(item_key, cutting_rows, stitching_rows, packing_rows, item_names: dict):
	for rows in (cutting_rows, stitching_rows, packing_rows):
		for r in rows:
			if r.get("item_key") == item_key:
				return _rich_item_fields(r, item_names)
	return {
		"item_label": item_key,
		"combo_detail": "",
		"so_item": None,
		"combo_item": None,
		"so_item_label": "",
		"combo_item_label": "",
		"is_combo": False,
	}


def _build_matrix(cutting_rows, stitching_rows, packing_rows, item_names: dict):
	labels = {}
	all_keys = set()

	for rows in (cutting_rows, stitching_rows, packing_rows):
		for r in rows:
			ik = r.get("item_key")
			if not ik:
				continue
			all_keys.add(ik)
			if ik not in labels:
				rich = _rich_item_fields(r, item_names)
				labels[ik] = rich["item_label"]

	matrix = []
	for ik in sorted(all_keys, key=lambda k: labels.get(k, "")):
		meta = _matrix_meta_for_key(ik, cutting_rows, stitching_rows, packing_rows, item_names)
		entry = {
			"item_key": ik,
			"item_label": meta["item_label"],
			"combo_detail": meta["combo_detail"],
			"so_item": meta["so_item"],
			"combo_item": meta["combo_item"],
			"so_item_label": meta["so_item_label"],
			"combo_item_label": meta["combo_item_label"],
			"is_combo": meta["is_combo"],
			"cutting": [],
			"stitching": [],
			"packing": [],
		}
		for r in cutting_rows:
			if r.get("item_key") == ik:
				entry["cutting"].append(
					{
						"contractor": r.get("contractor"),
						"contractor_name": _contractor_display_name(r.get("contractor")),
						"qty": flt(r.get("qty")),
					}
				)
		for r in stitching_rows:
			if r.get("item_key") == ik:
				entry["stitching"].append(
					{
						"contractor": r.get("contractor"),
						"contractor_name": _contractor_display_name(r.get("contractor")),
						"qty": flt(r.get("qty")),
					}
				)
		for r in packing_rows:
			if r.get("item_key") == ik:
				entry["packing"].append(
					{
						"contractor": r.get("contractor"),
						"contractor_name": _contractor_display_name(r.get("contractor")),
						"qty": flt(r.get("qty")),
					}
				)
		matrix.append(entry)

	return matrix


def _group_matrix_by_so_item(matrix_flat: list, item_names: dict) -> list:
	"""Nest flat matrix rows under each Sales Order line item (so_item); components = combo lines."""
	from collections import defaultdict

	buckets = defaultdict(list)
	unassigned = []

	for entry in matrix_flat:
		so = entry.get("so_item")
		if so:
			buckets[so].append(entry)
		else:
			unassigned.append(entry)

	def sort_so_key(k: str) -> str:
		return (item_names.get(k, k) or k).lower()

	groups = []
	for so in sorted(buckets.keys(), key=sort_so_key):
		lines_raw = buckets[so]
		lines_raw.sort(
			key=lambda e: (
				0 if e.get("combo_item") else 1,
				(e.get("combo_item_label") or e.get("combo_item") or "").lower(),
				e.get("item_key") or "",
			)
		)
		lines = []
		for e in lines_raw:
			row = dict(e)
			if row.get("combo_item"):
				row["component_title"] = row.get("combo_item_label") or row.get("combo_item")
			else:
				row["component_title"] = row.get("item_label") or row.get("item_key")
			lines.append(row)

		groups.append(
			{
				"so_item": so,
				"so_item_label": item_names.get(so, so),
				"lines": lines,
			}
		)

	if unassigned:
		u_lines = []
		for e in sorted(unassigned, key=lambda x: (x.get("item_label") or "").lower()):
			row = dict(e)
			row["component_title"] = row.get("item_label") or row.get("item_key")
			u_lines.append(row)
		groups.append(
			{
				"so_item": None,
				"so_item_label": _("Other (no SO item link)"),
				"lines": u_lines,
			}
		)

	return groups


def _strip_opt(val):
	if val is None:
		return None
	s = str(val).strip()
	return s or None


@frappe.whitelist()
def get_contractor_performance_data(
	from_date=None,
	to_date=None,
	customer=None,
	so_item=None,
	combo_item=None,
	supplier=None,
):
	"""Aggregate Cutting / Stitching / Packing reports: which contractor worked which item (qty)."""
	from_date, to_date = _date_range(from_date, to_date)

	customer = _strip_opt(customer)
	so_item = _strip_opt(so_item)
	combo_item = _strip_opt(combo_item)
	supplier = _strip_opt(supplier)

	cutting_raw = _drop_zero_qty_rows(_cutting_agg(from_date, to_date, customer, so_item, combo_item, supplier))
	stitching_raw = _drop_zero_qty_rows(_stitching_agg(from_date, to_date, customer, so_item, combo_item, supplier))
	packing_raw = _drop_zero_qty_rows(_packing_agg(from_date, to_date, customer, so_item, combo_item, supplier))

	item_names = _item_name_map(_collect_item_codes(cutting_raw, stitching_raw, packing_raw))

	matrix_flat = _build_matrix(cutting_raw, stitching_raw, packing_raw, item_names)

	return {
		"from_date": str(from_date),
		"to_date": str(to_date),
		"cutting": _rows_for_stage(cutting_raw, "Cutting", item_names),
		"stitching": _rows_for_stage(stitching_raw, "Stitching", item_names),
		"packing": _rows_for_stage(packing_raw, "Packing", item_names),
		"item_matrix": matrix_flat,
		"item_matrix_groups": _group_matrix_by_so_item(matrix_flat, item_names),
	}
