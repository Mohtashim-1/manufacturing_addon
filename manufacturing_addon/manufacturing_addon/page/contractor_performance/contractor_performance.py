# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate


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


def _article_display(article, design, colour) -> str:
	parts = [cstr(p).strip() for p in (article, design, colour) if cstr(p).strip()]
	return " / ".join(parts)


def _item_label(so_item, combo_item, article, design, colour) -> str:
	# Prefer stitching article over combo component (Pillow/Duvet).
	article_label = _article_display(article, design, colour)
	if article_label:
		return article_label
	code = so_item or combo_item
	if code:
		name = frappe.db.get_value("Item", code, "item_name")
		return name or code
	return _("Unknown item")


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
	"""
	Labels for contractor reporting.

	Article = stitching article (Fitted Sheet, PAIR PILLOW, …).
	Combo component (PILLOW / DUVET) is secondary — never the primary “article”.
	"""
	so_item = (row.get("so_item") or "").strip()
	combo_item = (row.get("combo_item") or "").strip()
	article = cstr(row.get("article") or "").strip()
	design = cstr(row.get("design") or "").strip()
	colour = cstr(row.get("colour") or "").strip()

	so_label = item_names.get(so_item, so_item) if so_item else ""
	co_label = item_names.get(combo_item, combo_item) if combo_item else ""
	article_label = _article_display(article, design, colour)

	detail_parts = []
	if so_item:
		detail_parts.append(_("SO item: {0}").format(so_label or so_item))
	if combo_item:
		detail_parts.append(_("Component: {0}").format(co_label or combo_item))

	if article_label:
		primary = article_label
	elif so_item:
		primary = so_label or so_item
	elif combo_item:
		primary = co_label or combo_item
	else:
		primary = _("Unknown item")

	return {
		"item_label": primary,
		"combo_detail": " · ".join(detail_parts),
		"article_label": article_label,
		"so_item": so_item or None,
		"combo_item": combo_item or None,
		"so_item_label": so_label,
		"combo_item_label": co_label,
		"is_combo": bool(combo_item and so_item),
	}


def _cutting_agg(
	from_date,
	to_date,
	customer=None,
	so_item=None,
	combo_item=None,
	supplier=None,
	order_sheet=None,
	skip_date_filter=False,
):
	conditions = ["cr.docstatus = 1"]
	values = {}
	if not skip_date_filter:
		conditions.extend(["cr.date >= %(from_date)s", "cr.date <= %(to_date)s"])
		values["from_date"] = from_date
		values["to_date"] = to_date
	if order_sheet:
		conditions.append("cr.order_sheet in %(order_sheet)s")
		values["order_sheet"] = tuple(order_sheet)
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
			CONCAT_WS(
				'|',
				NULLIF(TRIM(crct.so_item), ''),
				NULLIF(TRIM(crct.combo_item), ''),
				CASE
					WHEN NULLIF(TRIM(crct.so_item), '') IS NULL
						AND NULLIF(TRIM(crct.combo_item), '') IS NULL
					THEN CONCAT(
						'ATTR:',
						IFNULL(crct.article, ''),
						'|',
						IFNULL(crct.design, ''),
						'|',
						IFNULL(crct.colour, '')
					)
				END
			) AS item_key,
			NULLIF(TRIM(crct.so_item), '') AS so_item,
			NULLIF(TRIM(crct.combo_item), '') AS combo_item,
			NULLIF(TRIM(crct.article), '') AS article,
			NULLIF(TRIM(crct.design), '') AS design,
			NULLIF(TRIM(crct.colour), '') AS colour,
			cr.supplier AS contractor,
			SUM(IFNULL(crct.cutting_qty, 0)) AS qty,
			COUNT(DISTINCT cr.name) AS report_count,
			GROUP_CONCAT(DISTINCT cr.name ORDER BY cr.name SEPARATOR ',') AS reports
		FROM `tabCutting Report` cr
		INNER JOIN `tabCutting Report CT` crct ON crct.parent = cr.name
		WHERE {where_clause}
		GROUP BY item_key, cr.supplier, so_item, combo_item, article, design, colour
		HAVING SUM(IFNULL(crct.cutting_qty, 0)) <> 0
		ORDER BY so_item, combo_item, cr.supplier, article, design, colour
		""",
		values,
		as_dict=True,
	)


def _stitching_agg(
	from_date,
	to_date,
	customer=None,
	so_item=None,
	combo_item=None,
	supplier=None,
	order_sheet=None,
	skip_date_filter=False,
):
	conditions = ["sr.docstatus = 1"]
	values = {}
	if not skip_date_filter:
		conditions.extend(["sr.date >= %(from_date)s", "sr.date <= %(to_date)s"])
		values["from_date"] = from_date
		values["to_date"] = to_date
	if order_sheet:
		conditions.append("sr.order_sheet in %(order_sheet)s")
		values["order_sheet"] = tuple(order_sheet)
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
			CONCAT_WS(
				'|',
				NULLIF(TRIM(srct.so_item), ''),
				NULLIF(TRIM(srct.combo_item), ''),
				CASE
					WHEN NULLIF(TRIM(srct.so_item), '') IS NULL
						AND NULLIF(TRIM(srct.combo_item), '') IS NULL
					THEN CONCAT(
						'ATTR:',
						IFNULL(srct.article, ''),
						'|',
						IFNULL(srct.design, ''),
						'|',
						IFNULL(srct.colour, '')
					)
				END
			) AS item_key,
			NULLIF(TRIM(srct.so_item), '') AS so_item,
			NULLIF(TRIM(srct.combo_item), '') AS combo_item,
			NULLIF(TRIM(srct.article), '') AS article,
			NULLIF(TRIM(srct.design), '') AS design,
			NULLIF(TRIM(srct.colour), '') AS colour,
			sr.supplier AS contractor,
			SUM(IFNULL(srct.stitching_qty, 0)) AS qty,
			COUNT(DISTINCT sr.name) AS report_count,
			GROUP_CONCAT(DISTINCT sr.name ORDER BY sr.name SEPARATOR ',') AS reports
		FROM `tabStitching Report` sr
		INNER JOIN `tabStitching Report CT` srct ON srct.parent = sr.name
		WHERE {where_clause}
		GROUP BY item_key, sr.supplier, so_item, combo_item, article, design, colour
		HAVING SUM(IFNULL(srct.stitching_qty, 0)) <> 0
		ORDER BY so_item, combo_item, sr.supplier, article, design, colour
		""",
		values,
		as_dict=True,
	)


def _packing_agg(
	from_date,
	to_date,
	customer=None,
	so_item=None,
	combo_item=None,
	supplier=None,
	order_sheet=None,
	skip_date_filter=False,
):
	conditions = ["pr.docstatus = 1"]
	values = {}
	if not skip_date_filter:
		conditions.extend(["pr.date >= %(from_date)s", "pr.date <= %(to_date)s"])
		values["from_date"] = from_date
		values["to_date"] = to_date
	if order_sheet:
		conditions.append("pr.order_sheet in %(order_sheet)s")
		values["order_sheet"] = tuple(order_sheet)
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
			CONCAT_WS(
				'|',
				NULLIF(TRIM(prct.so_item), ''),
				NULLIF(TRIM(prct.combo_item), ''),
				CASE
					WHEN NULLIF(TRIM(prct.so_item), '') IS NULL
						AND NULLIF(TRIM(prct.combo_item), '') IS NULL
					THEN CONCAT(
						'ATTR:',
						IFNULL(prct.article, ''),
						'|',
						IFNULL(prct.design, ''),
						'|',
						IFNULL(prct.colour, '')
					)
				END
			) AS item_key,
			NULLIF(TRIM(prct.so_item), '') AS so_item,
			NULLIF(TRIM(prct.combo_item), '') AS combo_item,
			NULLIF(TRIM(prct.article), '') AS article,
			NULLIF(TRIM(prct.design), '') AS design,
			NULLIF(TRIM(prct.colour), '') AS colour,
			pr.supplier AS contractor,
			SUM(IFNULL(prct.packaging_qty, 0)) AS qty,
			COUNT(DISTINCT pr.name) AS report_count,
			GROUP_CONCAT(DISTINCT pr.name ORDER BY pr.name SEPARATOR ',') AS reports
		FROM `tabPacking Report` pr
		INNER JOIN `tabPacking Report CT` prct ON prct.parent = pr.name
		WHERE {where_clause}
		GROUP BY item_key, pr.supplier, so_item, combo_item, article, design, colour
		HAVING SUM(IFNULL(prct.packaging_qty, 0)) <> 0
		ORDER BY so_item, combo_item, pr.supplier, article, design, colour
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
				"article_label": rich.get("article_label") or "",
				"so_item": rich["so_item"],
				"combo_item": rich["combo_item"],
				"so_item_label": rich["so_item_label"],
				"combo_item_label": rich["combo_item_label"],
				"is_combo": rich["is_combo"],
				"article": row.get("article"),
				"design": row.get("design"),
				"colour": row.get("colour"),
				"contractor": row.get("contractor"),
				"contractor_name": _contractor_display_name(row.get("contractor")),
				"qty": flt(row.get("qty")),
				"report_count": int(row.get("report_count") or 0),
				"reports": reports,
			}
		)
	return out


def _merge_stage_contractors(rows: list[dict]) -> list[dict]:
	merged = {}
	for row in rows:
		key = row.get("contractor") or row.get("contractor_name") or ""
		if key not in merged:
			merged[key] = {
				"contractor": row.get("contractor"),
				"contractor_name": _contractor_display_name(row.get("contractor")),
				"qty": 0.0,
			}
		merged[key]["qty"] += flt(row.get("qty"))
	return sorted(merged.values(), key=lambda d: (d.get("contractor_name") or d.get("contractor") or "").lower())


def _matrix_meta_for_key(item_key, cutting_rows, stitching_rows, packing_rows, item_names: dict):
	for rows in (cutting_rows, stitching_rows, packing_rows):
		for r in rows:
			if r.get("item_key") == item_key:
				return _rich_item_fields(r, item_names)
	return {
		"item_label": item_key,
		"combo_detail": "",
		"article_label": "",
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
		cutting_for_item = [r for r in cutting_rows if r.get("item_key") == ik]
		stitching_for_item = [r for r in stitching_rows if r.get("item_key") == ik]
		packing_for_item = [r for r in packing_rows if r.get("item_key") == ik]
		entry = {
			"item_key": ik,
			"item_label": meta["item_label"],
			"combo_detail": meta["combo_detail"],
			"article_label": meta.get("article_label") or "",
			"so_item": meta["so_item"],
			"combo_item": meta["combo_item"],
			"so_item_label": meta["so_item_label"],
			"combo_item_label": meta["combo_item_label"],
			"is_combo": meta["is_combo"],
			"cutting": _merge_stage_contractors(cutting_for_item),
			"stitching": _merge_stage_contractors(stitching_for_item),
			"packing": _merge_stage_contractors(packing_for_item),
		}
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
			# Title = stitching article; keep combo name only as component subtitle
			row["component_title"] = (
				row.get("article_label")
				or row.get("item_label")
				or row.get("so_item_label")
				or row.get("item_key")
			)
			if row.get("combo_item"):
				row["component_subtitle"] = _("Component: {0}").format(
					row.get("combo_item_label") or row.get("combo_item")
				)
			else:
				row["component_subtitle"] = row.get("combo_detail") or ""
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
			row["component_title"] = (
				row.get("article_label") or row.get("item_label") or row.get("item_key")
			)
			if row.get("combo_item"):
				row["component_subtitle"] = _("Component: {0}").format(
					row.get("combo_item_label") or row.get("combo_item")
				)
			else:
				row["component_subtitle"] = row.get("combo_detail") or ""
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


def _parse_name_list(val) -> list[str]:
	"""Accept a single name, comma-separated string, JSON list or Python list."""
	if isinstance(val, str) and val.strip().startswith("["):
		val = frappe.parse_json(val)
	if isinstance(val, (list, tuple, set)):
		names = [cstr(v).strip() for v in val]
	else:
		names = cstr(val).split(",")
	return list(dict.fromkeys(n.strip() for n in names if n and n.strip()))


def _sales_orders_from_delivery_notes(delivery_notes: list[str]) -> list[str]:
	if not delivery_notes:
		return []
	rows = frappe.db.sql(
		"""
		select distinct nullif(trim(dni.against_sales_order), '')
		from `tabDelivery Note Item` dni
		where dni.parent in %(dns)s
			and ifnull(trim(dni.against_sales_order), '') != ''
		""",
		{"dns": tuple(delivery_notes)},
		as_list=True,
	)
	return [r[0] for r in rows if r and r[0]]


def _item_codes_from_delivery_notes(delivery_notes: list[str]) -> list[str]:
	if not delivery_notes:
		return []
	rows = frappe.db.sql(
		"""
		select distinct nullif(trim(dni.item_code), '')
		from `tabDelivery Note Item` dni
		where dni.parent in %(dns)s
			and ifnull(trim(dni.item_code), '') != ''
		""",
		{"dns": tuple(delivery_notes)},
		as_list=True,
	)
	return [r[0] for r in rows if r and r[0]]


def _order_sheets_for_sales_orders(sales_orders: list[str]) -> list[str]:
	if not sales_orders:
		return []
	return frappe.get_all(
		"Order Sheet",
		filters={"sales_order": ["in", sales_orders], "docstatus": ["<", 2]},
		pluck="name",
	)


def _resolve_scope_filters(order_sheet=None, sales_order=None, delivery_note=None):
	"""
	Combine Order Sheet / Sales Order / Delivery Note filters into:
	- order_sheet list (reports filter)
	- sales_order list (meta)
	- dn_item_codes list (optional SO-item restriction from DN lines)
	"""
	selected_sheets = set(_parse_name_list(order_sheet))
	selected_sos = set(_parse_name_list(sales_order))
	selected_dns = _parse_name_list(delivery_note)
	dn_item_codes: list[str] = []

	if selected_dns:
		selected_sos.update(_sales_orders_from_delivery_notes(selected_dns))
		dn_item_codes = _item_codes_from_delivery_notes(selected_dns)

	resolved_from_so = set(_order_sheets_for_sales_orders(list(selected_sos))) if selected_sos else set()

	if selected_sheets and resolved_from_so:
		sheets = selected_sheets & resolved_from_so
	elif selected_sheets:
		sheets = selected_sheets
	else:
		sheets = resolved_from_so

	# If user picked SO/DN but no Order Sheets exist, keep an empty tuple marker
	# so report queries return nothing instead of ignoring the filter.
	forced_empty = bool(selected_sos or selected_dns) and not sheets

	return {
		"order_sheet": list(sheets),
		"sales_order": list(selected_sos),
		"delivery_note": selected_dns,
		"dn_item_codes": dn_item_codes,
		"forced_empty": forced_empty,
	}


def _apply_dn_item_filter(rows: list, dn_item_codes: list[str]) -> list:
	"""When Delivery Note is selected, keep rows whose SO item appears on the DN."""
	if not dn_item_codes:
		return rows
	codes = set(dn_item_codes)
	out = []
	for row in rows:
		so_item = cstr(row.get("so_item") or "").strip()
		if so_item and so_item in codes:
			out.append(row)
	return out


@frappe.whitelist()
def get_contractor_performance_data(
	from_date=None,
	to_date=None,
	customer=None,
	so_item=None,
	combo_item=None,
	supplier=None,
	order_sheet=None,
	sales_order=None,
	delivery_note=None,
	all_dates=None,
):
	"""Aggregate Cutting / Stitching / Packing reports: which contractor worked which item (qty)."""
	customer = _strip_opt(customer)
	so_item = _strip_opt(so_item)
	combo_item = _strip_opt(combo_item)
	supplier = _strip_opt(supplier)
	scope = _resolve_scope_filters(order_sheet, sales_order, delivery_note)
	order_sheet = scope["order_sheet"]
	skip_date_filter = frappe.utils.cint(all_dates) and bool(
		order_sheet or scope["sales_order"] or scope["delivery_note"]
	)

	if scope["forced_empty"]:
		return {
			"from_date": str(from_date or nowdate()),
			"to_date": str(to_date or nowdate()),
			"order_sheet": None,
			"sales_order": ", ".join(scope["sales_order"]) or None,
			"delivery_note": ", ".join(scope["delivery_note"]) or None,
			"cutting": [],
			"stitching": [],
			"packing": [],
			"item_matrix": [],
			"item_matrix_groups": [],
		}

	if skip_date_filter:
		from_date = getdate("2000-01-01")
		to_date = getdate(nowdate())
	else:
		from_date, to_date = _date_range(from_date, to_date)

	cutting_raw = _drop_zero_qty_rows(
		_cutting_agg(
			from_date, to_date, customer, so_item, combo_item, supplier, order_sheet, skip_date_filter
		)
	)
	stitching_raw = _drop_zero_qty_rows(
		_stitching_agg(
			from_date, to_date, customer, so_item, combo_item, supplier, order_sheet, skip_date_filter
		)
	)
	packing_raw = _drop_zero_qty_rows(
		_packing_agg(
			from_date, to_date, customer, so_item, combo_item, supplier, order_sheet, skip_date_filter
		)
	)

	# Delivery Note narrows to shipped SO items when DN is used as a filter
	if scope["dn_item_codes"] and not so_item:
		cutting_raw = _apply_dn_item_filter(cutting_raw, scope["dn_item_codes"])
		stitching_raw = _apply_dn_item_filter(stitching_raw, scope["dn_item_codes"])
		packing_raw = _apply_dn_item_filter(packing_raw, scope["dn_item_codes"])

	item_names = _item_name_map(_collect_item_codes(cutting_raw, stitching_raw, packing_raw))

	matrix_flat = _build_matrix(cutting_raw, stitching_raw, packing_raw, item_names)

	return {
		"from_date": str(from_date),
		"to_date": str(to_date),
		"order_sheet": ", ".join(order_sheet) or None,
		"sales_order": ", ".join(scope["sales_order"]) or None,
		"delivery_note": ", ".join(scope["delivery_note"]) or None,
		"cutting": _rows_for_stage(cutting_raw, "Cutting", item_names),
		"stitching": _rows_for_stage(stitching_raw, "Stitching", item_names),
		"packing": _rows_for_stage(packing_raw, "Packing", item_names),
		"item_matrix": matrix_flat,
		"item_matrix_groups": _group_matrix_by_so_item(matrix_flat, item_names),
	}
