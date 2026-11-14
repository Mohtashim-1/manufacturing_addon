# Copyright (c) 2026, Manufacturing Addon and contributors
# For license information, please see license.txt

"""
Revise subcontract FG / service qty on submitted PO + SCO without amend/cancel.

- Does NOT touch Stock Entry (Send to Subcontractor)
- Updates Purchase Order Item (qty Kg + fg_item_qty meters)
- Updates Subcontracting Order items / service items / supplied required_qty
- System Manager only — so SCR can receive actual yield without cancelling the chain
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt


def _require_system_manager():
	if "System Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("Only System Manager can revise subcontract quantities"), frappe.PermissionError)


def _as_list(rows):
	if isinstance(rows, str):
		rows = json.loads(rows)
	if not isinstance(rows, list):
		frappe.throw(_("Invalid rows payload"))
	return rows


@frappe.whitelist()
def get_revise_rows(subcontracting_order: str | None = None, purchase_order: str | None = None):
	"""Return editable FG/service lines for the revise dialog."""
	_require_system_manager()

	sco_name, po_name, sco = _resolve_docs(subcontracting_order, purchase_order)
	rows = []
	for item in sco.items or []:
		poi = item.purchase_order_item
		po_row = frappe.db.get_value(
			"Purchase Order Item",
			poi,
			["name", "item_code", "qty", "fg_item_qty", "rate", "amount", "fg_item"],
			as_dict=True,
		) if poi else None

		service = None
		for si in sco.service_items or []:
			if si.purchase_order_item == poi:
				service = si
				break

		fg_qty = flt(item.qty)
		service_qty = flt(service.qty) if service else (flt(po_row.qty) if po_row else 0)
		conv = (flt(service_qty) / fg_qty) if fg_qty else 0

		supplied = frappe.get_all(
			"Subcontracting Order Supplied Item",
			filters={"parent": sco_name, "reference_name": item.name},
			fields=["name", "rm_item_code", "required_qty", "supplied_qty"],
		)

		rows.append(
			{
				"sco_item": item.name,
				"purchase_order_item": poi,
				"fg_item": item.item_code,
				"fg_item_name": item.item_name,
				"bom": item.bom,
				"current_fg_qty": fg_qty,
				"new_fg_qty": fg_qty,
				"uom": item.stock_uom or "Nos",
				"current_service_qty": service_qty,
				"new_service_qty": service_qty,
				"service_item": service.item_code if service else (po_row.item_code if po_row else None),
				"service_rate": flt(service.rate) if service else (flt(po_row.rate) if po_row else 0),
				"conversion_factor": conv,  # service qty per 1 FG
				"received_qty": flt(item.received_qty),
				"supplied": supplied,
			}
		)

	return {
		"subcontracting_order": sco_name,
		"purchase_order": po_name,
		"supplier": sco.supplier,
		"status": sco.status,
		"rows": rows,
	}


@frappe.whitelist()
def apply_revise_qty(
	rows,
	subcontracting_order: str | None = None,
	purchase_order: str | None = None,
	remarks: str | None = None,
):
	"""
	Apply new FG (+ optional service) qty to submitted PO and linked SCO.
	Stock Entry is intentionally not modified.
	"""
	_require_system_manager()
	rows = _as_list(rows)
	if not rows:
		frappe.throw(_("No rows to update"))

	sco_name, po_name, sco = _resolve_docs(subcontracting_order, purchase_order)
	if sco.docstatus != 1:
		frappe.throw(_("Subcontracting Order must be submitted"))

	po = frappe.get_doc("Purchase Order", po_name)
	if po.docstatus != 1:
		frappe.throw(_("Purchase Order must be submitted"))
	if not cint(po.is_subcontracted):
		frappe.throw(_("Purchase Order is not subcontracted"))

	# Block if submitted SCR already received more than new qty
	changes = []
	for row in rows:
		sco_item = row.get("sco_item")
		new_fg = flt(row.get("new_fg_qty"))
		new_service = flt(row.get("new_service_qty"))
		if new_fg <= 0:
			frappe.throw(_("Finished Good qty must be greater than zero"))
		if new_service < 0:
			frappe.throw(_("Service qty cannot be negative"))

		item = next((i for i in sco.items if i.name == sco_item), None)
		if not item:
			frappe.throw(_("SCO item {0} not found").format(sco_item))

		received = flt(item.received_qty)
		if received and new_fg < received:
			frappe.throw(
				_("Cannot set {0} below already received qty {1}").format(
					frappe.bold(item.item_code), received
				)
			)

		old_fg = flt(item.qty)
		if abs(new_fg - old_fg) < 0.00001 and abs(
			new_service - flt(row.get("current_service_qty") or 0)
		) < 0.00001:
			continue

		poi = item.purchase_order_item
		po_row = next((p for p in po.items if p.name == poi), None)
		if not po_row:
			frappe.throw(_("Purchase Order Item missing for {0}").format(item.item_code))

		# --- Purchase Order Item ---
		rate = flt(po_row.rate)
		amount = flt(new_service) * rate
		frappe.db.set_value(
			"Purchase Order Item",
			poi,
			{
				"fg_item_qty": new_fg,
				"qty": new_service,
				"stock_qty": new_service * flt(po_row.conversion_factor or 1),
				"amount": amount,
				"base_amount": amount * flt(po.conversion_rate or 1),
			},
			update_modified=False,
		)

		# --- SCO FG item ---
		frappe.db.set_value(
			"Subcontracting Order Item",
			sco_item,
			{"qty": new_fg},
			update_modified=False,
		)

		# --- SCO service item ---
		for si in sco.service_items or []:
			if si.purchase_order_item == poi:
				si_amount = flt(new_service) * flt(si.rate)
				frappe.db.set_value(
					"Subcontracting Order Service Item",
					si.name,
					{
						"qty": new_service,
						"fg_item_qty": new_fg,
						"amount": si_amount,
					},
					update_modified=False,
				)
				break

		# --- Supplied RM required_qty (scale with FG; do not change supplied_qty / STE) ---
		ratio = (new_fg / old_fg) if old_fg else 1
		for supplied in frappe.get_all(
			"Subcontracting Order Supplied Item",
			filters={"parent": sco_name, "reference_name": sco_item},
			fields=["name", "required_qty"],
		):
			# Prefer 1:1 with FG when old required matched old FG (typical dyeing BOM)
			old_req = flt(supplied.required_qty)
			if abs(old_req - old_fg) < 0.05:
				new_req = new_fg
			else:
				new_req = flt(old_req * ratio)
			frappe.db.set_value(
				"Subcontracting Order Supplied Item",
				supplied.name,
				{"required_qty": new_req},
				update_modified=False,
			)

		changes.append(
			{
				"item": item.item_code,
				"fg": f"{old_fg} → {new_fg}",
				"service": f"{flt(row.get('current_service_qty'))} → {new_service}",
			}
		)

	if not changes:
		frappe.msgprint(_("No quantity changes to apply"))
		return {"updated": 0}

	_recalculate_po_totals(po_name)
	_recalculate_sco_totals(sco_name)

	# Refresh reserved/ordered bins for SCO FG (safe; does not alter STE)
	try:
		sco.reload()
		sco.update_ordered_qty_for_subcontracting()
		sco.update_reserved_qty_for_subcontracting()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Revise Subcontract Qty Bin Update")

	note = remarks or _("Qty revised without amend (Stock Entry unchanged)")
	detail = "<br>".join(
		f"{c['item']}: FG {c['fg']}, Service {c['service']}" for c in changes
	)
	for doctype, name in (("Purchase Order", po_name), ("Subcontracting Order", sco_name)):
		frappe.get_doc(doctype, name).add_comment(
			"Comment",
			f"{note}<br>{detail}<br>By {frappe.session.user}",
		)

	frappe.db.commit()
	return {
		"updated": len(changes),
		"purchase_order": po_name,
		"subcontracting_order": sco_name,
		"changes": changes,
		"message": _("Updated {0} line(s). Stock Entry was not changed. You can create/submit Subcontracting Receipt now.").format(
			len(changes)
		),
	}


def _resolve_docs(subcontracting_order, purchase_order):
	sco_name = subcontracting_order
	po_name = purchase_order

	if sco_name:
		sco = frappe.get_doc("Subcontracting Order", sco_name)
		po_name = sco.purchase_order
	elif po_name:
		found = frappe.get_all(
			"Subcontracting Order",
			filters={"purchase_order": po_name, "docstatus": 1},
			pluck="name",
			order_by="creation desc",
			limit=1,
		)
		if not found:
			frappe.throw(_("No submitted Subcontracting Order found for {0}").format(po_name))
		sco_name = found[0]
		sco = frappe.get_doc("Subcontracting Order", sco_name)
	else:
		frappe.throw(_("Subcontracting Order or Purchase Order is required"))

	if not po_name:
		frappe.throw(_("Purchase Order missing on Subcontracting Order"))

	return sco_name, po_name, sco


def _recalculate_po_totals(po_name: str):
	po = frappe.get_doc("Purchase Order", po_name)
	total_qty = 0
	net_total = 0
	for item in po.items:
		# reload from DB values we just set
		item.qty = flt(frappe.db.get_value("Purchase Order Item", item.name, "qty"))
		item.fg_item_qty = flt(frappe.db.get_value("Purchase Order Item", item.name, "fg_item_qty"))
		item.amount = flt(frappe.db.get_value("Purchase Order Item", item.name, "amount"))
		total_qty += flt(item.qty)
		net_total += flt(item.amount)

	# Keep taxes proportional if any — simplest: set net/grand from items when no taxes
	tax_total = flt(frappe.db.sql(
		"select sum(tax_amount) from `tabPurchase Taxes and Charges` where parent=%s",
		po_name,
	)[0][0])
	grand = net_total + tax_total
	frappe.db.set_value(
		"Purchase Order",
		po_name,
		{
			"total_qty": total_qty,
			"net_total": net_total,
			"base_net_total": net_total * flt(po.conversion_rate or 1),
			"grand_total": grand,
			"base_grand_total": grand * flt(po.conversion_rate or 1),
			"rounded_total": grand,
			"base_rounded_total": grand * flt(po.conversion_rate or 1),
		},
		update_modified=True,
	)


def _recalculate_sco_totals(sco_name: str):
	sco = frappe.get_doc("Subcontracting Order", sco_name)
	# Reload qty from DB then run amount math in memory and write totals
	total_qty = 0
	total = 0
	for idx, item in enumerate(sco.items or []):
		item.qty = flt(frappe.db.get_value("Subcontracting Order Item", item.name, "qty"))
		service_amount = 0
		if idx < len(sco.service_items or []):
			si = sco.service_items[idx]
			si.qty = flt(frappe.db.get_value("Subcontracting Order Service Item", si.name, "qty"))
			si.amount = flt(frappe.db.get_value("Subcontracting Order Service Item", si.name, "amount"))
			service_amount = flt(si.amount)

		# Recompute service_cost_per_qty from updated service amount
		service_cost_per_qty = (service_amount / item.qty) if item.qty else 0
		rm_cost = flt(item.rm_cost_per_qty)
		addl = flt(item.additional_cost_per_qty)
		rate = rm_cost + service_cost_per_qty + addl
		amount = item.qty * rate
		frappe.db.set_value(
			"Subcontracting Order Item",
			item.name,
			{
				"service_cost_per_qty": service_cost_per_qty,
				"rate": rate,
				"amount": amount,
			},
			update_modified=False,
		)
		total_qty += item.qty
		total += amount

	frappe.db.set_value(
		"Subcontracting Order",
		sco_name,
		{"total_qty": total_qty, "total": total},
		update_modified=True,
	)
