import frappe
from frappe import _
from frappe.utils import flt

from manufacturing_addon.manufacturing_addon.page.subcontracting_order_history.subcontracting_order_history import (
	get_subcontracting_order_history,
)


def execute(filters=None):
	filters = filters or {}
	if not filters.get("subcontracting_order"):
		return get_columns(), []

	data = get_report_data(filters["subcontracting_order"])
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Section"), "fieldname": "section", "fieldtype": "Data", "width": 140},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Document Type"),
			"fieldname": "document_type",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Document"),
			"fieldname": "document",
			"fieldtype": "Dynamic Link",
			"options": "document_type",
			"width": 170,
		},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Data", "width": 220},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 260},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 70},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
	]


def get_report_data(subcontracting_order):
	history = get_subcontracting_order_history(subcontracting_order)
	rows = []

	header = history.get("header") or {}
	rows.append(
		_row(
			"Order Header",
			header.get("transaction_date"),
			"Subcontracting Order",
			header.get("name"),
			"",
			_("Supplier: {0} | Status: {1} | Received: {2}%").format(
				header.get("supplier_name") or header.get("supplier"),
				header.get("status"),
				flt(header.get("per_received"), 2),
			),
			header.get("total_qty"),
			"",
			"",
			header.get("total"),
			header.get("status"),
		)
	)

	for item in history.get("order_items") or []:
		rows.append(
			_row(
				"Finished Goods",
				header.get("transaction_date"),
				"Subcontracting Order",
				header.get("name"),
				item.get("item_code"),
				_("Ordered vs Received"),
				item.get("qty"),
				item.get("uom"),
				item.get("rate"),
				item.get("amount"),
				_("Received: {0}").format(flt(item.get("received_qty"), 2)),
			)
		)

	for item in history.get("supplied_items") or []:
		rows.append(
			_row(
				"Raw Material",
				header.get("transaction_date"),
				"Subcontracting Order",
				header.get("name"),
				item.get("rm_item_code"),
				_("FG: {0} | Req {1} / Sup {2} / Con {3}").format(
					item.get("main_item_code"),
					flt(item.get("required_qty"), 2),
					flt(item.get("supplied_qty"), 2),
					flt(item.get("consumed_qty"), 2),
				),
				item.get("required_qty"),
				item.get("stock_uom"),
				item.get("rate"),
				item.get("amount"),
				_("Pending: {0}").format(flt(item.get("pending_qty"), 2)),
			)
		)

	for entry in history.get("stock_entries") or []:
		for item in entry.get("items") or []:
			rows.append(
				_row(
					"Material Transfer",
					entry.get("posting_date"),
					"Stock Entry",
					entry.get("name"),
					item.get("item_code"),
					_("To FG: {0} | {1}").format(
						item.get("subcontracted_item") or "",
						entry.get("purpose") or entry.get("stock_entry_type"),
					),
					item.get("qty"),
					item.get("uom"),
					item.get("basic_rate"),
					item.get("amount"),
					entry.get("docstatus_label"),
				)
			)

	for receipt in history.get("receipts") or []:
		for item in receipt.get("items") or []:
			rows.append(
				_row(
					"Receipt",
					receipt.get("posting_date"),
					"Subcontracting Receipt",
					receipt.get("name"),
					item.get("item_code"),
					_("Subcontracting Receipt"),
					item.get("received_qty") or item.get("qty"),
					item.get("stock_uom"),
					item.get("rate"),
					item.get("amount"),
					receipt.get("docstatus_label"),
				)
			)

	for invoice in history.get("purchase_invoices") or []:
		for item in invoice.get("items") or []:
			rows.append(
				_row(
					"Purchase Invoice",
					invoice.get("posting_date"),
					"Purchase Invoice",
					invoice.get("name"),
					item.get("item_code"),
					_("Bill: {0}").format(invoice.get("bill_no") or invoice.get("name")),
					item.get("qty"),
					item.get("uom"),
					item.get("rate"),
					item.get("amount"),
					invoice.get("status") or invoice.get("docstatus_label"),
				)
			)

	for event in history.get("timeline") or []:
		rows.append(
			_row(
				"Timeline",
				event.get("date"),
				event.get("document_type"),
				event.get("document"),
				"",
				event.get("description"),
				event.get("qty"),
				"",
				"",
				event.get("amount"),
				event.get("status"),
			)
		)

	return rows


def _row(section, date, document_type, document, item_code, description, qty, uom, rate, amount, status):
	return {
		"section": section,
		"date": date,
		"document_type": document_type,
		"document": document,
		"item_code": item_code,
		"description": description,
		"qty": flt(qty) or None,
		"uom": uom,
		"rate": flt(rate) or None,
		"amount": flt(amount) or None,
		"status": status,
	}
