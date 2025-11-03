# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
from erpnext.stock.doctype.bin.bin import get_actual_qty


class RawMaterialTransferPlanning(Document):
	def validate(self):
		self.set_status_and_totals()

	def set_status_and_totals(self):
		total_planned = sum((d.qty or 0) for d in self.rmtp_raw_material)
		total_issued = sum((d.issued_qty or 0) for d in self.rmtp_raw_material)
		total_pending = sum((d.pending_qty or 0) for d in self.rmtp_raw_material)
		
		self.total_planned_qty = total_planned
		self.total_issued_qty = total_issued
		self.total_pending_qty = total_pending
		
		if total_pending <= 0 and total_planned > 0:
			self.status = "Completed"
		elif total_issued > 0:
			self.status = "Partially Issued"
		else:
			self.status = "Draft"

	@frappe.whitelist()
	def get_finished_from_sales_order(self):
		"""Fetch finished items from Sales Order"""
		self.finished_items = []
		if not self.sales_order:
			frappe.throw("Please set Sales Order.")
		
		soi = frappe.get_all(
			"Sales Order Item",
			fields=["name", "item_code", "item_name", "uom", "qty", "parent"],
			filters={"parent": self.sales_order}
		)
		
		for row in soi:
			self.append("finished_items", {
				"sales_order_item": row.name,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"uom": row.uom,
				"qty": row.qty
			})
		
		return {"message": f"Fetched {len(soi)} finished items."}

	@frappe.whitelist()
	def explode_boms(self):
		"""Explode BOMs for all finished items and aggregate raw materials"""
		if not self.finished_items:
			frappe.throw("No finished items. Use 'Get Finished from Sales Order' first.")
		
		self.rmtp_raw_material = []
		aggregate = {}  # item_code -> dict
		
		for fi in self.finished_items:
			bom_no = fi.bom or frappe.db.get_value(
				"BOM",
				{"item": fi.item_code, "is_default": 1, "is_active": 1},
				"name"
			)
			if not bom_no:
				frappe.throw(f"No active/default BOM found for {fi.item_code}")
			
			# Get BOM items as dict: { item_code: { 'qty': x, 'stock_uom': uom, ... }, ... }
			bom_items = get_bom_items_as_dict(
				bom_no,
				company=self.company,
				qty=fi.qty,
				fetch_exploded=True
			)
			
			for ic, meta in bom_items.items():
				key = ic
				if key not in aggregate:
					aggregate[key] = {
						"item_code": ic,
						"item_name": frappe.db.get_value("Item", ic, "item_name"),
						"stock_uom": meta.get("stock_uom"),
						"qty": 0.0
					}
				aggregate[key]["qty"] += float(meta.get("qty", 0) or 0)

		# Push to child table
		for _, row in sorted(aggregate.items()):
			self.append("rmtp_raw_material", {
				"rmtp_finished_row": None,  # Not set during aggregation since materials can come from multiple finished items
				"item_code": row["item_code"],
				"item_name": row["item_name"],
				"stock_uom": row["stock_uom"],
				"qty": row["qty"],
				"issued_qty": 0.0,
				"pending_qty": row["qty"]
			})
		
		self._refresh_availability_rows()
		self.set_status_and_totals()
		return {"message": f"Exploded BOMs to {len(self.rmtp_raw_material)} raw material rows."}

	@frappe.whitelist()
	def refresh_availability(self):
		"""Refresh availability for all material rows"""
		self._refresh_availability_rows()
		return {"message": "Availability refreshed."}

	def _refresh_availability_rows(self):
		"""Refresh availability for all material rows"""
		# For performance, pre-get all warehouses of company
		wh_list = [w.name for w in frappe.get_all("Warehouse", filters={"company": self.company})]
		
		for d in self.rmtp_raw_material:
			d.available_in_from_wh = self._bin_qty(d.item_code, self.from_warehouse)
			d.available_in_company = sum(self._bin_qty(d.item_code, wh) for wh in wh_list)
			d.pending_qty = max((d.qty or 0) - (d.issued_qty or 0), 0)

	def _bin_qty(self, item_code, warehouse):
		"""Get bin quantity for item and warehouse"""
		if not item_code or not warehouse:
			return 0
		try:
			return float(get_actual_qty(item_code, warehouse) or 0)
		except Exception:
			return 0

	def on_trash(self):
		"""Safety: cannot delete if any materials already issued"""
		if any((d.issued_qty or 0) > 0 for d in self.rmtp_raw_material):
			frappe.throw("Cannot delete: some materials already issued.")