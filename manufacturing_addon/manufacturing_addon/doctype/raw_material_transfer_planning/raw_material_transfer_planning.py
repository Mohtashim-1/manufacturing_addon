# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
from erpnext.stock.doctype.bin.bin import get_actual_qty


class RawMaterialTransferPlanning(Document):
	def validate(self):
		# Update issued_qty from stock entries if sales order is set
		if self.sales_order and self.rmtp_raw_material:
			self._update_issued_qty_from_stock_entries()
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

		# Fetch items from Material Requests linked to this Sales Order
		if self.sales_order:
			mr_items = self._get_items_from_material_requests()
			for ic, mr_data in mr_items.items():
				if ic not in aggregate:
					aggregate[ic] = {
						"item_code": ic,
						"item_name": mr_data.get("item_name"),
						"stock_uom": mr_data.get("stock_uom"),
						"qty": 0.0
					}
				aggregate[ic]["qty"] += float(mr_data.get("qty", 0) or 0)

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
		
		# Update issued_qty from stock entries against sales order cost center
		self._update_issued_qty_from_stock_entries()
		
		self._refresh_availability_rows()
		self.set_status_and_totals()
		return {"message": f"Exploded BOMs to {len(self.rmtp_raw_material)} raw material rows."}

	@frappe.whitelist()
	def refresh_availability(self):
		"""Refresh availability for all material rows"""
		self._refresh_availability_rows()
		return {"message": "Availability refreshed."}

	@frappe.whitelist()
	def refresh_issued_qty(self):
		"""Refresh issued_qty from stock entries against sales order cost center"""
		self._update_issued_qty_from_stock_entries()
		self._refresh_availability_rows()
		self.set_status_and_totals()
		return {"message": "Issued quantities refreshed from stock entries."}

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

	def _get_items_from_material_requests(self):
		"""Fetch items from Material Requests linked to this Sales Order via custom_sales_order"""
		if not self.sales_order:
			return {}
		
		material_requests = frappe.get_all(
			"Material Request",
			filters={"custom_sales_order": self.sales_order, "docstatus": ["<", 2]},
			fields=["name"]
		)
		
		if not material_requests:
			return {}
		
		mr_items = {}
		for mr in material_requests:
			mr_item_rows = frappe.get_all(
				"Material Request Item",
				filters={"parent": mr.name},
				fields=["item_code", "qty", "stock_uom", "item_name"]
			)
			
			for item_row in mr_item_rows:
				ic = item_row.item_code
				if ic not in mr_items:
					# Get item details if not present
					item_name = item_row.item_name or frappe.db.get_value("Item", ic, "item_name")
					stock_uom = item_row.stock_uom or frappe.db.get_value("Item", ic, "stock_uom")
					
					mr_items[ic] = {
						"item_code": ic,
						"item_name": item_name,
						"stock_uom": stock_uom,
						"qty": 0.0
					}
				mr_items[ic]["qty"] += float(item_row.qty or 0)
		
		return mr_items

	def _update_issued_qty_from_stock_entries(self):
		"""Update issued_qty in rmtp_raw_material from stock entries and Raw Material Issuance submissions"""
		# First, get issued_qty from Raw Material Issuance submissions (primary source)
		item_issued_from_rmi = {}
		
		# Get all submitted Raw Material Issuance for this planning
		rmi_list = frappe.get_all(
			"Raw Material Issuance",
			filters={"planning": self.name, "docstatus": 1},
			fields=["name"]
		)
		
		if rmi_list:
			# Get all items from these Raw Material Issuance documents
			rmi_item_names = [rmi.name for rmi in rmi_list]
			rmi_items = frappe.get_all(
				"RMTI Item",
				filters={"parent": ["in", rmi_item_names], "planning_row": ["is", "set"]},
				fields=["item_code", "qty", "planning_row"]
			)
			
			# Aggregate by item_code and planning_row
			for rmi_item in rmi_items:
				if rmi_item.item_code and rmi_item.planning_row:
					key = (rmi_item.item_code, rmi_item.planning_row)
					if key not in item_issued_from_rmi:
						item_issued_from_rmi[key] = 0.0
					item_issued_from_rmi[key] += float(rmi_item.qty or 0)
		
		# Second, get additional stock entries against sales order cost center
		item_issued_from_se = {}
		if self.sales_order:
			# Get sales order cost center
			so_cost_center = frappe.db.get_value("Sales Order", self.sales_order, "cost_center")
			if so_cost_center:
				# Get stock entries from Raw Material Issuance to exclude them
				rmi_stock_entries = []
				if rmi_list:
					rmi_stock_entries = frappe.get_all(
						"Raw Material Issuance",
						filters={"planning": self.name, "docstatus": 1, "stock_entry": ["is", "set"]},
						fields=["stock_entry"]
					)
					rmi_stock_entries = [se.stock_entry for se in rmi_stock_entries if se.stock_entry]
				
				# Get all stock entries with custom_cost_center matching sales order cost center
				# Exclude those already from Raw Material Issuance
				filters = {
					"custom_cost_center": so_cost_center,
					"docstatus": 1,
					"purpose": ["in", ["Material Transfer", "Material Transfer for Manufacture"]]
				}
				
				# Only add "not in" filter if we have stock entries to exclude
				if rmi_stock_entries:
					filters["name"] = ["not in", rmi_stock_entries]
				
				stock_entries = frappe.get_all(
					"Stock Entry",
					filters=filters,
					fields=["name"]
				)
				
				if stock_entries:
					se_names = [se.name for se in stock_entries]
					se_items = frappe.get_all(
						"Stock Entry Detail",
						filters={"parent": ["in", se_names]},
						fields=["item_code", "qty", "t_warehouse"]
					)
					
					# Aggregate by item_code only (we don't have planning_row for these)
					for se_item in se_items:
						ic = se_item.item_code
						if se_item.t_warehouse and ic:
							if ic not in item_issued_from_se:
								item_issued_from_se[ic] = 0.0
							item_issued_from_se[ic] += float(se_item.qty or 0)
		
		# Update issued_qty in rmtp_raw_material rows
		for rm_row in self.rmtp_raw_material:
			# Start with issued_qty from Raw Material Issuance for this specific row
			key = (rm_row.item_code, rm_row.name)
			issued_qty = item_issued_from_rmi.get(key, 0.0)
			
			# Add any additional stock entries against cost center for this item
			# (only if not already counted from Raw Material Issuance)
			if rm_row.item_code in item_issued_from_se:
				# Only add if this item doesn't have any Raw Material Issuance entries
				# Otherwise, we might double count
				has_rmi_for_item = any(k[0] == rm_row.item_code for k in item_issued_from_rmi.keys())
				if not has_rmi_for_item:
					issued_qty += item_issued_from_se[rm_row.item_code]
			
			rm_row.issued_qty = issued_qty
			rm_row.pending_qty = max((rm_row.qty or 0) - (rm_row.issued_qty or 0), 0)

	def on_trash(self):
		"""Safety: cannot delete if any materials already issued"""
		if any((d.issued_qty or 0) > 0 for d in self.rmtp_raw_material):
			frappe.throw("Cannot delete: some materials already issued.")


@frappe.whitelist()
def make_raw_material_issuance(source_name, target_doc=None):
	"""Create Raw Material Issuance from Raw Material Transfer Planning"""
	from frappe.model.mapper import get_mapped_doc
	
	def set_missing_values(source, target):
		target.planning = source.name
		target.sales_order = source.sales_order
		target.company = source.company
		target.from_warehouse = source.from_warehouse
		target.to_warehouse = source.to_warehouse
		target.posting_date = frappe.utils.today()
		target.status = "Draft"  # Ensure status is set correctly (not from planning)
		
		# Auto-populate items from planning if there are pending items
		if source.rmtp_raw_material:
			# Refresh issued_qty from stock entries first
			source._update_issued_qty_from_stock_entries()
			source._refresh_availability_rows()
			
			# Get pending items
			for rm_row in source.rmtp_raw_material:
				pending_qty = max((rm_row.qty or 0) - (rm_row.issued_qty or 0), 0)
				if pending_qty > 0 and rm_row.item_code:
					target.append("items", {
						"planning": source.name,
						"planning_row": rm_row.name,
						"item_code": rm_row.item_code,
						"item_name": rm_row.item_name,
						"stock_uom": rm_row.stock_uom,
						"qty": pending_qty
					})
	
	doc = get_mapped_doc(
		"Raw Material Transfer Planning",
		source_name,
		{
			"Raw Material Transfer Planning": {
				"doctype": "Raw Material Issuance",
				"field_map": {
					"name": "planning",
					"sales_order": "sales_order",
					"company": "company",
					"from_warehouse": "from_warehouse",
					"to_warehouse": "to_warehouse"
				}
			}
		},
		target_doc,
		set_missing_values,
		ignore_permissions=True
	)
	
	# Refresh availability after items are added
	if doc.items and hasattr(doc, '_refresh_availability'):
		try:
			doc._refresh_availability()
		except Exception:
			pass  # If method doesn't exist or fails, continue
	
	return doc