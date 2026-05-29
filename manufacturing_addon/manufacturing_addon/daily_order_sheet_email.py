import frappe
from frappe.utils import flt, formatdate, get_url, nowdate

from manufacturing_addon.manufacturing_addon.page.order_tracking.order_tracking import (
	get_dashboard_data,
)


def send_daily_active_order_sheet_email():
	"""Order Tracking email: today + total summary for active (open) order sheets."""
	recipients = _get_system_manager_emails()
	if not recipients:
		return

	active_names = _get_active_order_sheet_names()
	if not active_names:
		return

	today = nowdate()
	total_data = get_dashboard_data(order_sheets=active_names)
	today_data = get_dashboard_data(order_sheets=active_names, report_date=today)

	total_summary = total_data.get("summary") or {}
	today_summary = today_data.get("summary") or {}
	total_details = total_data.get("details") or []
	today_details = today_data.get("details") or []

	if not total_details and not today_details:
		return

	merged_details = _merge_today_into_details(total_details, today_details)
	order_sheet_rows = _build_order_sheet_summary_rows(merged_details)
	so_item_rows = _build_so_item_summary_rows(merged_details)

	dashboard_url = get_url("/app/order-tracking")
	subject = f"Order Tracking — Today & Total Production - {formatdate(today)}"
	message = _build_email_html(
		today=today,
		today_summary=today_summary,
		total_summary=total_summary,
		order_sheet_rows=order_sheet_rows,
		so_item_rows=so_item_rows,
		details=merged_details,
		dashboard_url=dashboard_url,
	)

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		now=False,
	)


@frappe.whitelist()
def trigger_daily_active_order_sheet_email():
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can trigger this email.")
	send_daily_active_order_sheet_email()
	return "Daily order tracking email has been queued."


def _get_system_manager_emails():
	rows = frappe.db.sql(
		"""
		SELECT DISTINCT u.email
		FROM `tabUser` u
		INNER JOIN `tabHas Role` hr ON hr.parent = u.name
		WHERE hr.role = 'System Manager'
			AND u.enabled = 1
			AND IFNULL(u.email, '') != ''
			AND u.name NOT IN ('Guest')
		ORDER BY u.email
		""",
		as_list=True,
	)
	return [r[0] for r in rows if r and r[0]]


def _get_active_order_sheet_names():
	rows = frappe.db.sql(
		"""
		SELECT os.name
		FROM `tabOrder Sheet` os
		INNER JOIN `tabSales Order` so ON so.name = os.sales_order
		WHERE os.docstatus = 1
			AND so.docstatus = 1
			AND IFNULL(os.sales_order, '') != ''
			AND so.status NOT IN ('Closed', 'Completed', 'On Hold', 'Cancelled')
			AND IFNULL(so.per_delivered, 0) < 100
		ORDER BY os.sales_order, os.name
		""",
		as_dict=True,
	)
	return [r.name for r in rows]


def _detail_key(row):
	return (
		row.get("order_sheet") or "",
		row.get("item") or "",
		row.get("bundle_item") or "",
	)


def _merge_today_into_details(total_details, today_details):
	today_map = {_detail_key(r): r for r in today_details}
	merged = []
	for row in total_details:
		t = today_map.get(_detail_key(row), {})
		merged.append(
			{
				**row,
				"today_cutting_finished": flt(t.get("cutting_finished")),
				"today_stitching_finished": flt(t.get("stitching_finished")),
				"today_packing_finished": flt(t.get("packing_finished")),
			}
		)
	return merged


def _build_order_sheet_summary_rows(merged_details):
	"""One row per order sheet: today + total cutting/stitching/packing (parent finished items only)."""
	buckets = {}
	for row in merged_details:
		if not row.get("is_parent"):
			continue
		os_name = row.get("order_sheet") or ""
		if os_name not in buckets:
			buckets[os_name] = {
				"order_sheet": os_name,
				"order_qty": 0,
				"today_cutting": 0,
				"today_stitching": 0,
				"today_packing": 0,
				"total_cutting": 0,
				"total_stitching": 0,
				"total_packing": 0,
			}
		b = buckets[os_name]
		b["order_qty"] += flt(row.get("order_qty"))
		b["today_cutting"] += flt(row.get("today_cutting_finished"))
		b["today_stitching"] += flt(row.get("today_stitching_finished"))
		b["today_packing"] += flt(row.get("today_packing_finished"))
		b["total_cutting"] += flt(row.get("cutting_finished"))
		b["total_stitching"] += flt(row.get("stitching_finished"))
		b["total_packing"] += flt(row.get("packing_finished"))

	return sorted(buckets.values(), key=lambda r: r["order_sheet"])


def _build_so_item_summary_rows(merged_details):
	"""One row per order sheet + SO Item (finished item / parent rows only)."""
	buckets = {}
	for row in merged_details:
		if not row.get("is_parent"):
			continue
		so_item = row.get("item") or ""
		key = (row.get("order_sheet") or "", so_item, row.get("size") or "", row.get("color") or "")
		if key not in buckets:
			buckets[key] = {
				"order_sheet": key[0],
				"so_item": so_item,
				"size": key[2],
				"color": key[3],
				"order_qty": 0,
				"planned_qty": 0,
				"today_cutting": 0,
				"today_stitching": 0,
				"today_packing": 0,
				"total_cutting": 0,
				"total_stitching": 0,
				"total_packing": 0,
			}
		b = buckets[key]
		b["order_qty"] += flt(row.get("order_qty"))
		b["planned_qty"] += flt(row.get("planned_qty"))
		b["today_cutting"] += flt(row.get("today_cutting_finished"))
		b["today_stitching"] += flt(row.get("today_stitching_finished"))
		b["today_packing"] += flt(row.get("today_packing_finished"))
		b["total_cutting"] += flt(row.get("cutting_finished"))
		b["total_stitching"] += flt(row.get("stitching_finished"))
		b["total_packing"] += flt(row.get("packing_finished"))

	rows = list(buckets.values())
	for r in rows:
		oq = flt(r["order_qty"])
		r["today_cut_pct"] = (flt(r["today_cutting"]) / oq * 100) if oq else 0
		r["total_cut_pct"] = (flt(r["total_cutting"]) / oq * 100) if oq else 0
		r["today_sti_pct"] = (flt(r["today_stitching"]) / oq * 100) if oq else 0
		r["total_sti_pct"] = (flt(r["total_stitching"]) / oq * 100) if oq else 0
		r["today_pack_pct"] = (flt(r["today_packing"]) / oq * 100) if oq else 0
		r["total_pack_pct"] = (flt(r["total_packing"]) / oq * 100) if oq else 0

	return sorted(rows, key=lambda r: (r["order_sheet"], r["so_item"], r["size"], r["color"]))


def _format_number(value):
	return f"{flt(value):,.0f}"


def _format_pct(value):
	return f"{flt(value):.1f}"


def _status_text(percent):
	p = flt(percent)
	if p >= 100:
		return f"Complete ({_format_pct(p)}%)" if p > 100 else "Complete"
	if p >= 75:
		return "In Progress"
	if p > 0:
		return "Started"
	return "Not Started"


def _row_metrics(row, parent_order_qty_map, child_count_map, use_today=False):
	"""Metrics for detail table; use_today uses today's qty for stage columns."""
	is_parent = row.get("is_parent") is True
	is_bundle = bool(row.get("bundle_item"))
	parent_key = f"{row.get('order_sheet')}||{row.get('item')}"

	order_qty = flt(row.get("order_qty"))
	if is_bundle:
		order_qty = flt(parent_order_qty_map.get(parent_key))

	row_pcs = flt(row.get("pcs")) or 1
	if use_today:
		cutting_finished = flt(row.get("today_cutting_finished"))
		stitching_finished = flt(row.get("today_stitching_finished"))
		packing_finished = flt(row.get("today_packing_finished"))
	else:
		cutting_finished = flt(row.get("cutting_finished"))
		stitching_finished = flt(row.get("stitching_finished"))
		packing_finished = flt(row.get("packing_finished"))

	cutting_base = cutting_finished if is_parent else (cutting_finished / row_pcs if row_pcs else 0)
	stitching_base = stitching_finished if is_parent else (stitching_finished / row_pcs if row_pcs else 0)
	packing_base = packing_finished if is_parent else (packing_finished / row_pcs if row_pcs else 0)

	cutting_planned = (
		flt(row.get("planned_qty") or row.get("cutting_planned"))
		if is_parent
		else flt(row.get("cutting_planned") or row.get("planned_qty"))
	)
	stitching_planned = (
		flt(row.get("planned_qty") or row.get("stitching_planned"))
		if is_parent
		else flt(row.get("stitching_planned") or row.get("planned_qty"))
	)
	packing_planned = flt(row.get("planned_qty") or row.get("packing_planned"))

	cutting_planned_pct = (cutting_base / cutting_planned * 100) if cutting_planned else 0
	cutting_qty_pct = (cutting_base / order_qty * 100) if order_qty else 0
	stitching_planned_pct = (stitching_base / stitching_planned * 100) if stitching_planned else 0
	stitching_qty_pct = (stitching_base / order_qty * 100) if order_qty else 0
	packing_planned_pct = (packing_base / packing_planned * 100) if packing_planned else 0
	packing_qty_pct = (packing_base / order_qty * 100) if order_qty else 0

	can_drill = is_parent and (child_count_map.get(parent_key) or 0) > 1
	if is_bundle and not can_drill:
		return None

	display_item = row.get("item") or ""
	if is_bundle:
		display_item = f"  └─ {row.get('bundle_item') or ''}"

	today_cut = flt(row.get("today_cutting_finished"))
	today_sti = flt(row.get("today_stitching_finished"))
	today_pack = flt(row.get("today_packing_finished"))
	if is_parent and order_qty:
		today_cut_pct = today_cut / order_qty * 100
		today_sti_pct = today_sti / order_qty * 100
		today_pack_pct = today_pack / order_qty * 100
	else:
		today_cut_pct = today_sti_pct = 0
		today_pack_pct = None if is_bundle else 0

	return {
		"order_sheet": row.get("order_sheet") or "",
		"so_item": row.get("item") or "",
		"combo_item": "" if is_parent else (row.get("bundle_item") or ""),
		"display_item": display_item,
		"size": row.get("size") or "",
		"color": row.get("color") or "",
		"order_qty": order_qty if not is_bundle else "",
		"planned_qty": flt(row.get("planned_qty")) if not is_bundle else "",
		"pcs": flt(row.get("pcs")),
		"today_cutting": today_cut,
		"today_stitching": today_sti,
		"today_packing": today_pack if not is_bundle else None,
		"cutting_finished": cutting_finished,
		"stitching_finished": stitching_finished,
		"packing_finished": packing_finished if not is_bundle else None,
		"today_cut_pct": today_cut_pct,
		"today_sti_pct": today_sti_pct if is_parent else 0,
		"today_pack_pct": today_pack_pct if is_parent else None,
		"cutting_qty_pct": cutting_qty_pct,
		"stitching_qty_pct": stitching_qty_pct,
		"packing_qty_pct": packing_qty_pct if not is_bundle else None,
		"is_parent": is_parent,
		"is_bundle": is_bundle,
	}


def _summary_block(title, summary, accent):
	"""KPI summary table."""
	return f"""
	<h3 style="margin: 20px 0 8px; color: {accent};">{frappe.utils.escape_html(title)}</h3>
	<table style="border-collapse: collapse; width: 100%; max-width: 720px; margin-bottom: 8px; font-size: 13px;">
		<tr><td style="padding: 8px 12px; border: 1px solid #ddd;"><b>Active Order Sheets</b></td>
			<td style="padding: 8px 12px; border: 1px solid #ddd;">{int(summary.get('total_orders') or 0)}</td></tr>
		<tr><td style="padding: 8px 12px; border: 1px solid #ddd;"><b>Total Order Qty</b></td>
			<td style="padding: 8px 12px; border: 1px solid #ddd;">{_format_number(summary.get('total_order_qty'))}</td></tr>
		<tr><td style="padding: 8px 12px; border: 1px solid #ddd;"><b>Today Cutting</b></td>
			<td style="padding: 8px 12px; border: 1px solid #ddd;">{_format_number(summary.get('cutting_finished'))}</td></tr>
		<tr><td style="padding: 8px 12px; border: 1px solid #ddd;"><b>Today Stitching</b></td>
			<td style="padding: 8px 12px; border: 1px solid #ddd;">{_format_number(summary.get('stitching_finished'))}</td></tr>
		<tr><td style="padding: 8px 12px; border: 1px solid #ddd;"><b>Today Packing</b></td>
			<td style="padding: 8px 12px; border: 1px solid #ddd;">{_format_number(summary.get('packing_finished'))}</td></tr>
		<tr><td style="padding: 8px 12px; border: 1px solid #ddd;"><b>Cutting Progress %</b></td>
			<td style="padding: 8px 12px; border: 1px solid #ddd;">{_format_pct(summary.get('cutting_progress'))}%</td></tr>
		<tr><td style="padding: 8px 12px; border: 1px solid #ddd;"><b>Stitching Progress %</b></td>
			<td style="padding: 8px 12px; border: 1px solid #ddd;">{_format_pct(summary.get('stitching_progress'))}%</td></tr>
		<tr><td style="padding: 8px 12px; border: 1px solid #ddd;"><b>Packing Progress %</b></td>
			<td style="padding: 8px 12px; border: 1px solid #ddd;">{_format_pct(summary.get('packing_progress'))}%</td></tr>
		<tr><td style="padding: 8px 12px; border: 1px solid #ddd;"><b>Overall Progress %</b></td>
			<td style="padding: 8px 12px; border: 1px solid #ddd;">{_format_pct(summary.get('overall_progress'))}%</td></tr>
	</table>
	"""


def _build_email_html(today, today_summary, total_summary, order_sheet_rows, so_item_rows, details, dashboard_url):
	def esc(value):
		return frappe.utils.escape_html(str(value or ""))

	os_rows = []
	for r in order_sheet_rows:
		os_rows.append(
			f"""
			<tr>
				<td style="border: 1px solid #ddd; padding: 6px;">{esc(r['order_sheet'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(r['order_qty'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right; background: #e3f2fd;">{_format_number(r['today_cutting'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right; background: #e3f2fd;">{_format_number(r['today_stitching'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right; background: #e3f2fd;">{_format_number(r['today_packing'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(r['total_cutting'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(r['total_stitching'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(r['total_packing'])}</td>
			</tr>
			"""
		)

	so_item_html_rows = []
	for r in so_item_rows:
		so_item_html_rows.append(
			f"""
			<tr>
				<td style="border: 1px solid #ddd; padding: 6px;">{esc(r['order_sheet'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{esc(r['so_item'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{esc(r['size'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{esc(r['color'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(r['order_qty'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right; background: #e3f2fd;">{_format_number(r['today_cutting'])}<br><small>{_format_pct(r['today_cut_pct'])}%</small></td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(r['total_cutting'])}<br><small>{_format_pct(r['total_cut_pct'])}%</small></td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right; background: #e3f2fd;">{_format_number(r['today_stitching'])}<br><small>{_format_pct(r['today_sti_pct'])}%</small></td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(r['total_stitching'])}<br><small>{_format_pct(r['total_sti_pct'])}%</small></td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right; background: #e3f2fd;">{_format_number(r['today_packing'])}<br><small>{_format_pct(r['today_pack_pct'])}%</small></td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(r['total_packing'])}<br><small>{_format_pct(r['total_pack_pct'])}%</small></td>
			</tr>
			"""
		)

	so_item_table = f"""
	<table style="border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 20px;">
		<thead>
			<tr style="background: #f1f5f9;">
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px;">Order Sheet</th>
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px;">SO Item</th>
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px;">Size</th>
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px;">Color</th>
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px; text-align: right;">Order Qty</th>
				<th colspan="2" style="border: 1px solid #ddd; padding: 6px; text-align: center; background: #17a2b8; color: #fff;">CUTTING</th>
				<th colspan="2" style="border: 1px solid #ddd; padding: 6px; text-align: center; background: #ffc107; color: #333;">STITCHING</th>
				<th colspan="2" style="border: 1px solid #ddd; padding: 6px; text-align: center; background: #28a745; color: #fff;">PACKING</th>
			</tr>
			<tr style="background: #f8f9fa;">
				<th style="border: 1px solid #ddd; padding: 4px; background: #e3f2fd;">Today</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Total</th>
				<th style="border: 1px solid #ddd; padding: 4px; background: #e3f2fd;">Today</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Total</th>
				<th style="border: 1px solid #ddd; padding: 4px; background: #e3f2fd;">Today</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Total</th>
			</tr>
		</thead>
		<tbody>{''.join(so_item_html_rows)}</tbody>
	</table>
	"""

	order_sheet_table = f"""
	<table style="border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 20px;">
		<thead>
			<tr style="background: #f1f5f9;">
				<th style="border: 1px solid #ddd; padding: 6px;">Order Sheet</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Order Qty</th>
				<th colspan="3" style="border: 1px solid #ddd; padding: 6px; text-align: center; background: #2196f3; color: #fff;">TODAY</th>
				<th colspan="3" style="border: 1px solid #ddd; padding: 6px; text-align: center; background: #455a64; color: #fff;">TOTAL</th>
			</tr>
			<tr style="background: #f8f9fa;">
				<th colspan="2"></th>
				<th style="border: 1px solid #ddd; padding: 4px;">Cutting</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Stitching</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Packing</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Cutting</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Stitching</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Packing</th>
			</tr>
		</thead>
		<tbody>{''.join(os_rows)}</tbody>
	</table>
	"""

	parent_order_qty_map = {}
	child_count_map = {}
	for row in details:
		if row.get("is_parent"):
			key = f"{row.get('order_sheet')}||{row.get('item')}"
			parent_order_qty_map[key] = flt(row.get("order_qty"))
			child_count_map.setdefault(key, 0)
		elif row.get("bundle_item"):
			key = f"{row.get('order_sheet')}||{row.get('item')}"
			child_count_map[key] = child_count_map.get(key, 0) + 1

	table_rows = []
	for row in details:
		m = _row_metrics(row, parent_order_qty_map, child_count_map, use_today=False)
		if not m:
			continue
		bg = "#f8f9fa" if m["is_parent"] else "#ffffff"
		indent = "padding-left: 24px;" if m["is_bundle"] else ""
		pack_today = "" if m["today_packing"] is None else _format_number(m["today_packing"])
		pack_total = "" if m["packing_finished"] is None else _format_number(m["packing_finished"])
		pack_today_pct = "" if m["today_pack_pct"] is None else f"<br><small>{_format_pct(m['today_pack_pct'])}%</small>"
		pack_total_pct = "" if m["packing_qty_pct"] is None else f"<br><small>{_format_pct(m['packing_qty_pct'])}%</small>"

		table_rows.append(
			f"""
			<tr style="background: {bg};">
				<td style="border: 1px solid #ddd; padding: 6px; {indent}">{esc(m['order_sheet'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; {indent}"><strong>{esc(m['so_item'])}</strong></td>
				<td style="border: 1px solid #ddd; padding: 6px;">{esc(m['combo_item'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{esc(m['size'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{esc(m['color'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(m['order_qty']) if m['order_qty'] != '' else ''}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right; background: #e3f2fd;">{_format_number(m['today_cutting'])}<br><small>{_format_pct(m['today_cut_pct'])}%</small></td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(m['cutting_finished'])}<br><small>{_format_pct(m['cutting_qty_pct'])}%</small></td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right; background: #e3f2fd;">{_format_number(m['today_stitching'])}<br><small>{_format_pct(m['today_sti_pct'])}%</small></td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{_format_number(m['stitching_finished'])}<br><small>{_format_pct(m['stitching_qty_pct'])}%</small></td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right; background: #e3f2fd;">{pack_today}{pack_today_pct}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{pack_total}{pack_total_pct}</td>
			</tr>
			"""
		)

	details_table = f"""
	<table style="border-collapse: collapse; width: 100%; font-size: 11px; margin-bottom: 16px;">
		<thead>
			<tr style="background: #f8f9fa;">
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px;">Order Sheet</th>
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px;">SO Item</th>
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px;">Combo Item</th>
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px;">Size</th>
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px;">Color</th>
				<th rowspan="2" style="border: 1px solid #ddd; padding: 6px; text-align: right;">Order Qty</th>
				<th colspan="2" style="border: 1px solid #ddd; padding: 6px; text-align: center; background: #17a2b8; color: #fff;">CUTTING</th>
				<th colspan="2" style="border: 1px solid #ddd; padding: 6px; text-align: center; background: #ffc107; color: #333;">STITCHING</th>
				<th colspan="2" style="border: 1px solid #ddd; padding: 6px; text-align: center; background: #28a745; color: #fff;">PACKING</th>
			</tr>
			<tr style="background: #f8f9fa;">
				<th style="border: 1px solid #ddd; padding: 4px; background: #e3f2fd;">Today</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Total</th>
				<th style="border: 1px solid #ddd; padding: 4px; background: #e3f2fd;">Today</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Total</th>
				<th style="border: 1px solid #ddd; padding: 4px; background: #e3f2fd;">Today</th>
				<th style="border: 1px solid #ddd; padding: 4px;">Total</th>
			</tr>
		</thead>
		<tbody>{''.join(table_rows)}</tbody>
	</table>
	"""

	return f"""
	<p>Dear Team,</p>
	<p>Production summary for <b>active (open) order sheets</b> — submitted Cutting, Stitching, and Packing reports.</p>
	<p><a href="{dashboard_url}">Open Order Tracking Dashboard</a></p>

	{_summary_block(f"Today's Summary ({formatdate(today)})", today_summary, "#1565c0")}
	{_summary_block("Total Summary (all reports till date)", total_summary, "#37474f")}

	<h3 style="margin: 20px 0 8px;">Order Sheet Summary — Today vs Total</h3>
	{order_sheet_table}

	<h3 style="margin: 20px 0 8px;">SO Item Summary — Today vs Total</h3>
	{so_item_table}

	<h3 style="margin: 20px 0 8px;">Item Details (SO Item + Combo) — Today vs Total</h3>
	{details_table}

	<p style="margin-top: 16px; font-size: 12px; color: #6c757d;">
		<b>Today</b> = quantities from reports dated {formatdate(today)} only.
		<b>Total</b> = cumulative from all submitted reports (same as the dashboard).
	</p>
	<p>Regards,<br>ERP System</p>
	"""
