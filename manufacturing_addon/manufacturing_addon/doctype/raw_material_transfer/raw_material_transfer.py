import frappe
from frappe import _
from frappe.utils import flt, now_datetime
from manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager import update_transfer_quantities

class RawMaterialTransfer(frappe.model.document.Document):
    def onload(self):
        """Ensure tracking fields are properly initialized when document is loaded"""
        self.initialize_tracking_fields()
        self.calculate_transferred_quantities()

    def validate(self):
        self.validate_transfer_quantities()
        self.validate_work_order_manager()
        self.validate_stock_entry_type()
        self.validate_warehouses()
        self.calculate_totals()

    def before_save(self):
        self.calculate_totals()
        self.populate_actual_quantities()
        self.calculate_transferred_quantities()
        self.initialize_tracking_fields()
        self.handle_extra_quantities_automatically()
        self.distribute_extra_quantities()
        self.sync_warehouse_information()

    def calculate_totals(self):
        total_transfer_qty = 0
        total_extra_qty = 0
        total_target_qty = 0
        total_expected_qty = 0
        total_items = len(self.raw_materials) if self.raw_materials else 0
        
        for item in (self.raw_materials or []):
            total_transfer_qty += flt(item.transfer_qty or 0)
            total_extra_qty += flt(item.extra_qty or 0)
            total_target_qty += flt(item.target_qty or 0)
            total_expected_qty += flt(item.expected_qty or 0)
            
        self.total_transfer_qty = total_transfer_qty
        self.total_extra_qty = total_extra_qty
        self.total_target_qty = total_target_qty
        self.total_expected_qty = total_expected_qty
        self.total_items = total_items

    def bulk_delete_rows(self, row_indices):
        """Bulk delete rows by their indices for better performance"""
        if not row_indices or not self.raw_materials:
            return
            
        # Convert to set for faster lookup
        indices_to_delete = set(row_indices)
        
        # Create new list without deleted rows - optimized for speed
        self.raw_materials = [row for i, row in enumerate(self.raw_materials) if i not in indices_to_delete]
        
        # Only recalculate totals - skip expensive operations
        self.calculate_totals()

    def bulk_clear_all_rows(self):
        """Clear all rows at once for maximum performance"""
        self.raw_materials = []
        self.calculate_totals()

    def populate_actual_quantities(self):
        if not self.raw_materials:
            return
        try:
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
                    params, as_dict=True
                )
                for row in results:
                    per_wh_balances[(row.item_code, wh)] = flt(row.actual_qty)

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
                    params, as_dict=True
                )
                for row in results:
                    per_company_totals[row.item_code] = flt(row.qty)

            for item in self.raw_materials:
                if not item.item_code:
                    continue
                source_wh = getattr(item, "source_warehouse", None) or getattr(item, "warehouse", None)
                if source_wh:
                    item.actual_qty_at_warehouse = per_wh_balances.get((item.item_code, source_wh), 0)
                if self.company:
                    item.actual_qty_at_company = per_company_totals.get(item.item_code, 0)
                
                # Calculate remaining quantity - this should be what's left after this transfer
                item.remaining_qty = max(flt(item.pending_qty) - flt(item.transfer_qty), 0)

        except Exception as e:
            frappe.log_error(f"Error in populate_actual_quantities for {self.name}: {str(e)}")

    def calculate_transferred_quantities(self):
        """Calculate transferred quantities from actual Stock Entries created from Raw Material Transfers"""
        if not self.work_order_transfer_manager or not self.raw_materials:
            return
            
        try:
            # Get all submitted Raw Material Transfers for this WOTM
            existing_transfers = frappe.get_all(
                "Raw Material Transfer",
                filters={"work_order_transfer_manager": self.work_order_transfer_manager, "docstatus": 1},
                fields=["name", "stock_entry"]
            )
            
            # Get all Stock Entries created from these transfers
            stock_entries = []
            for tr in existing_transfers:
                if tr.stock_entry:
                    stock_entries.append(tr.stock_entry)
            
            # Calculate total transferred for each item from actual Stock Entries
            item_total_transferred = {}
            
            if stock_entries:
                # Get Stock Entry Items for all related Stock Entries
                se_items = frappe.get_all(
                    "Stock Entry Detail",
                    filters={
                        "parent": ["in", stock_entries],
                        "s_warehouse": ["is", "not set"]  # Only target warehouse items (transferred out)
                    },
                    fields=["item_code", "qty", "parent"]
                )
                
                for se_item in se_items:
                    item_code = se_item.item_code
                    qty = flt(se_item.qty)
                    item_total_transferred[item_code] = item_total_transferred.get(item_code, 0) + qty
                    
                    print(f"DEBUG: Found {qty} of {item_code} transferred in Stock Entry {se_item.parent}")
            
            # Also check from Raw Material Transfer documents as fallback
            for tr in existing_transfers:
                tr_doc = frappe.get_doc("Raw Material Transfer", tr.name)
                for ti in tr_doc.raw_materials:
                    # Only add if not already counted from Stock Entries
                    if ti.item_code not in item_total_transferred:
                        item_total_transferred[ti.item_code] = flt(ti.transfer_qty)
                    print(f"DEBUG: Fallback - Found {ti.transfer_qty} of {ti.item_code} from RMT {tr.name}")
            
            # Update transferred_qty_so_far for each item in current document
            for item in self.raw_materials:
                if item.item_code:
                    item.transferred_qty_so_far = flt(item_total_transferred.get(item.item_code, 0))
                    print(f"DEBUG: Item {item.item_code} - Transferred So Far: {item.transferred_qty_so_far}")
                    
        except Exception as e:
            frappe.log_error(f"Error calculating transferred quantities for {self.name}: {str(e)}")
            print(f"DEBUG: Error calculating transferred quantities: {str(e)}")

    def before_submit(self):
        try:
            self.validate_allocation()
            self.create_stock_entries_for_work_orders()
            self.update_work_orders_with_allocation()
        except Exception as e:
            error_msg = str(e)
            # Truncate error message for log title if too long
            if len(error_msg) > 100:
                error_msg = error_msg[:97] + "..."
            frappe.log_error(f"RMT {self.name} before_submit error: {error_msg}")
            frappe.throw(f"Error processing transfer: {str(e)}")

    def on_submit(self):
        try:
            if self.work_order_transfer_manager:
                out = update_transfer_quantities(self.work_order_transfer_manager, self.name)
                if isinstance(out, dict) and not out.get("success", True):
                    frappe.msgprint(_(f"WOTM update failed: {out.get('message')}"), alert=True, indicator="red")
                else:
                    frappe.msgprint(_(f"WOTM updated successfully for {self.work_order_transfer_manager}"), alert=True, indicator="green")
                print(f"🔍 DEBUG: WOTM quantities updated for {self.work_order_transfer_manager} using transfer {self.name}")
        except Exception as e:
            frappe.msgprint(_(f"Error updating WOTM: {str(e)}"), alert=True, indicator="red")
            frappe.log_error(f"Error updating WOTM after submit for {self.name}: {str(e)}")

    def on_cancel(self):
        if self.stock_entry:
            try:
                stock_entry_doc = frappe.get_doc("Stock Entry", self.stock_entry)
                if stock_entry_doc.docstatus == 1:
                    stock_entry_doc.cancel()
                    print(f"🔍 DEBUG: Stock Entry {self.stock_entry} cancelled")
            except Exception as e:
                frappe.log_error(f"Error cancelling stock entry {self.stock_entry}: {str(e)}")

        # Recompute WOTM after cancel so remaining/transferred reflect reality
        try:
            if self.work_order_transfer_manager:
                update_transfer_quantities(self.work_order_transfer_manager, None)
                print(f"🔍 DEBUG: Recomputed WOTM after cancel: {self.work_order_transfer_manager}")
        except Exception as e:
            frappe.log_error(f"Error recomputing WOTM after cancel for {self.name}: {str(e)}")

    # ---------- validations ----------

    def validate_transfer_quantities(self):
        # Check if at least one item has transfer quantity > 0
        has_transfer_qty = any(flt(item.transfer_qty or 0) > 0 for item in (self.raw_materials or []))
        if not has_transfer_qty:
            frappe.throw("Please enter transfer quantities for at least one item")
            
        for item in (self.raw_materials or []):
            # Skip validation if transfer_qty is 0 (user hasn't entered anything yet)
            if flt(item.transfer_qty or 0) == 0:
                continue
                
            # Calculate target quantity (pending + extra)
            target_qty = flt(item.pending_qty or 0) + flt(item.extra_qty or 0)
            
            if flt(item.transfer_qty) > target_qty:
                frappe.throw(f"Transfer quantity ({item.transfer_qty}) for {item.item_code} cannot exceed target quantity ({target_qty}) which includes pending ({item.pending_qty}) + extra ({item.extra_qty})")
            
            # Check stock availability in source warehouse
            source_warehouse = item.source_warehouse or item.warehouse
            actual_qty = flt(item.actual_qty_at_warehouse or 0)
            
            # If actual_qty_at_warehouse is 0, get stock from source warehouse
            if actual_qty == 0 and source_warehouse:
                try:
                    from erpnext.stock.utils import get_stock_balance
                    actual_qty = get_stock_balance(item.item_code, source_warehouse, with_valuation_rate=False)
                except:
                    actual_qty = 0
            
            if flt(item.transfer_qty) > actual_qty:
                frappe.throw(f"Insufficient stock for {item.item_code}. Available: {actual_qty}, Required: {item.transfer_qty} in source warehouse {source_warehouse}")

    def validate_work_order_manager(self):
        if not self.work_order_transfer_manager:
            frappe.throw("Work Order Transfer Manager is required")
        wotm_doc = frappe.get_doc("Work Order Transfer Manager", self.work_order_transfer_manager)
        if wotm_doc.docstatus != 1:
            frappe.throw("Work Order Transfer Manager must be submitted before creating Raw Material Transfer")

    def validate_stock_entry_type(self):
        if not self.stock_entry_type:
            frappe.throw("Please select a Stock Entry Type")

    def validate_warehouses(self):
        if not self.raw_materials:
            return
        for row_index, item in enumerate(self.raw_materials, start=1):
            source_wh = getattr(item, "source_warehouse", None) or getattr(item, "warehouse", None) or self.warehouse
            if not source_wh:
                frappe.throw(_(f"Source warehouse is mandatory for row {row_index}"))

    def initialize_tracking_fields(self):
        """Initialize tracking fields for all items"""
        for item in (self.raw_materials or []):
            if not item.extra_qty:
                item.extra_qty = 0
            if not item.target_qty:
                item.target_qty = 0
            if not item.expected_qty:
                item.expected_qty = 0
            if not item.transfer_status:
                item.transfer_status = "Pending"
            
            # Calculate target quantity (pending + extra)
            item.target_qty = flt(item.pending_qty or 0) + flt(item.extra_qty or 0)
            
            # Calculate expected quantity (transfer + extra)
            item.expected_qty = flt(item.transfer_qty or 0) + flt(item.extra_qty or 0)
            
            # Update transfer status
            self.update_item_transfer_status(item)

    def handle_extra_quantities_automatically(self):
        """Handle extra quantities when users enter transfer_qty > pending_qty"""
        if not self.raw_materials:
            return
            
        # Process each item individually for work-order specific distribution
        for item in self.raw_materials:
            pending_qty = flt(item.pending_qty or 0)
            transfer_qty = flt(item.transfer_qty or 0)
            
            if transfer_qty > pending_qty:
                extra_qty = transfer_qty - pending_qty
                print(f"DEBUG: Item {item.item_code} has extra quantity: {extra_qty}")
                
                # Get work orders that use this specific item
                work_orders_using_item = self.get_work_orders_using_item(item.item_code)
                print(f"DEBUG: Work orders using {item.item_code}: {len(work_orders_using_item)}")
                
                if work_orders_using_item:
                    # Distribute extra quantity among work orders using this item
                    extra_per_wo = extra_qty / len(work_orders_using_item)
                    print(f"DEBUG: Extra per work order: {extra_per_wo}")
                    
                    # Add extra quantity to this item
                    item.extra_qty = flt(item.extra_qty or 0) + extra_qty
                    item.target_qty = flt(item.pending_qty or 0) + flt(item.extra_qty or 0)
                    item.expected_qty = flt(item.transfer_qty or 0) + flt(item.extra_qty or 0)
                    
                    # Update transfer status
                    self.update_item_transfer_status(item)
                    
                    print(f"DEBUG: Added {extra_qty} extra to {item.item_code} (distributed among {len(work_orders_using_item)} work orders)")
                else:
                    # If no work orders found, just add to this item
                    item.extra_qty = flt(item.extra_qty or 0) + extra_qty
                    item.target_qty = flt(item.pending_qty or 0) + flt(item.extra_qty or 0)
                    item.expected_qty = flt(item.transfer_qty or 0) + flt(item.extra_qty or 0)
                    self.update_item_transfer_status(item)
                    print(f"DEBUG: No work orders found for {item.item_code}, added {extra_qty} extra to item only")

    def get_work_orders_using_item(self, item_code):
        """Get work orders that use the specified item"""
        try:
            # Get work orders from the Work Order Transfer Manager
            if not self.work_order_transfer_manager:
                return []
                
            wotm_doc = frappe.get_doc("Work Order Transfer Manager", self.work_order_transfer_manager)
            work_orders = []
            
            for wo in wotm_doc.work_orders:
                # Check if this work order uses the item
                wo_doc = frappe.get_doc("Work Order", wo.work_order)
                for item in wo_doc.required_items:
                    if item.item_code == item_code:
                        work_orders.append(wo.work_order)
                        break
            
            return work_orders
        except Exception as e:
            print(f"DEBUG: Error getting work orders for item {item_code}: {str(e)}")
            return []

    def distribute_extra_quantities(self):
        """Distribute extra quantities evenly across all items"""
        if not self.raw_materials:
            return
            
        # Calculate total extra quantity to distribute
        total_extra = sum(flt(item.extra_qty or 0) for item in self.raw_materials)
        
        if total_extra <= 0:
            return
            
        # Count items that can receive extra quantity
        eligible_items = [item for item in self.raw_materials if flt(item.pending_qty or 0) > 0]
        
        if not eligible_items:
            return
            
        # Calculate average extra per item
        avg_extra_per_item = total_extra / len(eligible_items)
        
        # Distribute extra quantities
        for item in eligible_items:
            # Set extra quantity to average
            item.extra_qty = avg_extra_per_item
            
            # Recalculate target and expected quantities
            item.target_qty = flt(item.pending_qty or 0) + flt(item.extra_qty or 0)
            item.expected_qty = flt(item.transfer_qty or 0) + flt(item.extra_qty or 0)
            
            # Update transfer status
            self.update_item_transfer_status(item)

    def update_item_transfer_status(self, item):
        """Update transfer status based on quantities"""
        transfer_qty = flt(item.transfer_qty or 0)
        pending_qty = flt(item.pending_qty or 0)
        extra_qty = flt(item.extra_qty or 0)
        target_qty = flt(item.target_qty or 0)
        transferred_so_far = flt(item.transferred_qty_so_far or 0)
        
        # Calculate total required (original requirement)
        total_required = transferred_so_far + pending_qty
        
        # Check if fully transferred based on total requirement
        if transferred_so_far >= total_required:
            item.transfer_status = "Fully Transferred"
        elif transferred_so_far > 0:
            item.transfer_status = "Partially Transferred"
        else:
            item.transfer_status = "Pending"

    def set_extra_quantity_for_items(self, extra_quantities):
        """Set extra quantities for specific items"""
        for item_code, extra_qty in extra_quantities.items():
            for item in (self.raw_materials or []):
                if item.item_code == item_code:
                    item.extra_qty = flt(extra_qty)
                    item.target_qty = flt(item.pending_qty or 0) + flt(item.extra_qty or 0)
                    item.expected_qty = flt(item.transfer_qty or 0) + flt(item.extra_qty or 0)
                    self.update_item_transfer_status(item)
                    break

    def sync_warehouse_information(self):
        """Sync warehouse information from parent to child table rows"""
        if not self.raw_materials:
            return
            
        updated_count = 0
        for item in self.raw_materials:
            item_updated = False
            
            # Update source_warehouse if parent has it and child doesn't or it's different
            if self.source_warehouse and getattr(item, "source_warehouse", None) != self.source_warehouse:
                item.source_warehouse = self.source_warehouse
                item_updated = True
                
            # Update target_warehouse if parent has it and child doesn't or it's different
            if self.target_warehouse and getattr(item, "target_warehouse", None) != self.target_warehouse:
                item.target_warehouse = self.target_warehouse
                item_updated = True
                
            if item_updated:
                updated_count += 1
                
        if updated_count > 0:
            print(f"🔍 DEBUG: Synced warehouse information for {updated_count} items")

    # ---------- allocation / SE creation ----------

    def validate_allocation(self):
        if not self.raw_materials:
            return
            
        # Get work orders for this sales order
        work_orders = frappe.db.sql("""
            SELECT name, production_item, qty, material_transferred_for_manufacturing, docstatus
            FROM `tabWork Order`
            WHERE sales_order = %s AND docstatus = 1
        """, (self.sales_order,), as_dict=True)
        
        if not work_orders:
            frappe.throw("No submitted work orders found for this sales order")

        # Track items that cannot be allocated
        unallocated_items = []
        
        for raw_item in self.raw_materials:
            if flt(raw_item.transfer_qty) <= 0:
                continue
                
            can_allocate = False
            allocation_details = []
            
            for wo in work_orders:
                # Get BOM for this work order
                bom = frappe.db.get_value("BOM", {
                    "item": wo.production_item, 
                    "is_active": 1, 
                    "is_default": 1
                })
                
                if bom:
                    bom_doc = frappe.get_doc("BOM", bom)
                    # Check if this raw material is in the BOM
                    bom_items = [item.item_code for item in bom_doc.items]
                    if raw_item.item_code in bom_items:
                        can_allocate = True
                        allocation_details.append(f"Work Order {wo.name} (BOM: {bom})")
                    else:
                        allocation_details.append(f"Work Order {wo.name} - Not in BOM")
                else:
                    allocation_details.append(f"Work Order {wo.name} - No BOM found")
            
            if not can_allocate:
                unallocated_items.append({
                    "item_code": raw_item.item_code,
                    "details": allocation_details
                })
        
        # If there are unallocated items, provide detailed error message
        if unallocated_items:
            error_msg = "The following raw materials cannot be allocated to any work order:\n\n"
            for item in unallocated_items:
                error_msg += f"• {item['item_code']}:\n"
                for detail in item['details']:
                    error_msg += f"  - {detail}\n"
                error_msg += "\n"
            
            error_msg += "Please check BOM configurations or ensure the raw materials are included in the BOMs of the production items."
            
            frappe.throw(error_msg)

    def get_bom_allocation_debug_info(self, item_code):
        """Get detailed BOM allocation debug information for an item"""
        debug_info = {
            "item_code": item_code,
            "work_orders": [],
            "boms_checked": [],
            "can_allocate": False
        }
        
        # Get work orders for this sales order
        work_orders = frappe.db.sql("""
            SELECT name, production_item, qty, material_transferred_for_manufacturing, docstatus
            FROM `tabWork Order`
            WHERE sales_order = %s AND docstatus = 1
        """, (self.sales_order,), as_dict=True)
        
        for wo in work_orders:
            wo_info = {
                "work_order": wo.name,
                "production_item": wo.production_item,
                "bom_found": False,
                "bom_name": None,
                "item_in_bom": False
            }
            
            # Check for BOM
            bom = frappe.db.get_value("BOM", {
                "item": wo.production_item, 
                "is_active": 1, 
                "is_default": 1
            })
            
            if bom:
                wo_info["bom_found"] = True
                wo_info["bom_name"] = bom
                
                # Check if item is in BOM
                bom_doc = frappe.get_doc("BOM", bom)
                bom_items = [item.item_code for item in bom_doc.items]
                wo_info["item_in_bom"] = item_code in bom_items
                
                if item_code in bom_items:
                    debug_info["can_allocate"] = True
            
            debug_info["work_orders"].append(wo_info)
        
        return debug_info

    def create_stock_entries_for_work_orders(self):
        print(f"🔍 DEBUG: Creating stock entries for work orders")
        work_orders = frappe.db.sql(
            """
            SELECT name, production_item, qty, material_transferred_for_manufacturing, creation, docstatus, wip_warehouse
            FROM `tabWork Order`
            WHERE sales_order = %s AND docstatus = 1
            ORDER BY creation ASC
            """, (self.sales_order,), as_dict=True)
        print(f"🔍 DEBUG: Found {len(work_orders)} work orders for sales order {self.sales_order}")

        work_order_allocation = {}
        for raw_item in self.raw_materials:
            if flt(raw_item.transfer_qty) <= 0:
                continue

            remaining_qty = flt(raw_item.transfer_qty)
            print(f"🔍 DEBUG: Allocating {raw_item.item_code} - Transfer Qty: {raw_item.transfer_qty}, Remaining: {remaining_qty}")

            # First, calculate BOM requirements for all work orders
            bom_allocations = {}
            total_bom_requirement = 0
            
            for wo in work_orders:
                wo_pending_qty = flt(wo.qty) - flt(wo.material_transferred_for_manufacturing)
                if wo_pending_qty <= 0:
                    continue

                bom = frappe.db.get_value("BOM", {"item": wo.production_item, "is_active": 1, "is_default": 1})
                if not bom:
                    continue
                bom_doc = frappe.get_doc("BOM", bom)
                bom_item = next((i for i in bom_doc.items if i.item_code == raw_item.item_code), None)
                if not bom_item:
                    continue

                raw_qty_needed = flt(wo_pending_qty) * flt(bom_item.qty) / flt(bom_doc.quantity)
                bom_allocations[wo.name] = raw_qty_needed
                total_bom_requirement += raw_qty_needed

            # Allocate based on BOM requirements first
            for wo in work_orders:
                if remaining_qty <= 0:
                    break

                wo_pending_qty = flt(wo.qty) - flt(wo.material_transferred_for_manufacturing)
                if wo_pending_qty <= 0:
                    continue

                bom_qty_needed = bom_allocations.get(wo.name, 0)
                if bom_qty_needed <= 0:
                    continue

                qty_to_allocate = min(remaining_qty, bom_qty_needed)
                if qty_to_allocate > 0:
                    if wo.name not in work_order_allocation:
                        work_order_allocation[wo.name] = {
                            "work_order": wo.name,
                            "production_item": wo.production_item,
                            "items": []
                        }

                    item_source_wh = getattr(raw_item, "source_warehouse", None) or getattr(raw_item, "warehouse", None) or self.warehouse
                    item_target_wh = getattr(raw_item, "target_warehouse", None) or getattr(raw_item, "t_warehouse", None)

                    work_order_allocation[wo.name]["items"].append({
                        "item_code": raw_item.item_code,
                        "item_name": raw_item.item_name,
                        "qty": qty_to_allocate,
                        "uom": raw_item.uom,
                        "warehouse": item_source_wh,
                        "s_warehouse": item_source_wh,
                        "t_warehouse": item_target_wh
                    })

                    remaining_qty -= qty_to_allocate

            # If there's still remaining quantity (extra), distribute it proportionally among work orders
            if remaining_qty > 0 and total_bom_requirement > 0:
                print(f"🔍 DEBUG: Distributing extra quantity {remaining_qty} for {raw_item.item_code} among work orders")
                for wo in work_orders:
                    if remaining_qty <= 0:
                        break

                    wo_pending_qty = flt(wo.qty) - flt(wo.material_transferred_for_manufacturing)
                    if wo_pending_qty <= 0:
                        continue

                    bom_qty_needed = bom_allocations.get(wo.name, 0)
                    if bom_qty_needed <= 0:
                        continue

                    # Calculate proportional extra allocation
                    extra_proportion = bom_qty_needed / total_bom_requirement
                    extra_qty_to_allocate = min(remaining_qty, remaining_qty * extra_proportion)
                    
                    if extra_qty_to_allocate > 0:
                        if wo.name not in work_order_allocation:
                            work_order_allocation[wo.name] = {
                                "work_order": wo.name,
                                "production_item": wo.production_item,
                                "items": []
                            }

                        item_source_wh = getattr(raw_item, "source_warehouse", None) or getattr(raw_item, "warehouse", None) or self.warehouse
                        item_target_wh = getattr(raw_item, "target_warehouse", None) or getattr(raw_item, "t_warehouse", None)

                        work_order_allocation[wo.name]["items"].append({
                            "item_code": raw_item.item_code,
                            "item_name": raw_item.item_name,
                            "qty": extra_qty_to_allocate,
                            "uom": raw_item.uom,
                            "warehouse": item_source_wh,
                            "s_warehouse": item_source_wh,
                            "t_warehouse": item_target_wh
                        })

                        remaining_qty -= extra_qty_to_allocate
                        print(f"🔍 DEBUG: Allocated extra {extra_qty_to_allocate} to work order {wo.name}")

        # Fallback: if no allocation was created at all, allocate full transfer to the earliest WO with WIP and pending
        if not any(a.get("items") for a in work_order_allocation.values()):
            print("🔍 DEBUG: No BOM-based allocation produced; using fallback allocation to earliest pending Work Order")
            frappe.msgprint(_("No BOM-based allocation matched. Falling back to allocate full transfer to earliest pending Work Order."), alert=True, indicator="orange")
            # Find first WO with pending and wip_warehouse
            fallback_wo = None
            for wo in work_orders:
                wo_pending_qty = flt(wo.qty) - flt(wo.material_transferred_for_manufacturing)
                if wo_pending_qty > 0 and wo.wip_warehouse:
                    fallback_wo = wo
                    break
            if fallback_wo:
                alloc = {"work_order": fallback_wo.name, "production_item": fallback_wo.production_item, "items": []}
                for raw_item in self.raw_materials:
                    if flt(raw_item.transfer_qty) <= 0:
                        continue
                    item_source_wh = getattr(raw_item, "source_warehouse", None) or getattr(raw_item, "warehouse", None) or self.warehouse
                    item_target_wh = getattr(raw_item, "target_warehouse", None) or getattr(raw_item, "t_warehouse", None)
                    alloc["items"].append({
                        "item_code": raw_item.item_code,
                        "item_name": raw_item.item_name,
                        "qty": flt(raw_item.transfer_qty),
                        "uom": raw_item.uom,
                        "warehouse": item_source_wh,
                        "s_warehouse": item_source_wh,
                        "t_warehouse": item_target_wh
                    })
                work_order_allocation[fallback_wo.name] = alloc
            else:
                frappe.msgprint(_("No pending Work Orders with WIP Warehouse found. Cannot create Stock Entries."), alert=True, indicator="red")

        created_stock_entries = []
        for wo_name, allocation in work_order_allocation.items():
            if allocation["items"]:
                se = self.create_stock_entry_for_work_order(wo_name, allocation)
                created_stock_entries.append(se.name)

        if created_stock_entries:
            self.stock_entry = created_stock_entries[0]

        self.update_allocation_quantities(work_order_allocation)

    def update_allocation_quantities(self, work_order_allocation):
        print(f"🔍 DEBUG: Updating allocation quantities")
        item_allocation = {}
        for _, allocation in work_order_allocation.items():
            for item in allocation["items"]:
                item_allocation[item["item_code"]] = item_allocation.get(item["item_code"], 0) + flt(item["qty"])

        for raw_item in self.raw_materials:
            allocated_qty = item_allocation.get(raw_item.item_code, 0)
            raw_item.allocated_qty = allocated_qty
            raw_item.remaining_qty = flt(raw_item.transfer_qty) - allocated_qty

    def create_stock_entry_for_work_order(self, work_order_name, allocation):
        print(f"🔍 DEBUG: Creating stock entry for work order: {work_order_name}")
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

        for item in allocation["items"]:
            s_wh = item.get("s_warehouse") or self.warehouse
            t_wh = item.get("t_warehouse") or wip_warehouse
            stock_entry.append("items", {
                "item_code": item["item_code"],
                "qty": flt(item["qty"]),
                "uom": item["uom"],
                "s_warehouse": s_wh,
                "t_warehouse": t_wh,
                "is_finished_item": 0,
                # "allow_zero_valuation_rate": 1
            })

        try:
            stock_entry.insert(ignore_permissions=True)
            stock_entry.flags.ignore_permissions = True
            stock_entry.submit()
            frappe.msgprint(_(f"Stock Entry created: {stock_entry.name} for Work Order {work_order_name}"), alert=True, indicator="green")
            print(f"🔍 DEBUG: Stock Entry created: {stock_entry.name} for work order {work_order_name}")
        except Exception as e:
            frappe.msgprint(_(f"Error creating Stock Entry for Work Order {work_order_name}: {str(e)}"), alert=True, indicator="red")
            frappe.log_error(f"Error creating Stock Entry for Work Order {work_order_name} in RMT {self.name}: {str(e)}")
            raise
        return stock_entry

    def update_work_orders_with_allocation(self):
        print(f"🔍 DEBUG: Updating work orders with allocation")
        work_orders = frappe.db.sql("""
            SELECT name, production_item, qty, material_transferred_for_manufacturing, creation, docstatus
            FROM `tabWork Order`
            WHERE sales_order = %s AND docstatus = 1
            ORDER BY creation ASC
        """, (self.sales_order,), as_dict=True)

        for raw_item in self.raw_materials:
            if flt(raw_item.transfer_qty) <= 0:
                continue

            remaining_qty = flt(raw_item.transfer_qty)
            for wo in work_orders:
                if remaining_qty <= 0:
                    break

                bom = frappe.db.get_value("BOM", {"item": wo.production_item, "is_active": 1, "is_default": 1})
                if not bom:
                    continue
                bom_doc = frappe.get_doc("BOM", bom)
                bom_item = next((i for i in bom_doc.items if i.item_code == raw_item.item_code), None)
                if not bom_item:
                    continue

                wo_pending_qty = flt(wo.qty) - flt(wo.material_transferred_for_manufacturing)
                if wo_pending_qty <= 0:
                    continue

                raw_qty_needed = flt(wo_pending_qty) * flt(bom_item.qty) / flt(bom_doc.quantity)
                qty_to_allocate = min(remaining_qty, raw_qty_needed)
                if qty_to_allocate > 0:
                    try:
                        production_qty_equivalent = qty_to_allocate * flt(bom_doc.quantity) / flt(bom_item.qty)
                        current_transferred = frappe.db.get_value("Work Order", wo.name, "material_transferred_for_manufacturing") or 0
                        new_transferred = current_transferred + production_qty_equivalent
                        frappe.db.set_value("Work Order", wo.name, "material_transferred_for_manufacturing", new_transferred)
                        remaining_qty -= qty_to_allocate
                    except Exception as e:
                        frappe.log_error(f"Error updating work order {wo.name} in Raw Material Transfer {self.name}: {str(e)}")

# -------- API helpers tied to WOTM --------

@frappe.whitelist()
def get_pending_raw_materials(work_order_transfer_manager):
    """Get raw materials with remaining qty (uses submitted transfers only)"""
    try:
        wotm_doc = frappe.get_doc("Work Order Transfer Manager", work_order_transfer_manager)

        # Build transferred map from submitted RMT
        transferred_map = {}
        rmt_docs = frappe.get_all(
            "Raw Material Transfer",
            filters={"work_order_transfer_manager": work_order_transfer_manager, "docstatus": 1},
            fields=["name"]
        )
        for r in rmt_docs:
            d = frappe.get_doc("Raw Material Transfer", r.name)
            for it in d.raw_materials:
                transferred_map[it.item_code] = transferred_map.get(it.item_code, 0) + flt(it.transfer_qty)

        pending_items = []
        for item in wotm_doc.transfer_items:
            # The pending_qty in WOTM is already the remaining amount after previous transfers
            remaining_qty = flt(item.pending_qty)
            if remaining_qty > 0:
                pending_items.append({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "pending_qty": remaining_qty,
                    "uom": item.uom,
                    "warehouse": wotm_doc.source_warehouse
                })

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
def bulk_delete_raw_material_rows(doc_name, row_indices):
    """Bulk delete rows from Raw Material Transfer for better performance"""
    try:
        doc = frappe.get_doc("Raw Material Transfer", doc_name)
        
        # Convert string indices to integers
        if isinstance(row_indices, str):
            row_indices = [int(x.strip()) for x in row_indices.split(',') if x.strip().isdigit()]
        elif isinstance(row_indices, list):
            row_indices = [int(x) for x in row_indices if str(x).isdigit()]
        
        if not row_indices:
            return {"success": False, "message": "No valid row indices provided"}
        
        # Perform bulk delete
        doc.bulk_delete_rows(row_indices)
        doc.save()
        
        return {
            "success": True, 
            "message": f"Successfully deleted {len(row_indices)} rows",
            "remaining_rows": len(doc.raw_materials)
        }
        
    except Exception as e:
        frappe.log_error(f"Error in bulk_delete_raw_material_rows: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def bulk_clear_all_raw_material_rows(doc_name):
    """Clear all rows from Raw Material Transfer at once"""
    try:
        doc = frappe.get_doc("Raw Material Transfer", doc_name)
        
        # Perform bulk clear
        doc.bulk_clear_all_rows()
        doc.save()
        
        return {
            "success": True, 
            "message": "Successfully cleared all rows",
            "remaining_rows": 0
        }
        
    except Exception as e:
        frappe.log_error(f"Error in bulk_clear_all_raw_material_rows: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def bulk_select_and_delete_rows(doc_name, selected_items):
    """Delete rows based on selected item codes"""
    try:
        doc = frappe.get_doc("Raw Material Transfer", doc_name)
        
        # Convert selected items to list if it's a string
        if isinstance(selected_items, str):
            selected_items = [s.strip() for s in selected_items.split(',') if s.strip()]
        
        if not selected_items:
            return {"success": False, "message": "No items selected for deletion"}
        
        # Find indices of rows to delete
        indices_to_delete = []
        for i, row in enumerate(doc.raw_materials):
            if row.item_code in selected_items:
                indices_to_delete.append(i)
        
        if not indices_to_delete:
            return {"success": False, "message": "No matching items found"}
        
        # Perform bulk delete
        doc.bulk_delete_rows(indices_to_delete)
        doc.save()
        
        return {
            "success": True, 
            "message": f"Successfully deleted {len(indices_to_delete)} rows",
            "remaining_rows": len(doc.raw_materials)
        }
        
    except Exception as e:
        frappe.log_error(f"Error in bulk_select_and_delete_rows: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def distribute_extra_quantities(doc_name, total_extra_qty):
    """Distribute extra quantities evenly across all items in the document"""
    try:
        doc = frappe.get_doc("Raw Material Transfer", doc_name)
        
        if not doc.raw_materials:
            return {"success": False, "message": "No raw materials found"}
        
        # Get eligible items (items with pending quantity > 0)
        eligible_items = [item for item in doc.raw_materials if flt(item.pending_qty or 0) > 0]
        
        if not eligible_items:
            return {"success": False, "message": "No eligible items found for extra quantity distribution"}
        
        # Calculate average extra per item
        avg_extra_per_item = flt(total_extra_qty) / len(eligible_items)
        
        # Distribute extra quantities
        for item in eligible_items:
            item.extra_qty = avg_extra_per_item
            item.target_qty = flt(item.pending_qty or 0) + flt(item.extra_qty or 0)
            item.expected_qty = flt(item.transfer_qty or 0) + flt(item.extra_qty or 0)
            
            # Update transfer status
            if flt(item.transfer_qty or 0) >= flt(item.target_qty or 0):
                item.transfer_status = "Fully Transferred"
            elif flt(item.transfer_qty or 0) > 0:
                item.transfer_status = "Partially Transferred"
            else:
                item.transfer_status = "Pending"
        
        # Save the document
        doc.save()
        
        return {
            "success": True, 
            "message": f"Extra quantity {total_extra_qty} distributed evenly across {len(eligible_items)} items",
            "avg_extra_per_item": avg_extra_per_item
        }
        
    except Exception as e:
        frappe.log_error(f"Error distributing extra quantities: {str(e)}", "Extra Quantity Distribution Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def set_extra_quantity_for_item(doc_name, item_code, extra_qty):
    """Set extra quantity for a specific item"""
    try:
        doc = frappe.get_doc("Raw Material Transfer", doc_name)
        
        # Find the item
        item_found = False
        for item in doc.raw_materials:
            if item.item_code == item_code:
                item.extra_qty = flt(extra_qty)
                item.target_qty = flt(item.pending_qty or 0) + flt(item.extra_qty or 0)
                item.expected_qty = flt(item.transfer_qty or 0) + flt(item.extra_qty or 0)
                
                # Update transfer status
                if flt(item.transfer_qty or 0) >= flt(item.target_qty or 0):
                    item.transfer_status = "Fully Transferred"
                elif flt(item.transfer_qty or 0) > 0:
                    item.transfer_status = "Partially Transferred"
                else:
                    item.transfer_status = "Pending"
                
                item_found = True
                break
        
        if not item_found:
            return {"success": False, "message": f"Item {item_code} not found"}
        
        # Save the document
        doc.save()
        
        return {
            "success": True, 
            "message": f"Extra quantity {extra_qty} set for item {item_code}"
        }
        
    except Exception as e:
        frappe.log_error(f"Error setting extra quantity: {str(e)}", "Set Extra Quantity Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def refresh_transferred_quantities(doc_name):
    """Refresh transferred quantities from actual Stock Entries"""
    try:
        doc = frappe.get_doc("Raw Material Transfer", doc_name)
        doc.calculate_transferred_quantities()
        doc.save()
        
        return {
            "success": True,
            "message": "Transferred quantities refreshed successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error refreshing transferred quantities: {str(e)}", "Refresh Transferred Quantities Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_transfer_summary(doc_name):
    """Get comprehensive transfer summary with all quantities"""
    try:
        doc = frappe.get_doc("Raw Material Transfer", doc_name)
        
        summary = {
            "total_items": len(doc.raw_materials) if doc.raw_materials else 0,
            "total_pending_qty": 0,
            "total_transfer_qty": 0,
            "total_transferred_so_far": 0,
            "total_extra_qty": 0,
            "total_target_qty": 0,
            "total_expected_qty": 0,
            "items": []
        }
        
        for item in (doc.raw_materials or []):
            pending_qty = flt(item.pending_qty or 0)
            transfer_qty = flt(item.transfer_qty or 0)
            transferred_so_far = flt(item.transferred_qty_so_far or 0)
            extra_qty = flt(item.extra_qty or 0)
            target_qty = flt(item.target_qty or 0)
            expected_qty = flt(item.expected_qty or 0)
            
            summary["total_pending_qty"] += pending_qty
            summary["total_transfer_qty"] += transfer_qty
            summary["total_transferred_so_far"] += transferred_so_far
            summary["total_extra_qty"] += extra_qty
            summary["total_target_qty"] += target_qty
            summary["total_expected_qty"] += expected_qty
            
            summary["items"].append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "pending_qty": pending_qty,
                "transfer_qty": transfer_qty,
                "transferred_so_far": transferred_so_far,
                "extra_qty": extra_qty,
                "target_qty": target_qty,
                "expected_qty": expected_qty,
                "transfer_status": item.transfer_status,
                "uom": item.uom
            })
        
        return {"success": True, "summary": summary}
        
    except Exception as e:
        frappe.log_error(f"Error getting transfer summary: {str(e)}", "Transfer Summary Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def debug_bom_allocation(doc_name, item_code=None):
    """Debug BOM allocation for raw material transfer"""
    try:
        doc = frappe.get_doc("Raw Material Transfer", doc_name)
        
        if item_code:
            # Debug specific item
            debug_info = doc.get_bom_allocation_debug_info(item_code)
            return {"success": True, "debug_info": debug_info}
        else:
            # Debug all items
            debug_info = {}
            for item in doc.raw_materials:
                if item.item_code:
                    debug_info[item.item_code] = doc.get_bom_allocation_debug_info(item.item_code)
            
            return {"success": True, "debug_info": debug_info}
        
    except Exception as e:
        frappe.log_error(f"Error debugging BOM allocation: {str(e)}", "BOM Allocation Debug Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def sync_warehouse_information(doc_name):
    """Sync warehouse information from parent to child table rows"""
    try:
        doc = frappe.get_doc("Raw Material Transfer", doc_name)
        doc.sync_warehouse_information()
        doc.save()
        
        return {
            "success": True,
            "message": "Warehouse information synced successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error syncing warehouse information: {str(e)}", "Sync Warehouse Information Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def create_raw_material_transfer_from_pending(work_order_transfer_manager, selected_items=None):
    """Create a new Raw Material Transfer document with selected pending items"""
    try:
        wotm_doc = frappe.get_doc("Work Order Transfer Manager", work_order_transfer_manager)
        if wotm_doc.docstatus != 1:
            frappe.throw("Work Order Transfer Manager must be submitted first")

        # Selected filter
        selected_item_codes = []
        if selected_items:
            if isinstance(selected_items, str):
                selected_item_codes = [s.strip() for s in selected_items.split(',') if s.strip()]
            else:
                selected_item_codes = selected_items

        # Build transferred map from actual Stock Entries
        transferred_map = {}
        rmt_docs = frappe.get_all(
            "Raw Material Transfer",
            filters={"work_order_transfer_manager": work_order_transfer_manager, "docstatus": 1},
            fields=["name", "stock_entry"]
        )
        
        # Get all Stock Entries created from these transfers
        stock_entries = []
        for r in rmt_docs:
            if r.stock_entry:
                stock_entries.append(r.stock_entry)
        
        if stock_entries:
            # Get Stock Entry Items for all related Stock Entries
            se_items = frappe.get_all(
                "Stock Entry Detail",
                filters={
                    "parent": ["in", stock_entries],
                    "s_warehouse": ["is", "not set"]  # Only target warehouse items (transferred out)
                },
                fields=["item_code", "qty"]
            )
            
            for se_item in se_items:
                item_code = se_item.item_code
                qty = flt(se_item.qty)
                transferred_map[item_code] = transferred_map.get(item_code, 0) + qty
                print(f"DEBUG: Found {qty} of {item_code} transferred in Stock Entry")
        
        # Fallback to Raw Material Transfer documents if no Stock Entries found
        if not stock_entries:
            for r in rmt_docs:
                d = frappe.get_doc("Raw Material Transfer", r.name)
                for it in d.raw_materials:
                    transferred_map[it.item_code] = transferred_map.get(it.item_code, 0) + flt(it.transfer_qty)
                    print(f"DEBUG: Fallback - Found {it.transfer_qty} of {it.item_code} from RMT")

        pending_items = []
        for item in wotm_doc.transfer_items:
            if selected_item_codes and item.item_code not in selected_item_codes:
                continue
            # The pending_qty in WOTM is already the remaining amount after previous transfers
            remaining_qty = flt(item.pending_qty)
            if remaining_qty > 0:
                pending_items.append({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "pending_qty": remaining_qty,
                    "uom": item.uom,
                    "warehouse": wotm_doc.source_warehouse
                })

        if not pending_items:
            frappe.throw("No raw materials with pending quantities found")

        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = wotm_doc.sales_order
        rmt.work_order_transfer_manager = work_order_transfer_manager
        rmt.posting_date = wotm_doc.posting_date
        rmt.posting_time = wotm_doc.posting_time
        rmt.company = wotm_doc.company
        rmt.warehouse = wotm_doc.source_warehouse
        rmt.stock_entry_type = wotm_doc.stock_entry_type

        for item in pending_items:
            # Get the total required quantity from WOTM
            wotm_item = None
            for wotm_row in wotm_doc.transfer_items:
                if wotm_row.item_code == item["item_code"]:
                    wotm_item = wotm_row
                    break
            
            total_required = flt(wotm_item.total_required_qty) if wotm_item else flt(item["pending_qty"])
            transferred_so_far = flt(wotm_item.transferred_qty_so_far) if wotm_item else 0
            
            rmt.append("raw_materials", {
                "item_code": item["item_code"],
                "item_name": item["item_name"],
                "total_required_qty": total_required,  # Original requirement
                "pending_qty": item["pending_qty"],  # Remaining to transfer
                "transfer_qty": item["pending_qty"],  # Transfer the full remaining amount
                "transferred_qty_so_far": transferred_so_far,  # Already transferred
                "uom": item["uom"],
                "warehouse": item["warehouse"],
                "source_warehouse": item["warehouse"]
            })

        rmt.insert()
        return {
            "success": True,
            "message": f"Raw Material Transfer document created with {len(pending_items)} items: {rmt.name}",
            "doc_name": rmt.name
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
