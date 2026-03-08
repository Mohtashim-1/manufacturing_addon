import frappe
from frappe.utils import flt, formatdate, get_url, nowdate


def send_daily_active_order_sheet_email():
	"""Send a daily active order-sheet production summary to System Managers."""
	recipients = _get_system_manager_emails()
	if not recipients:
		return

	rows = _get_active_order_sheet_rows()
	if not rows:
		return

	stage_totals = _get_stage_totals([row["order_sheet"] for row in rows])

	email_rows = []
	total_order_qty = 0.0
	total_cutting = 0.0
	total_stitching = 0.0
	total_quality = 0.0
	total_packing = 0.0

	for row in rows:
		order_qty = flt(row.get("planned_qty") or row.get("order_qty") or 0)
		stage_key = (row["order_sheet"], row["so_item"])
		stage = stage_totals.get(stage_key, {})

		cutting_qty = flt(stage.get("cutting_qty", 0))
		stitching_qty = flt(stage.get("stitching_qty", 0))
		quality_qty = flt(stage.get("quality_qty", 0))
		packing_qty = flt(stage.get("packing_qty", 0))

		total_order_qty += order_qty
		total_cutting += cutting_qty
		total_stitching += stitching_qty
		total_quality += quality_qty
		total_packing += packing_qty

		email_rows.append(
			{
				"order_sheet": row["order_sheet"],
				"sales_order": row["sales_order"],
				"customer": row.get("customer") or "",
				"item": row.get("so_item") or "",
				"size": row.get("size") or "",
				"colour": row.get("colour") or "",
				"order_qty": order_qty,
				"cutting_qty": cutting_qty,
				"stitching_qty": stitching_qty,
				"quality_qty": quality_qty,
				"packing_qty": packing_qty,
			}
		)

	dashboard_url = get_url("/app/order-tracking")
	subject = f"Daily Active Order Sheet Status - {formatdate(nowdate())}"
	message = _build_email_html(
		email_rows=email_rows,
		total_order_qty=total_order_qty,
		total_cutting=total_cutting,
		total_stitching=total_stitching,
		total_quality=total_quality,
		total_packing=total_packing,
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
	"""Manual trigger for sending the daily active order-sheet email."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw("Only System Manager can trigger this email.")
	send_daily_active_order_sheet_email()
	return "Daily active order-sheet email has been queued."


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


def _get_active_order_sheet_rows():
	return frappe.db.sql(
		"""
		SELECT
			os.name AS order_sheet,
			os.sales_order,
			os.customer,
			osct.so_item,
			osct.size,
			osct.colour,
			osct.order_qty,
			osct.planned_qty
		FROM `tabOrder Sheet` os
		INNER JOIN `tabOrder Sheet CT` osct ON osct.parent = os.name
		INNER JOIN `tabSales Order` so ON so.name = os.sales_order
		WHERE os.docstatus = 1
			AND so.docstatus = 1
			AND IFNULL(os.sales_order, '') != ''
			AND so.status NOT IN ('Closed', 'Completed', 'On Hold', 'Cancelled')
			AND IFNULL(so.per_delivered, 0) < 100
			AND DATE(COALESCE(os.posting_date_and_time, os.creation)) < CURDATE()
		ORDER BY os.sales_order, os.name, osct.idx
		""",
		as_dict=True,
	)


def _get_stage_totals(order_sheets):
	if not order_sheets:
		return {}

	cutting_map = _query_stage_totals(
		order_sheets,
		parent_doctype="Cutting Report",
		child_doctype="Cutting Report CT",
		qty_field="cutting_qty",
	)
	stitching_map = _query_stage_totals(
		order_sheets,
		parent_doctype="Stitching Report",
		child_doctype="Stitching Report CT",
		qty_field="stitching_qty",
	)
	quality_map = _query_stage_totals(
		order_sheets,
		parent_doctype="Quality Report",
		child_doctype="Quality Report CT",
		qty_field="quality_qty",
	)
	packing_map = _query_stage_totals(
		order_sheets,
		parent_doctype="Packing Report",
		child_doctype="Packing Report CT",
		qty_field="packaging_qty",
	)

	stage_totals = {}
	keys = set(cutting_map) | set(stitching_map) | set(quality_map) | set(packing_map)
	for key in keys:
		stage_totals[key] = {
			"cutting_qty": flt(cutting_map.get(key, 0)),
			"stitching_qty": flt(stitching_map.get(key, 0)),
			"quality_qty": flt(quality_map.get(key, 0)),
			"packing_qty": flt(packing_map.get(key, 0)),
		}
	return stage_totals


def _query_stage_totals(order_sheets, parent_doctype, child_doctype, qty_field):
	rows = frappe.db.sql(
		f"""
		SELECT
			parent_doc.order_sheet AS order_sheet,
			child_doc.so_item AS so_item,
			SUM(child_doc.{qty_field}) AS qty
		FROM `tab{child_doctype}` child_doc
		INNER JOIN `tab{parent_doctype}` parent_doc ON parent_doc.name = child_doc.parent
		WHERE parent_doc.docstatus = 1
			AND parent_doc.order_sheet IN %(order_sheets)s
			AND DATE(COALESCE(parent_doc.date, parent_doc.creation)) < CURDATE()
		GROUP BY parent_doc.order_sheet, child_doc.so_item
		""",
		{"order_sheets": tuple(order_sheets)},
		as_dict=True,
	)
	return {(d["order_sheet"], d["so_item"]): flt(d["qty"]) for d in rows}


def _pct(value, base):
	base = flt(base)
	if not base:
		return 0.0
	return (flt(value) / base) * 100


def _build_email_html(
	email_rows,
	total_order_qty,
	total_cutting,
	total_stitching,
	total_quality,
	total_packing,
	dashboard_url,
):
	def n(v):
		return f"{flt(v):,.2f}"

	def stage_cell(stage_qty, order_qty):
		return f"{n(stage_qty)} ({_pct(stage_qty, order_qty):.1f}%)"

	summary_html = f"""
	<table style="border-collapse: collapse; margin-bottom: 16px;">
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Total Active Rows</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{len(email_rows)}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Total Order Qty</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{n(total_order_qty)}</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Cutting</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{n(total_cutting)} ({_pct(total_cutting, total_order_qty):.1f}%)</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Stitching</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{n(total_stitching)} ({_pct(total_stitching, total_order_qty):.1f}%)</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Quality</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{n(total_quality)} ({_pct(total_quality, total_order_qty):.1f}%)</td></tr>
		<tr><td style="padding: 6px 10px; border: 1px solid #ddd;"><b>Packing</b></td><td style="padding: 6px 10px; border: 1px solid #ddd;">{n(total_packing)} ({_pct(total_packing, total_order_qty):.1f}%)</td></tr>
	</table>
	"""

	table_rows = []
	for r in email_rows:
		table_rows.append(
			f"""
			<tr>
				<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(r['order_sheet'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(r['sales_order'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(r['customer'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(r['item'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(r['size'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px;">{frappe.utils.escape_html(r['colour'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{n(r['order_qty'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{stage_cell(r['cutting_qty'], r['order_qty'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{stage_cell(r['stitching_qty'], r['order_qty'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{stage_cell(r['quality_qty'], r['order_qty'])}</td>
				<td style="border: 1px solid #ddd; padding: 6px; text-align: right;">{stage_cell(r['packing_qty'], r['order_qty'])}</td>
			</tr>
			"""
		)

	details_table = f"""
	<table style="border-collapse: collapse; width: 100%; font-size: 12px;">
		<thead>
			<tr style="background: #f1f5f9;">
				<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Order Sheet</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Sales Order</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Customer</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Item</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Size</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: left;">Colour</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Order Qty</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Cutting</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Stitching</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Quality</th>
				<th style="border: 1px solid #ddd; padding: 6px; text-align: right;">Packing</th>
			</tr>
		</thead>
		<tbody>
			{''.join(table_rows)}
		</tbody>
	</table>
	"""

	return f"""
	<p>Dear System Managers,</p>
	<p>Please find below the daily summary of active sales-order order sheets with item-wise production progress.</p>
	<p><a href="{dashboard_url}">Open Order Tracking Dashboard</a></p>
	{summary_html}
	{details_table}
	<p style="margin-top: 16px;">Regards,<br>ERP System</p>
	"""
