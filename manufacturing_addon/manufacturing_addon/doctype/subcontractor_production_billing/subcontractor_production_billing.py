# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, today


class SubcontractorProductionBilling(Document):
	def validate(self):
		# Validate that period_to is after period_from
		if self.period_from and self.period_to and getdate(self.period_to) < getdate(self.period_from):
			frappe.throw(_("Period To date must be after Period From date"))
		
		# Validate billing items
		self.validate_billing_items()
		
		# Calculate total amount
		self.calculate_total()
	
	def validate_billing_items(self):
		"""Validate that all items have rates - show warning but allow saving"""
		missing_rates = []
		for item in self.billing_items:
			if not item.rate or flt(item.rate) <= 0:
				missing_rates.append(item.item_code)
		
		if missing_rates:
			# Show warning but don't prevent saving
			# User can add rates manually or set up rate cards later
			frappe.msgprint(_(
				"Rate not found for {0} item(s). "
				"Please set up Subcontractor Rate Cards or enter rates manually. "
				"Items without rates will have amount = 0."
			).format(len(missing_rates)), indicator="orange", title=_("Warning"))
	
	def calculate_total(self):
		"""Calculate total amount from billing items"""
		total = 0
		for item in self.billing_items:
			total += flt(item.amount)
		self.total_amount = total
	
	@frappe.whitelist()
	def generate_billing(self):
		"""Generate billing items from Delivery Notes and Production Reports"""
		# If called from client-side, reload the doc first
		if isinstance(self, str):
			self = frappe.get_doc("Subcontractor Production Billing", self)
		"""Generate billing items from Delivery Notes and Production Reports"""
		if not self.supplier:
			frappe.throw(_("Please select a Supplier first"))
		
		if not self.posting_date:
			self.posting_date = today()
		
		# Clear existing items
		self.billing_items = []
		
		# Get period dates
		period_from = self.period_from or getdate(self.posting_date)
		period_to = self.period_to or getdate(self.posting_date)
		
		# Fetch Delivery Note quantities
		dn_data = self.get_delivery_note_quantities(period_from, period_to)
		
		# Fetch production report quantities
		production_data = self.get_production_report_quantities(period_from, period_to)
		
		# Combine data and create billing items
		billing_items_map = {}
		
		# Start with DN data
		for item_code, qty in dn_data.items():
			billing_items_map[item_code] = {
				"item_code": item_code,
				"dn_qty": qty,
				"cutting_qty": 0,
				"stitching_qty": 0,
				"packing_qty": 0,
				"manufactured_qty": 0,
				"final_payable_qty": qty,  # Default to DN Qty
				"rate": 0,
				"amount": 0
			}
		
		# Add production data
		for item_code, data in production_data.items():
			if item_code not in billing_items_map:
				# If item not in DN but in reports, still create entry with 0 DN qty
				billing_items_map[item_code] = {
					"item_code": item_code,
					"dn_qty": 0,
					"cutting_qty": 0,
					"stitching_qty": 0,
					"packing_qty": 0,
					"manufactured_qty": 0,
					"final_payable_qty": 0,
					"rate": 0,
					"amount": 0
				}
			
			billing_items_map[item_code]["cutting_qty"] = data.get("cutting_qty", 0)
			billing_items_map[item_code]["stitching_qty"] = data.get("stitching_qty", 0)
			billing_items_map[item_code]["packing_qty"] = data.get("packing_qty", 0)
			
			# Calculate Manufactured Qty = max(cutting, stitching, packing)
			manufactured_qty = max(
				flt(data.get("cutting_qty", 0)),
				flt(data.get("stitching_qty", 0)),
				flt(data.get("packing_qty", 0))
			)
			billing_items_map[item_code]["manufactured_qty"] = manufactured_qty
			
			# Final Payable Qty = DN Qty (never exceed DN Qty)
			dn_qty = billing_items_map[item_code]["dn_qty"]
			billing_items_map[item_code]["final_payable_qty"] = dn_qty
		
		# Fetch rates and calculate amounts
		missing_rates = []
		for item_code, data in billing_items_map.items():
			rate_info = get_rate(self.supplier, item_code, self.posting_date)
			if rate_info:
				data["rate"] = flt(rate_info.get("rate_per_pcs", 0))
			else:
				missing_rates.append(item_code)
				data["rate"] = 0
			
			# Calculate amount = Final Payable Qty × Rate
			data["amount"] = flt(data["final_payable_qty"]) * flt(data["rate"])
		
		# Create billing items
		for item_code, data in sorted(billing_items_map.items()):
			# Ensure all values are properly formatted as floats
			billing_item = {
				"item_code": item_code,
				"dn_qty": flt(data.get("dn_qty", 0)),
				"cutting_qty": flt(data.get("cutting_qty", 0)),
				"stitching_qty": flt(data.get("stitching_qty", 0)),
				"packing_qty": flt(data.get("packing_qty", 0)),
				"manufactured_qty": flt(data.get("manufactured_qty", 0)),
				"final_payable_qty": flt(data.get("final_payable_qty", 0)),
				"rate": flt(data.get("rate", 0)),
				"amount": flt(data.get("amount", 0))
			}
			self.append("billing_items", billing_item)
		
		# Calculate total
		self.calculate_total()
		
		# Show warning if rates are missing (truncate list if too long)
		if missing_rates:
			if len(missing_rates) > 10:
				missing_list = ", ".join(missing_rates[:10]) + f" and {len(missing_rates) - 10} more items"
			else:
				missing_list = ", ".join(missing_rates)
			
			frappe.msgprint(_(
				"Rate not found for {0} item(s): {1}. "
				"Please set up Subcontractor Rate Cards for these items. "
				"You can still save and add rates manually."
			).format(len(missing_rates), missing_list), indicator="orange", title=_("Warning"))
		
		# Build references string
		self.build_references(period_from, period_to)
		
		return len(self.billing_items)
	
	def get_delivery_note_quantities(self, period_from, period_to):
		"""
		Get Delivery Note quantities for the supplier
		Links Delivery Notes to suppliers through Purchase Orders
		Also checks if supplier is set up as customer
		Returns: dict {item_code: total_qty}
		"""
		dn_data = {}
		
		# Method 1: Get Delivery Notes linked through Purchase Orders
		# Delivery Note Items may have purchase_order_item reference
		delivery_notes_po = frappe.db.sql("""
			SELECT dni.item_code, SUM(dni.qty) as total_qty
			FROM `tabDelivery Note Item` dni
			INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
			LEFT JOIN `tabPurchase Order Item` poi ON poi.name = dni.purchase_order_item
			LEFT JOIN `tabPurchase Order` po ON po.name = poi.parent
			WHERE po.supplier = %(supplier)s
				AND dn.docstatus = 1
				AND dn.posting_date BETWEEN %(period_from)s AND %(period_to)s
				AND dni.item_code IS NOT NULL
			GROUP BY dni.item_code
		""", {
			"supplier": self.supplier,
			"period_from": period_from,
			"period_to": period_to
		}, as_dict=True)
		
		for item in delivery_notes_po:
			item_code = item.item_code
			qty = flt(item.total_qty)
			if item_code not in dn_data:
				dn_data[item_code] = 0
			dn_data[item_code] += qty
		
		# Method 2: Get Delivery Notes where supplier is set up as customer
		try:
			supplier_doc = frappe.get_doc("Supplier", self.supplier)
			customer_name = None
			if hasattr(supplier_doc, 'customer') and supplier_doc.customer:
				customer_name = supplier_doc.customer
		except:
			customer_name = None
		
		if customer_name:
			delivery_notes_customer = frappe.db.sql("""
				SELECT dni.item_code, SUM(dni.qty) as total_qty
				FROM `tabDelivery Note` dn
				INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
				WHERE dn.customer = %(customer)s
					AND dn.docstatus = 1
					AND dn.posting_date BETWEEN %(period_from)s AND %(period_to)s
					AND dni.item_code IS NOT NULL
				GROUP BY dni.item_code
			""", {
				"customer": customer_name,
				"period_from": period_from,
				"period_to": period_to
			}, as_dict=True)
			
			for item in delivery_notes_customer:
				item_code = item.item_code
				qty = flt(item.total_qty)
				if item_code not in dn_data:
					dn_data[item_code] = 0
				dn_data[item_code] += qty
		
		return dn_data
	
	def get_production_report_quantities(self, period_from, period_to):
		"""
		Get production report quantities (Cutting, Stitching, Packing) for the supplier
		Returns: dict {item_code: {cutting_qty: x, stitching_qty: y, packing_qty: z}}
		"""
		production_data = {}
		
		# Get Cutting Report quantities
		cutting_data = frappe.db.sql("""
			SELECT crct.so_item as item_code, SUM(crct.cutting_qty) as total_qty
			FROM `tabCutting Report` cr
			INNER JOIN `tabCutting Report CT` crct ON crct.parent = cr.name
			WHERE cr.supplier = %(supplier)s
				AND cr.docstatus = 1
				AND cr.date BETWEEN %(period_from)s AND %(period_to)s
				AND crct.so_item IS NOT NULL
			GROUP BY crct.so_item
		""", {
			"supplier": self.supplier,
			"period_from": period_from,
			"period_to": period_to
		}, as_dict=True)
		
		# Get Stitching Report quantities
		stitching_data = frappe.db.sql("""
			SELECT srct.so_item as item_code, SUM(srct.stitching_qty) as total_qty
			FROM `tabStitching Report` sr
			INNER JOIN `tabStitching Report CT` srct ON srct.parent = sr.name
			WHERE sr.supplier = %(supplier)s
				AND sr.docstatus = 1
				AND sr.date BETWEEN %(period_from)s AND %(period_to)s
				AND srct.so_item IS NOT NULL
			GROUP BY srct.so_item
		""", {
			"supplier": self.supplier,
			"period_from": period_from,
			"period_to": period_to
		}, as_dict=True)
		
		# Get Packing Report quantities
		packing_data = frappe.db.sql("""
			SELECT prct.so_item as item_code, SUM(prct.packaging_qty) as total_qty
			FROM `tabPacking Report` pr
			INNER JOIN `tabPacking Report CT` prct ON prct.parent = pr.name
			WHERE pr.supplier = %(supplier)s
				AND pr.docstatus = 1
				AND pr.date BETWEEN %(period_from)s AND %(period_to)s
				AND prct.so_item IS NOT NULL
			GROUP BY prct.so_item
		""", {
			"supplier": self.supplier,
			"period_from": period_from,
			"period_to": period_to
		}, as_dict=True)
		
		# Combine data
		for item in cutting_data:
			item_code = item.item_code
			if item_code not in production_data:
				production_data[item_code] = {}
			production_data[item_code]["cutting_qty"] = flt(item.total_qty)
		
		for item in stitching_data:
			item_code = item.item_code
			if item_code not in production_data:
				production_data[item_code] = {}
			production_data[item_code]["stitching_qty"] = flt(item.total_qty)
		
		for item in packing_data:
			item_code = item.item_code
			if item_code not in production_data:
				production_data[item_code] = {}
			production_data[item_code]["packing_qty"] = flt(item.total_qty)
		
		return production_data
	
	def build_references(self, period_from, period_to):
		"""Build references string for Delivery Notes and Reports"""
		references = []
		
		# Get Delivery Note references linked through Purchase Orders
		dn_refs_po = frappe.db.sql("""
			SELECT DISTINCT dn.name
			FROM `tabDelivery Note Item` dni
			INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
			LEFT JOIN `tabPurchase Order Item` poi ON poi.name = dni.purchase_order_item
			LEFT JOIN `tabPurchase Order` po ON po.name = poi.parent
			WHERE po.supplier = %(supplier)s
				AND dn.docstatus = 1
				AND dn.posting_date BETWEEN %(period_from)s AND %(period_to)s
			ORDER BY dn.name
		""", {
			"supplier": self.supplier,
			"period_from": period_from,
			"period_to": period_to
		}, as_list=True)
		
		# Get Delivery Note references if supplier is customer
		try:
			supplier_doc = frappe.get_doc("Supplier", self.supplier)
			customer_name = None
			if hasattr(supplier_doc, 'customer') and supplier_doc.customer:
				customer_name = supplier_doc.customer
		except:
			customer_name = None
		
		dn_refs_customer = []
		if customer_name:
			dn_refs_customer = frappe.db.sql("""
				SELECT DISTINCT dn.name
				FROM `tabDelivery Note` dn
				INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
				WHERE dn.customer = %(customer)s
					AND dn.docstatus = 1
					AND dn.posting_date BETWEEN %(period_from)s AND %(period_to)s
				ORDER BY dn.name
			""", {
				"customer": customer_name,
				"period_from": period_from,
				"period_to": period_to
			}, as_list=True)
		
		# Combine and deduplicate
		all_dn_refs = list(set([ref[0] for ref in dn_refs_po] + [ref[0] for ref in dn_refs_customer]))
		if all_dn_refs:
			references.append("Delivery Notes: " + ", ".join(sorted(all_dn_refs)))
		
		# Get Purchase Receipt references
		pr_refs = frappe.db.sql("""
			SELECT DISTINCT pr.name
			FROM `tabPurchase Receipt` pr
			INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
			WHERE pr.supplier = %(supplier)s
				AND pr.docstatus = 1
				AND pr.posting_date BETWEEN %(period_from)s AND %(period_to)s
			ORDER BY pr.name
		""", {
			"supplier": self.supplier,
			"period_from": period_from,
			"period_to": period_to
		}, as_list=True)
		
		if pr_refs:
			references.append("Purchase Receipts: " + ", ".join([ref[0] for ref in pr_refs]))
		
		# Get Report references
		report_refs = []
		
		cutting_refs = frappe.db.sql("""
			SELECT DISTINCT name
			FROM `tabCutting Report`
			WHERE supplier = %(supplier)s
				AND docstatus = 1
				AND date BETWEEN %(period_from)s AND %(period_to)s
			ORDER BY name
		""", {
			"supplier": self.supplier,
			"period_from": period_from,
			"period_to": period_to
		}, as_list=True)
		
		if cutting_refs:
			report_refs.append("Cutting: " + ", ".join([ref[0] for ref in cutting_refs]))
		
		stitching_refs = frappe.db.sql("""
			SELECT DISTINCT name
			FROM `tabStitching Report`
			WHERE supplier = %(supplier)s
				AND docstatus = 1
				AND date BETWEEN %(period_from)s AND %(period_to)s
			ORDER BY name
		""", {
			"supplier": self.supplier,
			"period_from": period_from,
			"period_to": period_to
		}, as_list=True)
		
		if stitching_refs:
			report_refs.append("Stitching: " + ", ".join([ref[0] for ref in stitching_refs]))
		
		packing_refs = frappe.db.sql("""
			SELECT DISTINCT name
			FROM `tabPacking Report`
			WHERE supplier = %(supplier)s
				AND docstatus = 1
				AND date BETWEEN %(period_from)s AND %(period_to)s
			ORDER BY name
		""", {
			"supplier": self.supplier,
			"period_from": period_from,
			"period_to": period_to
		}, as_list=True)
		
		if packing_refs:
			report_refs.append("Packing: " + ", ".join([ref[0] for ref in packing_refs]))
		
		if report_refs:
			references.append(" | ".join(report_refs))
		
		self.references = "\n".join(references) if references else ""


@frappe.whitelist()
def create_rate_cards_for_items(supplier, item_codes, valid_from, valid_to=None, default_rate=0):
	"""
	Create Subcontractor Rate Cards for multiple items
	
	Args:
		supplier: Supplier name
		item_codes: List of item codes
		valid_from: Valid from date
		valid_to: Valid to date (optional)
		default_rate: Default rate to use for all items
	
	Returns:
		int: Number of rate cards created
	"""
	if not supplier or not item_codes:
		frappe.throw(_("Supplier and Item Codes are required"))
	
	if not isinstance(item_codes, list):
		item_codes = [item_codes]
	
	created_count = 0
	for item_code in item_codes:
		if not item_code:
			continue
		
		# Check if rate card already exists
		existing = frappe.db.exists("Subcontractor Rate Card", {
			"supplier": supplier,
			"item_code": item_code,
			"valid_from": valid_from
		})
		
		if not existing:
			try:
				rate_card = frappe.get_doc({
					"doctype": "Subcontractor Rate Card",
					"supplier": supplier,
					"item_code": item_code,
					"rate_per_pcs": flt(default_rate),
					"valid_from": valid_from,
					"valid_to": valid_to,
					"uom": "PCS"
				})
				rate_card.insert()
				created_count += 1
			except Exception as e:
				frappe.log_error(f"Error creating rate card for {item_code}: {str(e)}")
	
		return created_count


@frappe.whitelist()
def refresh_rates(docname):
	"""
	Refresh rates for existing billing items
	Useful when rate cards are added after billing generation
	
	Args:
		docname: Name of Subcontractor Production Billing document
	
	Returns:
		dict: {updated: count, missing: [item_codes]}
	"""
	doc = frappe.get_doc("Subcontractor Production Billing", docname)
	updated_count = 0
	missing_items = []
	
	for item in doc.billing_items:
		rate_info = get_rate(doc.supplier, item.item_code, doc.posting_date)
		if rate_info:
			new_rate = flt(rate_info.get("rate_per_pcs", 0))
			if new_rate > 0:
				item.rate = new_rate
				item.amount = flt(item.final_payable_qty) * new_rate
				updated_count += 1
			else:
				missing_items.append(item.item_code)
		else:
			missing_items.append(item.item_code)
	
	# Save the document
	doc.calculate_total()
	doc.save()
	
	return {
		"updated": updated_count,
		"missing": missing_items
	}


# Import the get_rate function
from manufacturing_addon.manufacturing_addon.doctype.subcontractor_rate_card.subcontractor_rate_card import get_rate

