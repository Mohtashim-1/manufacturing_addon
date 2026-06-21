# Copyright (c) 2026, Manufacturing Addon and contributors

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate


@frappe.whitelist()
def get_subcontracting_order_history(subcontracting_order):
	if not subcontracting_order:
		frappe.throw(_("Subcontracting Order is required"))

	if not frappe.db.exists("Subcontracting Order", subcontracting_order):
		frappe.throw(_("Subcontracting Order {0} does not exist").format(subcontracting_order))

	sco = frappe.get_doc("Subcontracting Order", subcontracting_order)
	header = _get_header(sco)
	purchase_order = _get_purchase_order(sco.purchase_order)
	order_items = _get_order_items(sco)
	service_items = _get_service_items(sco)
	supplied_items = _get_supplied_items(sco)
	stock_entries = _get_stock_entries(subcontracting_order)
	receipts = _get_subcontracting_receipts(subcontracting_order)
	purchase_invoices = _get_purchase_invoices(sco.purchase_order)
	timeline = _build_timeline(header, purchase_order, stock_entries, receipts, purchase_invoices)
	summary = _get_summary(order_items, supplied_items, stock_entries, receipts, header)
	supplied_by_fg = _group_supplied_by_fg(supplied_items)

	return {
		"header": header,
		"purchase_order": purchase_order,
		"order_items": order_items,
		"service_items": service_items,
		"supplied_items": supplied_items,
		"supplied_by_fg": supplied_by_fg,
		"stock_entries": stock_entries,
		"receipts": receipts,
		"purchase_invoices": purchase_invoices,
		"timeline": timeline,
		"summary": summary,
	}


def _get_header(sco):
	return {
		"name": sco.name,
		"supplier": sco.supplier,
		"supplier_name": sco.supplier_name,
		"purchase_order": sco.purchase_order,
		"company": sco.company,
		"transaction_date": sco.transaction_date,
		"schedule_date": sco.schedule_date,
		"status": sco.status,
		"docstatus": sco.docstatus,
		"per_received": flt(sco.per_received, 2),
		"total_qty": flt(sco.total_qty, 2),
		"total": flt(sco.total, 2),
		"set_warehouse": sco.set_warehouse,
		"supplier_warehouse": sco.supplier_warehouse,
		"owner": sco.owner,
		"creation": sco.creation,
		"modified": sco.modified,
	}


def _get_purchase_order(purchase_order):
	if not purchase_order:
		return None

	po = frappe.db.get_value(
		"Purchase Order",
		purchase_order,
		[
			"name",
			"supplier",
			"supplier_name",
			"transaction_date",
			"status",
			"docstatus",
			"grand_total",
			"per_received",
			"per_billed",
			"currency",
		],
		as_dict=True,
	)
	return po


def _get_order_items(sco):
	rows = []
	for row in sco.items or []:
		qty = flt(row.qty)
		received = flt(row.received_qty)
		pending = max(qty - received, 0)
		pct = flt(received / qty * 100, 2) if qty else 0
		rows.append(
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": qty,
				"received_qty": received,
				"pending_qty": pending,
				"received_pct": pct,
				"status": _fg_status(qty, received),
				"uom": row.stock_uom or getattr(row, "uom", None),
				"rate": flt(row.rate),
				"amount": flt(row.amount),
				"bom": row.bom,
				"warehouse": row.warehouse,
				"schedule_date": row.schedule_date,
			}
		)
	return rows


def _get_service_items(sco):
	rows = []
	for row in sco.service_items or []:
		rows.append(
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": flt(row.qty),
				"fg_item_qty": flt(row.fg_item_qty),
				"fg_item": getattr(row, "fg_item", None),
				"uom": frappe.db.get_value("Item", row.item_code, "stock_uom") if row.item_code else "",
				"rate": flt(row.rate),
				"amount": flt(row.amount),
				"purchase_order_item": row.purchase_order_item,
			}
		)
	return rows


def _get_supplied_items(sco):
	rows = []
	for row in sco.supplied_items or []:
		required = flt(row.required_qty)
		supplied = flt(row.supplied_qty)
		consumed = flt(row.consumed_qty)
		returned = flt(row.returned_qty)
		not_supplied = max(required - supplied, 0)
		pending_consumption = max(required - consumed, 0)
		rows.append(
			{
				"main_item_code": row.main_item_code,
				"rm_item_code": row.rm_item_code,
				"stock_uom": row.stock_uom,
				"required_qty": required,
				"supplied_qty": supplied,
				"consumed_qty": consumed,
				"returned_qty": returned,
				"not_supplied_qty": not_supplied,
				"pending_consumption_qty": pending_consumption,
				"total_supplied_qty": flt(row.total_supplied_qty),
				"supplied_pct": flt(supplied / required * 100, 2) if required else 0,
				"consumed_pct": flt(consumed / required * 100, 2) if required else 0,
				"supply_status": _supply_status(required, supplied),
				"consumption_status": _consumption_status(required, consumed),
				"reserve_warehouse": row.reserve_warehouse,
				"rate": flt(row.rate),
				"amount": flt(row.amount),
			}
		)
	return rows


def _get_stock_entries(subcontracting_order):
	entries = frappe.get_all(
		"Stock Entry",
		filters={"subcontracting_order": subcontracting_order},
		fields=[
			"name",
			"stock_entry_type",
			"purpose",
			"posting_date",
			"posting_time",
			"docstatus",
			"from_warehouse",
			"to_warehouse",
			"owner",
			"creation",
		],
		order_by="posting_date asc, posting_time asc, creation asc",
	)

	for entry in entries:
		entry["items"] = frappe.get_all(
			"Stock Entry Detail",
			filters={"parent": entry.name},
			fields=[
				"item_code",
				"item_name",
				"qty",
				"uom",
				"s_warehouse",
				"t_warehouse",
				"subcontracted_item",
				"basic_rate",
				"amount",
			],
			order_by="idx asc",
		)
		entry["total_qty"] = sum(flt(row.qty) for row in entry["items"])
		entry["docstatus_label"] = _docstatus_label(entry.docstatus)

	return entries


def _get_subcontracting_receipts(subcontracting_order):
	receipt_names = frappe.db.sql(
		"""
		SELECT DISTINCT parent
		FROM `tabSubcontracting Receipt Item`
		WHERE subcontracting_order = %s
		ORDER BY parent
		""",
		subcontracting_order,
		pluck=True,
	)

	receipts = []
	for name in receipt_names:
		scr = frappe.db.get_value(
			"Subcontracting Receipt",
			name,
			[
				"name",
				"supplier",
				"supplier_name",
				"posting_date",
				"posting_time",
				"docstatus",
				"set_warehouse",
				"supplier_warehouse",
				"total_qty",
				"total",
				"owner",
				"creation",
			],
			as_dict=True,
		)
		scr["items"] = frappe.get_all(
			"Subcontracting Receipt Item",
			filters={"parent": name, "subcontracting_order": subcontracting_order},
			fields=[
				"item_code",
				"item_name",
				"qty",
				"received_qty",
				"rejected_qty",
				"stock_uom",
				"rate",
				"amount",
				"subcontracting_order_item",
				"warehouse",
			],
			order_by="idx asc",
		)
		scr["supplied_items"] = frappe.get_all(
			"Subcontracting Receipt Supplied Item",
			filters={"parent": name, "subcontracting_order": subcontracting_order},
			fields=[
				"rm_item_code",
				"main_item_code",
				"consumed_qty",
				"stock_uom",
				"rate",
				"amount",
			],
			order_by="idx asc",
		)
		scr["docstatus_label"] = _docstatus_label(scr.docstatus)
		receipts.append(scr)

	return receipts


def _get_purchase_invoices(purchase_order):
	if not purchase_order:
		return []

	invoice_names = frappe.db.sql(
		"""
		SELECT DISTINCT pi.name
		FROM `tabPurchase Invoice` pi
		INNER JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
		WHERE pii.purchase_order = %s AND pi.docstatus != 2
		ORDER BY pi.posting_date, pi.name
		""",
		purchase_order,
		pluck=True,
	)

	invoices = []
	for name in invoice_names:
		inv = frappe.db.get_value(
			"Purchase Invoice",
			name,
			[
				"name",
				"supplier",
				"posting_date",
				"docstatus",
				"grand_total",
				"outstanding_amount",
				"status",
				"bill_no",
			],
			as_dict=True,
		)
		inv["items"] = frappe.get_all(
			"Purchase Invoice Item",
			filters={"parent": name, "purchase_order": purchase_order},
			fields=["item_code", "item_name", "qty", "rate", "amount", "uom"],
			order_by="idx asc",
		)
		inv["docstatus_label"] = _docstatus_label(inv.docstatus)
		invoices.append(inv)

	return invoices


def _build_timeline(header, purchase_order, stock_entries, receipts, purchase_invoices):
	events = []

	if purchase_order:
		events.append(
			{
				"datetime": get_datetime(f"{purchase_order.transaction_date} 00:00:00"),
				"date": purchase_order.transaction_date,
				"document_type": "Purchase Order",
				"document": purchase_order.name,
				"description": _("Purchase Order created for supplier {0}").format(
					purchase_order.supplier_name or purchase_order.supplier
				),
				"status": purchase_order.status,
				"qty": None,
				"amount": flt(purchase_order.grand_total),
			}
		)

	events.append(
		{
			"datetime": get_datetime(header.get("creation")),
			"date": header.get("transaction_date"),
			"document_type": "Subcontracting Order",
			"document": header.get("name"),
			"description": _("Subcontracting Order submitted - {0}% received").format(
				header.get("per_received")
			),
			"status": header.get("status"),
			"qty": flt(header.get("total_qty")),
			"amount": flt(header.get("total")),
		}
	)

	for entry in stock_entries:
		events.append(
			{
				"datetime": get_datetime(f"{entry.posting_date} {entry.posting_time or '00:00:00'}"),
				"date": entry.posting_date,
				"document_type": "Stock Entry",
				"document": entry.name,
				"description": _("{0} - {1} item(s), total qty {2}").format(
					entry.purpose or entry.stock_entry_type,
					len(entry.get("items") or []),
					flt(entry.get("total_qty")),
				),
				"status": entry.get("docstatus_label"),
				"qty": flt(entry.get("total_qty")),
				"amount": None,
			}
		)

	for receipt in receipts:
		events.append(
			{
				"datetime": get_datetime(f"{receipt.posting_date} {receipt.posting_time or '00:00:00'}"),
				"date": receipt.posting_date,
				"document_type": "Subcontracting Receipt",
				"document": receipt.name,
				"description": _("Received {0} qty from subcontractor").format(flt(receipt.total_qty)),
				"status": receipt.get("docstatus_label"),
				"qty": flt(receipt.total_qty),
				"amount": flt(receipt.total),
			}
		)

	for invoice in purchase_invoices:
		events.append(
			{
				"datetime": get_datetime(f"{invoice.posting_date} 00:00:00"),
				"date": invoice.posting_date,
				"document_type": "Purchase Invoice",
				"document": invoice.name,
				"description": _("Purchase Invoice - {0}").format(invoice.bill_no or invoice.name),
				"status": invoice.get("status") or invoice.get("docstatus_label"),
				"qty": None,
				"amount": flt(invoice.grand_total),
			}
		)

	events.sort(key=lambda row: (row.get("datetime"), row.get("document_type"), row.get("document")))
	for idx, event in enumerate(events, start=1):
		event["idx"] = idx
		if event.get("datetime"):
			event["datetime"] = str(event["datetime"])

	return events


def _get_summary(order_items, supplied_items, stock_entries, receipts, header):
	total_ordered = sum(flt(row.get("qty")) for row in order_items)
	total_received = sum(flt(row.get("received_qty")) for row in order_items)
	total_rm_required = sum(flt(row.get("required_qty")) for row in supplied_items)
	total_rm_supplied = sum(flt(row.get("supplied_qty")) for row in supplied_items)
	total_rm_consumed = sum(flt(row.get("consumed_qty")) for row in supplied_items)
	total_transfer_qty = sum(flt(entry.get("total_qty")) for entry in stock_entries)
	total_receipt_qty = sum(flt(receipt.get("total_qty")) for receipt in receipts)

	return {
		"total_ordered_qty": total_ordered,
		"total_received_qty": total_received,
		"pending_fg_qty": max(total_ordered - total_received, 0),
		"per_received": flt(header.get("per_received"), 2),
		"fg_complete_count": sum(1 for r in order_items if r.get("status") == "Complete"),
		"fg_partial_count": sum(1 for r in order_items if r.get("status") == "Partial"),
		"fg_pending_count": sum(1 for r in order_items if r.get("status") in ("Pending", "Not Started")),
		"rm_required_qty": total_rm_required,
		"rm_supplied_qty": total_rm_supplied,
		"rm_consumed_qty": total_rm_consumed,
		"rm_pending_consumption_qty": sum(flt(r.get("pending_consumption_qty")) for r in supplied_items),
		"rm_not_supplied_qty": sum(flt(r.get("not_supplied_qty")) for r in supplied_items),
		"rm_fully_consumed_count": sum(1 for r in supplied_items if r.get("consumption_status") == "Fully Consumed"),
		"rm_pending_consumption_count": sum(
			1 for r in supplied_items if r.get("consumption_status") in ("Pending Consumption", "Partially Consumed")
		),
		"material_transfer_count": len(stock_entries),
		"material_transfer_qty": total_transfer_qty,
		"receipt_count": len(receipts),
		"receipt_qty": total_receipt_qty,
	}


def _fg_status(ordered, received):
	if not ordered:
		return "Not Started"
	if received >= ordered:
		return "Complete"
	if received > 0:
		return "Partial"
	return "Pending"


def _supply_status(required, supplied):
	if not required:
		return "Not Required"
	if supplied >= required:
		return "Fully Supplied"
	if supplied > 0:
		return "Partially Supplied"
	return "Not Supplied"


def _consumption_status(required, consumed):
	if not required:
		return "Not Required"
	if consumed >= required:
		return "Fully Consumed"
	if consumed > 0:
		return "Partially Consumed"
	return "Pending Consumption"


def _group_supplied_by_fg(supplied_items):
	grouped = {}
	for row in supplied_items:
		key = row.get("main_item_code") or _("General")
		grouped.setdefault(key, []).append(row)
	return [{"fg_item": key, "items": items} for key, items in grouped.items()]


def _docstatus_label(docstatus):
	return {0: _("Draft"), 1: _("Submitted"), 2: _("Cancelled")}.get(docstatus, "")


def _status_color(name):
	return {
		"green": "#2e7d32",
		"orange": "#f57c00",
		"red": "#d32f2f",
		"blue": "#1976d2",
		"gray": "#666666",
	}.get(name, "#666666")


def _paginate_rows(rows, page, page_size):
	try:
		page = int(page) if page else 1
		page_size = int(page_size) if page_size else 50
	except Exception:
		page, page_size = 1, 50
	page = max(page, 1)
	page_size = max(page_size, 1)
	total_items = len(rows)
	total_pages = max((total_items + page_size - 1) // page_size, 1)
	start_index = (page - 1) * page_size
	end_index = min(start_index + page_size, total_items)
	return rows[start_index:end_index], {
		"page": page,
		"page_size": page_size,
		"total_items": total_items,
		"total_pages": total_pages,
		"start_index": start_index,
		"end_index": end_index,
	}


@frappe.whitelist()
def get_subcontracting_order_status_dashboard(
	subcontracting_order,
	fg_page=1,
	fg_page_size=50,
	rm_page=1,
	rm_page_size=50,
):
	"""Dashboard payload for Subcontracting Order form (same style as Material Request)."""
	if not subcontracting_order:
		return None

	try:
		history = get_subcontracting_order_history(subcontracting_order)
	except Exception as e:
		frappe.log_error(f"SCO dashboard error for {subcontracting_order}: {e}")
		return None

	header = history.get("header") or {}
	summary = history.get("summary") or {}
	order_items = history.get("order_items") or []
	supplied_items = history.get("supplied_items") or []

	total_fg_ordered = flt(summary.get("total_ordered_qty"))
	total_fg_received = flt(summary.get("total_received_qty"))
	total_fg_pending = flt(summary.get("pending_fg_qty"))
	total_rm_required = flt(summary.get("rm_required_qty"))
	total_rm_supplied = flt(summary.get("rm_supplied_qty"))
	total_rm_consumed = flt(summary.get("rm_consumed_qty"))
	total_rm_pending = flt(summary.get("rm_pending_consumption_qty"))

	overall_received_pct = min(
		flt(total_fg_received / total_fg_ordered * 100, 1) if total_fg_ordered else 0, 100
	)
	overall_supplied_pct = min(
		flt(total_rm_supplied / total_rm_required * 100, 1) if total_rm_required else 0, 100
	)
	overall_consumed_pct = min(
		flt(total_rm_consumed / total_rm_required * 100, 1) if total_rm_required else 0, 100
	)

	fg_items_data = []
	for item in order_items:
		fg_items_data.append(
			{
				"item_code": item.get("item_code"),
				"item_name": item.get("item_name"),
				"ordered_qty": flt(item.get("qty")),
				"received_qty": flt(item.get("received_qty")),
				"pending_qty": flt(item.get("pending_qty")),
				"received_percentage": flt(item.get("received_pct"), 1),
				"status": item.get("status"),
				"uom": item.get("uom"),
			}
		)

	rm_items_data = []
	for item in supplied_items:
		rm_items_data.append(
			{
				"main_item_code": item.get("main_item_code"),
				"rm_item_code": item.get("rm_item_code"),
				"required_qty": flt(item.get("required_qty")),
				"supplied_qty": flt(item.get("supplied_qty")),
				"consumed_qty": flt(item.get("consumed_qty")),
				"pending_qty": flt(item.get("pending_consumption_qty")),
				"not_supplied_qty": flt(item.get("not_supplied_qty")),
				"supplied_percentage": flt(item.get("supplied_pct"), 1),
				"consumed_percentage": flt(item.get("consumed_pct"), 1),
				"supply_status": item.get("supply_status"),
				"consumption_status": item.get("consumption_status"),
				"uom": item.get("stock_uom"),
			}
		)

	fg_page_rows, fg_pagination = _paginate_rows(fg_items_data, fg_page, fg_page_size)
	rm_page_rows, rm_pagination = _paginate_rows(rm_items_data, rm_page, rm_page_size)

	status_info = _get_sco_status_info(header, overall_received_pct, overall_consumed_pct)
	receipt_status = _get_sco_receipt_status(history, summary)

	return {
		"sco_name": header.get("name"),
		"supplier_name": header.get("supplier_name") or header.get("supplier"),
		"purchase_order": header.get("purchase_order"),
		"transaction_date": header.get("transaction_date"),
		"status": header.get("status"),
		"per_received": flt(header.get("per_received"), 2),
		"total_fg_ordered": total_fg_ordered,
		"total_fg_received": total_fg_received,
		"total_fg_pending": total_fg_pending,
		"total_rm_required": total_rm_required,
		"total_rm_supplied": total_rm_supplied,
		"total_rm_consumed": total_rm_consumed,
		"total_rm_pending": total_rm_pending,
		"overall_received_percentage": overall_received_pct,
		"overall_supplied_percentage": overall_supplied_pct,
		"overall_consumed_percentage": overall_consumed_pct,
		"fg_items_data": fg_page_rows,
		"rm_items_data": rm_page_rows,
		"fg_pagination": fg_pagination,
		"rm_pagination": rm_pagination,
		"status_info": status_info,
		"receipt_status": receipt_status,
	}


def _get_sco_status_info(header, received_pct, consumed_pct):
	docstatus = header.get("docstatus")
	status = header.get("status") or ""

	if docstatus == 0:
		return {"status": "Draft", "status_color": "gray", "message": _("Subcontracting Order is in draft")}
	if docstatus == 2:
		return {"status": "Cancelled", "status_color": "red", "message": _("Subcontracting Order is cancelled")}
	if received_pct >= 100 and consumed_pct >= 100:
		return {
			"status": "Completed",
			"status_color": "green",
			"message": _("All finished goods received and raw materials consumed"),
		}
	if received_pct >= 100:
		return {
			"status": "Fully Received",
			"status_color": "green",
			"message": _("All finished goods received"),
		}
	if received_pct > 0:
		return {
			"status": status or "Partially Received",
			"status_color": "orange",
			"message": _("{0}% finished goods received").format(flt(received_pct, 1)),
		}
	return {
		"status": status or "Pending Receipt",
		"status_color": "red",
		"message": _("No finished goods received yet"),
	}


def _get_sco_receipt_status(history, summary):
	receipt_count = summary.get("receipt_count") or 0
	transfer_count = summary.get("material_transfer_count") or 0
	receipt_qty = flt(summary.get("receipt_qty"))

	if receipt_count:
		color = "green" if flt(summary.get("per_received")) >= 100 else "orange"
		return {
			"status": _("Receipts Created"),
			"status_color": color,
			"message": _("{0} subcontracting receipt(s), {1} material transfer(s)").format(
				receipt_count, transfer_count
			),
			"receipt_count": receipt_count,
			"transfer_count": transfer_count,
			"receipt_qty": receipt_qty,
		}

	if transfer_count:
		return {
			"status": _("Material Sent"),
			"status_color": "blue",
			"message": _("{0} material transfer(s), no receipt yet").format(transfer_count),
			"receipt_count": 0,
			"transfer_count": transfer_count,
			"receipt_qty": 0,
		}

	return {
		"status": _("No Activity"),
		"status_color": "red",
		"message": _("No material transfer or receipt created yet"),
		"receipt_count": 0,
		"transfer_count": 0,
		"receipt_qty": 0,
	}
