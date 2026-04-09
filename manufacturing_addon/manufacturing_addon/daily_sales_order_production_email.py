import frappe
from frappe.utils import flt, format_datetime, formatdate, get_datetime, now_datetime


def send_daily_sales_order_production_email():
	"""Send today's production summary grouped by sales order."""
	recipients = _get_system_manager_emails()
	if not recipients:
		return

	rows = _get_today_sales_order_rows()
	if not rows:
		return

	subject = f"Sales Order Production Summary - {formatdate(now_datetime())}"
	message = _build_email_html(rows)

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
		now=False,
	)


@frappe.whitelist()
def trigger_daily_sales_order_production_email():
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can trigger this email.")

	send_daily_sales_order_production_email()
	return "Daily sales order production email has been queued."


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


def _get_today_sales_order_rows():
	stage_rows = _get_today_stage_rows()
	if not stage_rows:
		return []

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
				"last_activity": stage_row.get("posting_datetime"),
			},
		)

		stage_field = f"{(stage_row.get('stage') or '').lower()}_qty"
		if stage_field in row:
			row[stage_field] += flt(stage_row.get("qty"))

		posting_datetime = stage_row.get("posting_datetime")
		if posting_datetime and (
			not row["last_activity"] or get_datetime(posting_datetime) > get_datetime(row["last_activity"])
		):
			row["last_activity"] = posting_datetime

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


def _get_today_stage_rows():
	return frappe.db.sql(
		"""
		SELECT
			so.name AS sales_order,
			os.customer,
			os.name AS order_sheet,
			osct.so_item,
			IFNULL(osct.colour, '') AS colour,
			IFNULL(osct.size, '') AS size,
			IFNULL(osct.order_qty, 0) AS order_qty,
			IFNULL(osct.planned_qty, 0) AS planned_qty,
			stage_rows.stage,
			stage_rows.qty,
			stage_rows.posting_datetime
		FROM (
			SELECT
				'cutting' AS stage,
				cr.order_sheet,
				crct.so_item,
				IFNULL(crct.colour, '') AS colour,
				IFNULL(crct.finished_size, '') AS size,
				SUM(IFNULL(crct.cutting_qty, 0)) AS qty,
				MAX(TIMESTAMP(cr.date, IFNULL(cr.time, '00:00:00'))) AS posting_datetime
			FROM `tabCutting Report` cr
			INNER JOIN `tabCutting Report CT` crct ON crct.parent = cr.name
			WHERE cr.docstatus = 1
				AND cr.date = CURDATE()
			GROUP BY cr.order_sheet, crct.so_item, IFNULL(crct.colour, ''), IFNULL(crct.finished_size, '')

			UNION ALL

			SELECT
				'stitching' AS stage,
				sr.order_sheet,
				srct.so_item,
				IFNULL(srct.colour, '') AS colour,
				IFNULL(srct.finished_size, '') AS size,
				SUM(IFNULL(srct.stitching_qty, 0)) AS qty,
				MAX(TIMESTAMP(sr.date, IFNULL(sr.time, '00:00:00'))) AS posting_datetime
			FROM `tabStitching Report` sr
			INNER JOIN `tabStitching Report CT` srct ON srct.parent = sr.name
			WHERE sr.docstatus = 1
				AND sr.date = CURDATE()
			GROUP BY sr.order_sheet, srct.so_item, IFNULL(srct.colour, ''), IFNULL(srct.finished_size, '')

			UNION ALL

			SELECT
				'packing' AS stage,
				pr.order_sheet,
				prct.so_item,
				IFNULL(prct.colour, '') AS colour,
				IFNULL(prct.finished_size, '') AS size,
				SUM(IFNULL(prct.packaging_qty, 0)) AS qty,
				MAX(TIMESTAMP(pr.date, IFNULL(pr.time, '00:00:00'))) AS posting_datetime
			FROM `tabPacking Report` pr
			INNER JOIN `tabPacking Report CT` prct ON prct.parent = pr.name
			WHERE pr.docstatus = 1
				AND pr.date = CURDATE()
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
		ORDER BY so.name, os.name, osct.idx, stage_rows.stage
		""",
		as_dict=True,
	)


def _build_email_html(rows):
	def n(value):
		return f"{flt(value):,.2f}"

	sales_orders = []
	so_map = {}
	grand_order_qty = 0.0
	grand_planned_qty = 0.0
	grand_cutting_qty = 0.0
	grand_stitching_qty = 0.0
	grand_packing_qty = 0.0

	for row in rows:
		sales_order = row.get("sales_order") or "Not Linked"
		so_bucket = so_map.setdefault(
			sales_order,
			{
				"sales_order": sales_order,
				"customer": row.get("customer") or "",
				"order_qty": 0.0,
				"planned_qty": 0.0,
				"cutting_qty": 0.0,
				"stitching_qty": 0.0,
				"packing_qty": 0.0,
				"rows": [],
			},
		)
		if not so_bucket["rows"]:
			sales_orders.append(so_bucket)

		so_bucket["order_qty"] += flt(row.get("order_qty"))
		so_bucket["planned_qty"] += flt(row.get("planned_qty"))
		so_bucket["cutting_qty"] += flt(row.get("cutting_qty"))
		so_bucket["stitching_qty"] += flt(row.get("stitching_qty"))
		so_bucket["packing_qty"] += flt(row.get("packing_qty"))
		so_bucket["rows"].append(row)

		grand_order_qty += flt(row.get("order_qty"))
		grand_planned_qty += flt(row.get("planned_qty"))
		grand_cutting_qty += flt(row.get("cutting_qty"))
		grand_stitching_qty += flt(row.get("stitching_qty"))
		grand_packing_qty += flt(row.get("packing_qty"))

	summary_rows = []
	for so_bucket in sales_orders:
		summary_rows.append(
			f"""
			<tr>
				<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(so_bucket['sales_order'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(so_bucket['customer'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(so_bucket['order_qty'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(so_bucket['planned_qty'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(so_bucket['cutting_qty'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(so_bucket['stitching_qty'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(so_bucket['packing_qty'])}</td>
			</tr>
			"""
		)

	detail_sections = []
	for so_bucket in sales_orders:
		detail_rows = []
		for row in so_bucket["rows"]:
			detail_rows.append(
				f"""
				<tr>
					<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(row['order_sheet'])}</td>
					<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(row['so_item'])}</td>
					<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(row['colour'])}</td>
					<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(row['size'])}</td>
					<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(row['order_qty'])}</td>
					<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(row['planned_qty'])}</td>
					<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(row['cutting_qty'])}</td>
					<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(row['stitching_qty'])}</td>
					<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(row['packing_qty'])}</td>
					<td style="border: 1px solid #ddd; padding: 6px;">{format_datetime(row['last_activity']) if row.get('last_activity') else ''}</td>
				</tr>
				"""
			)

		detail_sections.append(
			f"""
			<h3 style="margin: 18px 0 8px;">Sales Order: {frappe.utils.escape_html(so_bucket['sales_order'])}</h3>
			<p style="margin: 0 0 8px;">Customer: {frappe.utils.escape_html(so_bucket['customer'])}</p>
			<table style="border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 18px;">
				<thead>
					<tr style="background: #f1f5f9;">
						<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Order Sheet</th>
						<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">SO Item</th>
						<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Colour</th>
						<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Size</th>
						<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Order Qty</th>
						<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Planned Qty</th>
						<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Today Cutting</th>
						<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Today Stitching</th>
						<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Today Packing</th>
						<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Last Activity</th>
					</tr>
				</thead>
				<tbody>
					{''.join(detail_rows)}
				</tbody>
			</table>
			"""
		)

	return f"""
	<p>Dear Team,</p>
	<p>This is the sales-order-wise production summary for <b>{formatdate(now_datetime())}</b>. The figures below include only today's submitted entries from Cutting Report, Stitching Report, Packing Report, and matching Order Sheet rows.</p>

	<table style="border-collapse: collapse; margin-bottom: 18px;">
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Total Sales Orders</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{len(sales_orders)}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Total Detail Rows</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{len(rows)}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Total Order Qty</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{n(grand_order_qty)}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Total Planned Qty</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{n(grand_planned_qty)}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Today Cutting</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{n(grand_cutting_qty)}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Today Stitching</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{n(grand_stitching_qty)}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Today Packing</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{n(grand_packing_qty)}</td></tr>
	</table>

	<h3 style="margin: 18px 0 8px;">Sales Order Summary</h3>
	<table style="border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 18px;">
		<thead>
			<tr style="background: #f1f5f9;">
				<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Sales Order</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Customer</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Order Qty</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Planned Qty</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Today Cutting</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Today Stitching</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Today Packing</th>
			</tr>
		</thead>
		<tbody>
			{''.join(summary_rows)}
		</tbody>
	</table>

	{''.join(detail_sections)}
	<p style="margin-top: 16px;">Regards,<br>ERP System</p>
	"""
