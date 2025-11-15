# Copyright (c) 2024, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def convert_service_item_rates(doc):
	"""
	Convert service item rate from Purchase Order transaction currency 
	to company base currency in Subcontracting Order.
	
	This fixes the issue where PO rate in USD (e.g., 1.55 USD) is copied 
	as-is to SCO, but SCO uses company currency (PKR), so it should be 
	converted to base rate (e.g., 1.55 * 281.15 = 435.78 PKR).
	"""
	if not doc.purchase_order or not doc.service_items:
		return
	
	try:
		# Get Purchase Order details for currency conversion
		po = frappe.get_cached_doc("Purchase Order", doc.purchase_order)
		company_currency = frappe.get_cached_value("Company", doc.company, "default_currency")
		
		# If PO currency is same as company currency, no conversion needed
		if po.currency == company_currency:
			return
		
		rate_updated = False
		for service_item in doc.service_items:
			if not service_item.purchase_order_item:
				continue
			
			try:
				po_item = frappe.get_cached_doc("Purchase Order Item", service_item.purchase_order_item)
				
				# Convert rate from PO transaction currency to company base currency
				if po_item.base_rate:
					# Use base_rate (already in company currency)
					old_rate = service_item.rate
					service_item.rate = po_item.base_rate
					if old_rate != service_item.rate:
						rate_updated = True
				elif po.conversion_rate and service_item.rate:
					# Calculate base rate if base_rate is not available
					old_rate = service_item.rate
					service_item.rate = flt(service_item.rate) * flt(po.conversion_rate)
					if old_rate != service_item.rate:
						rate_updated = True
				
				# Recalculate amount with corrected rate
				if hasattr(service_item, 'qty') and service_item.qty:
					service_item.amount = flt(service_item.qty) * flt(service_item.rate)
			except Exception as e:
				frappe.log_error(
					f"Error converting rate for service item {service_item.name} in SCO {doc.name}: {str(e)}",
					"Subcontracting Order Currency Conversion Error"
				)
				# Continue with other items even if one fails
				continue
		
		# Log conversion for debugging (remove msgprint to avoid annoying users)
		# if rate_updated:
		# 	frappe.msgprint(_("Service item rates have been converted from {0} to {1}").format(
		# 		po.currency, company_currency
		# 	), alert=True, indicator="blue")
	except Exception as e:
		frappe.log_error(
			f"Error in convert_service_item_rates for SCO {doc.name}: {str(e)}",
			"Subcontracting Order Currency Conversion Error"
		)


def before_validate_currency_conversion(doc, method):
	"""
	Convert service item rates before validation.
	This runs after populate_items_table is called.
	"""
	convert_service_item_rates(doc)


def validate_currency_conversion(doc, method):
	"""
	Convert service item rates during validation.
	This ensures rates are always correct.
	"""
	convert_service_item_rates(doc)


def on_update_currency_conversion(doc, method):
	"""
	Convert service item rates when document is updated.
	This fixes rates if they were changed manually or incorrectly.
	"""
	convert_service_item_rates(doc)

