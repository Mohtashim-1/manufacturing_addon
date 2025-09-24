# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ExtraQtyRequest(Document):
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
			qty_value = getattr(row, "qty", 0) or 0
			if qty_value <= 0:
				continue
			se.append("items", {
				"item_code": getattr(row, "item", None),
				"qty": qty_value,
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
		
