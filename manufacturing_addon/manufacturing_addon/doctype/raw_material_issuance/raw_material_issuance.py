# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RawMaterialIssuance(Document):
	def validate(self):
		if not self.from_warehouse or not self.to_warehouse:
			frappe.throw("From Warehouse and To Warehouse are required.")
		
		# Note: Allowing quantities to exceed pending on planning rows
		# This allows flexibility for additional material requirements

	@frappe.whitelist()
	def get_from_sales_order(self):
		"""Get items from Sales Order by exploding BOMs"""
		if not self.sales_order:
			frappe.throw("Set Sales Order first.")
		
		return _populate_items_from_sales_order(self)

	@frappe.whitelist()
	def get_from_planning(self):
		"""Get pending items from Raw Material Transfer Planning"""
		import frappe
		frappe.log_error(f"[RMTI] get_from_planning START - Planning: {self.planning}", "RMTI Debug")
		
		if not self.planning:
			frappe.log_error("[RMTI] ERROR: No planning selected", "RMTI Debug")
			frappe.throw("Select a Raw Material Transfer Planning.")
		
		# Refresh issued_qty from stock entries before reading planning data
		planning_doc = frappe.get_doc("Raw Material Transfer Planning", self.planning)
		if planning_doc.sales_order:
			planning_doc._update_issued_qty_from_stock_entries()
			planning_doc._refresh_availability_rows()
			planning_doc.set_status_and_totals()
			
			# Update child table rows directly using db_set to bypass submit restrictions
			for rm_row in planning_doc.rmtp_raw_material:
				frappe.db.set_value(
					"RMTP Raw Material",
					rm_row.name,
					{
						"issued_qty": rm_row.issued_qty,
						"pending_qty": rm_row.pending_qty,
						"available_in_from_wh": rm_row.available_in_from_wh,
						"available_in_company": rm_row.available_in_company
					},
					update_modified=False
				)
			
			# Update parent totals using db_set
			frappe.db.set_value(
				"Raw Material Transfer Planning",
				self.planning,
				{
					"total_planned_qty": planning_doc.total_planned_qty,
					"total_issued_qty": planning_doc.total_issued_qty,
					"total_pending_qty": planning_doc.total_pending_qty,
					"status": planning_doc.status
				},
				update_modified=False
			)
		
		frappe.log_error(f"[RMTI] Querying RMTP Raw Material for parent: {self.planning}", "RMTI Debug")
		
		# Try to get child table rows directly from database first
		raw_material_rows = frappe.get_all(
			"RMTP Raw Material",
			filters={"parent": self.planning, "parenttype": "Raw Material Transfer Planning"},
			fields=["name", "item_code", "item_name", "stock_uom", "qty", "issued_qty", "pending_qty"],
			order_by="idx asc"
		)
		
		frappe.log_error(f"[RMTI] Found {len(raw_material_rows)} raw material rows", "RMTI Debug")
		
		if not raw_material_rows:
			frappe.log_error(f"[RMTI] ERROR: No raw materials found for planning {self.planning}", "RMTI Debug")
			frappe.throw("The selected planning document has no raw materials. Please run 'Explode BOMs' on the planning document first.")
		
		# Log first few rows for debugging
		if len(raw_material_rows) > 0:
			first_row = raw_material_rows[0]
			frappe.log_error(
				f"[RMTI] First row: {first_row.get('item_code', 'N/A')} - qty:{first_row.get('qty', 0)} pending:{first_row.get('pending_qty', 0)}",
				"RMTI Debug"
			)
		
		# Calculate pending_qty if not already set
		total_rows = len(raw_material_rows)
		rows_with_pending = []
		
		for d in raw_material_rows:
			# Calculate pending_qty
			qty = d.get("qty") or 0
			issued_qty = d.get("issued_qty") or 0
			pending = max(float(qty) - float(issued_qty), 0)
			
			# Log only essential info (truncate item_code if too long)
			item_code = str(d.get('item_code', 'N/A'))[:20] if d.get('item_code') else 'N/A'
			row_name = str(d.get('name', 'N/A'))[:15] if d.get('name') else 'N/A'
			frappe.log_error(
				f"[RMTI] {row_name}: {item_code} q:{qty} i:{issued_qty} p:{pending}",
				"RMTI Debug"
			)
			
			if pending > 0 and d.get("item_code"):
				rows_with_pending.append({
					"name": d.get("name"),
					"item_code": d.get("item_code"),
					"item_name": d.get("item_name"),
					"stock_uom": d.get("stock_uom"),
					"pending_qty": pending
				})
		
		frappe.log_error(f"[RMTI] Found {len(rows_with_pending)} rows with pending qty > 0", "RMTI Debug")
		
		if not rows_with_pending:
			frappe.log_error(
				f"[RMTI] ERROR: No pending items. Total rows: {total_rows}",
				"RMTI Debug"
			)
			frappe.throw(
				f"No pending items found. The planning document has {total_rows} raw material row(s), "
				"but all have been issued (pending_qty = 0).",
				title="No Pending Items"
			)
		
		self.items = []
		for d in rows_with_pending:
			# Fetch item details if not present
			if not d.get("item_name") or not d.get("stock_uom"):
				item_details = frappe.db.get_value(
					"Item",
					d.get("item_code"),
					["item_name", "stock_uom"],
					as_dict=True
				)
				if item_details:
					d["item_name"] = d.get("item_name") or item_details.get("item_name")
					d["stock_uom"] = d.get("stock_uom") or item_details.get("stock_uom")
			
			item_dict = {
				"planning": self.planning,
				"planning_row": d.get("name"),
				"item_code": d.get("item_code"),
				"item_name": d.get("item_name"),
				"stock_uom": d.get("stock_uom"),
				"qty": d.get("pending_qty")
			}
			
			# Log only essential info (truncate item_code if too long)
			item_code = str(d.get("item_code", "N/A"))[:25] if d.get("item_code") else "N/A"
			pending_qty = d.get('pending_qty', 0)
			frappe.log_error(f"[RMTI] Append: {item_code} q:{pending_qty}", "RMTI Debug")
			self.append("items", item_dict)
		
		frappe.log_error(f"[RMTI] Created {len(self.items)} items", "RMTI Debug")
		
		if not self.items:
			frappe.log_error("[RMTI] ERROR: Failed to create items", "RMTI Debug")
			frappe.throw("Failed to create items. Please check the planning document data.")
		
		self._refresh_availability()
		frappe.log_error(f"[RMTI] get_from_planning END - Returning success with {len(self.items)} items", "RMTI Debug")
		return {"message": f"Loaded {len(self.items)} pending item(s) from planning."}

	@frappe.whitelist()
	def recalc_availability(self):
		"""Recalculate availability for all items"""
		self._refresh_availability()
		return {"message": "Availability recalculated."}

	def _refresh_availability(self):
		"""Refresh availability for all items"""
		wh_list = [w.name for w in frappe.get_all("Warehouse", filters={"company": self.company})]
		
		for d in self.items:
			d.available_in_from_wh = _bin_qty(d.item_code, self.from_warehouse)
			d.available_in_company = sum(_bin_qty(d.item_code, wh) for wh in wh_list)

	def on_submit(self):
		"""On submit: create Stock Entry and update planning"""
		se = make_stock_entry_from_issuance(self)
		self.db_set("status", "Submitted")
		
		# Update planning issued/pending by recalculating from all sources
		if self.planning:
			plan = frappe.get_doc("Raw Material Transfer Planning", self.planning)
			# Recalculate issued_qty from all sources (Raw Material Issuance + Stock Entries)
			plan._update_issued_qty_from_stock_entries()
			plan._refresh_availability_rows()
			plan.set_status_and_totals()
			
			# Update child table rows directly using db_set
			for rm_row in plan.rmtp_raw_material:
				frappe.db.set_value(
					"RMTP Raw Material",
					rm_row.name,
					{
						"issued_qty": rm_row.issued_qty,
						"pending_qty": rm_row.pending_qty,
						"available_in_from_wh": rm_row.available_in_from_wh,
						"available_in_company": rm_row.available_in_company
					},
					update_modified=False
				)
			
			# Update parent totals using db_set
			if plan.docstatus == 1:
				frappe.db.set_value(
					"Raw Material Transfer Planning",
					self.planning,
					{
						"status": plan.status,
						"total_planned_qty": plan.total_planned_qty,
						"total_issued_qty": plan.total_issued_qty,
						"total_pending_qty": plan.total_pending_qty
					},
					update_modified=False
				)
			else:
				plan.save(ignore_permissions=True)
		
		frappe.msgprint(f"Stock Entry {se.name} created.", alert=True)


def _populate_items_from_sales_order(doc):
	"""Optional: explode BOM like planning and populate doc.items"""
	from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
	
	so_items = frappe.get_all(
		"Sales Order Item",
		fields=["item_code", "qty", "parent"],
		filters={"parent": doc.sales_order}
	)
	
	if not so_items:
		frappe.throw("No items on Sales Order.")
	
	aggregate = {}
	company = doc.company
	
	for row in so_items:
		bom_no = frappe.db.get_value(
			"BOM",
			{"item": row.item_code, "is_default": 1, "is_active": 1},
			"name"
		)
		if not bom_no:
			frappe.throw(f"No active/default BOM for {row.item_code}")
		
		bom_items = get_bom_items_as_dict(
			bom_no,
			company=company,
			qty=row.qty,
			fetch_exploded=True
		)
		
		for ic, meta in bom_items.items():
			if ic not in aggregate:
				aggregate[ic] = {
					"item_name": frappe.db.get_value("Item", ic, "item_name"),
					"uom": meta.get("stock_uom"),
					"qty": 0.0
				}
			aggregate[ic]["qty"] += float(meta.get("qty") or 0)

	doc.items = []
	for ic, meta in aggregate.items():
		doc.append("items", {
			"item_code": ic,
			"item_name": meta["item_name"],
			"stock_uom": meta["uom"],
			"qty": meta["qty"]
		})
	
	doc._refresh_availability()
	return {"message": f"Loaded {len(doc.items)} items from Sales Order BOMs."}


def _bin_qty(item_code, warehouse):
	"""Get bin quantity for item and warehouse"""
	from erpnext.stock.doctype.bin.bin import get_actual_qty
	
	if not item_code or not warehouse:
		return 0
	try:
		return float(get_actual_qty(item_code, warehouse) or 0)
	except Exception:
		return 0


def make_stock_entry_from_issuance(iss_doc):
	"""Create ONE Material Transfer Stock Entry from issuance rows"""
	se = frappe.new_doc("Stock Entry")
	se.company = iss_doc.company
	se.stock_entry_type = frappe.db.get_value(
		"Stock Entry Type",
		{"purpose": "Material Transfer"},
		"name"
	)
	
	if not se.stock_entry_type:
		# Fallback: set purpose directly if no stock entry type found
		se.purpose = "Material Transfer"
	
	se.posting_date = iss_doc.posting_date
	se.from_warehouse = iss_doc.from_warehouse
	se.to_warehouse = iss_doc.to_warehouse
	
	# Add items
	for it in iss_doc.items:
		# Skip zero qty lines
		if not it.qty:
			continue
		
		item_dict = {
			"item_code": it.item_code,
			"qty": it.qty,
			"s_warehouse": iss_doc.from_warehouse,
			"t_warehouse": iss_doc.to_warehouse,
			"uom": it.stock_uom,
			"conversion_factor": 1
		}
		
		# Add custom fields for tracking
		if iss_doc.planning:
			item_dict["custom_raw_material_transfer_planning"] = iss_doc.planning
		if iss_doc.name:
			item_dict["custom_raw_material_transfer_issuance"] = iss_doc.name
		
		se.append("items", item_dict)
	
	se.insert(ignore_permissions=True)
	se.submit()
	
	# Save link on Issuance
	iss_doc.db_set("stock_entry", se.name)
	
	return se
