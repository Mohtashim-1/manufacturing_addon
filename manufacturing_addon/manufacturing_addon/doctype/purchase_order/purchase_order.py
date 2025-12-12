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
			
			# Get total requested quantity in stock UOM - ALWAYS use stock_qty
			# This ensures comparison is always in stock UOM (e.g., pcs vs pcs, not pcs vs kg)
			if not mr_item.stock_qty or mr_item.stock_qty <= 0:
				frappe.throw(
					_("Row {0}: Material Request item {1} has invalid or missing stock quantity. Please ensure stock quantity is set correctly.").format(
						item.idx,
						item.material_request_item
					),
					title=_("Invalid Material Request Stock Quantity")
				)
			mr_total_stock_qty = mr_item.stock_qty
			
			# Get current PO item stock qty - ALWAYS use stock_qty
			# This ensures comparison is always in stock UOM
			if not item.stock_qty or item.stock_qty <= 0:
				frappe.throw(
					_("Row {0}: Purchase Order item {1} has invalid or missing stock quantity. Please ensure stock quantity is set correctly.").format(
						item.idx,
						item.item_code or mr_item.item_code
					),
					title=_("Invalid Purchase Order Stock Quantity")
				)
			po_stock_qty = item.stock_qty
			
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
			# ALWAYS use stock_qty only - ensures comparison is in stock UOM
			sql_query = """
				SELECT 
					po.name as po_name,
					po.docstatus,
					po_item.stock_qty,
					po_item.qty
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
				print(f"    * PO: {row.po_name}, docstatus: {row.docstatus}, stock_qty: {row.stock_qty}, qty: {row.qty}")
			
			# Get sum - ALWAYS use stock_qty only
			sum_query = """
				SELECT COALESCE(SUM(COALESCE(po_item.stock_qty, 0)), 0) as total
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
			# ALWAYS use stock_qty only
			old_po_item_qty = 0
			if exclude_po_name and item.name:
				existing_po_item = frappe.db.get_value(
					"Purchase Order Item",
					item.name,
					["stock_qty"],
					as_dict=True
				)
				if existing_po_item and existing_po_item.stock_qty:
					old_po_item_qty = existing_po_item.stock_qty
					print(f"  - Existing PO item old stock_qty: {old_po_item_qty}")
			
			# Calculate available quantity
			# For new PO: Available = MR Total - Total from other POs
			# For existing PO: Available = MR Total - Total from other POs + Old qty (old qty is being replaced, so add it back)
			mr_available_stock_qty = mr_total_stock_qty - total_ordered_from_other_pos
			
			# If updating an existing PO, add back the old qty since it's being replaced
			if old_po_item_qty > 0:
				mr_available_stock_qty += old_po_item_qty
			
			print(f"  - MR Total: {mr_total_stock_qty}")
			print(f"  - Total Ordered from other POs: {total_ordered_from_other_pos}")
			if old_po_item_qty > 0:
				print(f"  - Old qty of current PO (being replaced): {old_po_item_qty}")
				print(f"  - Available qty (after adding back old qty): {mr_available_stock_qty}")
			else:
				print(f"  - Available qty: {mr_available_stock_qty}")
			print(f"  - Current/New PO qty: {po_stock_qty}")
			print(f"  - Validation: {po_stock_qty} > {mr_available_stock_qty} = {po_stock_qty > mr_available_stock_qty}")
			
			# Check if PO quantity exceeds available MR quantity
			if po_stock_qty > mr_available_stock_qty:
				print(f"  - ERROR: Quantity exceeds available MR quantity!")
				
				# Build a clear, user-friendly error message with HTML formatting
				item_name = item.item_code or mr_item.item_code
				mr_name = mr_item.parent
				
				# Format quantities for display
				po_qty_formatted = f"{po_stock_qty:,.2f}".rstrip('0').rstrip('.')
				available_qty_formatted = f"{mr_available_stock_qty:,.2f}".rstrip('0').rstrip('.')
				total_qty_formatted = f"{mr_total_stock_qty:,.2f}".rstrip('0').rstrip('.')
				ordered_qty_formatted = f"{total_ordered_from_other_pos:,.2f}".rstrip('0').rstrip('.')
				
				# Build breakdown of existing POs
				po_breakdown_html = ""
				if detailed_result:
					po_breakdown_html = '<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #90caf9;"><strong style="color: #1565c0; display: block; margin-bottom: 8px; font-size: 12px;">📋 Purchase Orders Already Created:</strong><table style="width: 100%; border-collapse: collapse; font-size: 12px;">'
					for po_row in detailed_result:
						po_qty = po_row.stock_qty or 0
						po_qty_display = f"{po_qty:,.2f}".rstrip('0').rstrip('.')
						po_status = "Draft" if po_row.docstatus == 0 else "Submitted"
						po_status_color = "#ff9800" if po_row.docstatus == 0 else "#4caf50"
						po_breakdown_html += f'''
							<tr>
								<td style="padding: 4px 0; color: #555;">
									<a href="/app/purchase-order/{po_row.po_name}" style="color: #1976d2; text-decoration: none;">{po_row.po_name}</a>
									<span style="color: {po_status_color}; margin-left: 8px; font-size: 11px;">({po_status})</span>
								</td>
								<td style="padding: 4px 0; color: #f57c00; font-weight: 600; text-align: right;">{po_qty_display} units</td>
							</tr>
						'''
					po_breakdown_html += '</table></div>'
				else:
					po_breakdown_html = '<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #90caf9;"><span style="color: #999; font-size: 12px; font-style: italic;">No other Purchase Orders found</span></div>'
				
				# Create a well-formatted HTML error message
				error_msg = f"""
					<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
						<div style="background-color: #fee; border-left: 4px solid #f44336; padding: 12px; margin-bottom: 16px; border-radius: 4px;">
							<strong style="color: #c62828; font-size: 14px;">⚠️ Row {item.idx}: Quantity Exceeds Available Material Request</strong>
						</div>
						
						<div style="margin-bottom: 16px;">
							<div style="background-color: #f5f5f5; padding: 12px; border-radius: 4px; margin-bottom: 8px;">
								<strong style="color: #333; display: block; margin-bottom: 8px;">📦 Item:</strong>
								<span style="color: #666; font-size: 13px;">{item_name}</span>
							</div>
							
							<div style="background-color: #fff3cd; padding: 12px; border-radius: 4px; margin-bottom: 8px; border-left: 3px solid #ffc107;">
								<strong style="color: #856404; display: block; margin-bottom: 8px;">📋 Material Request:</strong>
								<span style="color: #856404; font-size: 13px;">{mr_name}</span>
							</div>
						</div>
						
						<div style="background-color: #e3f2fd; padding: 16px; border-radius: 4px; margin-bottom: 16px; border-left: 3px solid #2196f3;">
							<strong style="color: #1565c0; display: block; margin-bottom: 12px; font-size: 14px;">📊 Quantity Summary:</strong>
							<table style="width: 100%; border-collapse: collapse;">
								<tr>
									<td style="padding: 6px 0; color: #555; font-size: 13px; width: 200px;">Total Requested:</td>
									<td style="padding: 6px 0; color: #333; font-weight: 600; font-size: 13px;">{total_qty_formatted} units</td>
								</tr>
								<tr>
									<td style="padding: 6px 0; color: #555; font-size: 13px; vertical-align: top;">Already Ordered:</td>
									<td style="padding: 6px 0; color: #f57c00; font-weight: 600; font-size: 13px;">{ordered_qty_formatted} units</td>
								</tr>
								<tr style="border-top: 1px solid #90caf9;">
									<td style="padding: 8px 0 6px 0; color: #1565c0; font-size: 13px; font-weight: 600;">Available to Order:</td>
									<td style="padding: 8px 0 6px 0; color: #1565c0; font-weight: 700; font-size: 14px;">{available_qty_formatted} units</td>
								</tr>
							</table>
							{po_breakdown_html}
						</div>
						
						<div style="background-color: #ffebee; padding: 12px; border-radius: 4px; margin-bottom: 16px; border-left: 3px solid #f44336;">
							<strong style="color: #c62828; display: block; margin-bottom: 4px;">❌ You are trying to order:</strong>
							<span style="color: #c62828; font-size: 16px; font-weight: 700;">{po_qty_formatted} units</span>
						</div>
						
						<div style="background-color: #e8f5e9; padding: 12px; border-radius: 4px; border-left: 3px solid #4caf50;">
							<strong style="color: #2e7d32; display: block; margin-bottom: 6px;">✅ Solution:</strong>
							<span style="color: #2e7d32; font-size: 13px;">
								Reduce the quantity to <strong>{available_qty_formatted} units</strong> or less, 
								or cancel/modify other Purchase Orders linked to Material Request <strong>{mr_name}</strong>.
							</span>
						</div>
					</div>
				"""
				
				frappe.throw(
					error_msg,
					title=_("Quantity Exceeds Available Material Request")
				)
			else:
				print(f"  - ✓ Validation passed")
		
		print(f"{'='*80}\n")

