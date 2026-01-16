import frappe
from frappe.model.mapper import get_mapped_doc

@frappe.whitelist()
def make_delivery_note_with_all_items(source_name, target_doc=None):
	"""
	Custom function to create Delivery Note from Sales Order showing ALL items,
	even if they are fully delivered. This overrides the standard behavior.
	"""
	from erpnext.stock.doctype.packed_item.packed_item import make_packing_list
	from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
		get_sre_details_for_voucher,
		get_sre_reserved_qty_details_for_voucher,
		get_ssb_bundle_for_voucher,
	)
	from erpnext.stock.get_item_details import get_item_defaults, get_item_group_defaults
	from erpnext.accounts.utils import get_company_address
	from erpnext.stock.doctype.delivery_note.delivery_note import get_fetch_values
	from frappe.utils import flt, cstr
	
	kwargs = frappe._dict({})
	sre_details = {}
	
	mapper = {
		"Sales Order": {"doctype": "Delivery Note", "validation": {"docstatus": ["=", 1]}},
		"Sales Taxes and Charges": {"doctype": "Sales Taxes and Charges", "reset_value": True},
		"Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
	}
	
	has_unit_price_items = frappe.db.get_value("Sales Order", source_name, "has_unit_price_items")
	
	def is_unit_price_row(source):
		return has_unit_price_items and source.qty == 0
	
	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		target.run_method("set_po_nos")
		target.run_method("calculate_taxes_and_totals")
		target.run_method("set_use_serial_batch_fields")
		
		if source.company_address:
			target.update({"company_address": source.company_address})
		else:
			target.update(get_company_address(target.company))
		
		if target.company_address:
			target.update(get_fetch_values("Delivery Note", "company_address", target.company_address))
		
		if frappe.flags.bulk_transaction:
			target.set_new_name()
		
		make_packing_list(target)
	
	def condition(doc):
		"""
		MODIFIED: Show ALL items regardless of delivered_qty.
		Only exclude items delivered by supplier.
		"""
		# Only exclude if delivered by supplier
		return doc.delivered_by_supplier != 1
	
	def update_item(source, target, source_parent):
		"""
		MODIFIED: Set qty to remaining pending qty, but allow 0 qty items to show.
		"""
		pending_qty = flt(source.qty) - flt(source.delivered_qty)
		
		# For fully delivered items, set qty to 0 but still include them
		if pending_qty <= 0 and not is_unit_price_row(source):
			target.qty = 0
			target.base_amount = 0
			target.amount = 0
		else:
			target.base_amount = pending_qty * flt(source.base_rate)
			target.amount = pending_qty * flt(source.rate)
			target.qty = flt(source.qty) if is_unit_price_row(source) else pending_qty
		
		item = get_item_defaults(target.item_code, source_parent.company)
		item_group = get_item_group_defaults(target.item_code, source_parent.company)
		
		if item:
			target.cost_center = (
				frappe.db.get_value("Project", source_parent.project, "cost_center")
				or item.get("buying_cost_center")
				or item_group.get("buying_cost_center")
			)
	
	mapper["Sales Order Item"] = {
		"doctype": "Delivery Note Item",
		"field_map": {
			"rate": "rate",
			"name": "so_detail",
			"parent": "against_sales_order",
		},
		"condition": condition,
		"postprocess": update_item,
	}
	
	doc = get_mapped_doc(
		"Sales Order",
		source_name,
		mapper,
		target_doc,
		set_missing_values,
	)
	
	return doc















