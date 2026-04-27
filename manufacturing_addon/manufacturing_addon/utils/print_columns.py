# Copyright (c) 2026, mohtashim and contributors
# Dynamic child-table columns for print formats from GridView user settings.
# Pattern: Sudhanshu Badole — cache hgetall, SQL fallback, meta in_list_view.

import json

import frappe

PARENT_DOCTYPE = "Order Sheet"
CHILD_DOCTYPE = "Order Sheet CT"
SKIP_FIELD_TYPES = frozenset(
	("Section Break", "Column Break", "Tab Break", "HTML", "Button", "Fold", "Heading")
)


def _map_fieldnames(meta, fieldnames: list[str]) -> list[dict]:
	out = []
	for fn in fieldnames:
		if not fn:
			continue
		df = meta.get_field(fn)
		if df and df.fieldtype not in SKIP_FIELD_TYPES and not getattr(df, "hidden", 0):
			out.append({"label": df.label, "fieldname": df.fieldname})
	return out


def _columns_from_gridview(gridview_data: dict, meta) -> list[dict] | None:
	if not isinstance(gridview_data, dict):
		return None
	rows = gridview_data.get(CHILD_DOCTYPE) or gridview_data.get("order_sheet_ct")
	if not rows:
		return None
	fieldnames = [r.get("fieldname") for r in rows if r.get("fieldname")]
	cols = _map_fieldnames(meta, fieldnames)
	return cols or None


def _gridview_columns_for_session_user(meta, user: str):
	"""Resolve GridView from Redis scan, SQL, then get_user_settings (current UI columns)."""
	try:
		user_settings_all = frappe.cache.hgetall("_user_settings")
	except Exception:
		user_settings_all = None

	if user_settings_all:
		for key, data in user_settings_all.items():
			key = frappe.safe_decode(key)
			try:
				dt_key, usr = key.split("::")
			except ValueError:
				continue
			if dt_key != PARENT_DOCTYPE or usr != user:
				continue
			try:
				payload = json.loads(frappe.safe_decode(data) if data else "{}")
				gv = payload.get("GridView") or {}
				cols = _columns_from_gridview(gv, meta)
				if cols:
					return cols
			except Exception:
				continue

	try:
		sql_rows = frappe.db.sql(
			"""SELECT data FROM `__UserSettings` WHERE `user`=%s AND `doctype`=%s""",
			(user, PARENT_DOCTYPE),
			as_dict=True,
		)
	except Exception:
		sql_rows = []

	for row in sql_rows or []:
		try:
			parsed = json.loads(row.get("data") or "{}")
			gv = parsed.get("GridView") or {}
			cols = _columns_from_gridview(gv, meta)
			if cols:
				return cols
		except Exception:
			continue

	try:
		from frappe.model.utils.user_settings import get_user_settings

		raw = get_user_settings(PARENT_DOCTYPE)
		parsed = json.loads(raw or "{}")
		gv = parsed.get("GridView") or {}
		cols = _columns_from_gridview(gv, meta)
		if cols:
			return cols
	except Exception:
		pass

	return None


def get_order_sheet_ct_dynamic_columns(doc=None):
	"""Jinja method: Order Sheet CT columns matching GridView (Configure Columns).

	Priority (important):
	1. Live GridView — Redis ``hgetall``, ``__UserSettings`` SQL, ``get_user_settings`` so print
	   always matches **current** Configure Columns (Sudhanshu Badole pattern).
	2. Document ``order_sheet_print_column_order`` — only used when no GridView is found (e.g. stale
	   JSON must **not** override a 6-column grid because the doc once saved only 2 columns).

	Usage: ``{% set columns = get_order_sheet_ct_dynamic_columns(doc) %}``
	"""
	user = frappe.session.user
	meta = frappe.get_meta(CHILD_DOCTYPE)

	cols = _gridview_columns_for_session_user(meta, user)
	if cols:
		return cols

	if doc is not None:
		raw = doc.get("order_sheet_print_column_order")
		if isinstance(raw, str) and raw.strip():
			try:
				names = json.loads(raw)
			except json.JSONDecodeError:
				names = []
			if isinstance(names, list):
				from_doc = _map_fieldnames(meta, [n for n in names if isinstance(n, str)])
				if from_doc:
					return from_doc

	out = [
		{"label": f.label, "fieldname": f.fieldname}
		for f in meta.fields
		if getattr(f, "in_list_view", 0)
		and (getattr(f, "columns", None) or 0) > 0
		and f.fieldtype not in SKIP_FIELD_TYPES
		and not getattr(f, "hidden", 0)
	]
	if out:
		return out

	# Last resort: common columns if meta has no in_list_view widths
	return _map_fieldnames(
		meta,
		[
			"design",
			"ean",
			"colour",
			"stitching_article_no",
			"order_qty",
			"planned_qty",
		],
	)
