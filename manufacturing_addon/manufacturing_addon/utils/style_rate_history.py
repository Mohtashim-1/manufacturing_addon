# Copyright (c) 2026, Manufacturing Addon and contributors
# License: MIT

"""Log and query Style rate changes (Style master + Item style tabs)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

ITEM_STYLE_TABLES = (
	("custom_cutting_style", "Cutting"),
	("custom_stitching_style", "Stitching"),
	("custom_packing", "Packing"),
	("custom_checking_style", "Checking"),
)


def _assert_system_manager():
	if "System Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("Only System Manager can view Style Rate History."), frappe.PermissionError)


def log_style_rate_change(
	style,
	new_rate,
	old_rate=None,
	item=None,
	operation=None,
	source="Manual",
	qty=None,
	amount=None,
	reference_doctype=None,
	reference_name=None,
	remarks=None,
):
	"""Insert one Style Rate History row (skips if rates unchanged)."""
	if not style:
		return None

	old_rate = flt(old_rate)
	new_rate = flt(new_rate)
	if abs(old_rate - new_rate) < 1e-9:
		return None

	doc = frappe.get_doc(
		{
			"doctype": "Style Rate History",
			"style": style,
			"item": item,
			"operation": operation,
			"source": source,
			"old_rate": old_rate,
			"new_rate": new_rate,
			"qty": flt(qty) if qty is not None else None,
			"amount": flt(amount) if amount is not None else None,
			"changed_by": frappe.session.user,
			"changed_on": now_datetime(),
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"remarks": remarks,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def on_style_update(doc, method=None):
	"""Capture Style.default_rate changes."""
	if doc.is_new():
		return
	before = doc.get_doc_before_save()
	if not before:
		return
	old_rate = flt(before.get("default_rate"))
	new_rate = flt(doc.get("default_rate"))
	log_style_rate_change(
		style=doc.name,
		old_rate=old_rate,
		new_rate=new_rate,
		operation=doc.get("operation"),
		source="Style Master",
		reference_doctype="Style",
		reference_name=doc.name,
		remarks=_("Style master default rate updated"),
	)


def _style_rows_snapshot(doc):
	"""Map stable key → {style, rate, qty, amount, operation, parentfield}."""
	snapshot = {}
	for fieldname, default_operation in ITEM_STYLE_TABLES:
		if not doc.meta.has_field(fieldname):
			continue
		for row in doc.get(fieldname) or []:
			if not row.get("style"):
				continue
			operation = row.get("operation") or default_operation
			combo = row.get("combo_item") or row.get("stitching_component") or ""
			key = f"{fieldname}|{row.style}|{operation}|{combo}|{row.idx}"
			snapshot[key] = {
				"style": row.style,
				"rate": flt(row.get("rate")),
				"qty": flt(row.get("qty") or 1) or 1,
				"amount": flt(row.get("amount")),
				"operation": operation,
				"parentfield": fieldname,
			}
	return snapshot


def on_item_update(doc, method=None):
	"""Capture Item style-tab rate changes."""
	if doc.is_new():
		return
	before = doc.get_doc_before_save()
	if not before:
		return

	old_map = _style_rows_snapshot(before)
	new_map = _style_rows_snapshot(doc)

	# Index old rows by style|operation|combo (ignore idx) for rematched rows
	old_by_style = {}
	for key, row in old_map.items():
		parts = key.split("|")
		style_key = "|".join(parts[:4])  # field|style|operation|combo
		old_by_style.setdefault(style_key, []).append(row)

	seen_old = set()
	for key, new_row in new_map.items():
		parts = key.split("|")
		style_key = "|".join(parts[:4])
		old_row = old_map.get(key)
		if not old_row:
			candidates = old_by_style.get(style_key) or []
			old_row = candidates.pop(0) if candidates else None
		if old_row:
			seen_old.add(id(old_row))

		old_rate = flt(old_row.get("rate")) if old_row else None
		new_rate = flt(new_row.get("rate"))
		if old_rate is None:
			# Brand-new style row — log only if rate set
			if new_rate <= 0:
				continue
			old_rate = 0

		log_style_rate_change(
			style=new_row["style"],
			item=doc.name,
			old_rate=old_rate,
			new_rate=new_rate,
			operation=new_row.get("operation"),
			source="Item Style",
			qty=new_row.get("qty"),
			amount=new_row.get("amount") or (new_rate * flt(new_row.get("qty") or 1)),
			reference_doctype="Item",
			reference_name=doc.name,
			remarks=_("Item style rate updated ({0})").format(new_row.get("parentfield")),
		)


def _styles_for_order_sheet(order_sheet):
	"""Unique styles used by Items on an Order Sheet."""
	if not order_sheet or not frappe.db.exists("Order Sheet", order_sheet):
		return []

	item_codes = frappe.get_all(
		"Order Sheet CT",
		filters={"parent": order_sheet},
		pluck="so_item",
	)
	item_codes = [c for c in set(item_codes or []) if c]
	if not item_codes:
		return []

	styles = set()
	for child_dt in ("Style CT", "Stitching Style", "Packing Style", "Checking Style"):
		if not frappe.db.table_exists(child_dt):
			continue
		rows = frappe.get_all(
			child_dt,
			filters={"parent": ["in", item_codes], "parenttype": "Item"},
			fields=["style"],
		)
		for r in rows:
			if r.style:
				styles.add(r.style)
	return sorted(styles)


@frappe.whitelist()
def get_style_rate_history(style=None, item=None, order_sheet=None, limit=500):
	"""Return rate history rows + HTML for System Managers."""
	_assert_system_manager()
	limit = min(cint_safe(limit), 2000)

	filters = {}
	if style:
		filters["style"] = style
	if item:
		filters["item"] = item

	styles_filter = None
	if order_sheet and not style:
		styles_filter = _styles_for_order_sheet(order_sheet)
		if not styles_filter:
			return {"rows": [], "html": _render_html([], style, item, order_sheet)}

	or_filters = None
	if styles_filter:
		filters["style"] = ["in", styles_filter]

	rows = frappe.get_all(
		"Style Rate History",
		filters=filters,
		fields=[
			"name",
			"style",
			"item",
			"operation",
			"source",
			"old_rate",
			"new_rate",
			"qty",
			"amount",
			"changed_by",
			"changed_on",
			"reference_doctype",
			"reference_name",
			"remarks",
		],
		order_by="changed_on desc",
		limit_page_length=limit,
	)

	return {
		"rows": rows,
		"html": _render_html(rows, style, item, order_sheet),
		"styles": styles_filter,
	}


def cint_safe(v):
	try:
		return int(v or 500)
	except Exception:
		return 500


def _render_html(rows, style=None, item=None, order_sheet=None):
	title_bits = []
	if style:
		title_bits.append(f"Style: {frappe.utils.escape_html(style)}")
	if item:
		title_bits.append(f"Item: {frappe.utils.escape_html(item)}")
	if order_sheet:
		title_bits.append(f"Order Sheet: {frappe.utils.escape_html(order_sheet)}")
	subtitle = " · ".join(title_bits) if title_bits else _("All styles")

	if not rows:
		return f"""
		<div class="srh-wrap">
			<h3>{_("Style Rate History")}</h3>
			<p class="text-muted">{subtitle}</p>
			<div class="text-muted" style="padding:24px 0;">{_("No rate changes logged yet.")}</div>
		</div>
		"""

	body = []
	for r in rows:
		delta = flt(r.new_rate) - flt(r.old_rate)
		delta_cls = "srh-up" if delta > 0 else ("srh-down" if delta < 0 else "")
		delta_txt = f"{delta:+.4f}" if delta else "0"
		changed_on = frappe.format(r.changed_on, {"fieldtype": "Datetime"}) if r.changed_on else ""
		body.append(
			f"""
			<tr>
				<td>{frappe.utils.escape_html(r.style or "")}</td>
				<td>{frappe.utils.escape_html(r.item or "—")}</td>
				<td>{frappe.utils.escape_html(r.operation or "—")}</td>
				<td>{frappe.utils.escape_html(r.source or "")}</td>
				<td class="text-right">{flt(r.old_rate):.4f}</td>
				<td class="text-right"><strong>{flt(r.new_rate):.4f}</strong></td>
				<td class="text-right {delta_cls}">{delta_txt}</td>
				<td>{frappe.utils.escape_html(r.changed_by or "")}</td>
				<td>{changed_on}</td>
			</tr>
			"""
		)

	return f"""
	<div class="srh-wrap">
		<style>
			.srh-wrap {{ font-family: inherit; }}
			.srh-wrap table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
			.srh-wrap th, .srh-wrap td {{ border-bottom: 1px solid #e5e7eb; padding: 8px 10px; text-align: left; }}
			.srh-wrap th {{ background: #f8fafc; font-weight: 600; color: #334155; }}
			.srh-wrap .text-right {{ text-align: right; }}
			.srh-up {{ color: #b91c1c; font-weight: 600; }}
			.srh-down {{ color: #15803d; font-weight: 600; }}
			.srh-wrap h3 {{ margin: 0 0 4px; }}
		</style>
		<h3>{_("Style Rate History")}</h3>
		<p class="text-muted" style="margin-bottom:16px;">{subtitle} · {len(rows)} {_("rows")}</p>
		<div style="overflow:auto; max-height:70vh;">
			<table>
				<thead>
					<tr>
						<th>{_("Style")}</th>
						<th>{_("Item")}</th>
						<th>{_("Operation")}</th>
						<th>{_("Source")}</th>
						<th class="text-right">{_("Old Rate")}</th>
						<th class="text-right">{_("New Rate")}</th>
						<th class="text-right">{_("Δ")}</th>
						<th>{_("Changed By")}</th>
						<th>{_("Changed On")}</th>
					</tr>
				</thead>
				<tbody>
					{"".join(body)}
				</tbody>
			</table>
		</div>
	</div>
	"""
