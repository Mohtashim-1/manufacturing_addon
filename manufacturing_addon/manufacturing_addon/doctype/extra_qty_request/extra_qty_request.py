# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ExtraQtyRequest(Document):
	def on_load(self):
		"""Populate actual quantities when document is loaded"""
		print(f"🔍 DEBUG: on_load() called for Extra Qty Request: {self.name}")
		self.populate_actual_quantities()

	@frappe.whitelist()
	def refresh_actual_quantities(self):
		"""Manually refresh actual quantities - can be called from client side"""
		print(f"🔍 DEBUG: refresh_actual_quantities() called for Extra Qty Request: {self.name}")
		self.populate_actual_quantities()
		return {"status": "success", "message": "Actual quantities refreshed"}

	@frappe.whitelist()
	def debug_warehouse_stock(self):
		"""Debug method to check warehouse and stock"""
		print(f"🔍 DEBUG: debug_warehouse_stock() called for Extra Qty Request: {self.name}")
		
		from_warehouse = getattr(self, "from_warehouse", None)
		company = getattr(self, "company", None)
		
		print(f"🔍 DEBUG: from_warehouse: {from_warehouse}, company: {company}")
		
		# Check if warehouse exists
		warehouse_exists = frappe.db.exists("Warehouse", from_warehouse)
		print(f"🔍 DEBUG: Warehouse exists: {warehouse_exists}")
		
		# Check total bins in warehouse
		total_bins = frappe.db.count("Bin", {"warehouse": from_warehouse})
		print(f"🔍 DEBUG: Total bins in warehouse: {total_bins}")
		
		# Check if there are any items with stock
		stocked_items = frappe.db.sql("""
			SELECT COUNT(*) as count
			FROM `tabBin` b
			WHERE b.warehouse = %s AND b.actual_qty > 0
		""", (from_warehouse,), as_dict=True)
		
		print(f"🔍 DEBUG: Items with stock: {stocked_items}")
		
		# Get sample items from the warehouse
		sample_items = frappe.db.sql("""
			SELECT b.item_code, b.actual_qty
			FROM `tabBin` b
			WHERE b.warehouse = %s
			ORDER BY b.actual_qty DESC
			LIMIT 10
		""", (from_warehouse,), as_dict=True)
		
		print(f"🔍 DEBUG: Sample items: {sample_items}")
		
		return {
			"from_warehouse": from_warehouse,
			"company": company,
			"warehouse_exists": warehouse_exists,
			"total_bins": total_bins,
			"stocked_items": stocked_items[0].count if stocked_items else 0,
			"sample_items": sample_items
		}

	@frappe.whitelist()
	def test_stock_query(self):
		"""Test method to debug stock queries"""
		print(f"🔍 DEBUG: test_stock_query() called for Extra Qty Request: {self.name}")
		
		from_warehouse = getattr(self, "from_warehouse", None)
		company = getattr(self, "company", None)
		
		print(f"🔍 DEBUG: from_warehouse: {from_warehouse}, company: {company}")
		
		if not from_warehouse or not company:
			return {"error": "Missing warehouse or company", "from_warehouse": from_warehouse, "company": company}
		
		# Test with a simple query
		test_results = frappe.db.sql("""
			SELECT b.item_code, b.warehouse, b.actual_qty
			FROM `tabBin` b
			WHERE b.warehouse = %s
			LIMIT 5
		""", (from_warehouse,), as_dict=True)
		
		print(f"🔍 DEBUG: Test query results: {test_results}")
		
		return {
			"from_warehouse": from_warehouse,
			"company": company,
			"test_results": test_results
		}

	def populate_actual_quantities(self):
		"""Populate actual_qty_at_warehouse and actual_qty_at_company for all items"""
		print(f"🔍 DEBUG: populate_actual_quantities() called for Extra Qty Request: {self.name}")
		if not self.extra_qty_request_item:
			print(f"🔍 DEBUG: No items found in extra_qty_request_item")
			return
			
		try:
			from_warehouse = getattr(self, "from_warehouse", None)
			company = getattr(self, "company", None)
			
			print(f"🔍 DEBUG: from_warehouse: {from_warehouse}, company: {company}")
			
			if not from_warehouse or not company:
				print(f"🔍 DEBUG: Missing warehouse or company - cannot populate actual quantities")
				frappe.msgprint(f"⚠️ Missing warehouse or company - cannot populate actual quantities")
				return
			
			# Get all item codes
			all_item_codes = [item.item for item in self.extra_qty_request_item if item.item]
			print(f"🔍 DEBUG: Item codes found: {all_item_codes}")
			if not all_item_codes:
				print(f"🔍 DEBUG: No item codes found")
				return
			
			# Get actual quantities at warehouse
			warehouse_balances = {}
			if from_warehouse and all_item_codes:
				placeholders = ",".join(["%s"] * len(all_item_codes))
				params = all_item_codes + [from_warehouse]
				print(f"🔍 DEBUG: Querying warehouse balances with params: {params}")
				results = frappe.db.sql(
					f"""
					SELECT b.item_code, b.actual_qty
					FROM `tabBin` b
					WHERE b.item_code IN ({placeholders}) AND b.warehouse = %s
					""",
					params, as_dict=True
				)
				print(f"🔍 DEBUG: Warehouse balance results: {results}")
				for row in results:
					warehouse_balances[row.item_code] = flt(row.actual_qty)
			
			# Get actual quantities at company
			company_balances = {}
			if company and all_item_codes:
				placeholders = ",".join(["%s"] * len(all_item_codes))
				params = all_item_codes + [company]
				print(f"🔍 DEBUG: Querying company balances with params: {params}")
				results = frappe.db.sql(
					f"""
					SELECT b.item_code, SUM(b.actual_qty) AS qty
					FROM `tabBin` b
					JOIN `tabWarehouse` w ON w.name = b.warehouse
					WHERE b.item_code IN ({placeholders}) AND w.company = %s AND w.is_group = 0
					GROUP BY b.item_code
					""",
					params, as_dict=True
				)
				print(f"🔍 DEBUG: Company balance results: {results}")
				for row in results:
					company_balances[row.item_code] = flt(row.qty)
			
			# Update the child table items
			updated_count = 0
			for item in self.extra_qty_request_item:
				if not item.item:
					continue
					
				old_warehouse_qty = getattr(item, "actual_qty_at_warehouse", 0)
				old_company_qty = getattr(item, "actual_qty_at_company", 0)
				
				item.actual_qty_at_warehouse = warehouse_balances.get(item.item, 0)
				item.actual_qty_at_company = company_balances.get(item.item, 0)
				
				print(f"🔍 DEBUG: Item {item.item} - Warehouse: {old_warehouse_qty} -> {item.actual_qty_at_warehouse}, Company: {old_company_qty} -> {item.actual_qty_at_company}")
				updated_count += 1
			
			print(f"🔍 DEBUG: Updated {updated_count} items with actual quantities")
			frappe.msgprint(f"✅ Updated {updated_count} items with actual stock quantities")
				
		except Exception as e:
			frappe.log_error(f"Error in populate_actual_quantities for {self.name}: {str(e)}")
			print(f"❌ DEBUG: Error populating actual quantities: {e}")
			frappe.msgprint(f"❌ Error populating actual quantities: {e}")

	def on_submit(self):
		print(f"🔍 DEBUG: on_submit() called for document: {self.name}")
		frappe.msgprint(f"🔍 DEBUG: on_submit() called for document: {self.name}")
		self.create_stock_entry()

	def create_stock_entry(self):
		print(f"🔍 DEBUG: create_stock_entry() called for document: {self.name}")
		frappe.msgprint(f"🔍 DEBUG: create_stock_entry() called for document: {self.name}")
		# Resolve warehouses: prefer fields on this doc; else pull from linked WOTM
		from_warehouse = getattr(self, "from_warehouse", None)
		to_warehouse = getattr(self, "to_warehouse", None)
		if (not from_warehouse or not to_warehouse) and getattr(self, "work_order_transfer_maanger", None):
			try:
				wotm = frappe.get_doc("Work Order Transfer Manager", self.work_order_transfer_maanger)
				from_warehouse = from_warehouse or getattr(wotm, "source_warehouse", None)
				to_warehouse = to_warehouse or getattr(wotm, "target_warehouse", None)
			except Exception:
				pass

		# Build items from child table rows
		child_rows = list(getattr(self, "extra_qty_request_item", []) or [])
		if not child_rows:
			frappe.msgprint("No items to transfer on Extra Qty Request.")
			return

		# Basic validation
		if not from_warehouse or not to_warehouse:
			raise frappe.ValidationError("Source and Target Warehouses are required to create Stock Entry.")

		print(f"🔍 DEBUG: Creating stock entry for Extra Qty Request: {self.name}")
		frappe.msgprint(f"🔍 DEBUG: Creating stock entry for Extra Qty Request: {self.name}")
		se = frappe.new_doc("Stock Entry")
		se.company = getattr(self, "company", None) or frappe.defaults.get_global_default("company")
		se.stock_entry_type = "Material Transfer for Manufacture"
		se.from_warehouse = from_warehouse
		se.to_warehouse = to_warehouse
		# Link back
		se.work_order_transfer_manager = getattr(self, "work_order_transfer_maanger", None)
		se.extra_qty_request = self.name

		for row in child_rows:
			# Get the actual stock quantity at warehouse instead of just the requested qty
			actual_qty_at_warehouse = getattr(row, "actual_qty_at_warehouse", 0) or 0
			requested_qty = getattr(row, "qty", 0) or 0
			
			# Use the actual available quantity, but don't exceed the requested quantity
			transfer_qty = min(actual_qty_at_warehouse, requested_qty)
			
			if transfer_qty <= 0:
				print(f"🔍 DEBUG: Skipping item {getattr(row, 'item', 'Unknown')} - no stock available (actual: {actual_qty_at_warehouse}, requested: {requested_qty})")
				frappe.msgprint(f"⚠️ No stock available for item {getattr(row, 'item', 'Unknown')} (Available: {actual_qty_at_warehouse}, Requested: {requested_qty})")
				continue
				
			print(f"🔍 DEBUG: Transferring {transfer_qty} of {getattr(row, 'item', 'Unknown')} (actual stock: {actual_qty_at_warehouse}, requested: {requested_qty})")
			
			se.append("items", {
				"item_code": getattr(row, "item", None),
				"qty": transfer_qty,  # Use actual available quantity
				"uom": getattr(row, "uom", None),
				"from_warehouse": from_warehouse,
				"to_warehouse": to_warehouse,
				"is_finished_item": 0,
			})

		print(f"🔍 DEBUG: About to insert stock entry: {se.name}")
		frappe.msgprint(f"🔍 DEBUG: About to insert stock entry: {se.name}")
		se.insert(ignore_permissions=True)
		se.submit()
		# Save reference on Extra Qty Request without triggering re-submit
		frappe.db.set_value(self.doctype, self.name, "stock_entry", se.name)
		print(f"🔍 DEBUG: Stock entry submitted: {se.name}")
		frappe.msgprint(f"🔍 DEBUG: Stock entry submitted: {se.name}")

	def on_cancel(self):
		print(f"🔍 DEBUG: on_cancel() called for document: {self.name}")
		frappe.msgprint(f"🔍 DEBUG: on_cancel() called for document: {self.name}")
		stock_entry_name = frappe.db.get_value(self.doctype, self.name, "stock_entry")
		if stock_entry_name and frappe.db.exists("Stock Entry", stock_entry_name):
			se = frappe.get_doc("Stock Entry", stock_entry_name)
			if se.docstatus == 1:
				se.cancel()
				print(f"🔍 DEBUG: Stock entry cancelled: {se.name}")
				frappe.msgprint(f"🔍 DEBUG: Stock entry cancelled: {se.name}")
		
