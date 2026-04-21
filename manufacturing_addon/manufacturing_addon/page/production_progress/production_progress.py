import csv
import io

import frappe
from frappe.utils import add_days, flt, get_url, nowdate


def _validate_dates(from_date=None, to_date=None):
	from_date = from_date or nowdate()
	to_date = to_date or from_date
	if from_date > to_date:
		frappe.throw("From Date cannot be greater than To Date.")
	return from_date, to_date


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
	return [row[0] for row in rows if row and row[0]]


def _get_stage_rows(from_date, to_date):
	return frappe.db.sql(
		"""
		SELECT
			so.name AS sales_order,
			os.customer,
			os.name AS order_sheet,
			stage_rows.so_item,
			stage_rows.combo_item,
			stage_rows.colour,
			stage_rows.size,
			stage_rows.stage,
			stage_rows.qty,
			IFNULL(osct.order_qty, 0) AS order_qty,
			IFNULL(osct.planned_qty, 0) AS planned_qty
		FROM (
			SELECT
				'cutting' AS stage,
				cr.order_sheet,
				crct.so_item,
				IFNULL(crct.combo_item, '') AS combo_item,
				IFNULL(crct.colour, '') AS colour,
				IFNULL(crct.finished_size, '') AS size,
				SUM(IFNULL(crct.cutting_qty, 0)) AS qty
			FROM `tabCutting Report` cr
			INNER JOIN `tabCutting Report CT` crct ON crct.parent = cr.name
			WHERE cr.docstatus = 1
				AND cr.date BETWEEN %(from_date)s AND %(to_date)s
			GROUP BY cr.order_sheet, crct.so_item, IFNULL(crct.combo_item, ''), IFNULL(crct.colour, ''), IFNULL(crct.finished_size, '')

			UNION ALL

			SELECT
				'stitching' AS stage,
				sr.order_sheet,
				srct.so_item,
				IFNULL(srct.combo_item, '') AS combo_item,
				IFNULL(srct.colour, '') AS colour,
				IFNULL(srct.finished_size, '') AS size,
				SUM(IFNULL(srct.stitching_qty, 0)) AS qty
			FROM `tabStitching Report` sr
			INNER JOIN `tabStitching Report CT` srct ON srct.parent = sr.name
			WHERE sr.docstatus = 1
				AND sr.date BETWEEN %(from_date)s AND %(to_date)s
			GROUP BY sr.order_sheet, srct.so_item, IFNULL(srct.combo_item, ''), IFNULL(srct.colour, ''), IFNULL(srct.finished_size, '')

			UNION ALL

			SELECT
				'packing' AS stage,
				pr.order_sheet,
				prct.so_item,
				'' AS combo_item,
				IFNULL(prct.colour, '') AS colour,
				IFNULL(prct.finished_size, '') AS size,
				SUM(IFNULL(prct.packaging_qty, 0)) AS qty
			FROM `tabPacking Report` pr
			INNER JOIN `tabPacking Report CT` prct ON prct.parent = pr.name
			WHERE pr.docstatus = 1
				AND pr.date BETWEEN %(from_date)s AND %(to_date)s
			GROUP BY pr.order_sheet, prct.so_item, IFNULL(prct.colour, ''), IFNULL(prct.finished_size, '')
		) AS stage_rows
		INNER JOIN `tabOrder Sheet` os ON os.name = stage_rows.order_sheet
		INNER JOIN `tabSales Order` so ON so.name = os.sales_order
		LEFT JOIN `tabOrder Sheet CT` osct
			ON osct.parent = os.name
			AND osct.so_item = stage_rows.so_item
			AND IFNULL(osct.colour, '') = stage_rows.colour
			AND IFNULL(osct.size, '') = stage_rows.size
		WHERE so.docstatus < 2
		ORDER BY so.name, os.name, stage_rows.so_item, stage_rows.colour, stage_rows.size, stage_rows.stage
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)


def _build_rows(stage_rows):
	row_map = {}
	for stage_row in stage_rows:
		key = (
			stage_row.get("order_sheet"),
			stage_row.get("so_item"),
			stage_row.get("colour") or "",
			stage_row.get("size") or "",
		)
		row = row_map.setdefault(
			key,
			{
				"sales_order": stage_row.get("sales_order"),
				"customer": stage_row.get("customer") or "",
				"order_sheet": stage_row.get("order_sheet"),
				"so_item": stage_row.get("so_item") or "",
				"colour": stage_row.get("colour") or "",
				"size": stage_row.get("size") or "",
				"order_qty": flt(stage_row.get("order_qty")),
				"planned_qty": flt(stage_row.get("planned_qty")),
				"cutting_qty": 0.0,
				"stitching_qty": 0.0,
				"packing_qty": 0.0,
			},
		)

		stage_field = f"{(stage_row.get('stage') or '').lower()}_qty"
		if stage_field in row:
			row[stage_field] += flt(stage_row.get("qty"))

	rows = list(row_map.values())
	rows.sort(
		key=lambda row: (
			row.get("sales_order") or "",
			row.get("order_sheet") or "",
			row.get("so_item") or "",
			row.get("colour") or "",
			row.get("size") or "",
		)
	)
	return rows


def _build_summary(rows):
	return {
		"rows_count": len(rows),
		"total_order_qty": sum(flt(r.get("order_qty")) for r in rows),
		"total_planned_qty": sum(flt(r.get("planned_qty")) for r in rows),
		"total_cutting_qty": sum(flt(r.get("cutting_qty")) for r in rows),
		"total_stitching_qty": sum(flt(r.get("stitching_qty")) for r in rows),
		"total_packing_qty": sum(flt(r.get("packing_qty")) for r in rows),
	}


def _build_item_rows(rows):
	item_map = {}
	for row in rows:
		key = (row.get("so_item") or "", row.get("colour") or "", row.get("size") or "")
		bucket = item_map.setdefault(
			key,
			{
				"so_item": row.get("so_item") or "",
				"colour": row.get("colour") or "",
				"size": row.get("size") or "",
				"order_qty": 0.0,
				"planned_qty": 0.0,
				"cutting_qty": 0.0,
				"stitching_qty": 0.0,
				"packing_qty": 0.0,
			},
		)
		bucket["order_qty"] += flt(row.get("order_qty"))
		bucket["planned_qty"] += flt(row.get("planned_qty"))
		bucket["cutting_qty"] += flt(row.get("cutting_qty"))
		bucket["stitching_qty"] += flt(row.get("stitching_qty"))
		bucket["packing_qty"] += flt(row.get("packing_qty"))

	item_rows = list(item_map.values())
	item_rows.sort(key=lambda d: (d.get("so_item") or "", d.get("colour") or "", d.get("size") or ""))
	return item_rows


def _build_sales_order_rows(rows):
	so_map = {}
	for row in rows:
		so = row.get("sales_order") or "Not Linked"
		bucket = so_map.setdefault(
			so,
			{
				"sales_order": so,
				"customer": row.get("customer") or "",
				"order_qty": 0.0,
				"planned_qty": 0.0,
				"cutting_qty": 0.0,
				"stitching_qty": 0.0,
				"packing_qty": 0.0,
			},
		)
		bucket["order_qty"] += flt(row.get("order_qty"))
		bucket["planned_qty"] += flt(row.get("planned_qty"))
		bucket["cutting_qty"] += flt(row.get("cutting_qty"))
		bucket["stitching_qty"] += flt(row.get("stitching_qty"))
		bucket["packing_qty"] += flt(row.get("packing_qty"))

	so_rows = list(so_map.values())
	so_rows.sort(key=lambda d: (d.get("sales_order") or ""))
	return so_rows


def _build_attachment_csv(rows):
	buffer = io.StringIO()
	writer = csv.writer(buffer)
	writer.writerow(
		[
			"Sales Order",
			"Customer",
			"Order Sheet",
			"SO Item",
			"Colour",
			"Size",
			"Order Qty",
			"Planned Qty",
			"Cutting Qty",
			"Stitching Qty",
			"Packing Qty",
		]
	)
	for row in rows:
		writer.writerow(
			[
				row.get("sales_order") or "",
				row.get("customer") or "",
				row.get("order_sheet") or "",
				row.get("so_item") or "",
				row.get("colour") or "",
				row.get("size") or "",
				flt(row.get("order_qty")),
				flt(row.get("planned_qty")),
				flt(row.get("cutting_qty")),
				flt(row.get("stitching_qty")),
				flt(row.get("packing_qty")),
			]
		)
	return buffer.getvalue()


def _build_email_html(from_date, to_date, summary, sales_order_rows, dashboard_url):
	def fmt(value):
		return f"{flt(value):,.2f}"

	def pct(stage_qty, base_qty):
		base_qty = flt(base_qty)
		if not base_qty:
			return "0.00%"
		return f"{(flt(stage_qty) / base_qty) * 100:.2f}%"

	so_table_rows = []
	for row in sales_order_rows:
		so_table_rows.append(
			f"""
			<tr>
				<td style="padding: 6px 10px; border: 1px solid #ddd;">{frappe.utils.escape_html(row.get('sales_order') or '')}</td>
				<td style="padding: 6px 10px; border: 1px solid #ddd;">{frappe.utils.escape_html(row.get('customer') or '')}</td>
				<td style="padding: 6px 10px; border: 1px solid #ddd; text-align:right;">{fmt(row.get('order_qty'))}</td>
				<td style="padding: 6px 10px; border: 1px solid #ddd; text-align:right;">{fmt(row.get('planned_qty'))}</td>
				<td style="padding: 6px 10px; border: 1px solid #ddd; text-align:right;">{fmt(row.get('cutting_qty'))} ({pct(row.get('cutting_qty'), row.get('order_qty'))})</td>
				<td style="padding: 6px 10px; border: 1px solid #ddd; text-align:right;">{fmt(row.get('stitching_qty'))} ({pct(row.get('stitching_qty'), row.get('order_qty'))})</td>
				<td style="padding: 6px 10px; border: 1px solid #ddd; text-align:right;">{fmt(row.get('packing_qty'))} ({pct(row.get('packing_qty'), row.get('order_qty'))})</td>
			</tr>
			"""
		)

	so_rows_html = "".join(so_table_rows)
	if not so_rows_html:
		so_rows_html = '<tr><td colspan="7" style="padding:8px; border:1px solid #ddd; color:#6b7280;">No sales order rows found.</td></tr>'

	sales_order_summary_html = f"""
	<h4 style="margin: 14px 0 8px 0;">Sales Order-wise Summary</h4>
	<table style="border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 14px;">
		<thead>
			<tr style="background: #f8fafc;">
				<th style="padding: 6px 10px; border: 1px solid #ddd; text-align:left;">Sales Order</th>
				<th style="padding: 6px 10px; border: 1px solid #ddd; text-align:left;">Customer</th>
				<th style="padding: 6px 10px; border: 1px solid #ddd; text-align:right;">Order Qty</th>
				<th style="padding: 6px 10px; border: 1px solid #ddd; text-align:right;">Planned Qty</th>
				<th style="padding: 6px 10px; border: 1px solid #ddd; text-align:right;">Cutting Progress</th>
				<th style="padding: 6px 10px; border: 1px solid #ddd; text-align:right;">Stitching Progress</th>
				<th style="padding: 6px 10px; border: 1px solid #ddd; text-align:right;">Packing Progress</th>
			</tr>
		</thead>
		<tbody>
			{so_rows_html}
		</tbody>
	</table>
	"""

	return f"""
	<p>Dear System Managers,</p>
	<p>Production progress summary for <b>{from_date}</b> to <b>{to_date}</b>.</p>
	<p><a href="{dashboard_url}">Open Production Progress Dashboard</a></p>
	<table style="border-collapse: collapse; margin-bottom: 16px;">
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Total Rows</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{summary.get("rows_count", 0)}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Order Qty</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{fmt(summary.get("total_order_qty", 0))}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Planned Qty</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{fmt(summary.get("total_planned_qty", 0))}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Cutting</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{fmt(summary.get("total_cutting_qty", 0))}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Stitching</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{fmt(summary.get("total_stitching_qty", 0))}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Packing</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{fmt(summary.get("total_packing_qty", 0))}</td></tr>
	</table>
	{sales_order_summary_html}
	<p>Detailed item-wise progress is attached as CSV.</p>
	<p>Regards,<br>ERP System</p>
	"""


def _send_production_progress_email(from_date=None, to_date=None):
	from_date, to_date = _validate_dates(from_date, to_date)
	recipients = _get_system_manager_emails()
	if not recipients:
		return "No active System Manager email recipients found."

	stage_rows = _get_stage_rows(from_date, to_date)
	rows = _build_rows(stage_rows)
	summary = _build_summary(rows)
	sales_order_rows = _build_sales_order_rows(rows)
	dashboard_url = get_url("/app/page/production-progress")

	subject = f"Production Progress Summary - {from_date} to {to_date}"
	message = _build_email_html(from_date, to_date, summary, sales_order_rows, dashboard_url)
	attachments = [
		{
			"fname": f"production_progress_{from_date}_to_{to_date}.csv",
			"fcontent": _build_attachment_csv(rows),
		}
	]

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		attachments=attachments,
		now=False,
	)
	return "Production progress email has been queued."


@frappe.whitelist()
def get_production_progress_data(from_date=None, to_date=None):
	from_date, to_date = _validate_dates(from_date, to_date)
	stage_rows = _get_stage_rows(from_date, to_date)
	rows = _build_rows(stage_rows)
	sales_order_rows = _build_sales_order_rows(rows)
	item_rows = _build_item_rows(rows)
	return {
		"from_date": from_date,
		"to_date": to_date,
		"summary": _build_summary(rows),
		"stage_rows": stage_rows,
		"rows": rows,
		"sales_order_rows": sales_order_rows,
		"item_rows": item_rows,
	}


@frappe.whitelist()
def send_production_progress_email(from_date=None, to_date=None):
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can trigger this email.")
	return _send_production_progress_email(from_date, to_date)


def send_scheduled_production_progress_email():
	# Send the previous day's report at scheduled time.
	previous_day = add_days(nowdate(), -1)
	_send_production_progress_email(previous_day, previous_day)
