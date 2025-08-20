import frappe
from frappe import _
from frappe.utils import flt, now_datetime
from manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager import update_transfer_quantities

class RawMaterialTransfer(frappe.model.document.Document):
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

    def calculate_totals(self):
        total_transfer_qty = 0
        total_items = len(self.raw_materials) if self.raw_materials else 0
        for item in (self.raw_materials or []):
            total_transfer_qty += flt(item.transfer_qty or 0)
        self.total_transfer_qty = total_transfer_qty
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
        print(f"🔍 DEBUG: populate_actual_quantities() called for Raw Material Transfer: {self.name}")
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
        """Calculate transferred quantities from existing submitted transfers"""
        if not self.work_order_transfer_manager or not self.raw_materials:
            return
            
        try:
            # Get all submitted transfers for this WOTM
            existing_transfers = frappe.get_all(
                "Raw Material Transfer",
                filters={"work_order_transfer_manager": self.work_order_transfer_manager, "docstatus": 1},
                fields=["name"]
            )
            
            # Calculate total transferred for each item
            item_total_transferred = {}
            for tr in existing_transfers:
                tr_doc = frappe.get_doc("Raw Material Transfer", tr.name)
                for ti in tr_doc.raw_materials:
                    item_total_transferred[ti.item_code] = item_total_transferred.get(ti.item_code, 0) + flt(ti.transfer_qty)
            
            # Update transferred_qty_so_far for each item in current document
            for item in self.raw_materials:
                if item.item_code:
                    item.transferred_qty_so_far = flt(item_total_transferred.get(item.item_code, 0))
                    
        except Exception as e:
            frappe.log_error(f"Error calculating transferred quantities for {self.name}: {str(e)}")

    def before_submit(self):
        print(f"🔍 DEBUG: before_submit() called for Raw Material Transfer: {self.name}")
        try:
            self.validate_allocation()
            self.create_stock_entries_for_work_orders()
            self.update_work_orders_with_allocation()
        except Exception as e:
            frappe.log_error(f"Error in before_submit for Raw Material Transfer {self.name}: {str(e)}")
            frappe.throw(f"Error processing transfer: {str(e)}")

    def on_submit(self):
        try:
            if self.work_order_transfer_manager:
                update_transfer_quantities(self.work_order_transfer_manager, self.name)
                print(f"🔍 DEBUG: WOTM quantities updated for {self.work_order_transfer_manager} using transfer {self.name}")
        except Exception as e:
            frappe.log_error(f"Error updating WOTM after submit for {self.name}: {str(e)}")

    def on_cancel(self):
        print(f"🔍 DEBUG: on_cancel() called for Raw Material Transfer: {self.name}")
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
        for item in (self.raw_materials or []):
            if flt(item.transfer_qty) > flt(item.pending_qty):
                frappe.throw(f"Transfer quantity ({item.transfer_qty}) for {item.item_code} cannot exceed pending quantity ({item.pending_qty})")
            if flt(item.transfer_qty) <= 0:
                frappe.throw(f"Transfer quantity for {item.item_code} must be greater than 0")

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

    # ---------- allocation / SE creation ----------

    def validate_allocation(self):
        if not self.raw_materials:
            return
        work_orders = frappe.db.sql("""
            SELECT name, production_item, qty, material_transferred_for_manufacturing, docstatus
            FROM `tabWork Order`
            WHERE sales_order = %s AND docstatus = 1
        """, (self.sales_order,), as_dict=True)
        if not work_orders:
            frappe.throw("No submitted work orders found for this sales order")

        for raw_item in self.raw_materials:
            if flt(raw_item.transfer_qty) <= 0:
                continue
            can_allocate = False
            for wo in work_orders:
                bom = frappe.db.get_value("BOM", {"item": wo.production_item, "is_active": 1, "is_default": 1})
                if bom:
                    bom_doc = frappe.get_doc("BOM", bom)
                    if any(item.item_code == raw_item.item_code for item in bom_doc.items):
                        can_allocate = True
                        break
            if not can_allocate:
                frappe.throw(f"Raw material {raw_item.item_code} cannot be allocated to any work order. Please check BOM configurations.")

    def create_stock_entries_for_work_orders(self):
        print(f"🔍 DEBUG: Creating stock entries for work orders")
        work_orders = frappe.db.sql("""
            SELECT name, production_item, qty, material_transferred_for_manufacturing, creation, docstatus
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
                "allow_zero_valuation_rate": 1
            })

        stock_entry.insert()
        stock_entry.submit()
        print(f"🔍 DEBUG: Stock Entry created: {stock_entry.name} for work order {work_order_name}")
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
    print(f"🔍 DEBUG: get_pending_raw_materials called for: {work_order_transfer_manager}")
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
def create_raw_material_transfer_from_pending(work_order_transfer_manager, selected_items=None):
    """Create a new Raw Material Transfer document with selected pending items"""
    print(f"🔍 DEBUG: create_raw_material_transfer_from_pending called")
    print(f"🔍 DEBUG: work_order_transfer_manager: {work_order_transfer_manager}")
    print(f"🔍 DEBUG: selected_items: {selected_items}")

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

        # Build transferred map
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
