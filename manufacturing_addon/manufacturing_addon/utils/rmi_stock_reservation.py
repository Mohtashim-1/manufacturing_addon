# Copyright (c) 2026, Manufacturing Addon and contributors
# License: MIT

"""Allow Raw Material Issuance to consume Production Plan stock reservations.

When stock is reserved against a Production Plan for the same Sales Order as the
RMI, transfer via RMI must reduce SRE.transferred_qty *before* the Stock Entry
posts — otherwise SLE treats the qty as reserved for other vouchers.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cstr, flt


def get_production_plans_for_sales_order(sales_order, planning=None):
	"""Return submitted Production Plan names linked to this Sales Order."""
	plans = set()
	if not sales_order:
		return []

	if planning:
		pp = frappe.db.get_value(
			"Raw Material Transfer Planning", planning, "custom_production_plan"
		)
		if pp:
			plans.add(pp)

	# Child table has no docstatus; filter submitted parents separately
	for name in frappe.get_all(
		"Production Plan Item",
		filters={"sales_order": sales_order},
		pluck="parent",
	):
		if frappe.db.get_value("Production Plan", name, "docstatus") == 1:
			plans.add(name)

	# Also PPs that list SO on header (some versions)
	if frappe.get_meta("Production Plan").has_field("sales_order"):
		for name in frappe.get_all(
			"Production Plan",
			filters={"sales_order": sales_order, "docstatus": 1},
			pluck="name",
		):
			plans.add(name)

	return sorted(plans)


def get_open_sre_for_item(item_code, warehouse, production_plans):
	"""Open SREs for item/warehouse against given Production Plans (FIFO)."""
	if not item_code or not warehouse or not production_plans:
		return []

	return frappe.get_all(
		"Stock Reservation Entry",
		filters={
			"docstatus": 1,
			"status": ["in", ["Reserved", "Partially Reserved", "Partially Delivered", "Partially Used"]],
			"item_code": item_code,
			"warehouse": warehouse,
			"voucher_type": "Production Plan",
			"voucher_no": ["in", list(production_plans)],
		},
		fields=[
			"name",
			"reserved_qty",
			"delivered_qty",
			"transferred_qty",
			"consumed_qty",
			"voucher_no",
			"status",
		],
		order_by="creation asc",
	)


def _available_on_sre(sre):
	return flt(sre.reserved_qty) - flt(sre.delivered_qty) - flt(sre.transferred_qty) - flt(
		sre.consumed_qty
	)


def apply_pp_reservations_for_rmi(iss_doc):
	"""Mark matching PP SRE qty as transferred so RMI Stock Entry can post.

	Returns list of {sre, item_code, qty} allocations (also stored on RMI).
	"""
	sales_order = cstr(iss_doc.sales_order or "")
	warehouse = cstr(iss_doc.from_warehouse or "")
	if not sales_order or not warehouse:
		return []

	production_plans = get_production_plans_for_sales_order(sales_order, iss_doc.planning)
	if not production_plans:
		return []

	allocations = []
	for row in iss_doc.items or []:
		item_code = cstr(getattr(row, "item_code", None) or getattr(row, "item", None))
		qty = flt(row.qty)
		if not item_code or qty <= 0:
			continue

		remaining = qty
		for sre in get_open_sre_for_item(item_code, warehouse, production_plans):
			if remaining <= 0:
				break
			available = _available_on_sre(sre)
			if available <= 0:
				continue
			take = min(remaining, available)
			doc = frappe.get_doc("Stock Reservation Entry", sre.name)
			new_transferred = flt(doc.transferred_qty) + take
			doc.transferred_qty = new_transferred
			doc.db_set("transferred_qty", new_transferred, update_modified=False)
			doc.update_status()
			doc.update_reserved_stock_in_bin()
			allocations.append(
				{
					"sre": sre.name,
					"item_code": item_code,
					"qty": take,
					"voucher_no": sre.voucher_no,
				}
			)
			remaining -= take

	if allocations:
		iss_doc.db_set("sre_allocations", json.dumps(allocations), update_modified=False)
		frappe.msgprint(
			_("Consumed {0} Production Plan reservation line(s) for this issuance.").format(
				len(allocations)
			),
			alert=True,
			indicator="green",
		)

	return allocations


def reverse_pp_reservations_for_rmi(iss_doc):
	"""Undo transferred_qty applied on submit (on cancel)."""
	raw = cstr(iss_doc.get("sre_allocations") or "")
	allocations = []
	if raw:
		try:
			allocations = json.loads(raw)
		except Exception:
			allocations = []

	if not allocations:
		# Fallback: reverse from SE lines against open transferred SREs (LIFO)
		if not iss_doc.stock_entry or not iss_doc.sales_order:
			return
		production_plans = get_production_plans_for_sales_order(
			iss_doc.sales_order, iss_doc.planning
		)
		warehouse = iss_doc.from_warehouse
		for se_item in frappe.get_all(
			"Stock Entry Detail",
			filters={"parent": iss_doc.stock_entry},
			fields=["item_code", "transfer_qty", "qty"],
		):
			qty = flt(se_item.transfer_qty or se_item.qty)
			if qty <= 0:
				continue
			sres = frappe.get_all(
				"Stock Reservation Entry",
				filters={
					"docstatus": 1,
					"item_code": se_item.item_code,
					"warehouse": warehouse,
					"voucher_type": "Production Plan",
					"voucher_no": ["in", production_plans or ["__none__"]],
					"transferred_qty": [">", 0],
				},
				fields=["name", "transferred_qty", "reserved_qty"],
				order_by="creation desc",
			)
			left = qty
			for sre in sres:
				if left <= 0:
					break
				take = min(left, flt(sre.transferred_qty))
				allocations.append({"sre": sre.name, "qty": take})
				left -= take

	for a in allocations:
		name = a.get("sre")
		qty = flt(a.get("qty"))
		if not name or qty <= 0 or not frappe.db.exists("Stock Reservation Entry", name):
			continue
		doc = frappe.get_doc("Stock Reservation Entry", name)
		if doc.docstatus != 1:
			continue
		new_transferred = max(flt(doc.transferred_qty) - qty, 0)
		doc.transferred_qty = new_transferred
		doc.db_set("transferred_qty", new_transferred, update_modified=False)
		doc.update_status()
		doc.update_reserved_stock_in_bin()

	if iss_doc.meta.has_field("sre_allocations"):
		iss_doc.db_set("sre_allocations", "", update_modified=False)


def _remaining_reserved_qty(doc):
	return (
		flt(doc.reserved_qty)
		- flt(doc.delivered_qty)
		- flt(doc.transferred_qty)
		- flt(doc.consumed_qty)
	)


@frappe.whitelist()
def unreserve_remaining_qty(name, qty=None):
	"""Release leftover reserved qty on a submitted Stock Reservation Entry.

	ERPNext's normal "update reserved qty" validates like a *new* reserve, so
	reducing leftover qty often fails when other SREs already lock the warehouse.
	This method only lowers reserved_qty down toward transferred/delivered/consumed.
	"""
	if not name:
		frappe.throw(_("Stock Reservation Entry is required"))

	doc = frappe.get_doc("Stock Reservation Entry", name)
	if doc.docstatus != 1:
		frappe.throw(_("Only submitted Stock Reservation Entries can be unreserved"))

	remaining = _remaining_reserved_qty(doc)
	if remaining <= 0:
		frappe.msgprint(_("Nothing left to unreserve on {0}.").format(doc.name), alert=True)
		return {"name": doc.name, "unreserved_qty": 0, "reserved_qty": flt(doc.reserved_qty)}

	qty = flt(qty) if qty not in (None, "") else remaining
	if qty <= 0:
		frappe.throw(_("Qty to unreserve must be greater than zero"))
	if qty > remaining:
		frappe.throw(
			_("Cannot unreserve {0}; only {1} remaining on {2}.").format(qty, remaining, doc.name)
		)

	new_reserved = flt(doc.reserved_qty) - qty
	# Must stay at least what's already used
	min_reserved = flt(doc.delivered_qty) + flt(doc.transferred_qty) + flt(doc.consumed_qty)
	if new_reserved < min_reserved:
		frappe.throw(
			_("Reserved Qty cannot go below already used qty ({0}).").format(min_reserved)
		)

	doc.db_set("reserved_qty", new_reserved)
	doc.reserved_qty = new_reserved
	doc.update_reserved_qty_in_voucher()
	doc.update_status()
	doc.update_reserved_stock_in_bin()

	frappe.msgprint(
		_("Unreserved {0} {1} from {2}. Reserved Qty is now {3}.").format(
			frappe.bold(qty), doc.stock_uom, frappe.bold(doc.name), frappe.bold(new_reserved)
		),
		alert=True,
		indicator="green",
	)
	return {
		"name": doc.name,
		"unreserved_qty": qty,
		"reserved_qty": new_reserved,
		"status": frappe.db.get_value("Stock Reservation Entry", doc.name, "status"),
	}


@frappe.whitelist()
def get_blocking_reservations_for_rmi(issuance_name):
	"""List open SREs that are *not* for this RMI's Sales Order (cross-SO locks)."""
	iss = frappe.get_doc("Raw Material Issuance", issuance_name)
	if not iss.from_warehouse:
		return []

	same_so_plans = set(get_production_plans_for_sales_order(iss.sales_order, iss.planning))
	item_codes = [
		cstr(getattr(row, "item_code", None) or getattr(row, "item", None))
		for row in (iss.items or [])
	]
	item_codes = [i for i in item_codes if i]
	if not item_codes:
		return []

	rows = frappe.get_all(
		"Stock Reservation Entry",
		filters={
			"docstatus": 1,
			"item_code": ["in", item_codes],
			"warehouse": iss.from_warehouse,
			"status": ["in", ["Reserved", "Partially Reserved", "Partially Delivered", "Partially Used"]],
		},
		fields=[
			"name",
			"item_code",
			"warehouse",
			"reserved_qty",
			"delivered_qty",
			"transferred_qty",
			"consumed_qty",
			"voucher_type",
			"voucher_no",
			"status",
		],
		order_by="item_code, creation",
	)

	blocking = []
	for r in rows:
		open_qty = (
			flt(r.reserved_qty)
			- flt(r.delivered_qty)
			- flt(r.transferred_qty)
			- flt(r.consumed_qty)
		)
		if open_qty <= 0:
			continue
		# Same-SO PP reservations are consumed automatically on RMI submit
		if r.voucher_type == "Production Plan" and r.voucher_no in same_so_plans:
			continue
		blocking.append(
			{
				"name": r.name,
				"item_code": r.item_code,
				"open_qty": open_qty,
				"voucher_type": r.voucher_type,
				"voucher_no": r.voucher_no,
				"status": r.status,
			}
		)
	return blocking
