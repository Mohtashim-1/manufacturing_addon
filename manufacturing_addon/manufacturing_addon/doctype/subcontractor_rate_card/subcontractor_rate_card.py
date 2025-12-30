# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class SubcontractorRateCard(Document):
	def validate(self):
		# Validate that valid_to is after valid_from
		if self.valid_to and self.valid_from and self.valid_to < self.valid_from:
			frappe.throw(_("Valid To date must be after Valid From date"))
		
		# Check for overlapping rate cards for same supplier and item
		self.check_overlapping_rates()
	
	def check_overlapping_rates(self):
		"""Check if there are overlapping rate cards for the same supplier and item"""
		if not self.supplier or not self.item_code or not self.valid_from:
			return
		
		filters = {
			"supplier": self.supplier,
			"item_code": self.item_code,
			"name": ["!=", self.name] if self.name else None
		}
		
		# Remove None values
		filters = {k: v for k, v in filters.items() if v is not None}
		
		existing_cards = frappe.get_all(
			"Subcontractor Rate Card",
			filters=filters,
			fields=["name", "valid_from", "valid_to"]
		)
		
		for card in existing_cards:
			# Check if dates overlap
			card_from = card.valid_from
			card_to = card.valid_to or "2099-12-31"  # If no valid_to, assume far future
			
			self_from = self.valid_from
			self_to = self.valid_to or "2099-12-31"
			
			# Check overlap: (start1 <= end2) and (start2 <= end1)
			if (self_from <= card_to) and (card_from <= self_to):
				frappe.throw(_(
					"Overlapping rate card found: {0}. "
					"Please adjust the validity period."
				).format(card.name))


@frappe.whitelist()
def get_rate(supplier, item_code, posting_date=None):
	"""
	Get the latest valid rate for a supplier and item on a given date
	
	Args:
		supplier: Supplier name
		item_code: Item code
		posting_date: Date to check validity (defaults to today)
	
	Returns:
		dict: Rate information or None
	"""
	if not posting_date:
		posting_date = frappe.utils.today()
	
	# Convert posting_date to date object for comparison
	from frappe.utils import getdate
	posting_date_obj = getdate(posting_date)
	
	# Find the latest valid rate card
	# First try: Find rate card where posting_date falls within valid_from and valid_to
	rate_card = frappe.db.sql("""
		SELECT name, rate_per_pcs, uom, valid_from, valid_to
		FROM `tabSubcontractor Rate Card`
		WHERE supplier = %(supplier)s
			AND item_code = %(item_code)s
			AND valid_from <= %(posting_date)s
			AND (valid_to IS NULL OR valid_to >= %(posting_date)s)
		ORDER BY valid_from DESC
		LIMIT 1
	""", {
		"supplier": supplier,
		"item_code": item_code,
		"posting_date": posting_date
	}, as_dict=True)
	
	if rate_card:
		return rate_card[0]
	
	# Fallback: If no rate card found for the exact date, get the latest rate card
	# (in case valid_from is in the future but user wants to use it)
	latest_rate_card = frappe.db.sql("""
		SELECT name, rate_per_pcs, uom, valid_from, valid_to
		FROM `tabSubcontractor Rate Card`
		WHERE supplier = %(supplier)s
			AND item_code = %(item_code)s
		ORDER BY valid_from DESC
		LIMIT 1
	""", {
		"supplier": supplier,
		"item_code": item_code
	}, as_dict=True)
	
	if latest_rate_card:
		return latest_rate_card[0]
	
	return None

