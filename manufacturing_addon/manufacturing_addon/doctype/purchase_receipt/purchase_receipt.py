import frappe
from frappe import _
from frappe.utils import flt
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import PurchaseReceipt
from erpnext.stock.get_item_details import get_conversion_factor


class CustomPurchaseReceipt(PurchaseReceipt):
	def before_validate(self):
		"""Store original rates before validation to prevent auto-change"""
		self._preserve_rates()
		super().before_validate()

	def validate(self):
		super().validate()
		self._auto_fetch_conversion_factor()
		self._validate_rate_locking()
		self._recalculate_amounts_with_locked_rates()

	def _preserve_rates(self):
		"""Store original rates to prevent auto-change"""
		if not hasattr(self, '_original_rates'):
			self._original_rates = {}
			for item in self.get("items"):
				if item.name:
					self._original_rates[item.name] = {
						'rate': flt(item.rate),
						'qty': flt(item.qty),
						'stock_qty': flt(item.stock_qty),
						'conversion_factor': flt(item.conversion_factor)
					}
				elif item.rate and flt(item.rate) > 0:
					# For new items, store rate if it's set
					item._original_rate = flt(item.rate)

	def _validate_rate_locking(self):
		"""Ensure rate never changes when qty, stock_qty, or conversion_factor is edited"""
		for item in self.get("items"):
			original_rate = None
			
			# Get original rate from stored rates or item attribute
			if item.name and item.name in getattr(self, '_original_rates', {}):
				original_rate = self._original_rates[item.name].get('rate')
			elif hasattr(item, '_original_rate'):
				original_rate = item._original_rate
			elif item.rate and flt(item.rate) > 0:
				# Store current rate as original if not stored
				original_rate = flt(item.rate)
				item._original_rate = original_rate
			
			# If we have an original rate and current rate differs, restore it
			if original_rate and original_rate > 0:
				current_rate = flt(item.rate)
				if current_rate != original_rate:
					# Check if qty, stock_qty, or conversion_factor changed
					original = self._original_rates.get(item.name, {}) if item.name else {}
					qty_changed = flt(item.qty) != original.get('qty', 0)
					stock_qty_changed = flt(item.stock_qty) != original.get('stock_qty', 0)
					conversion_factor_changed = flt(item.conversion_factor) != original.get('conversion_factor', 0)
					
					# If any quantity field changed, lock the rate
					if qty_changed or stock_qty_changed or conversion_factor_changed:
						item.rate = original_rate
						item._original_rate = original_rate

	def _recalculate_amounts_with_locked_rates(self):
		"""Recalculate amounts using locked rates"""
		for item in self.get("items"):
			# Get locked rate
			locked_rate = None
			if hasattr(item, '_original_rate') and item._original_rate:
				locked_rate = item._original_rate
			elif item.name and item.name in getattr(self, '_original_rates', {}):
				locked_rate = self._original_rates[item.name].get('rate')
			elif item.rate and flt(item.rate) > 0:
				locked_rate = flt(item.rate)
			
			# Calculate amount = qty × rate (rate is locked)
			if locked_rate and locked_rate > 0 and flt(item.qty):
				item.amount = flt(item.qty) * locked_rate
				item.rate = locked_rate  # Ensure rate stays locked

	def _auto_fetch_conversion_factor(self):
		"""Auto-fetch conversion factor from Item master or PO if Purchase UOM != Stock UOM"""
		for item in self.get("items"):
			if not item.item_code or not item.uom or not item.stock_uom:
				continue
			
			# Only auto-fetch if UOM != Stock UOM
			if item.uom != item.stock_uom:
				# If conversion_factor is not set or is 0, fetch it
				if not flt(item.conversion_factor):
					conversion_factor = None
					
					# Priority 1: Get from PO item if PR is against PO
					if item.purchase_order_item:
						conversion_factor = frappe.db.get_value(
							"Purchase Order Item",
							item.purchase_order_item,
							"conversion_factor"
						)
					
					# Priority 2: Get from Item master using get_conversion_factor
					if not conversion_factor:
						try:
							conv_data = get_conversion_factor(item.item_code, item.uom)
							if conv_data and conv_data.get("conversion_factor"):
								conversion_factor = conv_data.get("conversion_factor")
						except:
							pass
					
					if conversion_factor:
						item.conversion_factor = flt(conversion_factor)
						# Recalculate stock_qty
						if flt(item.qty):
							item.stock_qty = flt(item.qty) * flt(item.conversion_factor)
					
					# If still no conversion factor, calculate from stock_qty and qty
					if not flt(item.conversion_factor) and flt(item.qty) and flt(item.stock_qty):
						item.conversion_factor = flt(item.stock_qty) / flt(item.qty)
				else:
					# If conversion_factor exists, ensure stock_qty matches
					# But if user entered stock_qty, calculate conversion_factor from it
					if flt(item.stock_qty) and flt(item.qty) and flt(item.qty) > 0:
						# User entered stock_qty, calculate conversion_factor
						item.conversion_factor = flt(item.stock_qty) / flt(item.qty)
					elif flt(item.qty) and flt(item.conversion_factor):
						# Recalculate stock_qty from qty and conversion_factor
						item.stock_qty = flt(item.qty) * flt(item.conversion_factor)
