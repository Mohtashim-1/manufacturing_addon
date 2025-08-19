import frappe
from frappe import _
from frappe.utils import flt, now_datetime
from manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager import update_transfer_quantities

class RawMaterialTransfer(frappe.model.document.Document):
    def validate(self):
        """Validate the document before saving"""
        self.validate_transfer_quantities()
        self.validate_work_order_manager()
        self.validate_stock_entry_type()
        # Ensure each row has a resolvable source warehouse (row-level or document-level)
        self.validate_warehouses()
        # Intentionally skip heavy checks here to keep creation fast
        self.calculate_totals()
        # Skip populate_actual_quantities() here; it's handled in before_save with optimized batching
    
    def before_save(self):
        """Actions to perform before saving the document"""
        self.calculate_totals()
        self.populate_actual_quantities()
    
    def calculate_totals(self):
        """Calculate totals for the document"""
        total_transfer_qty = 0
        total_items = len(self.raw_materials) if self.raw_materials else 0
        
        for item in self.raw_materials:
            total_transfer_qty += flt(item.transfer_qty or 0)
        
        self.total_transfer_qty = total_transfer_qty
        self.total_items = total_items
    
    def populate_actual_quantities(self):
        """Populate actual quantities at warehouse and company level using batched queries"""
        print(f"🔍 DEBUG: populate_actual_quantities() called for Raw Material Transfer: {self.name}")
        
        if not self.raw_materials:
            return
        
        try:
            # Build unique (warehouse -> set(item_code)) for per-warehouse balance
            warehouse_to_items = {}
            all_item_codes = set()
            for item in self.raw_materials:
                if not item.item_code:
                    continue
                source_wh = getattr(item, "source_warehouse", None) or getattr(item, "warehouse", None)
                if not source_wh:
                    continue
                all_item_codes.add(item.item_code)
                warehouse_to_items.setdefault(source_wh, set()).add(item.item_code)
            
            # Fetch balances per warehouse in batches (one query per unique warehouse)
            per_wh_balances = {}
            for wh, item_codes in warehouse_to_items.items():
                if not item_codes:
                    continue
                placeholders = ",".join(["%s"] * len(item_codes))
                params = list(item_codes) + [wh]
                results = frappe.db.sql(
                    f"""
                    SELECT b.item_code, b.actual_qty
                    FROM `tabBin` b
                    WHERE b.item_code IN ({placeholders}) AND b.warehouse = %s
                    """,
                    params,
                    as_dict=True,
                )
                for row in results:
                    per_wh_balances[(row.item_code, wh)] = flt(row.actual_qty)
            
            # Fetch company totals in one query
            per_company_totals = {}
            if self.company and all_item_codes:
                placeholders = ",".join(["%s"] * len(all_item_codes))
                params = list(all_item_codes) + [self.company]
                results = frappe.db.sql(
                    f"""
                    SELECT b.item_code, SUM(b.actual_qty) AS qty
                    FROM `tabBin` b
                    JOIN `tabWarehouse` w ON w.name = b.warehouse
                    WHERE b.item_code IN ({placeholders}) AND w.company = %s AND w.is_group = 0
                    GROUP BY b.item_code
                    """,
                    params,
                    as_dict=True,
                )
                for row in results:
                    per_company_totals[row.item_code] = flt(row.qty)
            
            # Assign values back to rows
            for item in self.raw_materials:
                if not item.item_code:
                    continue
                source_wh = getattr(item, "source_warehouse", None) or getattr(item, "warehouse", None)
                if source_wh:
                    item.actual_qty_at_warehouse = per_wh_balances.get((item.item_code, source_wh), 0)
                    print(f"🔍 DEBUG: {item.item_code} - Actual qty at warehouse {source_wh}: {item.actual_qty_at_warehouse}")
                if self.company:
                    item.actual_qty_at_company = per_company_totals.get(item.item_code, 0)
                    print(f"🔍 DEBUG: {item.item_code} - Actual qty at company {self.company}: {item.actual_qty_at_company}")
        except Exception as e:
            frappe.log_error(f"Error in populate_actual_quantities for {self.name}: {str(e)}")
    
    def before_submit(self):
        """Actions to perform before submitting the document"""
        print(f"🔍 DEBUG: before_submit() called for Raw Material Transfer: {self.name}")
        try:
            # Run heavy validations at submission time
            self.validate_allocation()
            self.create_stock_entries_for_work_orders()
            self.update_work_orders_with_allocation()
        except Exception as e:
            frappe.log_error(f"Error in before_submit for Raw Material Transfer {self.name}: {str(e)}")
            frappe.throw(f"Error processing transfer: {str(e)}")
    
    def on_submit(self):
        """Update Work Order Transfer Manager after successful submission"""
        try:
            if self.work_order_transfer_manager:
                update_transfer_quantities(self.work_order_transfer_manager, self.name)
                print(f"🔍 DEBUG: WOTM quantities updated for {self.work_order_transfer_manager} using transfer {self.name}")
        except Exception as e:
            frappe.log_error(f"Error updating WOTM after submit for {self.name}: {str(e)}")
    
    def on_cancel(self):
        """Actions to perform when cancelling the document"""
        print(f"🔍 DEBUG: on_cancel() called for Raw Material Transfer: {self.name}")
        if self.stock_entry:
            try:
                stock_entry_doc = frappe.get_doc("Stock Entry", self.stock_entry)
                if stock_entry_doc.docstatus == 1:
                    stock_entry_doc.cancel()
                    print(f"🔍 DEBUG: Stock Entry {self.stock_entry} cancelled")
            except Exception as e:
                frappe.log_error(f"Error cancelling stock entry {self.stock_entry}: {str(e)}")
    
    def validate_transfer_quantities(self):
        """Validate that transfer quantities don't exceed pending quantities"""
        for item in self.raw_materials:
            if flt(item.transfer_qty) > flt(item.pending_qty):
                frappe.throw(f"Transfer quantity ({item.transfer_qty}) for {item.item_code} cannot exceed pending quantity ({item.pending_qty})")
            if flt(item.transfer_qty) <= 0:
                frappe.throw(f"Transfer quantity for {item.item_code} must be greater than 0")
    
    def validate_work_order_manager(self):
        """Validate that work order transfer manager exists and is submitted"""
        if not self.work_order_transfer_manager:
            frappe.throw("Work Order Transfer Manager is required")
        
        wotm_doc = frappe.get_doc("Work Order Transfer Manager", self.work_order_transfer_manager)
        if wotm_doc.docstatus != 1:
            frappe.throw("Work Order Transfer Manager must be submitted before creating Raw Material Transfer")
    
    def validate_stock_entry_type(self):
        """Validate that stock entry type is selected"""
        if not self.stock_entry_type:
            frappe.throw("Please select a Stock Entry Type")
    
    def validate_warehouses(self):
        """Ensure that each row has a resolvable source warehouse"""
        if not self.raw_materials:
            return
        for row_index, item in enumerate(self.raw_materials, start=1):
            source_wh = getattr(item, "source_warehouse", None) or getattr(item, "warehouse", None) or self.warehouse
            if not source_wh:
                frappe.throw(_(f"Source warehouse is mandatory for row {row_index}"))
    
    def validate_allocation(self):
        """Validate that all transfer quantities can be allocated to work orders"""
        if not self.raw_materials:
            return
            
        # Get all work orders for this sales order
        work_orders = frappe.db.sql("""
            SELECT 
                wo.name, 
                wo.production_item, 
                wo.qty, 
                wo.material_transferred_for_manufacturing,
                wo.docstatus
            FROM `tabWork Order` wo
            WHERE wo.sales_order = %s AND wo.docstatus = 1
        """, (self.sales_order,), as_dict=True)
        
        if not work_orders:
            frappe.throw("No submitted work orders found for this sales order")
        
        # Check if each raw material can be allocated
        for raw_item in self.raw_materials:
            if flt(raw_item.transfer_qty) <= 0:
                continue
                
            can_allocate = False
            for wo in work_orders:
                # Check if this work order needs this raw material
                bom = frappe.db.get_value("BOM", 
                    {"item": wo.production_item, "is_active": 1, "is_default": 1})
                
                if bom:
                    bom_doc = frappe.get_doc("BOM", bom)
                    for item in bom_doc.items:
                        if item.item_code == raw_item.item_code:
                            can_allocate = True
                            break
                    if can_allocate:
                        break
            
            if not can_allocate:
                frappe.throw(f"Raw material {raw_item.item_code} cannot be allocated to any work order. Please check BOM configurations.")
    
    def create_stock_entries_for_work_orders(self):
        """Create stock entries for each work order based on allocation"""
        print(f"🔍 DEBUG: Creating stock entries for work orders")
        
        # Get all work orders for this sales order, ordered by creation date (oldest first)
        work_orders = frappe.db.sql("""
            SELECT 
                wo.name, 
                wo.production_item, 
                wo.qty, 
                wo.material_transferred_for_manufacturing,
                wo.creation,
                wo.docstatus
            FROM `tabWork Order` wo
            WHERE wo.sales_order = %s AND wo.docstatus = 1
            ORDER BY wo.creation ASC
        """, (self.sales_order,), as_dict=True)
        
        print(f"🔍 DEBUG: Found {len(work_orders)} work orders for sales order {self.sales_order}")
        
        # Track allocation for each work order
        work_order_allocation = {}
        
        # Process each raw material and allocate to work orders
        for raw_item in self.raw_materials:
            if flt(raw_item.transfer_qty) <= 0:
                continue
                
            print(f"🔍 DEBUG: Processing raw material: {raw_item.item_code}, transfer qty: {raw_item.transfer_qty}")
            
            remaining_qty = flt(raw_item.transfer_qty)
            
            # Allocate to work orders in order of creation (oldest first)
            for wo in work_orders:
                if remaining_qty <= 0:
                    break
                    
                print(f"🔍 DEBUG: Checking work order: {wo.name}")
                
                # Check if this work order needs this raw material
                bom = frappe.db.get_value("BOM", 
                    {"item": wo.production_item, "is_active": 1, "is_default": 1})
                
                if not bom:
                    print(f"🔍 DEBUG: No BOM found for work order {wo.name}")
                    continue
                
                bom_doc = frappe.get_doc("BOM", bom)
                bom_item = None
                
                # Find the raw material in the BOM
                for item in bom_doc.items:
                    if item.item_code == raw_item.item_code:
                        bom_item = item
                        break
                
                if not bom_item:
                    print(f"🔍 DEBUG: Raw material {raw_item.item_code} not found in BOM for work order {wo.name}")
                    continue
                
                # Calculate how much raw material this work order needs
                wo_pending_qty = flt(wo.qty) - flt(wo.material_transferred_for_manufacturing)
                if wo_pending_qty <= 0:
                    print(f"🔍 DEBUG: Work order {wo.name} has no pending quantity")
                    continue
                
                # Calculate raw material needed for this work order
                raw_qty_needed = flt(wo_pending_qty) * flt(bom_item.qty) / flt(bom_doc.quantity)
                
                print(f"🔍 DEBUG: Work order {wo.name} needs {raw_qty_needed} of {raw_item.item_code}")
                
                # Calculate how much to allocate to this work order
                qty_to_allocate = min(remaining_qty, raw_qty_needed)
                
                if qty_to_allocate > 0:
                    # Initialize work order allocation if not exists
                    if wo.name not in work_order_allocation:
                        work_order_allocation[wo.name] = {
                            "work_order": wo.name,
                            "production_item": wo.production_item,
                            "items": []
                        }
                    
                    # Resolve source and target warehouses for this item
                    item_source_wh = getattr(raw_item, "source_warehouse", None) or getattr(raw_item, "warehouse", None) or self.warehouse
                    item_target_wh = getattr(raw_item, "target_warehouse", None) or getattr(raw_item, "t_warehouse", None)
                    
                    # Add item to work order allocation
                    work_order_allocation[wo.name]["items"].append({
                        "item_code": raw_item.item_code,
                        "item_name": raw_item.item_name,
                        "qty": qty_to_allocate,
                        "uom": raw_item.uom,
                        "warehouse": item_source_wh,
                        "s_warehouse": item_source_wh,
                        "t_warehouse": item_target_wh
                    })
                    
                    print(f"🔍 DEBUG: Allocated {qty_to_allocate} of {raw_item.item_code} to work order {wo.name}")
                    
                    remaining_qty -= qty_to_allocate
        
        # Create stock entries for each work order
        created_stock_entries = []
        for wo_name, allocation in work_order_allocation.items():
            if allocation["items"]:
                stock_entry = self.create_stock_entry_for_work_order(wo_name, allocation)
                created_stock_entries.append(stock_entry.name)
        
        # Store the first stock entry name (for backward compatibility)
        if created_stock_entries:
            self.stock_entry = created_stock_entries[0]
        
        print(f"🔍 DEBUG: Created {len(created_stock_entries)} stock entries")
        
        # Update allocation quantities in raw materials table
        self.update_allocation_quantities(work_order_allocation)
    
    def update_allocation_quantities(self, work_order_allocation):
        """Update allocation quantities in the raw materials table"""
        print(f"🔍 DEBUG: Updating allocation quantities")
        
        # Create a mapping of item_code to total allocated quantity
        item_allocation = {}
        for wo_name, allocation in work_order_allocation.items():
            for item in allocation["items"]:
                item_code = item["item_code"]
                if item_code not in item_allocation:
                    item_allocation[item_code] = 0
                item_allocation[item_code] += flt(item["qty"])
        
        # Update the raw materials table
        for raw_item in self.raw_materials:
            allocated_qty = item_allocation.get(raw_item.item_code, 0)
            raw_item.allocated_qty = allocated_qty
            raw_item.remaining_qty = flt(raw_item.transfer_qty) - allocated_qty
    
    def create_stock_entry_for_work_order(self, work_order_name, allocation):
        """Create a stock entry for a specific work order"""
        print(f"🔍 DEBUG: Creating stock entry for work order: {work_order_name}")
        
        # Get work order details to get the WIP warehouse
        work_order = frappe.get_doc("Work Order", work_order_name)
        wip_warehouse = work_order.wip_warehouse
        
        if not wip_warehouse:
            frappe.throw(f"Work Order {work_order_name} does not have a WIP warehouse configured")
        
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = self.stock_entry_type
        stock_entry.posting_date = self.posting_date
        stock_entry.posting_time = self.posting_time
        stock_entry.company = self.company
        stock_entry.from_warehouse = self.warehouse
        stock_entry.to_warehouse = wip_warehouse
        stock_entry.work_order = work_order_name
        
        # Add items to stock entry
        for item in allocation["items"]:
            resolved_s_warehouse = item.get("s_warehouse") or self.warehouse
            resolved_t_warehouse = item.get("t_warehouse") or wip_warehouse
            stock_entry.append("items", {
                "item_code": item["item_code"],
                "qty": flt(item["qty"]),
                "uom": item["uom"],
                "s_warehouse": resolved_s_warehouse,
                "t_warehouse": resolved_t_warehouse,
                "is_finished_item": 0,
                "allow_zero_valuation_rate": 1
            })
        
        stock_entry.insert()
        stock_entry.submit()
        
        print(f"🔍 DEBUG: Stock Entry created: {stock_entry.name} for work order {work_order_name}")
        
        return stock_entry
    
    def update_work_orders_with_allocation(self):
        """Update work orders with the allocated quantities"""
        print(f"🔍 DEBUG: Updating work orders with allocation")
        
        # Get all work orders for this sales order, ordered by creation date (oldest first)
        work_orders = frappe.db.sql("""
            SELECT 
                wo.name, 
                wo.production_item, 
                wo.qty, 
                wo.material_transferred_for_manufacturing,
                wo.creation,
                wo.docstatus
            FROM `tabWork Order` wo
            WHERE wo.sales_order = %s AND wo.docstatus = 1
            ORDER BY wo.creation ASC
        """, (self.sales_order,), as_dict=True)
        
        # Process each raw material and update work orders
        for raw_item in self.raw_materials:
            if flt(raw_item.transfer_qty) <= 0:
                continue
                
            print(f"🔍 DEBUG: Updating work orders for raw material: {raw_item.item_code}")
            
            remaining_qty = flt(raw_item.transfer_qty)
            
            # Allocate to work orders in order of creation (oldest first)
            for wo in work_orders:
                if remaining_qty <= 0:
                    break
                    
                # Check if this work order needs this raw material
                bom = frappe.db.get_value("BOM", 
                    {"item": wo.production_item, "is_active": 1, "is_default": 1})
                
                if not bom:
                    continue
                
                bom_doc = frappe.get_doc("BOM", bom)
                bom_item = None
                
                # Find the raw material in the BOM
                for item in bom_doc.items:
                    if item.item_code == raw_item.item_code:
                        bom_item = item
                        break
                
                if not bom_item:
                    continue
                
                # Calculate how much raw material this work order needs
                wo_pending_qty = flt(wo.qty) - flt(wo.material_transferred_for_manufacturing)
                if wo_pending_qty <= 0:
                    continue
                
                # Calculate raw material needed for this work order
                raw_qty_needed = flt(wo_pending_qty) * flt(bom_item.qty) / flt(bom_doc.quantity)
                
                # Calculate how much to allocate to this work order
                qty_to_allocate = min(remaining_qty, raw_qty_needed)
                
                if qty_to_allocate > 0:
                    try:
                        # Update work order using database update to avoid validation issues
                        # Calculate the equivalent production quantity for this raw material allocation
                        production_qty_equivalent = qty_to_allocate * flt(bom_doc.quantity) / flt(bom_item.qty)
                        
                        # Use database update to bypass validation
                        current_transferred = frappe.db.get_value("Work Order", wo.name, "material_transferred_for_manufacturing") or 0
                        new_transferred = current_transferred + production_qty_equivalent
                        
                        frappe.db.set_value("Work Order", wo.name, "material_transferred_for_manufacturing", new_transferred)
                        
                        print(f"🔍 DEBUG: Updated work order {wo.name} - allocated {qty_to_allocate} of {raw_item.item_code}")
                        print(f"🔍 DEBUG: Updated material_transferred_for_manufacturing from {current_transferred} to {new_transferred}")
                        
                        remaining_qty -= qty_to_allocate
                    except Exception as e:
                        print(f"🔍 DEBUG: Error updating work order {wo.name}: {str(e)}")
                        frappe.log_error(f"Error updating work order {wo.name} in Raw Material Transfer {self.name}: {str(e)}")
                        # Continue with other work orders even if one fails
        
        print(f"🔍 DEBUG: Work order updates completed")

@frappe.whitelist()
def get_pending_raw_materials(work_order_transfer_manager):
    """Get raw materials that still have pending quantities"""
    print(f"🔍 DEBUG: get_pending_raw_materials called for: {work_order_transfer_manager}")
    
    try:
        wotm_doc = frappe.get_doc("Work Order Transfer Manager", work_order_transfer_manager)
        
        # Get all raw materials with pending quantities
        pending_items = []
        
        for item in wotm_doc.transfer_items:
            if flt(item.pending_qty) > 0:
                pending_items.append({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "pending_qty": item.pending_qty,
                    "uom": item.uom,
                    "warehouse": wotm_doc.warehouse
                })
        
        print(f"🔍 DEBUG: Found {len(pending_items)} items with pending quantities")
        return pending_items
        
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 60:
            error_msg = error_msg[:57] + "..."
        full_message = f"Error getting pending raw materials: {error_msg}"
        if len(full_message) > 140:
            full_message = f"Error getting pending raw materials: {error_msg[:50]}..."
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def create_raw_material_transfer_from_pending(work_order_transfer_manager, selected_items=None):
    """Create a new Raw Material Transfer document with selected pending items"""
    print(f"🔍 DEBUG: create_raw_material_transfer_from_pending called")
    print(f"🔍 DEBUG: work_order_transfer_manager: {work_order_transfer_manager}")
    print(f"🔍 DEBUG: selected_items: {selected_items}")
    
    try:
        wotm_doc = frappe.get_doc("Work Order Transfer Manager", work_order_transfer_manager)
        
        if wotm_doc.docstatus != 1:
            frappe.throw("Work Order Transfer Manager must be submitted first")
        
        # Parse selected items if provided
        selected_item_codes = []
        if selected_items:
            if isinstance(selected_items, str):
                selected_item_codes = selected_items.split(',')
            else:
                selected_item_codes = selected_items
        
        # Get pending items
        pending_items = []
        for item in wotm_doc.transfer_items:
            if flt(item.pending_qty) > 0:
                # If specific items are selected, only include those
                if not selected_item_codes or item.item_code in selected_item_codes:
                    pending_items.append({
                        "item_code": item.item_code,
                        "item_name": item.item_name,
                        "pending_qty": item.pending_qty,
                        "uom": item.uom,
                        "warehouse": wotm_doc.warehouse
                    })
        
        if not pending_items:
            frappe.throw("No raw materials with pending quantities found")
        
        # Create new Raw Material Transfer document
        raw_transfer_doc = frappe.new_doc("Raw Material Transfer")
        raw_transfer_doc.sales_order = wotm_doc.sales_order
        raw_transfer_doc.work_order_transfer_manager = work_order_transfer_manager
        raw_transfer_doc.posting_date = wotm_doc.posting_date
        raw_transfer_doc.posting_time = wotm_doc.posting_time
        raw_transfer_doc.company = wotm_doc.company
        raw_transfer_doc.warehouse = wotm_doc.warehouse
        raw_transfer_doc.stock_entry_type = wotm_doc.stock_entry_type
        
        # Add items to the document
        for item in pending_items:
            raw_transfer_doc.append("raw_materials", {
                "item_code": item["item_code"],
                "item_name": item["item_name"],
                "pending_qty": item["pending_qty"],
                "transfer_qty": item["pending_qty"],  # Set to pending quantity by default
                "uom": item["uom"],
                "warehouse": item["warehouse"],
                "source_warehouse": item["warehouse"]
            })
        
        raw_transfer_doc.insert()
        
        return {
            "success": True,
            "message": f"Raw Material Transfer document created with {len(pending_items)} items: {raw_transfer_doc.name}",
            "doc_name": raw_transfer_doc.name
        }
        
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 60:
            error_msg = error_msg[:57] + "..."
        full_message = f"Error creating raw material transfer: {error_msg}"
        if len(full_message) > 140:
            full_message = f"Error creating raw material transfer: {error_msg[:50]}..."
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)} 