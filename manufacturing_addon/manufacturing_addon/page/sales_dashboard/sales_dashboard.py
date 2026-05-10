import calendar
import json
from collections import defaultdict
from datetime import date, datetime, timedelta

import frappe
from frappe.utils import cint, flt, getdate, nowdate


@frappe.whitelist()
def get_dashboard_data(filters=None):
	filters = _coerce_filters(filters)
	from_date = getdate(filters["from_date"])
	to_date = getdate(filters["to_date"])
	if from_date > to_date:
		from_date, to_date = to_date, from_date
		filters["from_date"], filters["to_date"] = from_date, to_date

	currency = _get_currency(filters.get("company"))
	sales_invoice_where, sales_invoice_params = _build_sales_invoice_where(filters, from_date, to_date)
	sales_order_where, sales_order_params = _build_sales_order_where(filters, from_date, to_date)
	quotation_where, quotation_params = _build_quotation_where(filters, from_date, to_date)

	invoice_metrics = frappe.db.sql(
		f"""
		select
			sum(case when ifnull(si.is_return, 0) = 0 then si.base_grand_total else 0 end) as total_sales,
			sum(case when ifnull(si.is_return, 0) = 0 then si.base_net_total else 0 end) as net_sales_before_returns,
			sum(case when ifnull(si.is_return, 0) = 1 then abs(si.base_net_total) else 0 end) as return_amount,
			sum(case when ifnull(si.is_return, 0) = 1 then abs(si.base_grand_total) else 0 end) as return_gross_amount,
			count(distinct case when ifnull(si.is_return, 0) = 0 then si.name end) as total_orders,
			count(distinct case when ifnull(si.is_return, 0) = 0 then si.customer end) as customers_with_sales,
			sum(case when ifnull(si.outstanding_amount, 0) > 0 then ifnull(si.outstanding_amount, 0) * ifnull(si.conversion_rate, 1) else 0 end) as outstanding_amount,
			sum(
				case
					when ifnull(si.outstanding_amount, 0) > 0 and si.due_date < curdate()
					then ifnull(si.outstanding_amount, 0) * ifnull(si.conversion_rate, 1)
					else 0
				end
			) as overdue_amount
		from `tabSales Invoice` si
		{sales_invoice_where}
		""",
		sales_invoice_params,
		as_dict=True,
	)[0]

	gross_profit_row = frappe.db.sql(
		f"""
		select
			sum(
				case
					when ifnull(si.is_return, 0) = 1 then -1 * abs(ifnull(sii.base_net_amount, 0))
					else ifnull(sii.base_net_amount, 0)
				end
			) as net_sales_items,
			sum(
				case
					when ifnull(si.is_return, 0) = 1 then -1 * abs(ifnull(sii.base_net_amount, 0) - (ifnull(sii.incoming_rate, 0) * ifnull(sii.stock_qty, 0)))
					else ifnull(sii.base_net_amount, 0) - (ifnull(sii.incoming_rate, 0) * ifnull(sii.stock_qty, 0))
				end
			) as gross_profit
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		{sales_invoice_where}
		""",
		sales_invoice_params,
		as_dict=True,
	)[0]

	total_sales = flt(invoice_metrics.total_sales)
	return_amount = flt(invoice_metrics.return_amount)
	net_sales = flt(invoice_metrics.net_sales_before_returns) - return_amount
	gross_profit = flt(gross_profit_row.gross_profit)
	total_orders = cint(invoice_metrics.total_orders)
	order_fallback = _get_sales_order_metrics(sales_order_where, sales_order_params)
	use_sales_order_fallback = not total_sales and cint(order_fallback.get("total_orders"))
	if use_sales_order_fallback:
		total_sales = flt(order_fallback.get("total_sales"))
		net_sales = flt(order_fallback.get("net_sales"))
		total_orders = cint(order_fallback.get("total_orders"))
		gross_profit = 0
	total_customers = _get_total_customers(filters)
	new_customers = _get_new_customers(filters, from_date, to_date)
	outstanding_amount = flt(invoice_metrics.outstanding_amount)
	overdue_amount = flt(invoice_metrics.overdue_amount)
	average_order_value = total_sales / total_orders if total_orders else 0
	gross_profit_pct = (gross_profit / net_sales * 100) if net_sales else 0

	trend = _get_sales_trend(filters, from_date, to_date, sales_invoice_where, sales_invoice_params)
	top_customers = _get_top_customers(sales_invoice_where, sales_invoice_params)
	top_items = _get_top_items(sales_invoice_where, sales_invoice_params)
	sales_people = _get_sales_people(sales_invoice_where, sales_invoice_params)
	if not sales_people.get("labels"):
		sales_people = _get_sales_people_fallback_from_invoices(sales_invoice_where, sales_invoice_params)
	payment_status = _get_payment_status(sales_invoice_where, sales_invoice_params)
	sales_order_status = _get_sales_order_status(sales_order_where, sales_order_params)
	territory_sales = _get_territory_sales(sales_invoice_where, sales_invoice_params)
	currency_wise_sales = _get_currency_wise_sales(sales_invoice_where, sales_invoice_params)
	customer_group_sales = _get_customer_group_sales(sales_invoice_where, sales_invoice_params)
	commission_agents = _get_commission_agent_sales(sales_invoice_where, sales_invoice_params)
	financial_snapshot = _get_financial_snapshot(total_sales, net_sales, gross_profit, outstanding_amount, overdue_amount, flt(invoice_metrics.return_gross_amount), target_total=0, pipeline_value=0)
	if use_sales_order_fallback:
		trend = _get_sales_order_trend(sales_order_where, sales_order_params, from_date, to_date)
		top_customers = _get_top_customers_from_sales_orders(sales_order_where, sales_order_params)
		top_items = _get_top_items_from_sales_orders(sales_order_where, sales_order_params)
		sales_people = _get_sales_people_from_sales_orders(sales_order_where, sales_order_params)
		if not sales_people.get("labels"):
			sales_people = _get_sales_people_fallback_from_orders(sales_order_where, sales_order_params)
		territory_sales = _get_territory_sales_from_sales_orders(sales_order_where, sales_order_params)
		currency_wise_sales = _get_currency_wise_sales_from_sales_orders(sales_order_where, sales_order_params)
		customer_group_sales = _get_customer_group_sales_from_sales_orders(sales_order_where, sales_order_params)
	quotation_stats = _get_quotation_stats(quotation_where, quotation_params)

	month_starts = _month_starts_between(from_date, to_date)
	actual_monthly = _get_monthly_actuals(filters, from_date, to_date)
	target_monthly = _get_monthly_targets(filters, month_starts)
	target_total = sum(target_monthly.values())
	actual_total = sum(actual_monthly.values())
	target_achievement_pct = (actual_total / target_total * 100) if target_total else 0
	financial_snapshot = _get_financial_snapshot(
		total_sales=total_sales,
		net_sales=net_sales,
		gross_profit=gross_profit,
		outstanding_amount=outstanding_amount,
		overdue_amount=overdue_amount,
		return_amount=flt(invoice_metrics.return_gross_amount),
		target_total=target_total,
		pipeline_value=flt(quotation_stats["sales_pipeline_value"]),
	)

	return {
		"currency": currency,
		"filters": {
			**filters,
			"from_date": str(from_date),
			"to_date": str(to_date),
		},
		"kpis": {
			"total_sales": total_sales,
			"net_sales": net_sales,
			"gross_profit": gross_profit,
			"gross_profit_pct": gross_profit_pct,
			"total_orders": total_orders,
			"average_order_value": average_order_value,
			"total_customers": total_customers,
			"new_customers": new_customers,
			"outstanding_amount": outstanding_amount,
			"overdue_amount": overdue_amount,
			"sales_return_amount": flt(invoice_metrics.return_gross_amount),
			"target_achievement_pct": target_achievement_pct,
			"sales_target": target_total,
			"quotation_value": flt(quotation_stats["quotation_value"]),
			"pending_quotation_amount": flt(quotation_stats["pending_quotation_amount"]),
			"conversion_rate": flt(quotation_stats["conversion_rate"]),
			"sales_pipeline_value": flt(quotation_stats["sales_pipeline_value"]),
		},
		"charts": {
			"sales_trend": trend,
			"target_vs_actual": {
				"labels": [d.strftime("%b %Y") for d in month_starts],
				"target": [flt(target_monthly.get(d.strftime("%Y-%m"), 0)) for d in month_starts],
				"actual": [flt(actual_monthly.get(d.strftime("%Y-%m"), 0)) for d in month_starts],
			},
			"top_customers": top_customers,
			"top_items": top_items,
			"sales_people": sales_people,
			"payment_status": payment_status,
			"sales_order_status": sales_order_status,
			"territory_sales": territory_sales,
			"currency_wise_sales": currency_wise_sales,
			"customer_group_sales": customer_group_sales,
			"commission_agents": commission_agents,
			"financial_snapshot": financial_snapshot,
		},
		"data_source": "Sales Order" if use_sales_order_fallback else "Sales Invoice",
	}


def _coerce_filters(filters):
	if isinstance(filters, str):
		filters = json.loads(filters)
	filters = filters or {}
	today = getdate(nowdate())
	first_day = today.replace(day=1)
	return {
		"from_date": filters.get("from_date") or first_day,
		"to_date": filters.get("to_date") or today,
		"company": filters.get("company"),
		"sales_person": filters.get("sales_person"),
		"customer": filters.get("customer"),
		"item_group": filters.get("item_group"),
		"territory": filters.get("territory"),
		"customer_group": filters.get("customer_group"),
		"payment_status": filters.get("payment_status"),
	}


def _get_currency(company):
	if company:
		currency = frappe.db.get_value("Company", company, "default_currency")
		if currency:
			return currency
	default_company = frappe.defaults.get_defaults().get("company")
	if default_company:
		return frappe.db.get_value("Company", default_company, "default_currency")
	return frappe.db.get_single_value("Global Defaults", "default_currency") or "USD"


def _build_sales_invoice_where(filters, from_date, to_date):
	conditions = ["where si.docstatus = 1", "and si.posting_date between %s and %s"]
	params = [from_date, to_date]

	if filters.get("company"):
		conditions.append("and si.company = %s")
		params.append(filters["company"])
	if filters.get("customer"):
		conditions.append("and si.customer = %s")
		params.append(filters["customer"])
	if filters.get("territory"):
		conditions.append("and si.territory = %s")
		params.append(filters["territory"])
	if filters.get("customer_group"):
		conditions.append("and si.customer_group = %s")
		params.append(filters["customer_group"])
	if filters.get("sales_person"):
		conditions.append(
			"""and exists(
				select 1 from `tabSales Team` st
				where st.parent = si.name
					and st.parenttype = 'Sales Invoice'
					and st.sales_person = %s
			)"""
		)
		params.append(filters["sales_person"])
	if filters.get("item_group"):
		conditions.append(
			"""and exists(
				select 1 from `tabSales Invoice Item` sii2
				where sii2.parent = si.name
					and sii2.item_group = %s
			)"""
		)
		params.append(filters["item_group"])
	if filters.get("payment_status"):
		conditions.append(f"and {_payment_status_condition(filters['payment_status'])}")

	return "\n".join(conditions), params


def _build_sales_order_where(filters, from_date, to_date):
	conditions = ["where so.docstatus < 2", "and so.transaction_date between %s and %s"]
	params = [from_date, to_date]
	if filters.get("company"):
		conditions.append("and so.company = %s")
		params.append(filters["company"])
	if filters.get("customer"):
		conditions.append("and so.customer = %s")
		params.append(filters["customer"])
	if filters.get("territory"):
		conditions.append("and so.territory = %s")
		params.append(filters["territory"])
	if filters.get("customer_group"):
		conditions.append("and so.customer_group = %s")
		params.append(filters["customer_group"])
	if filters.get("sales_person"):
		conditions.append(
			"""and exists(
				select 1 from `tabSales Team` st
				where st.parent = so.name
					and st.parenttype = 'Sales Order'
					and st.sales_person = %s
			)"""
		)
		params.append(filters["sales_person"])
	if filters.get("item_group"):
		conditions.append(
			"""and exists(
				select 1 from `tabSales Order Item` soi
				where soi.parent = so.name
					and soi.item_group = %s
			)"""
		)
		params.append(filters["item_group"])
	return "\n".join(conditions), params


def _build_quotation_where(filters, from_date, to_date):
	conditions = ["where q.docstatus < 2", "and q.transaction_date between %s and %s"]
	params = [from_date, to_date]
	if filters.get("company"):
		conditions.append("and q.company = %s")
		params.append(filters["company"])
	if filters.get("customer"):
		conditions.append("and q.party_name = %s")
		params.append(filters["customer"])
	if filters.get("territory"):
		conditions.append("and q.territory = %s")
		params.append(filters["territory"])
	if filters.get("customer_group"):
		conditions.append("and q.customer_group = %s")
		params.append(filters["customer_group"])
	if filters.get("item_group"):
		conditions.append(
			"""and exists(
				select 1 from `tabQuotation Item` qi
				where qi.parent = q.name
					and qi.item_group = %s
			)"""
		)
		params.append(filters["item_group"])
	return "\n".join(conditions), params


def _payment_status_condition(payment_status):
	mapping = {
		"Paid": "ifnull(si.outstanding_amount, 0) <= 0",
		"Overdue": "ifnull(si.outstanding_amount, 0) > 0 and si.due_date < curdate()",
		"Partially Paid": "ifnull(si.outstanding_amount, 0) > 0 and ifnull(si.outstanding_amount, 0) < ifnull(si.grand_total, 0) and si.due_date >= curdate()",
		"Unpaid": "ifnull(si.outstanding_amount, 0) >= ifnull(si.grand_total, 0) and si.due_date >= curdate()",
	}
	return mapping.get(payment_status, "1=1")


def _get_total_customers(filters):
	conditions = ["disabled = 0"]
	params = []
	if filters.get("customer_group"):
		conditions.append("customer_group = %s")
		params.append(filters["customer_group"])
	if filters.get("territory"):
		conditions.append("territory = %s")
		params.append(filters["territory"])
	if filters.get("customer"):
		conditions.append("name = %s")
		params.append(filters["customer"])

	return cint(
		frappe.db.sql(
			f"select count(name) from `tabCustomer` where {' and '.join(conditions)}",
			params,
		)[0][0]
		or 0
	)


def _get_new_customers(filters, from_date, to_date):
	conditions = ["disabled = 0", "date(creation) between %s and %s"]
	params = [from_date, to_date]
	if filters.get("customer_group"):
		conditions.append("customer_group = %s")
		params.append(filters["customer_group"])
	if filters.get("territory"):
		conditions.append("territory = %s")
		params.append(filters["territory"])
	if filters.get("customer"):
		conditions.append("name = %s")
		params.append(filters["customer"])

	return cint(
		frappe.db.sql(
			f"select count(name) from `tabCustomer` where {' and '.join(conditions)}",
			params,
		)[0][0]
		or 0
	)


def _get_sales_trend(filters, from_date, to_date, where_clause, params):
	group_daily = (to_date - from_date).days <= 45
	label_expr = "date_format(si.posting_date, '%%Y-%%m-%%d')" if group_daily else "date_format(si.posting_date, '%%Y-%%m')"
	rows = frappe.db.sql(
		f"""
		select
			{label_expr} as bucket,
			sum(case when ifnull(si.is_return, 0) = 1 then -1 * abs(si.base_net_total) else si.base_net_total end) as amount
		from `tabSales Invoice` si
		{where_clause}
		group by bucket
		order by bucket
		""",
		params,
		as_dict=True,
	)
	return {
		"labels": [row.bucket for row in rows],
		"values": [flt(row.amount) for row in rows],
		"mode": "daily" if group_daily else "monthly",
	}


def _get_sales_order_metrics(where_clause, params):
	row = frappe.db.sql(
		f"""
		select
			sum(ifnull(so.base_grand_total, 0)) as total_sales,
			sum(ifnull(so.base_net_total, 0)) as net_sales,
			count(distinct so.name) as total_orders
		from `tabSales Order` so
		{where_clause}
			and so.docstatus = 1
		""",
		params,
		as_dict=True,
	)[0]
	return row or {}


def _get_sales_order_trend(where_clause, params, from_date, to_date):
	group_daily = (to_date - from_date).days <= 45
	label_expr = "date_format(so.transaction_date, '%%Y-%%m-%%d')" if group_daily else "date_format(so.transaction_date, '%%Y-%%m')"
	rows = frappe.db.sql(
		f"""
		select
			{label_expr} as bucket,
			sum(ifnull(so.base_net_total, 0)) as amount
		from `tabSales Order` so
		{where_clause}
			and so.docstatus = 1
		group by bucket
		order by bucket
		""",
		params,
		as_dict=True,
	)
	return {
		"labels": [row.bucket for row in rows],
		"values": [flt(row.amount) for row in rows],
		"mode": "daily" if group_daily else "monthly",
	}


def _get_top_customers(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			si.customer as label,
			sum(case when ifnull(si.is_return, 0) = 1 then -1 * abs(si.base_net_total) else si.base_net_total end) as value
		from `tabSales Invoice` si
		{where_clause}
		group by si.customer
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_top_customers_from_sales_orders(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			so.customer as label,
			sum(ifnull(so.base_net_total, 0)) as value
		from `tabSales Order` so
		{where_clause}
			and so.docstatus = 1
		group by so.customer
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_top_items(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			sii.item_code as label,
			sum(case when ifnull(si.is_return, 0) = 1 then -1 * abs(ifnull(sii.qty, 0)) else ifnull(sii.qty, 0) end) as qty,
			sum(case when ifnull(si.is_return, 0) = 1 then -1 * abs(ifnull(sii.base_net_amount, 0)) else ifnull(sii.base_net_amount, 0) end) as value
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		{where_clause}
		group by sii.item_code
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return {
		"labels": [row.label for row in rows],
		"values": [flt(row.value) for row in rows],
		"quantities": [flt(row.qty) for row in rows],
	}


def _get_top_items_from_sales_orders(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			soi.item_code as label,
			sum(ifnull(soi.qty, 0)) as qty,
			sum(ifnull(soi.base_net_amount, 0)) as value
		from `tabSales Order Item` soi
		inner join `tabSales Order` so on so.name = soi.parent
		{where_clause}
			and so.docstatus = 1
		group by soi.item_code
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return {
		"labels": [row.label for row in rows],
		"values": [flt(row.value) for row in rows],
		"quantities": [flt(row.qty) for row in rows],
	}


def _get_sales_people(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			st.sales_person as label,
			sum(
				(case when ifnull(si.is_return, 0) = 1 then -1 else 1 end)
				* ifnull(si.base_net_total, 0)
				* ifnull(st.allocated_percentage, 100) / 100
			) as value
		from `tabSales Team` st
		inner join `tabSales Invoice` si on si.name = st.parent and st.parenttype = 'Sales Invoice'
		{where_clause}
		group by st.sales_person
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_sales_people_from_sales_orders(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			st.sales_person as label,
			sum(ifnull(so.base_net_total, 0) * ifnull(st.allocated_percentage, 100) / 100) as value
		from `tabSales Team` st
		inner join `tabSales Order` so on so.name = st.parent and st.parenttype = 'Sales Order'
		{where_clause}
			and so.docstatus = 1
		group by st.sales_person
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_sales_people_fallback_from_invoices(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(si.owner, ''), 'Unassigned') as label,
			sum(case when ifnull(si.is_return, 0) = 1 then -1 * abs(ifnull(si.base_net_total, 0)) else ifnull(si.base_net_total, 0) end) as value
		from `tabSales Invoice` si
		{where_clause}
		group by label
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_sales_people_fallback_from_orders(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(so.owner, ''), 'Unassigned') as label,
			sum(ifnull(so.base_net_total, 0)) as value
		from `tabSales Order` so
		{where_clause}
			and so.docstatus = 1
		group by label
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_payment_status(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			case
				when ifnull(si.outstanding_amount, 0) <= 0 then 'Paid'
				when ifnull(si.outstanding_amount, 0) > 0 and si.due_date < curdate() then 'Overdue'
				when ifnull(si.outstanding_amount, 0) < ifnull(si.grand_total, 0) then 'Partially Paid'
				else 'Unpaid'
			end as label,
			count(*) as value
		from `tabSales Invoice` si
		{where_clause}
		group by label
		order by value desc
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_sales_order_status(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			coalesce(so.status, 'Draft') as label,
			count(*) as value
		from `tabSales Order` so
		{where_clause}
		group by so.status
		order by value desc
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_territory_sales(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(si.territory, ''), 'Unassigned') as label,
			sum(case when ifnull(si.is_return, 0) = 1 then -1 * abs(si.base_net_total) else si.base_net_total end) as value
		from `tabSales Invoice` si
		{where_clause}
		group by label
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_territory_sales_from_sales_orders(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(so.territory, ''), 'Unassigned') as label,
			sum(ifnull(so.base_net_total, 0)) as value
		from `tabSales Order` so
		{where_clause}
			and so.docstatus = 1
		group by label
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_currency_wise_sales(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(si.currency, ''), 'Unspecified') as label,
			sum(case when ifnull(si.is_return, 0) = 1 then -1 * abs(ifnull(si.net_total, 0)) else ifnull(si.net_total, 0) end) as value
		from `tabSales Invoice` si
		{where_clause}
		group by label
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_currency_wise_sales_from_sales_orders(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(so.currency, ''), 'Unspecified') as label,
			sum(ifnull(so.net_total, 0)) as value
		from `tabSales Order` so
		{where_clause}
			and so.docstatus = 1
		group by label
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_customer_group_sales(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(si.customer_group, ''), 'Unassigned') as label,
			sum(case when ifnull(si.is_return, 0) = 1 then -1 * abs(si.base_net_total) else si.base_net_total end) as value
		from `tabSales Invoice` si
		{where_clause}
		group by label
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_customer_group_sales_from_sales_orders(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(so.customer_group, ''), 'Unassigned') as label,
			sum(ifnull(so.base_net_total, 0)) as value
		from `tabSales Order` so
		{where_clause}
			and so.docstatus = 1
		group by label
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_commission_agent_sales(where_clause, params):
	rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(sio.supplier, ''), 'Unassigned') as label,
			sum(ifnull(sio.base_amount, 0)) as value
		from `tabSales Invoice Overheads` sio
		inner join `tabSales Invoice` si on si.name = sio.parent
		{where_clause}
		group by label
		having sum(ifnull(sio.base_amount, 0)) <> 0
		order by value desc
		limit 10
		""",
		params,
		as_dict=True,
	)
	return _chart_payload(rows)


def _get_financial_snapshot(total_sales, net_sales, gross_profit, outstanding_amount, overdue_amount, return_amount, target_total, pipeline_value):
	rows = [
		frappe._dict(label="Total Sales", value=flt(total_sales)),
		frappe._dict(label="Net Sales", value=flt(net_sales)),
		frappe._dict(label="Gross Profit", value=flt(gross_profit)),
		frappe._dict(label="Outstanding", value=flt(outstanding_amount)),
		frappe._dict(label="Overdue", value=flt(overdue_amount)),
		frappe._dict(label="Returns", value=flt(return_amount)),
		frappe._dict(label="Target", value=flt(target_total)),
		frappe._dict(label="Pipeline", value=flt(pipeline_value)),
	]
	return _chart_payload(rows)


def _get_quotation_stats(where_clause, params):
	row = frappe.db.sql(
		f"""
		select
			sum(case when q.docstatus = 1 then q.base_grand_total else 0 end) as quotation_value,
			sum(case when q.docstatus = 0 then q.base_grand_total else 0 end) as pending_quotation_amount,
			sum(case when q.status not in ('Lost', 'Ordered') then q.base_grand_total else 0 end) as sales_pipeline_value,
			count(case when q.docstatus < 2 then 1 end) as quotation_count,
			sum(case when q.status = 'Ordered' then 1 else 0 end) as converted_count
		from `tabQuotation` q
		{where_clause}
		""",
		params,
		as_dict=True,
	)[0]
	quotation_count = cint(row.quotation_count)
	converted_count = cint(row.converted_count)
	row["conversion_rate"] = (converted_count / quotation_count * 100) if quotation_count else 0
	return row


def _get_monthly_actuals(filters, from_date, to_date):
	where_clause, params = _build_sales_invoice_where(filters, from_date, to_date)
	rows = frappe.db.sql(
		f"""
		select
			date_format(si.posting_date, '%%Y-%%m') as bucket,
			sum(case when ifnull(si.is_return, 0) = 1 then -1 * abs(si.base_net_total) else si.base_net_total end) as value
		from `tabSales Invoice` si
		{where_clause}
		group by bucket
		order by bucket
		""",
		params,
		as_dict=True,
	)
	return {row.bucket: flt(row.value) for row in rows}


def _get_monthly_targets(filters, month_starts):
	if not month_starts:
		return {}

	target_rows = frappe.db.sql(
		"""
		select
			sp.name as sales_person,
			td.fiscal_year,
			td.target_amount,
			td.distribution_id,
			td.item_group
		from `tabSales Person` sp
		inner join `tabTarget Detail` td on td.parent = sp.name and td.parenttype = 'Sales Person'
		where 1 = 1
			{sales_person_condition}
			{item_group_condition}
		""".format(
			sales_person_condition="and sp.name = %(sales_person)s" if filters.get("sales_person") else "",
			item_group_condition="and td.item_group = %(item_group)s" if filters.get("item_group") else "",
		),
		{k: v for k, v in filters.items() if v},
		as_dict=True,
	)
	if not target_rows:
		return {}

	fiscal_years = {
		row.name: row
		for row in frappe.get_all(
			"Fiscal Year",
			fields=["name", "year_start_date", "year_end_date"],
		)
	}
	distribution_ids = sorted({row.distribution_id for row in target_rows if row.distribution_id})
	distribution_map = defaultdict(dict)
	if distribution_ids:
		for row in frappe.get_all(
			"Monthly Distribution Percentage",
			filters={"parent": ["in", distribution_ids]},
			fields=["parent", "month", "percentage_allocation"],
		):
			distribution_map[row.parent][row.month] = flt(row.percentage_allocation)

	monthly_targets = defaultdict(float)
	for month_start in month_starts:
		month_key = month_start.strftime("%Y-%m")
		month_name = month_start.strftime("%B")
		for target in target_rows:
			fiscal_year = fiscal_years.get(target.fiscal_year)
			if not fiscal_year:
				continue
			if not (getdate(fiscal_year.year_start_date) <= month_start <= getdate(fiscal_year.year_end_date)):
				continue
			allocation = distribution_map.get(target.distribution_id, {}).get(month_name, 0)
			monthly_targets[month_key] += flt(target.target_amount) * allocation / 100

	return monthly_targets


def _month_starts_between(from_date, to_date):
	current = date(from_date.year, from_date.month, 1)
	end = date(to_date.year, to_date.month, 1)
	out = []
	while current <= end:
		out.append(current)
		if current.month == 12:
			current = date(current.year + 1, 1, 1)
		else:
			current = date(current.year, current.month + 1, 1)
	return out


def _chart_payload(rows):
	return {
		"labels": [row.label for row in rows],
		"values": [flt(row.value) for row in rows],
	}
