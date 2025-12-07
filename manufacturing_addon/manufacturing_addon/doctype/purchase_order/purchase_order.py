import frappe
from frappe import _
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder as ERPNextPurchaseOrder


class PurchaseOrder(ERPNextPurchaseOrder):
	"""
	Override PurchaseOrder to validate that PO item qty doesn't exceed Material Request qty
	"""
	
	def validate(self):
		"""Override validate to add Material Request quantity validation"""
		super().validate()
		self.validate_po_qty_against_mr()
	
	def validate_po_qty_against_mr(self):
		"""
		Validate that Purchase Order item quantity doesn't exceed Material Request item quantity.
		This prevents users from increasing quantities beyond what was requested in MR.
		Accounts for already ordered quantities from other POs.
		"""
		if not self.items:
			return
		
		print(f"\n{'='*80}")
		print(f"[validate_po_qty_against_mr] Starting validation for PO: {self.name}")
		print(f"{'='*80}")
		
		for item in self.items:
			if not item.material_request_item:
				print(f"[validate_po_qty_against_mr] Row {item.idx}: Skipping - no material_request_item")
				continue
			
			print(f"\n[validate_po_qty_against_mr] Processing Row {item.idx}:")
			print(f"  - Item: {item.item_code}")
			print(f"  - Material Request Item: {item.material_request_item}")
			print(f"  - PO Item qty: {item.qty}")
			print(f"  - PO Item stock_qty: {item.stock_qty}")
			
			# Get Material Request Item details
			mr_item = frappe.db.get_value(
				"Material Request Item",
				item.material_request_item,
				["qty", "stock_qty", "item_code", "parent"],
				as_dict=True
			)
			
			if not mr_item:
				print(f"  - ERROR: Material Request Item not found!")
				continue
			
			print(f"  - MR Item Code: {mr_item.item_code}")
			print(f"  - MR Parent: {mr_item.parent}")
			print(f"  - MR qty: {mr_item.qty}")
			print(f"  - MR stock_qty: {mr_item.stock_qty}")
			
			# Get total requested quantity in stock UOM
			mr_total_stock_qty = mr_item.stock_qty or mr_item.qty or 0
			
			if mr_total_stock_qty <= 0:
				print(f"  - Skipping: MR total qty is 0 or negative")
				continue
			
			# Get current PO item stock qty
			po_stock_qty = item.stock_qty or item.qty or 0
			
			if po_stock_qty <= 0:
				print(f"  - Skipping: PO qty is 0 or negative")
				continue
			
			# Calculate total ordered quantity from all POs linked to this MR item
			# Use SQL query for reliability - include all draft and submitted POs, exclude cancelled
			exclude_po_name = None
			if self.name and not self.name.startswith("new-"):
				exclude_po_name = self.name
			
			print(f"  - Current PO name: {self.name}")
			print(f"  - Exclude PO name: {exclude_po_name}")
			
			# Get sum of all PO items linked to this MR item
			# Include draft (docstatus=0) and submitted (docstatus=1) POs
			# Exclude cancelled (docstatus=2) POs
			# Handle NULL stock_qty by using COALESCE
			sql_query = """
				SELECT 
					po.name as po_name,
					po.docstatus,
					po_item.stock_qty,
					po_item.qty,
					COALESCE(po_item.stock_qty, po_item.qty, 0) as effective_qty
				FROM `tabPurchase Order Item` po_item
				INNER JOIN `tabPurchase Order` po ON po_item.parent = po.name
				WHERE po_item.material_request_item = %(mr_item)s
				AND po.docstatus != 2
			"""
			
			params = {"mr_item": item.material_request_item}
			
			# Exclude current PO if it's saved
			if exclude_po_name:
				sql_query += " AND po.name != %(exclude_po)s"
				params["exclude_po"] = exclude_po_name
			
			# Get detailed list for debugging
			detailed_result = frappe.db.sql(sql_query, params, as_dict=True)
			print(f"  - Found {len(detailed_result)} existing PO items linked to this MR item:")
			for row in detailed_result:
				print(f"    * PO: {row.po_name}, docstatus: {row.docstatus}, stock_qty: {row.stock_qty}, qty: {row.qty}, effective_qty: {row.effective_qty}")
			
			# Get sum
			sum_query = """
				SELECT COALESCE(SUM(COALESCE(po_item.stock_qty, po_item.qty, 0)), 0) as total
				FROM `tabPurchase Order Item` po_item
				INNER JOIN `tabPurchase Order` po ON po_item.parent = po.name
				WHERE po_item.material_request_item = %(mr_item)s
				AND po.docstatus != 2
			"""
			
			sum_params = {"mr_item": item.material_request_item}
			if exclude_po_name:
				sum_query += " AND po.name != %(exclude_po)s"
				sum_params["exclude_po"] = exclude_po_name
			
			result = frappe.db.sql(sum_query, sum_params, as_dict=True)
			total_ordered_from_other_pos = result[0].total if result and result[0].total else 0
			
			print(f"  - Total ordered qty from other POs (excluding current): {total_ordered_from_other_pos}")
			
			# Get old qty of current PO item if it exists (for updates)
			old_po_item_qty = 0
			if exclude_po_name and item.name:
				existing_po_item = frappe.db.get_value(
					"Purchase Order Item",
					item.name,
					["stock_qty", "qty"],
					as_dict=True
				)
				if existing_po_item:
					old_po_item_qty = existing_po_item.stock_qty or existing_po_item.qty or 0
					print(f"  - Existing PO item old qty: {old_po_item_qty}")
			
			# Calculate available quantity
			# For new PO: Available = MR Total - Total from other POs
			# For existing PO: Available = MR Total - Total from other POs (old qty is being replaced)
			mr_available_stock_qty = mr_total_stock_qty - total_ordered_from_other_pos
			
			print(f"  - MR Total: {mr_total_stock_qty}")
			print(f"  - Total Ordered from other POs: {total_ordered_from_other_pos}")
			if old_po_item_qty > 0:
				print(f"  - Old qty of current PO (being replaced): {old_po_item_qty}")
			print(f"  - Available qty: {mr_available_stock_qty}")
			print(f"  - Current/New PO qty: {po_stock_qty}")
			print(f"  - Validation: {po_stock_qty} > {mr_available_stock_qty} = {po_stock_qty > mr_available_stock_qty}")
			
			# Check if PO quantity exceeds available MR quantity
			if po_stock_qty > mr_available_stock_qty:
				print(f"  - ERROR: Quantity exceeds available MR quantity!")
				frappe.throw(
					_("Row {0}: Purchase Order quantity ({1}) cannot exceed available Material Request quantity ({2} out of {3} total) for item {4}").format(
						item.idx,
						po_stock_qty,
						mr_available_stock_qty,
						mr_total_stock_qty,
						item.item_code or mr_item.item_code
					),
					title=_("Quantity Exceeds Material Request")
				)
			else:
				print(f"  - ✓ Validation passed")
		
		print(f"{'='*80}\n")

