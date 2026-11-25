# Copyright (c) 2026, SAH Exports and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


OPERATION_SOURCES = {
	"Cutting": {
		"parent": "Cutting Report",
		"child": "Cutting Report CT",
		"qty_field": "cutting_qty",
		"alias": "cr",
		"child_alias": "ct",
	},
	"Stitching": {
		"parent": "Stitching Report",
		"child": "Stitching Report CT",
		"qty_field": "stitching_qty",
		"alias": "sr",
		"child_alias": "ct",
	},
	"Packing": {
		"parent": "Packing Report",
		"child": "Packing Report CT",
		"qty_field": "packaging_qty",
		"alias": "pr",
		"child_alias": "ct",
	},
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_summary(data)
	return columns, data, None, chart, summary


def get_columns():
	return [
		{
			"label": _("Operation"),
			"fieldname": "operation",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Manufacturing Contractor",
			"width": 180,
		},
		{
			"label": _("Report"),
			"fieldname": "report_name",
			"fieldtype": "Dynamic Link",
			"options": "report_doctype",
			"width": 160,
		},
		{
			"label": _("Report DocType"),
			"fieldname": "report_doctype",
			"fieldtype": "Data",
			"hidden": 1,
			"width": 0,
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 105,
		},
		{
			"label": _("Order Sheet"),
			"fieldname": "order_sheet",
			"fieldtype": "Link",
			"options": "Order Sheet",
			"width": 160,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 160,
		},
		{
			"label": _("SO Item"),
			"fieldname": "so_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 200,
		},
		{
			"label": _("Combo Item"),
			"fieldname": "combo_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Article"),
			"fieldname": "article",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Finished Size"),
			"fieldname": "finished_size",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Planned Qty"),
			"fieldname": "planned_qty",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Done Qty"),
			"fieldname": "done_qty",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Balance Qty"),
			"fieldname": "balance_qty",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Progress %"),
			"fieldname": "progress_pct",
			"fieldtype": "Percent",
			"width": 100,
		},
	]


def get_selected_operations(filters):
	operation = (filters.get("operation") or "All").strip()
	if operation == "All" or not operation:
		return list(OPERATION_SOURCES.keys())
	if operation not in OPERATION_SOURCES:
		frappe.throw(_("Invalid operation: {0}").format(operation))
	return [operation]


def get_data(filters):
	rows = []
	for operation in get_selected_operations(filters):
		rows.extend(fetch_operation_rows(operation, filters))

	rows.sort(
		key=lambda r: (
			r.get("posting_date") or "",
			r.get("operation") or "",
			r.get("supplier") or "",
			r.get("report_name") or "",
			r.get("so_item") or "",
		),
		reverse=True,
	)
	return rows


def fetch_operation_rows(operation, filters):
	cfg = OPERATION_SOURCES[operation]
	parent = cfg["parent"]
	child = cfg["child"]
	qty_field = cfg["qty_field"]
	p = cfg["alias"]
	c = cfg["child_alias"]

	conditions = [f"{p}.docstatus = 1"]
	values = {}

	if filters.get("from_date"):
		conditions.append(f"{p}.date >= %(from_date)s")
		values["from_date"] = filters.get("from_date")
	if filters.get("to_date"):
		conditions.append(f"{p}.date <= %(to_date)s")
		values["to_date"] = filters.get("to_date")
	if filters.get("supplier"):
		conditions.append(f"{p}.supplier = %(supplier)s")
		values["supplier"] = filters.get("supplier")
	if filters.get("customer"):
		conditions.append(f"{p}.customer = %(customer)s")
		values["customer"] = filters.get("customer")
	if filters.get("order_sheet"):
		conditions.append(f"{p}.order_sheet = %(order_sheet)s")
		values["order_sheet"] = filters.get("order_sheet")
	if filters.get("so_item"):
		conditions.append(f"{c}.so_item = %(so_item)s")
		values["so_item"] = filters.get("so_item")

	where_clause = " AND ".join(conditions)

	raw = frappe.db.sql(
		f"""
		SELECT
			{p}.supplier AS supplier,
			{p}.name AS report_name,
			{p}.date AS posting_date,
			{p}.order_sheet AS order_sheet,
			{p}.customer AS customer,
			{c}.so_item AS so_item,
			{c}.combo_item AS combo_item,
			{c}.article AS article,
			{c}.finished_size AS finished_size,
			IFNULL({c}.planned_qty, 0) AS planned_qty,
			IFNULL({c}.{qty_field}, 0) AS done_qty
		FROM `tab{parent}` {p}
		LEFT JOIN `tab{child}` {c} ON {c}.parent = {p}.name
		WHERE {where_clause}
		ORDER BY {p}.date DESC, {p}.name, {c}.idx
		""",
		values,
		as_dict=True,
	)

	data = []
	for row in raw:
		planned = flt(row.get("planned_qty"))
		done = flt(row.get("done_qty"))
		data.append(
			{
				"operation": operation,
				"supplier": row.get("supplier"),
				"report_name": row.get("report_name"),
				"report_doctype": parent,
				"posting_date": row.get("posting_date"),
				"order_sheet": row.get("order_sheet"),
				"customer": row.get("customer"),
				"so_item": row.get("so_item"),
				"combo_item": row.get("combo_item"),
				"article": row.get("article"),
				"finished_size": row.get("finished_size"),
				"planned_qty": planned,
				"done_qty": done,
				"balance_qty": planned - done,
				"progress_pct": (done / planned * 100.0) if planned else 0.0,
			}
		)
	return data


def get_chart(data):
	totals = {"Cutting": 0.0, "Stitching": 0.0, "Packing": 0.0}
	for row in data:
		op = row.get("operation")
		if op in totals:
			totals[op] += flt(row.get("done_qty"))

	return {
		"data": {
			"labels": ["Cutting", "Stitching", "Packing"],
			"datasets": [
				{
					"name": _("Done Qty"),
					"values": [totals["Cutting"], totals["Stitching"], totals["Packing"]],
				}
			],
		},
		"type": "bar",
	}


def get_summary(data):
	planned = sum(flt(r.get("planned_qty")) for r in data)
	done = sum(flt(r.get("done_qty")) for r in data)
	return [
		{"label": _("Rows"), "value": len(data), "datatype": "Int"},
		{"label": _("Planned Qty"), "value": planned, "datatype": "Float"},
		{"label": _("Done Qty"), "value": done, "datatype": "Float"},
		{
			"label": _("Overall Progress %"),
			"value": (done / planned * 100.0) if planned else 0.0,
			"datatype": "Percent",
		},
	]
