import json

import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, get_first_day, get_last_day, getdate, now_datetime, nowdate


@frappe.whitelist()
def get_sales_addon_customer_sales_data(filters=None):
	filters = _coerce_filters(filters)
	conditions = ["so.docstatus < 2", "so.transaction_date between %(from_date)s and %(to_date)s"]
	params = {
		"from_date": filters["from_date"],
		"to_date": filters["to_date"],
		"top_n": filters["top_n"],
	}

	if filters.get("company"):
		conditions.append("so.company = %(company)s")
		params["company"] = filters["company"]

	where_clause = " where " + " and ".join(conditions)

	top_customers = frappe.db.sql(
		f"""
		select
			so.customer,
			max(coalesce(so.customer_name, so.customer)) as customer_name,
			sum(ifnull(so.base_grand_total, 0)) as amount,
			count(so.name) as order_count
		from `tabSales Order` so
		{where_clause}
		and so.status != 'Cancelled'
		group by so.customer
		order by amount desc
		limit %(top_n)s
		""",
		params,
		as_dict=True,
	)

	orders = frappe.db.sql(
		f"""
		select
			so.name,
			so.docstatus,
			so.transaction_date,
			so.delivery_date,
			so.customer,
			coalesce(so.customer_name, so.customer) as customer_name,
			coalesce(so.territory, 'Unassigned') as territory,
			so.currency,
			ifnull(so.grand_total, 0) as grand_total,
			ifnull(so.base_grand_total, 0) as base_grand_total,
			ifnull(so.per_delivered, 0) as per_delivered,
			ifnull(so.per_billed, 0) as per_billed,
			ifnull(so.total_qty, 0) as total_qty,
			so.status
		from `tabSales Order` so
		{where_clause}
		order by so.transaction_date asc, so.modified desc
		""",
		params,
		as_dict=True,
	)

	territory_breakdown = frappe.db.sql(
		f"""
		select
			coalesce(nullif(so.territory, ''), 'Unassigned') as name,
			sum(ifnull(so.base_grand_total, 0)) as value,
			count(so.name) as order_count
		from `tabSales Order` so
		{where_clause}
		and so.status != 'Cancelled'
		group by coalesce(nullif(so.territory, ''), 'Unassigned')
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)

	status_pipeline_rows = frappe.db.sql(
		f"""
		select
			case
				when so.docstatus = 0 then 'Draft'
				when so.status = 'Closed' then 'Closed'
				when so.status = 'Completed' then 'Completed'
				when so.status = 'To Bill' then 'To Bill'
				when so.status = 'To Deliver' then 'To Deliver'
				when so.status = 'To Deliver and Bill' then 'To Deliver and Bill'
				else coalesce(nullif(so.status, ''), 'Other')
			end as name,
			sum(ifnull(so.base_grand_total, 0)) as value,
			count(so.name) as order_count
		from `tabSales Order` so
		{where_clause}
		and so.status != 'Cancelled'
		group by 1
		""",
		params,
		as_dict=True,
	)

	item_group_breakdown = frappe.db.sql(
		f"""
		select
			coalesce(nullif(soi.item_group, ''), 'Unassigned') as name,
			sum(ifnull(soi.base_amount, 0)) as value,
			count(distinct so.name) as order_count
		from `tabSales Order` so
		inner join `tabSales Order Item` soi on soi.parent = so.name
		{where_clause}
		and so.status != 'Cancelled'
		group by coalesce(nullif(soi.item_group, ''), 'Unassigned')
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)

	grouped_orders = _group_orders_by_currency(orders)
	orders_list = _normalize_orders(orders)

	return {
		"currency": _get_default_currency(filters.get("company")),
		"filters": {
			"from_date": str(filters["from_date"]),
			"to_date": str(filters["to_date"]),
			"company": filters.get("company"),
			"top_n": filters["top_n"],
		},
		"top_customers": [
			{
				"customer": row.customer,
				"customer_name": row.customer_name,
				"amount": flt(row.amount),
				"order_count": int(row.order_count or 0),
			}
			for row in top_customers
		],
		"territory_breakdown": [
			{
				"name": row.name,
				"value": flt(row.value),
				"order_count": int(row.order_count or 0),
			}
			for row in territory_breakdown
		],
		"status_pipeline": _ordered_status_pipeline(status_pipeline_rows),
		"item_group_breakdown": [
			{
				"name": row.name,
				"value": flt(row.value),
				"order_count": int(row.order_count or 0),
			}
			for row in item_group_breakdown
		],
		"orders": orders_list,
		"currency_wise_orders": grouped_orders,
	}


def _coerce_filters(filters):
	if isinstance(filters, str):
		filters = json.loads(filters)

	filters = filters or {}
	today = getdate(nowdate())
	first_day = today.replace(day=1)

	return {
		"from_date": getdate(filters.get("from_date") or first_day),
		"to_date": getdate(filters.get("to_date") or today),
		"company": filters.get("company"),
		"top_n": cint_or_default(filters.get("top_n"), 8),
	}


def _group_orders_by_currency(orders):
	grouped = {}

	for row in orders:
		currency = row.currency or _("Not Set")
		if currency not in grouped:
			grouped[currency] = {
				"currency": currency,
				"order_count": 0,
				"total_amount": 0.0,
				"base_total_amount": 0.0,
				"orders": [],
			}

		group = grouped[currency]
		group["order_count"] += 1
		group["total_amount"] += flt(row.grand_total)
		group["base_total_amount"] += flt(row.base_grand_total)
		group["orders"].append(
			{
				"name": row.name,
				"docstatus": int(row.docstatus or 0),
				"transaction_date": str(row.transaction_date),
				"delivery_date": str(row.delivery_date) if row.delivery_date else None,
				"customer": row.customer,
				"customer_name": row.customer_name,
				"territory": row.territory,
				"currency": currency,
				"grand_total": flt(row.grand_total),
				"base_grand_total": flt(row.base_grand_total),
				"per_delivered": flt(row.per_delivered),
				"per_billed": flt(row.per_billed),
				"total_qty": flt(row.total_qty),
				"status": row.status,
			}
		)

	return list(grouped.values())


def _normalize_orders(orders):
	return [
		{
			"name": row.name,
			"docstatus": int(row.docstatus or 0),
			"transaction_date": str(row.transaction_date),
			"delivery_date": str(row.delivery_date) if row.delivery_date else None,
			"customer": row.customer,
			"customer_name": row.customer_name,
			"territory": row.territory,
			"currency": row.currency,
			"grand_total": flt(row.grand_total),
			"base_grand_total": flt(row.base_grand_total),
			"per_delivered": flt(row.per_delivered),
			"per_billed": flt(row.per_billed),
			"total_qty": flt(row.total_qty),
			"status": row.status,
		}
		for row in orders
	]


def _get_default_currency(company=None):
	if company:
		currency = frappe.db.get_value("Company", company, "default_currency")
		if currency:
			return currency

	default_company = frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default(
		"company"
	)
	if default_company:
		currency = frappe.db.get_value("Company", default_company, "default_currency")
		if currency:
			return currency

	return frappe.db.get_single_value("Global Defaults", "default_currency") or "USD"


def cint_or_default(value, default):
	try:
		return max(int(value), 1)
	except (TypeError, ValueError):
		return default


def _ordered_status_pipeline(rows):
	order = [
		"Draft",
		"To Deliver and Bill",
		"To Deliver",
		"To Bill",
		"Completed",
		"Closed",
	]
	row_map = {
		(row.name or "Other"): {
			"name": row.name or "Other",
			"value": flt(row.value),
			"order_count": int(row.order_count or 0),
		}
		for row in rows
	}

	ordered = [row_map.pop(name) for name in order if name in row_map]
	ordered.extend(sorted(row_map.values(), key=lambda row: row["value"], reverse=True))
	return ordered


@frappe.whitelist()
def get_sales_order_listview_dashboard(from_date=None, to_date=None, company=None):
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Managers can view Sales Order list KPIs."), frappe.PermissionError)

	today = getdate(nowdate())
	to_date = getdate(to_date) if to_date else today
	default_from_date = get_first_day(add_months(to_date, -11))
	from_date = getdate(from_date) if from_date else default_from_date
	company = company or None

	conditions = [
		"so.docstatus = 1",
		"so.status != 'Cancelled'",
		"so.transaction_date between %(from_date)s and %(to_date)s",
	]
	params = {"from_date": from_date, "to_date": to_date}

	if company:
		conditions.append("so.company = %(company)s")
		params["company"] = company

	where_clause = " where " + " and ".join(conditions)

	kpi_row = frappe.db.sql(
		f"""
		select
			count(so.name) as total_orders,
			sum(ifnull(so.base_grand_total, 0)) as total_value,
			sum(case when so.docstatus = 0 then ifnull(so.base_grand_total, 0) else 0 end) as draft_value,
			sum(case when so.status in ('To Deliver and Bill', 'To Deliver', 'To Bill') then ifnull(so.base_grand_total, 0) else 0 end) as pending_value,
			sum(case when so.status = 'Completed' then ifnull(so.base_grand_total, 0) else 0 end) as completed_value,
			sum(case when so.status = 'Closed' then ifnull(so.base_grand_total, 0) else 0 end) as closed_value
		from `tabSales Order` so
		{where_clause}
		""",
		params,
		as_dict=True,
	)[0]

	trend_start = get_first_day(add_months(to_date, -11))
	trend_params = {"trend_start": trend_start, "to_date": to_date}
	if company:
		trend_params["company"] = company

	trend_conditions = [
		"so.docstatus = 1",
		"so.status != 'Cancelled'",
		"so.transaction_date between %(trend_start)s and %(to_date)s",
	]
	if company:
		trend_conditions.append("so.company = %(company)s")
	trend_where_clause = " where " + " and ".join(trend_conditions)

	trend_rows = frappe.db.sql(
		f"""
		select
			date_format(so.transaction_date, '%%Y-%%m') as sort_key,
			sum(ifnull(so.base_grand_total, 0)) as value,
			count(so.name) as order_count
		from `tabSales Order` so
		{trend_where_clause}
		group by sort_key
		order by sort_key asc
		""",
		trend_params,
		as_dict=True,
	)

	status_rows = frappe.db.sql(
		f"""
		select
			case
				when so.docstatus = 0 then 'Draft'
				when so.status = 'Closed' then 'Closed'
				when so.status = 'Completed' then 'Completed'
				when so.status = 'To Bill' then 'To Bill'
				when so.status = 'To Deliver' then 'To Deliver'
				when so.status = 'To Deliver and Bill' then 'To Deliver and Bill'
				else coalesce(nullif(so.status, ''), 'Other')
			end as name,
			sum(ifnull(so.base_grand_total, 0)) as value,
			count(so.name) as order_count
		from `tabSales Order` so
		{where_clause}
		group by 1
		""",
		params,
		as_dict=True,
	)

	territory_rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(so.territory, ''), 'Unassigned') as name,
			sum(ifnull(so.base_grand_total, 0)) as value,
			count(so.name) as order_count
		from `tabSales Order` so
		{where_clause}
		group by coalesce(nullif(so.territory, ''), 'Unassigned')
		order by value desc
		limit 6
		""",
		params,
		as_dict=True,
	)

	currency_rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(so.currency, ''), %(base_currency)s) as name,
			sum(ifnull(so.grand_total, 0)) as currency_value,
			sum(ifnull(so.base_grand_total, 0)) as base_value,
			count(so.name) as order_count
		from `tabSales Order` so
		{where_clause}
		group by coalesce(nullif(so.currency, ''), %(base_currency)s)
		order by base_value desc
		limit 6
		""",
		{**params, "base_currency": _get_default_currency(company)},
		as_dict=True,
	)

	customer_rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(so.customer, ''), '') as customer,
			coalesce(
				nullif(max(so.customer_name), ''),
				nullif(so.customer, ''),
				'Unassigned'
			) as name,
			sum(ifnull(so.base_grand_total, 0)) as value,
			count(so.name) as order_count
		from `tabSales Order` so
		{where_clause}
		group by coalesce(nullif(so.customer, ''), '')
		order by value desc
		limit 5
		""",
		params,
		as_dict=True,
	)

	trend_map = {row.sort_key: row for row in trend_rows}
	yearly_trend = []
	for month_offset in range(12):
		month_start = get_first_day(add_months(trend_start, month_offset))
		month_key = month_start.strftime("%Y-%m")
		row = trend_map.get(month_key)
		yearly_trend.append(
			{
				"label": month_start.strftime("%b %Y"),
				"sort_key": month_key,
				"value": flt(row.value) if row else 0.0,
				"order_count": int((row.order_count if row else 0) or 0),
			}
		)

	return {
		"currency": _get_default_currency(company),
		"filters": {
			"from_date": str(trend_start),
			"to_date": str(to_date),
			"company": company,
		},
		"kpis": {
			"total_orders": int(kpi_row.total_orders or 0),
			"total_value": flt(kpi_row.total_value),
			"draft_value": flt(kpi_row.draft_value),
			"pending_value": flt(kpi_row.pending_value),
			"completed_value": flt(kpi_row.completed_value),
			"closed_value": flt(kpi_row.closed_value),
		},
		"yearly_trend": [
			row for row in yearly_trend
		],
		"status_pipeline": _ordered_status_pipeline(status_rows),
		"territory_breakdown": [
			{
				"name": row.name,
				"value": flt(row.value),
				"order_count": int(row.order_count or 0),
			}
			for row in territory_rows
		],
		"currency_breakdown": [
			{
				"name": row.name,
				"currency_value": flt(row.currency_value),
				"base_value": flt(row.base_value),
				"order_count": int(row.order_count or 0),
			}
			for row in currency_rows
		],
		"top_customers": [
			{
				"name": row.name,
				"customer": row.customer or None,
				"value": flt(row.value),
				"order_count": int(row.order_count or 0),
			}
			for row in customer_rows
		],
	}


# ── Sales Dashboard helpers ───────────────────────────────────────────────────

def _sd_exists(dt):
	try:
		return bool(frappe.db.exists("DocType", dt))
	except Exception:
		return False


def _sd_count(dt, filters=None):
	if not _sd_exists(dt):
		return 0
	try:
		return int(frappe.db.count(dt, filters=filters or {}) or 0)
	except Exception:
		return 0


def _sd_sql(q, p=None):
	try:
		return frappe.db.sql(q, p or [], as_dict=True)
	except Exception:
		return []


def _sd_f(v):
	try:
		return float(v or 0)
	except Exception:
		return 0.0


def _sd_mlabel(d):
	return d.strftime("%b %Y")


# ── Sales Dashboard main API ──────────────────────────────────────────────────

@frappe.whitelist()
def get_dashboard_data(from_date=None, to_date=None):
	today    = getdate(nowdate())
	end_date = getdate(to_date) if to_date else today
	cme      = get_last_day(end_date)
	cms      = get_first_day(end_date)

	# Build month buckets (from_date → to_date, max 12)
	if from_date:
		start_date = getdate(from_date)
		months, cur = [], get_first_day(start_date)
		while cur <= cms and len(months) < 12:
			months.append(cur)
			cur = add_months(cur, 1)
		if not months:
			months = [cms]
	else:
		months = [get_first_day(add_months(end_date, i)) for i in range(-5, 1)]

	six_start    = months[0]
	month_labels = [_sd_mlabel(ms) for ms in months]

	def _mk(d):
		return d.strftime("%Y-%m")

	# ── KPIs ─────────────────────────────────────────────────────────────────
	active_customers = _sd_count("Customer", {"disabled": 0})

	open_leads = 0
	if _sd_exists("Lead"):
		try:
			open_leads = int(frappe.db.count(
				"Lead",
				filters={"status": ["not in", ["Converted", "Do Not Contact", "Junk", "Lost Quotation"]]}
			) or 0)
		except Exception:
			pass

	open_opportunities = _sd_count("Opportunity", {"status": "Open"})

	open_quotations = 0
	if _sd_exists("Quotation"):
		try:
			open_quotations = int(frappe.db.count(
				"Quotation",
				filters={"status": ["not in", ["Ordered", "Cancelled", "Lost"]], "docstatus": ["<", 2]}
			) or 0)
		except Exception:
			pass

	sales_orders_period = _sd_count(
		"Sales Order",
		{"transaction_date": ["between", [six_start, cme]], "docstatus": 1}
	)

	pending_deliveries = 0
	if _sd_exists("Delivery Note"):
		try:
			pending_deliveries = int(frappe.db.count(
				"Delivery Note",
				filters={"status": ["not in", ["Closed", "Cancelled"]], "docstatus": 1}
			) or 0)
		except Exception:
			pass

	sales_invoices_period = _sd_count(
		"Sales Invoice",
		{"posting_date": ["between", [six_start, cme]], "docstatus": 1}
	)

	overdue_invoices = 0
	outstanding_amount = 0.0
	total_invoiced = 0.0
	if _sd_exists("Sales Invoice"):
		try:
			overdue_invoices = frappe.db.sql(
				"SELECT COUNT(*) FROM `tabSales Invoice` WHERE docstatus=1 AND outstanding_amount>0 AND due_date<%s",
				[today]
			)[0][0] or 0
			outstanding_amount = _sd_f(frappe.db.sql(
				"SELECT SUM(outstanding_amount) FROM `tabSales Invoice` WHERE docstatus=1 AND outstanding_amount>0"
			)[0][0])
			total_invoiced = _sd_f(frappe.db.sql(
				"SELECT SUM(grand_total) FROM `tabSales Invoice` WHERE docstatus=1 AND posting_date BETWEEN %s AND %s",
				[six_start, cme]
			)[0][0])
		except Exception:
			pass

	collected_period = 0.0
	payment_entries_period = 0
	if _sd_exists("Payment Entry"):
		try:
			collected_period = _sd_f(frappe.db.sql(
				"SELECT SUM(paid_amount) FROM `tabPayment Entry` WHERE payment_type='Receive' AND posting_date BETWEEN %s AND %s AND docstatus=1",
				[six_start, cme]
			)[0][0])
			payment_entries_period = int(frappe.db.sql(
				"SELECT COUNT(*) FROM `tabPayment Entry` WHERE payment_type='Receive' AND posting_date BETWEEN %s AND %s AND docstatus=1",
				[six_start, cme]
			)[0][0] or 0)
		except Exception:
			pass

	lost_leads_period = 0
	if _sd_exists("Lead"):
		try:
			lost_leads_period = int(frappe.db.count(
				"Lead",
				filters={"status": ["in", ["Lost Quotation", "Do Not Contact", "Junk"]], "modified": ["between", [six_start, cme]]}
			) or 0)
		except Exception:
			pass

	new_customers_period = _sd_count("Customer", {"creation": ["between", [six_start, cme]]})

	# ── CRM: Lead status distribution ────────────────────────────────────────
	lead_status_rows = _sd_sql("""
		SELECT COALESCE(NULLIF(status,''), 'Unknown') AS status, COUNT(*) AS cnt
		FROM `tabLead` WHERE creation BETWEEN %s AND %s AND docstatus < 2
		GROUP BY status ORDER BY cnt DESC LIMIT 8
	""", [six_start, cme])

	# Lead trend (6M)
	lead_trend_rows = _sd_sql("""
		SELECT DATE_FORMAT(creation,'%%Y-%%m') AS mk, COUNT(*) AS cnt
		FROM `tabLead` WHERE creation BETWEEN %s AND %s
		GROUP BY mk ORDER BY mk
	""", [six_start, cme])
	lead_trend_map   = {r.mk: int(r.cnt or 0) for r in lead_trend_rows}
	lead_trend_data  = [lead_trend_map.get(_mk(ms), 0) for ms in months]

	# Opportunities by status
	opp_rows = _sd_sql("""
		SELECT COALESCE(NULLIF(status,''), 'Unknown') AS status, COUNT(*) AS cnt
		FROM `tabOpportunity` WHERE creation BETWEEN %s AND %s AND docstatus < 2
		GROUP BY status ORDER BY cnt DESC LIMIT 8
	""", [six_start, cme])

	# ── Quotations ────────────────────────────────────────────────────────────
	quot_status_rows = _sd_sql("""
		SELECT COALESCE(NULLIF(status,''), 'Unknown') AS status, COUNT(*) AS cnt
		FROM `tabQuotation` WHERE transaction_date BETWEEN %s AND %s AND docstatus < 2
		GROUP BY status ORDER BY cnt DESC
	""", [six_start, cme])

	quot_trend_rows = _sd_sql("""
		SELECT DATE_FORMAT(transaction_date,'%%Y-%%m') AS mk, COUNT(*) AS cnt
		FROM `tabQuotation` WHERE transaction_date BETWEEN %s AND %s AND docstatus < 2
		GROUP BY mk ORDER BY mk
	""", [six_start, cme])
	quot_trend_map  = {r.mk: int(r.cnt or 0) for r in quot_trend_rows}
	quot_trend_data = [quot_trend_map.get(_mk(ms), 0) for ms in months]

	# ── Sales Orders ──────────────────────────────────────────────────────────
	so_status_rows = _sd_sql("""
		SELECT COALESCE(NULLIF(status,''), 'Unknown') AS status, COUNT(*) AS cnt
		FROM `tabSales Order` WHERE transaction_date BETWEEN %s AND %s AND docstatus < 2
		GROUP BY status ORDER BY cnt DESC
	""", [six_start, cme])

	so_trend_rows = _sd_sql("""
		SELECT DATE_FORMAT(transaction_date,'%%Y-%%m') AS mk,
		       SUM(grand_total) AS amt
		FROM `tabSales Order` WHERE transaction_date BETWEEN %s AND %s AND docstatus=1
		GROUP BY mk ORDER BY mk
	""", [six_start, cme])
	so_trend_map    = {r.mk: _sd_f(r.amt) for r in so_trend_rows}
	so_trend_amount = [round(so_trend_map.get(_mk(ms), 0), 2) for ms in months]

	so_customer_rows = _sd_sql("""
		SELECT COALESCE(NULLIF(customer_name, customer), customer) AS cust,
		       SUM(grand_total) AS amt
		FROM `tabSales Order`
		WHERE transaction_date BETWEEN %s AND %s AND docstatus=1
		GROUP BY customer ORDER BY amt DESC LIMIT 8
	""", [six_start, cme])

	# ── Delivery Notes ────────────────────────────────────────────────────────
	dn_status_rows = _sd_sql("""
		SELECT COALESCE(NULLIF(status,''), 'Unknown') AS status, COUNT(*) AS cnt
		FROM `tabDelivery Note` WHERE posting_date BETWEEN %s AND %s AND docstatus < 2
		GROUP BY status ORDER BY cnt DESC
	""", [six_start, cme])

	dn_trend_rows = _sd_sql("""
		SELECT DATE_FORMAT(posting_date,'%%Y-%%m') AS mk, COUNT(*) AS cnt
		FROM `tabDelivery Note` WHERE posting_date BETWEEN %s AND %s AND docstatus < 2
		GROUP BY mk ORDER BY mk
	""", [six_start, cme])
	dn_trend_map  = {r.mk: int(r.cnt or 0) for r in dn_trend_rows}
	dn_trend_data = [dn_trend_map.get(_mk(ms), 0) for ms in months]

	# ── Sales Invoices ────────────────────────────────────────────────────────
	si_status_rows = _sd_sql("""
		SELECT COALESCE(NULLIF(status,''), 'Unknown') AS status, COUNT(*) AS cnt
		FROM `tabSales Invoice` WHERE posting_date BETWEEN %s AND %s AND docstatus=1
		GROUP BY status ORDER BY cnt DESC
	""", [six_start, cme])

	si_trend_rows = _sd_sql("""
		SELECT DATE_FORMAT(posting_date,'%%Y-%%m') AS mk, SUM(grand_total) AS amt
		FROM `tabSales Invoice` WHERE posting_date BETWEEN %s AND %s AND docstatus=1
		GROUP BY mk ORDER BY mk
	""", [six_start, cme])
	si_trend_map    = {r.mk: _sd_f(r.amt) for r in si_trend_rows}
	si_trend_amount = [round(si_trend_map.get(_mk(ms), 0), 2) for ms in months]

	# ── Payment Entries (receipts trend) ──────────────────────────────────────
	pe_trend_rows = _sd_sql("""
		SELECT DATE_FORMAT(posting_date,'%%Y-%%m') AS mk, SUM(paid_amount) AS amt
		FROM `tabPayment Entry`
		WHERE payment_type='Receive' AND posting_date BETWEEN %s AND %s AND docstatus=1
		GROUP BY mk ORDER BY mk
	""", [six_start, cme])
	pe_trend_map    = {r.mk: _sd_f(r.amt) for r in pe_trend_rows}
	pe_trend_amount = [round(pe_trend_map.get(_mk(ms), 0), 2) for ms in months]

	# ── Performance: Top Customers by revenue ─────────────────────────────────
	top_customer_rows = _sd_sql("""
		SELECT COALESCE(NULLIF(customer_name, customer), customer) AS cust,
		       SUM(grand_total) AS amt
		FROM `tabSales Invoice`
		WHERE posting_date BETWEEN %s AND %s AND docstatus=1
		GROUP BY customer ORDER BY amt DESC LIMIT 10
	""", [six_start, cme])

	# ── Performance: Sales Person ─────────────────────────────────────────────
	sp_rows = _sd_sql("""
		SELECT sst.sales_person AS sp,
		       SUM(sst.allocated_amount) AS amt,
		       COUNT(DISTINCT si.name) AS cnt
		FROM `tabSales Invoice` si
		JOIN `tabSales Team` sst ON sst.parent = si.name AND sst.parenttype = 'Sales Invoice'
		WHERE si.posting_date BETWEEN %s AND %s AND si.docstatus = 1
		GROUP BY sst.sales_person ORDER BY amt DESC LIMIT 10
	""", [six_start, cme])

	# ── Performance: Territory ────────────────────────────────────────────────
	territory_rows = _sd_sql("""
		SELECT COALESCE(NULLIF(territory,''), 'Unassigned') AS territory,
		       SUM(grand_total) AS amt
		FROM `tabSales Invoice`
		WHERE posting_date BETWEEN %s AND %s AND docstatus=1
		GROUP BY territory ORDER BY amt DESC LIMIT 10
	""", [six_start, cme])

	# ─────────────────────────────────────────────────────────────────────────
	return {
		"generated_on": now_datetime().isoformat(),
		"period_label": "{} – {}".format(_sd_mlabel(months[0]), _sd_mlabel(months[-1])),
		"months": month_labels,

		"kpis": {
			"active_customers":       active_customers,
			"open_leads":             open_leads,
			"open_opportunities":     open_opportunities,
			"open_quotations":        open_quotations,
			"sales_orders_period":    sales_orders_period,
			"pending_deliveries":     pending_deliveries,
			"sales_invoices_period":  sales_invoices_period,
			"overdue_invoices":       overdue_invoices,
			"outstanding_amount":     round(outstanding_amount, 2),
			"collected_period":       round(collected_period, 2),
			"total_invoiced":         round(total_invoiced, 2),
			"payment_entries_period": payment_entries_period,
			"lost_leads_period":      lost_leads_period,
			"new_customers_period":   new_customers_period,
		},

		"crm": {
			"lead_status_labels": [r.status for r in lead_status_rows],
			"lead_status_counts": [int(r.cnt or 0) for r in lead_status_rows],
			"lead_trend":         lead_trend_data,
			"opp_labels":         [r.status for r in opp_rows],
			"opp_counts":         [int(r.cnt or 0) for r in opp_rows],
		},

		"quotation": {
			"status_labels": [r.status for r in quot_status_rows],
			"status_counts": [int(r.cnt or 0) for r in quot_status_rows],
			"trend":         quot_trend_data,
		},

		"sales_order": {
			"status_labels":    [r.status for r in so_status_rows],
			"status_counts":    [int(r.cnt or 0) for r in so_status_rows],
			"trend_amount":     so_trend_amount,
			"customer_labels":  [r.cust for r in so_customer_rows],
			"customer_amounts": [round(_sd_f(r.amt), 2) for r in so_customer_rows],
		},

		"delivery": {
			"status_labels": [r.status for r in dn_status_rows],
			"status_counts": [int(r.cnt or 0) for r in dn_status_rows],
			"trend":         dn_trend_data,
		},

		"invoice": {
			"status_labels": [r.status for r in si_status_rows],
			"status_counts": [int(r.cnt or 0) for r in si_status_rows],
			"trend_amount":  si_trend_amount,
		},

		"payment": {
			"trend_amount": pe_trend_amount,
		},

		"performance": {
			"customer_labels":   [r.cust for r in top_customer_rows],
			"customer_amounts":  [round(_sd_f(r.amt), 2) for r in top_customer_rows],
			"sp_labels":         [r.sp for r in sp_rows],
			"sp_amounts":        [round(_sd_f(r.amt), 2) for r in sp_rows],
			"sp_counts":         [int(r.cnt or 0) for r in sp_rows],
			"territory_labels":  [r.territory for r in territory_rows],
			"territory_amounts": [round(_sd_f(r.amt), 2) for r in territory_rows],
		},
	}
