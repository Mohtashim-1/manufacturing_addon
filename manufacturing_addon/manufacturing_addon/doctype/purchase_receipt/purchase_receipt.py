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
		# Call parent validate (which calls set_qty_as_per_stock_uom - our override)
		super().validate()
		# After parent validate, ensure stock_qty is preserved if user entered it
		self._preserve_user_entered_stock_qty()
		self._auto_fetch_conversion_factor()
		self._validate_rate_locking()
		self._recalculate_amounts_with_locked_rates()
	
	def _preserve_user_entered_stock_qty(self):
		"""Final check to preserve user-entered stock_qty values after all validations"""
		user_entered_stock_qty = getattr(self, '_user_entered_stock_qty', {})
		
		for item in self.get("items"):
			if not item.item_code or not item.uom or not item.stock_uom or item.uom == item.stock_uom:
				continue
			
			# Restore from stored values - this is the most reliable source
			exact_value = None
			if item.name and item.name in user_entered_stock_qty:
				exact_value = user_entered_stock_qty[item.name]
			elif item.idx in user_entered_stock_qty:
				exact_value = user_entered_stock_qty[item.idx]
			
			# Also check if conversion_factor matches what would be calculated from stock_qty/qty
			# This indicates user entered stock_qty
			if not exact_value and flt(item.stock_qty) and flt(item.qty) and flt(item.qty) > 0 and flt(item.conversion_factor):
				calculated_cf = flt(item.stock_qty) / flt(item.qty)
				# If conversion_factor matches (within precision), user entered stock_qty
				if abs(flt(item.conversion_factor) - calculated_cf) < 0.0001:
					exact_value = flt(item.stock_qty)
					# Store it for future reference
					if item.name:
						if not hasattr(self, '_user_entered_stock_qty'):
							self._user_entered_stock_qty = {}
						self._user_entered_stock_qty[item.name] = exact_value
					elif item.idx:
						if not hasattr(self, '_user_entered_stock_qty'):
							self._user_entered_stock_qty = {}
						self._user_entered_stock_qty[item.idx] = exact_value
			
			# If we have an exact value, ALWAYS restore it to prevent floating-point precision issues
			if exact_value:
				# Calculate what stock_qty would be from qty * conversion_factor
				recalculated_stock_qty = flt(item.qty) * flt(item.conversion_factor)
				# If recalculated value differs from exact value (due to floating point precision),
				# restore the exact user-entered value
				# Use a small tolerance to catch cases like 3200.01 vs 3200
				if abs(flt(item.stock_qty) - exact_value) > 0.0001 or abs(recalculated_stock_qty - exact_value) > 0.0001:
					# Preserve the exact value user entered
					item.stock_qty = exact_value

	def _preserve_rates(self):
		"""Store original rates to prevent auto-change"""
		if not hasattr(self, '_original_rates'):
			self._original_rates = {}
		# Also store user-entered stock_qty values
		if not hasattr(self, '_user_entered_stock_qty'):
			self._user_entered_stock_qty = {}
		
		for item in self.get("items"):
			if item.name:
				self._original_rates[item.name] = {
					'rate': flt(item.rate),
					'qty': flt(item.qty),
					'stock_qty': flt(item.stock_qty),
					'conversion_factor': flt(item.conversion_factor)
				}
				# Store stock_qty if conversion_factor matches what would be calculated from it
				# This indicates user entered stock_qty
				if item.uom and item.stock_uom and item.uom != item.stock_uom:
					if flt(item.stock_qty) and flt(item.qty) and flt(item.qty) > 0 and flt(item.conversion_factor):
						calculated_cf = flt(item.stock_qty) / flt(item.qty)
						if abs(flt(item.conversion_factor) - calculated_cf) < 0.0001:
							# User entered stock_qty, store exact value
							self._user_entered_stock_qty[item.name] = flt(item.stock_qty)
			elif item.rate and flt(item.rate) > 0:
				# For new items, store rate if it's set
				item._original_rate = flt(item.rate)
				# Also store stock_qty for new items
				if item.uom and item.stock_uom and item.uom != item.stock_uom:
					if flt(item.stock_qty) and flt(item.qty) and flt(item.qty) > 0 and flt(item.conversion_factor):
						calculated_cf = flt(item.stock_qty) / flt(item.qty)
						if abs(flt(item.conversion_factor) - calculated_cf) < 0.0001:
							# User entered stock_qty, store exact value
							self._user_entered_stock_qty[item.idx] = flt(item.stock_qty)

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

	def set_qty_as_per_stock_uom(self):
		"""Override to preserve user-entered stock_qty values"""
		# Store user-entered stock_qty values before parent method recalculates them
		user_entered_stock_qty = {}
		for item in self.get("items"):
			if not item.item_code or not item.uom or not item.stock_uom:
				continue
			
			# Only check if UOM != Stock UOM
			if item.uom != item.stock_uom:
				should_preserve = False
				preserve_value = None
				
				if item.name and item.name in getattr(self, '_original_rates', {}):
					original_stock_qty = self._original_rates[item.name].get('stock_qty')
					current_stock_qty = flt(item.stock_qty)
					# If stock_qty changed significantly, user likely entered it manually
					if abs(current_stock_qty - original_stock_qty) > 0.0001:
						should_preserve = True
						preserve_value = current_stock_qty
				
				# ALWAYS check if conversion_factor matches what would be calculated from stock_qty/qty
				# This is the key indicator that user entered stock_qty
				if flt(item.stock_qty) and flt(item.qty) and flt(item.qty) > 0 and flt(item.conversion_factor):
					calculated_cf = flt(item.stock_qty) / flt(item.qty)
					# If conversion_factor matches (within precision), user entered stock_qty
					if abs(flt(item.conversion_factor) - calculated_cf) < 0.0001:
						should_preserve = True
						# Preserve exact value - use current stock_qty, not calculated one
						preserve_value = flt(item.stock_qty)
				
				if should_preserve and preserve_value:
					if item.name:
						user_entered_stock_qty[item.name] = preserve_value
					else:
						user_entered_stock_qty[item.idx] = preserve_value
		
		# Call parent method (which will recalculate stock_qty)
		super().set_qty_as_per_stock_uom()
		
		# CRITICAL: Restore user-entered stock_qty values to preserve exact precision
		# This must happen AFTER parent method to override its recalculation
		for item in self.get("items"):
			if item.name and item.name in user_entered_stock_qty:
				# Restore exact user-entered value - ALWAYS restore if stored
				exact_value = user_entered_stock_qty[item.name]
				# Always restore to preserve exact precision (even if difference is tiny)
				item.stock_qty = exact_value
			elif item.idx in user_entered_stock_qty:
				# For new items without name yet
				exact_value = user_entered_stock_qty[item.idx]
				# Always restore to preserve exact precision (even if difference is tiny)
				item.stock_qty = exact_value

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
				# Store original stock_qty to detect if user manually entered it
				original_stock_qty = None
				if item.name and item.name in getattr(self, '_original_rates', {}):
					original_stock_qty = self._original_rates[item.name].get('stock_qty')
				
				# Check if stock_qty was manually changed (user entered it)
				stock_qty_manually_entered = False
				if original_stock_qty is not None:
					# If stock_qty changed significantly, user likely entered it manually
					if abs(flt(item.stock_qty) - flt(original_stock_qty)) > 0.0001:
						stock_qty_manually_entered = True
				elif flt(item.stock_qty) and flt(item.qty) and flt(item.qty) > 0:
					# If conversion_factor matches what would be calculated from stock_qty, user entered stock_qty
					calculated_cf = flt(item.stock_qty) / flt(item.qty)
					if flt(item.conversion_factor) and abs(flt(item.conversion_factor) - calculated_cf) < 0.0001:
						stock_qty_manually_entered = True
				
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
						# Only recalculate stock_qty if user didn't manually enter it
						if flt(item.qty) and not stock_qty_manually_entered:
							item.stock_qty = flt(item.qty) * flt(item.conversion_factor)
					
					# If still no conversion factor, calculate from stock_qty and qty
					if not flt(item.conversion_factor) and flt(item.qty) and flt(item.stock_qty):
						item.conversion_factor = flt(item.stock_qty) / flt(item.qty)
				else:
					# If conversion_factor exists, check if user entered stock_qty
					if flt(item.stock_qty) and flt(item.qty) and flt(item.qty) > 0:
						# Check if conversion_factor matches what would be calculated from stock_qty
						calculated_cf_from_stock_qty = flt(item.stock_qty) / flt(item.qty)
						if abs(flt(item.conversion_factor) - calculated_cf_from_stock_qty) < 0.0001:
							# User entered stock_qty, conversion_factor was calculated from it
							# CRITICAL: Don't recalculate stock_qty - preserve exact user value
							# Just ensure conversion_factor is correct
							item.conversion_factor = calculated_cf_from_stock_qty
							# DO NOT recalculate stock_qty - preserve exact value
							# Also check if we have stored value and restore it
							user_entered_stock_qty = getattr(self, '_user_entered_stock_qty', {})
							if item.name and item.name in user_entered_stock_qty:
								item.stock_qty = user_entered_stock_qty[item.name]
							elif item.idx in user_entered_stock_qty:
								item.stock_qty = user_entered_stock_qty[item.idx]
						else:
							# Conversion_factor doesn't match - user might have changed conversion_factor
							# Only recalculate stock_qty if user didn't manually enter it
							if not stock_qty_manually_entered and flt(item.qty) and flt(item.conversion_factor):
								item.stock_qty = flt(item.qty) * flt(item.conversion_factor)
					elif flt(item.qty) and flt(item.conversion_factor) and not stock_qty_manually_entered:
						# Recalculate stock_qty from qty and conversion_factor only if user didn't enter it
						item.stock_qty = flt(item.qty) * flt(item.conversion_factor)
