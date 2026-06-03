# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

import frappe
from frappe.utils import flt, formatdate, get_url, nowdate

from manufacturing_addon.manufacturing_addon.daily_order_sheet_email import (
	_get_system_manager_emails,
)
from manufacturing_addon.manufacturing_addon.page.contractor_performance.contractor_performance import (
	get_contractor_performance_data,
)


def send_daily_contractor_performance_email():
	"""Email System Managers a static snapshot of Contractor Performance for today."""
	recipients = _get_system_manager_emails()
	if not recipients:
		return

	today = nowdate()
	data = get_contractor_performance_data(from_date=today, to_date=today)

	dashboard_url = get_url(f"/app/contractor-performan?from_date={today}&to_date={today}")
	subject = f"Contractor Performance — {formatdate(today)}"
	message = _build_email_html(today=today, data=data, dashboard_url=dashboard_url)

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		now=False,
	)


@frappe.whitelist()
def trigger_daily_contractor_performance_email():
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can trigger this email.")
	send_daily_contractor_performance_email()
	return "Contractor performance email has been queued."


def _esc(value):
	return frappe.utils.escape_html(str(value or ""))


def _format_number(value):
	return f"{flt(value):,.0f}"


def _article_label(row):
	parts = [row.get("article"), row.get("design"), row.get("colour")]
	parts = [p for p in parts if p and str(p).strip()]
	return " / ".join(parts) if parts else "—"


def _contractor_chips_html(contractors):
	if not contractors:
		return '<span style="color:#94a3b8;font-style:italic;">—</span>'
	chips = []
	for c in contractors:
		name = _esc(c.get("contractor_name") or c.get("contractor") or "—")
		qty = _format_number(c.get("qty"))
		chips.append(
			f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:4px 10px;'
			f'background:#f8fafc;border:1px solid #e2e8f0;border-radius:999px;font-size:11px;">'
			f'<span style="color:#334155;">{name}</span> '
			f'<strong style="color:#0f172a;">{qty}</strong></span>'
		)
	return "".join(chips)


def _contractor_summary_rows(data):
	buckets = {}
	for stage_key, stage_label in (
		("cutting", "cutting"),
		("stitching", "stitching"),
		("packing", "packing"),
	):
		for row in data.get(stage_key) or []:
			name = row.get("contractor_name") or row.get("contractor") or "—"
			if name not in buckets:
				buckets[name] = {
					"name": name,
					"cutting": 0,
					"stitching": 0,
					"packing": 0,
					"total": 0,
				}
			buckets[name][stage_label] += flt(row.get("qty"))
			buckets[name]["total"] += flt(row.get("qty"))
	return sorted(buckets.values(), key=lambda r: -r["total"])


def _summary_block(today, data):
	rows = _contractor_summary_rows(data)
	total_cut = sum(flt(r.get("qty")) for r in data.get("cutting") or [])
	total_sti = sum(flt(r.get("qty")) for r in data.get("stitching") or [])
	total_pack = sum(flt(r.get("qty")) for r in data.get("packing") or [])
	return f"""
	<table style="border-collapse:collapse;width:100%;max-width:720px;font-size:13px;margin-bottom:16px;">
		<tr><td style="padding:8px 12px;border:1px solid #ddd;"><b>Report date</b></td>
			<td style="padding:8px 12px;border:1px solid #ddd;">{formatdate(today)}</td></tr>
		<tr><td style="padding:8px 12px;border:1px solid #ddd;"><b>Contractors (active)</b></td>
			<td style="padding:8px 12px;border:1px solid #ddd;">{len(rows)}</td></tr>
		<tr><td style="padding:8px 12px;border:1px solid #ddd;"><b>Cutting qty (today)</b></td>
			<td style="padding:8px 12px;border:1px solid #ddd;">{_format_number(total_cut)}</td></tr>
		<tr><td style="padding:8px 12px;border:1px solid #ddd;"><b>Stitching qty (today)</b></td>
			<td style="padding:8px 12px;border:1px solid #ddd;">{_format_number(total_sti)}</td></tr>
		<tr><td style="padding:8px 12px;border:1px solid #ddd;"><b>Packing qty (today)</b></td>
			<td style="padding:8px 12px;border:1px solid #ddd;">{_format_number(total_pack)}</td></tr>
	</table>
	"""


def _contractor_summary_table(data):
	rows = _contractor_summary_rows(data)
	if not rows:
		return '<p style="color:#64748b;">No contractor activity for this date.</p>'

	body = []
	for r in rows:
		body.append(
			f"""
			<tr>
				<td style="border:1px solid #ddd;padding:6px;">{_esc(r["name"])}</td>
				<td style="border:1px solid #ddd;padding:6px;text-align:right;">{_format_number(r["cutting"])}</td>
				<td style="border:1px solid #ddd;padding:6px;text-align:right;">{_format_number(r["stitching"])}</td>
				<td style="border:1px solid #ddd;padding:6px;text-align:right;">{_format_number(r["packing"])}</td>
				<td style="border:1px solid #ddd;padding:6px;text-align:right;font-weight:700;">{_format_number(r["total"])}</td>
			</tr>
			"""
		)

	return f"""
	<table style="border-collapse:collapse;width:100%;font-size:12px;margin-bottom:20px;">
		<thead>
			<tr style="background:#f1f5f9;">
				<th style="border:1px solid #ddd;padding:6px;">Contractor</th>
				<th style="border:1px solid #ddd;padding:6px;text-align:right;">Cutting</th>
				<th style="border:1px solid #ddd;padding:6px;text-align:right;">Stitching</th>
				<th style="border:1px solid #ddd;padding:6px;text-align:right;">Packing</th>
				<th style="border:1px solid #ddd;padding:6px;text-align:right;">Total</th>
			</tr>
		</thead>
		<tbody>{"".join(body)}</tbody>
	</table>
	"""


def _matrix_table(data, max_rows=150):
	groups = data.get("item_matrix_groups") or []
	if groups:
		sections = []
		row_count = 0
		for g in groups:
			if row_count >= max_rows:
				break
			so_title = _esc(g.get("so_item_label") or g.get("so_item") or "Other")
			so_code = _esc(g.get("so_item") or "")
			head = f"""
			<div style="margin:12px 0 6px;padding:10px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #2563eb;">
				<div style="font-size:10px;text-transform:uppercase;color:#64748b;font-weight:700;">Sales order line</div>
				<div style="font-size:14px;font-weight:600;color:#0f172a;">{so_title}</div>
				<div style="font-size:11px;color:#64748b;">{so_code}</div>
			</div>
			"""
			lines = g.get("lines") or []
			trs = []
			for line in lines:
				if row_count >= max_rows:
					break
				row_count += 1
				component = _esc(line.get("component_title") or line.get("item_label") or "")
				trs.append(
					f"""
					<tr>
						<td style="border:1px solid #ddd;padding:6px;">{component}</td>
						<td style="border:1px solid #ddd;padding:6px;">{_contractor_chips_html(line.get("cutting"))}</td>
						<td style="border:1px solid #ddd;padding:6px;">{_contractor_chips_html(line.get("stitching"))}</td>
						<td style="border:1px solid #ddd;padding:6px;">{_contractor_chips_html(line.get("packing"))}</td>
					</tr>
					"""
				)
			if trs:
				sections.append(
					head
					+ f"""
				<table style="border-collapse:collapse;width:100%;font-size:11px;margin-bottom:16px;">
					<thead>
						<tr style="background:#f8f9fa;">
							<th style="border:1px solid #ddd;padding:6px;">Component</th>
							<th style="border:1px solid #ddd;padding:6px;">Cutting</th>
							<th style="border:1px solid #ddd;padding:6px;">Stitching</th>
							<th style="border:1px solid #ddd;padding:6px;">Packing</th>
						</tr>
					</thead>
					<tbody>{"".join(trs)}</tbody>
				</table>
				"""
				)
		tail = ""
		if row_count >= max_rows:
			tail = f'<p style="font-size:12px;color:#64748b;">Showing first {max_rows} matrix rows. Open the dashboard for the full list.</p>'
		return ("".join(sections) if sections else '<p style="color:#64748b;">No item matrix data.</p>') + tail

	matrix = data.get("item_matrix") or []
	if not matrix:
		return '<p style="color:#64748b;">No item matrix data.</p>'

	trs = []
	for m in matrix[:max_rows]:
		trs.append(
			f"""
			<tr>
				<td style="border:1px solid #ddd;padding:6px;">{_esc(m.get("item_label"))}</td>
				<td style="border:1px solid #ddd;padding:6px;">{_esc(m.get("so_item_label") or m.get("so_item") or "")}</td>
				<td style="border:1px solid #ddd;padding:6px;">{_esc(m.get("combo_item_label") or m.get("combo_item") or "")}</td>
				<td style="border:1px solid #ddd;padding:6px;">{_contractor_chips_html(m.get("cutting"))}</td>
				<td style="border:1px solid #ddd;padding:6px;">{_contractor_chips_html(m.get("stitching"))}</td>
				<td style="border:1px solid #ddd;padding:6px;">{_contractor_chips_html(m.get("packing"))}</td>
			</tr>
			"""
		)

	tail = ""
	if len(matrix) > max_rows:
		tail = f'<p style="font-size:12px;color:#64748b;">Showing first {max_rows} rows. Open the dashboard for the full list.</p>'

	return f"""
	<table style="border-collapse:collapse;width:100%;font-size:11px;margin-bottom:20px;">
		<thead>
			<tr style="background:#f1f5f9;">
				<th style="border:1px solid #ddd;padding:6px;">Item</th>
				<th style="border:1px solid #ddd;padding:6px;">SO Item</th>
				<th style="border:1px solid #ddd;padding:6px;">Combo Item</th>
				<th style="border:1px solid #ddd;padding:6px;">Cutting</th>
				<th style="border:1px solid #ddd;padding:6px;">Stitching</th>
				<th style="border:1px solid #ddd;padding:6px;">Packing</th>
			</tr>
		</thead>
		<tbody>{"".join(trs)}</tbody>
	</table>
	{tail}
	"""


def _stage_detail_table(rows, stage_label, max_rows=100):
	if not rows:
		return f'<p style="color:#64748b;">No {stage_label.lower()} lines for this date.</p>'

	trs = []
	for r in rows[:max_rows]:
		reports = ", ".join((r.get("reports") or [])[:5])
		trs.append(
			f"""
			<tr>
				<td style="border:1px solid #ddd;padding:6px;">{_esc(r.get("item_label"))}</td>
				<td style="border:1px solid #ddd;padding:6px;">{_esc(_article_label(r))}</td>
				<td style="border:1px solid #ddd;padding:6px;">{_esc(r.get("so_item_label") or r.get("so_item") or "")}</td>
				<td style="border:1px solid #ddd;padding:6px;">{_esc(r.get("combo_item_label") or r.get("combo_item") or "")}</td>
				<td style="border:1px solid #ddd;padding:6px;">{_esc(r.get("contractor_name") or r.get("contractor") or "")}</td>
				<td style="border:1px solid #ddd;padding:6px;text-align:right;">{_format_number(r.get("qty"))}</td>
				<td style="border:1px solid #ddd;padding:6px;text-align:right;">{int(r.get("report_count") or 0)}</td>
				<td style="border:1px solid #ddd;padding:6px;font-size:10px;">{_esc(reports)}</td>
			</tr>
			"""
		)

	tail = ""
	if len(rows) > max_rows:
		tail = f'<p style="font-size:12px;color:#64748b;">Showing first {max_rows} {stage_label.lower()} rows.</p>'

	return f"""
	<table style="border-collapse:collapse;width:100%;font-size:11px;margin-bottom:20px;">
		<thead>
			<tr style="background:#f1f5f9;">
				<th style="border:1px solid #ddd;padding:6px;">Item</th>
				<th style="border:1px solid #ddd;padding:6px;">Article</th>
				<th style="border:1px solid #ddd;padding:6px;">SO Item</th>
				<th style="border:1px solid #ddd;padding:6px;">Combo Item</th>
				<th style="border:1px solid #ddd;padding:6px;">Contractor</th>
				<th style="border:1px solid #ddd;padding:6px;text-align:right;">Qty</th>
				<th style="border:1px solid #ddd;padding:6px;text-align:right;">Reports</th>
				<th style="border:1px solid #ddd;padding:6px;">Sample IDs</th>
			</tr>
		</thead>
		<tbody>{"".join(trs)}</tbody>
	</table>
	{tail}
	"""


def _build_email_html(today, data, dashboard_url):
	return f"""
	<p>Dear Team,</p>
	<p>Contractor performance summary for <b>{formatdate(today)}</b> (submitted Cutting, Stitching, and Packing reports dated today).</p>
	<p><a href="{dashboard_url}" style="display:inline-block;padding:10px 16px;background:#0f172a;color:#fff;text-decoration:none;border-radius:6px;font-weight:600;">Open Contractor Performance Dashboard</a></p>
	<p style="font-size:12px;color:#64748b;">Use the link above for interactive drill-down, tabs, and filters. Email shows a static snapshot only.</p>

	<h3 style="margin:20px 0 8px;color:#1565c0;">Summary</h3>
	{_summary_block(today, data)}

	<h3 style="margin:20px 0 8px;">By contractor (all stages)</h3>
	{_contractor_summary_table(data)}

	<h3 style="margin:20px 0 8px;">By item — all stages (matrix)</h3>
	{_matrix_table(data)}

	<h3 style="margin:20px 0 8px;">Cutting detail</h3>
	{_stage_detail_table(data.get("cutting") or [], "Cutting")}

	<h3 style="margin:20px 0 8px;">Stitching detail</h3>
	{_stage_detail_table(data.get("stitching") or [], "Stitching")}

	<h3 style="margin:20px 0 8px;">Packing detail</h3>
	{_stage_detail_table(data.get("packing") or [], "Packing")}

	<p style="margin-top:16px;font-size:12px;color:#6c757d;">
		Data matches the Contractor Performance dashboard with <b>From Date</b> and <b>To Date</b> set to today.
		Drill-down and animations are only available on the live dashboard.
	</p>
	<p>Regards,<br>ERP System</p>
	"""
