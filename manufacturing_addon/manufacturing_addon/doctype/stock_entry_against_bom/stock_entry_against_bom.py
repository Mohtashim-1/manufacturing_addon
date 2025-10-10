# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StockEntryAgainstBOM(Document):
    def validate(self):
        self.calculate_total_qty()
        self.calculate_total_qty_raw_materials()
        self.initialize_tracking_fields()
        # Adjust quantities based on remaining across previously submitted documents for the same Sales Order
        self._enforce_cross_document_remaining()

    def onload(self):
        """Ensure tracking fields are properly initialized when document is loaded"""
        self.ensure_tracking_fields_initialized()

    def ensure_tracking_fields_initialized(self):
        """Ensure tracking fields are properly initialized"""
        try:
            # Initialize tracking fields for finished items
            for row in self.stock_entry_item_table:
                if row.issued_qty is None:
                    row.issued_qty = 0
                if row.remaining_qty is None:
                    row.remaining_qty = (row.qty or 0) - (row.issued_qty or 0)
                if not row.transfer_status:
                    row.transfer_status = "Pending"
            
            # Initialize tracking fields for raw materials
            for row in self.stock_entry_required_item_table:
                if row.issued_qty is None:
                    row.issued_qty = 0
                if row.remaining_qty is None:
                    row.remaining_qty = (row.qty or 0) - (row.issued_qty or 0)
                if not row.transfer_status:
                    row.transfer_status = "Pending"
            
            print(f"DEBUG: Ensured tracking fields initialized for {self.name}")
        except Exception as e:
            print(f"DEBUG: Error initializing tracking fields: {str(e)}")

    def check_database_values(self):
        """Check the current database values for tracking fields"""
        try:
            print(f"DEBUG: ===== CHECKING DATABASE VALUES =====")
            print(f"DEBUG: Document: {self.name}")
            
            # Check finished goods table
            print(f"DEBUG: Checking finished goods table:")
            for i, row in enumerate(self.stock_entry_item_table[:3]):
                print(f"DEBUG:   Row {i}: {row.item}")
                print(f"DEBUG:     qty: {row.qty}")
                print(f"DEBUG:     issued_qty: {row.issued_qty}")
                print(f"DEBUG:     remaining_qty: {row.remaining_qty}")
                print(f"DEBUG:     transfer_status: {row.transfer_status}")
                if hasattr(row, 'name') and row.name:
                    print(f"DEBUG:     row name: {row.name}")
                else:
                    print(f"DEBUG:     no row name")
            
            # Check raw materials table
            print(f"DEBUG: Checking raw materials table:")
            for i, row in enumerate(self.stock_entry_required_item_table[:3]):
                print(f"DEBUG:   Row {i}: {row.item}")
                print(f"DEBUG:     qty: {row.qty}")
                print(f"DEBUG:     issued_qty: {row.issued_qty}")
                print(f"DEBUG:     remaining_qty: {row.remaining_qty}")
                print(f"DEBUG:     transfer_status: {row.transfer_status}")
                if hasattr(row, 'name') and row.name:
                    print(f"DEBUG:     row name: {row.name}")
                else:
                    print(f"DEBUG:     no row name")
            
            print(f"DEBUG: ===== COMPLETED CHECKING DATABASE VALUES =====")
        except Exception as e:
            print(f"DEBUG: ERROR in check_database_values: {str(e)}")

    def force_update_tracking_fields(self):
        """Force update tracking fields in the database"""
        try:
            print(f"DEBUG: ===== FORCE UPDATE TRACKING FIELDS =====")
            print(f"DEBUG: Document: {self.name}")
            
            # Update finished goods tracking fields
            print(f"DEBUG: Updating {len(self.stock_entry_item_table)} finished goods items")
            for i, row in enumerate(self.stock_entry_item_table):
                if row.issued_qty is None:
                    row.issued_qty = 0
                if row.remaining_qty is None:
                    row.remaining_qty = (row.qty or 0) - (row.issued_qty or 0)
                if not row.transfer_status:
                    row.transfer_status = "Pending"
                
                print(f"DEBUG: Finished item {i}: {row.item}")
                print(f"DEBUG:   qty: {row.qty}, issued_qty: {row.issued_qty}, remaining_qty: {row.remaining_qty}")
                
                # Force update the database
                if hasattr(row, 'name') and row.name:
                    frappe.db.set_value("Stock Entry Item Table", row.name, "issued_qty", row.issued_qty)
                    frappe.db.set_value("Stock Entry Item Table", row.name, "remaining_qty", row.remaining_qty)
                    frappe.db.set_value("Stock Entry Item Table", row.name, "transfer_status", row.transfer_status)
                    print(f"DEBUG:   Updated database for row {row.name}")
                else:
                    print(f"DEBUG:   No row name found, skipping database update")
            
            # Update raw materials tracking fields
            print(f"DEBUG: Updating {len(self.stock_entry_required_item_table)} raw material items")
            for i, row in enumerate(self.stock_entry_required_item_table):
                if row.issued_qty is None:
                    row.issued_qty = 0
                if row.remaining_qty is None:
                    row.remaining_qty = (row.qty or 0) - (row.issued_qty or 0)
                if not row.transfer_status:
                    row.transfer_status = "Pending"
                
                print(f"DEBUG: Raw material {i}: {row.item}")
                print(f"DEBUG:   qty: {row.qty}, issued_qty: {row.issued_qty}, remaining_qty: {row.remaining_qty}")
                
                # Force update the database
                if hasattr(row, 'name') and row.name:
                    frappe.db.set_value("Stock Entry Required Item Table", row.name, "issued_qty", row.issued_qty)
                    frappe.db.set_value("Stock Entry Required Item Table", row.name, "remaining_qty", row.remaining_qty)
                    frappe.db.set_value("Stock Entry Required Item Table", row.name, "transfer_status", row.transfer_status)
                    print(f"DEBUG:   Updated database for row {row.name}")
                else:
                    print(f"DEBUG:   No row name found, skipping database update")
            
            print(f"DEBUG: ===== COMPLETED FORCE UPDATE TRACKING FIELDS =====")
        except Exception as e:
            print(f"DEBUG: ERROR in force_update_tracking_fields: {str(e)}")
            print(f"DEBUG: Error updating tracking fields: {str(e)}")

    def calculate_total_qty(self):
        total_qty = 0
        for row in self.stock_entry_item_table:
            total_qty += row.qty
        self.total_quantity = total_qty

    def calculate_total_qty_raw_materials(self):
        total_qty_raw_materials = 0
        for row in self.stock_entry_required_item_table:
            total_qty_raw_materials += row.qty
        self.total_qty = total_qty_raw_materials

    def initialize_tracking_fields(self):
        """Initialize tracking fields for new items"""
        for row in self.stock_entry_item_table:
            if not row.issued_qty:
                row.issued_qty = 0
            if not row.remaining_qty:
                row.remaining_qty = row.qty
            if not row.transfer_status:
                row.transfer_status = "Pending"
        
        for row in self.stock_entry_required_item_table:
            if not row.issued_qty:
                row.issued_qty = 0
            if not row.remaining_qty:
                row.remaining_qty = row.qty
            if not row.transfer_status:
                row.transfer_status = "Pending"

    def update_tracking_fields(self):
        """Update tracking fields based on issued quantities"""
        for row in self.stock_entry_item_table:
            row.remaining_qty = row.qty - row.issued_qty
            if row.remaining_qty == 0:
                row.transfer_status = "Fully Transferred"
            elif row.issued_qty > 0:
                row.transfer_status = "Partially Transferred"
            else:
                row.transfer_status = "Pending"
        
        for row in self.stock_entry_required_item_table:
            row.remaining_qty = row.qty - row.issued_qty
            if row.remaining_qty == 0:
                row.transfer_status = "Fully Transferred"
            elif row.issued_qty > 0:
                row.transfer_status = "Partially Transferred"
            else:
                row.transfer_status = "Pending"

    def track_item_issuance(self, item_code, qty_to_issue, item_type="finished"):
        """Track issuance of items and update tracking fields"""
        try:
            if item_type == "finished":
                for row in self.stock_entry_item_table:
                    if row.item == item_code:
                        if row.remaining_qty >= qty_to_issue:
                            row.issued_qty += qty_to_issue
                            row.remaining_qty = row.qty - row.issued_qty
                            
                            # Update transfer status
                            if row.remaining_qty == 0:
                                row.transfer_status = "Fully Transferred"
                            else:
                                row.transfer_status = "Partially Transferred"
                            
                            print(f"DEBUG: Issued {qty_to_issue} of {item_code} (Finished Item)")
                            return True
                        else:
                            frappe.throw(f"Insufficient remaining quantity for {item_code}. Available: {row.remaining_qty}, Requested: {qty_to_issue}")
            else:
                for row in self.stock_entry_required_item_table:
                    if row.item == item_code:
                        if row.remaining_qty >= qty_to_issue:
                            row.issued_qty += qty_to_issue
                            row.remaining_qty = row.qty - row.issued_qty
                            
                            # Update transfer status
                            if row.remaining_qty == 0:
                                row.transfer_status = "Fully Transferred"
                            else:
                                row.transfer_status = "Partially Transferred"
                            
                            print(f"DEBUG: Issued {qty_to_issue} of {item_code} (Raw Material)")
                            return True
                        else:
                            frappe.throw(f"Insufficient remaining quantity for {item_code}. Available: {row.remaining_qty}, Requested: {qty_to_issue}")
            
            return False
        except Exception as e:
            frappe.log_error(f"Error tracking item issuance: {str(e)}", "Item Issuance Tracking Error")
            frappe.throw(f"Error tracking item issuance: {str(e)}")

    def create_transfer_stock_entry(self, item_code, qty_to_transfer, item_type="finished"):
        """Create and submit Stock Entry for item transfer"""
        try:
            # Track the issuance first
            if not self.track_item_issuance(item_code, qty_to_transfer, item_type):
                frappe.throw(f"Failed to track issuance for {item_code}")
            
            # Create Stock Entry
            stock_entry = frappe.new_doc("Stock Entry")
            stock_entry.stock_entry_type = "Material Transfer"
            stock_entry.posting_date = self.posting_date
            stock_entry.posting_time = self.posting_time
            stock_entry.custom_cost_center = self.cost_center
            
            # Set warehouses
            stock_entry.from_warehouse = self.source_warehouse
            stock_entry.to_warehouse = self.target_warehouse
            
            # Add item to Stock Entry
            stock_entry.append("items", {
                "item_code": item_code,
                "qty": qty_to_transfer,
                "s_warehouse": self.source_warehouse,
                "t_warehouse": self.target_warehouse,
                "uom": frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
            })
            
            # Save and submit Stock Entry
            stock_entry.save(ignore_permissions=True)
            stock_entry.submit()
            
            print(f"DEBUG: Created and submitted Stock Entry {stock_entry.name} for {qty_to_transfer} {item_code}")
            
            # Update tracking fields
            self.update_tracking_fields()
            self.save()
            
            return stock_entry.name
            
        except Exception as e:
            frappe.log_error(f"Error creating transfer Stock Entry: {str(e)}", "Transfer Stock Entry Error")
            frappe.throw(f"Error creating transfer Stock Entry: {str(e)}")


    def on_submit(self):
        # Create Stock Entry for each finished item using BOM
        # No capping or restrictions - allow any quantities
        
        for row in self.stock_entry_item_table:
            if row.bom and row.qty:
                
                stock_entry = frappe.new_doc("Stock Entry")
                stock_entry.stock_entry_type = self.stock_entry_type
                stock_entry.from_bom = 1
                stock_entry.use_multi_level_bom = 0
                stock_entry.fg_completed_qty = row.qty
                stock_entry.bom_no = row.bom
                stock_entry.custom_cost_center = self.cost_center
                stock_entry.custom_stock_entry_against_bom = self.name
                
                # Set source and target warehouses from the document
                if hasattr(self, 'source_warehouse') and self.source_warehouse:
                    stock_entry.from_warehouse = self.source_warehouse
                if hasattr(self, 'target_warehouse') and self.target_warehouse:
                    stock_entry.to_warehouse = self.target_warehouse

                # Handle different Stock Entry types
                if self.stock_entry_type == "Material Transfer for Manufacture":
                    # For Material Transfer, add finished item as target
                    stock_entry.append("items", {
                        "item_code": row.item,
                        "qty": row.qty,
                        "t_warehouse": self.target_warehouse if hasattr(self, "target_warehouse") and self.target_warehouse else None,
                    })
                elif self.stock_entry_type == "Manufacture":
                    # For Manufacture, add finished item as target (no source warehouse)
                    stock_entry.append("items", {
                        "item_code": row.item,
                        "qty": row.qty,
                        "t_warehouse": self.target_warehouse if hasattr(self, "target_warehouse") and self.target_warehouse else None,
                    })
                else:
                    # For other types, add with both source and target
                    stock_entry.append("items", {
                        "item_code": row.item,
                        "qty": row.qty,
                        "t_warehouse": self.target_warehouse if hasattr(self, "target_warehouse") and self.target_warehouse else None,
                        "s_warehouse": self.source_warehouse if hasattr(self, "source_warehouse") and self.source_warehouse else None,
                    })
                
                # Save the Stock Entry
                stock_entry.save(ignore_permissions=True)
                
                # Trigger the get_items button to fetch raw materials from BOM
                stock_entry.get_items()
                
                # Debug prints to track posting date and time
                print("=== DEBUG POSTING DATE/TIME ===")
                print(f"Parent document posting_date: {self.posting_date}")
                print(f"Parent document posting_time: {self.posting_time}")
                print(f"Stock Entry posting_date before setting: {stock_entry.posting_date}")
                print(f"Stock Entry posting_time before setting: {stock_entry.posting_time}")
                
                # Set posting date and time AFTER get_items() to ensure they are not overridden
                stock_entry.posting_date = self.posting_date
                stock_entry.posting_time = self.posting_time
                
                print(f"Stock Entry posting_date after setting: {stock_entry.posting_date}")
                print(f"Stock Entry posting_time after setting: {stock_entry.posting_time}")
                print("=== END DEBUG ===")
                
                # The expense_account will be automatically set by the hook in stock_addon
                # based on the Stock Entry Type's custom_account field
                
                # Save again with the raw materials
                stock_entry.save(ignore_permissions=True)
                
                # Debug prints after save
                print("=== DEBUG AFTER SAVE ===")
                print(f"Stock Entry posting_date after save: {stock_entry.posting_date}")
                print(f"Stock Entry posting_time after save: {stock_entry.posting_time}")
                print(f"Stock Entry name: {stock_entry.name}")
                print("=== END DEBUG AFTER SAVE ===")
                
                # Use database update to directly set posting date and time
                frappe.db.set_value("Stock Entry", stock_entry.name, "posting_date", self.posting_date)
                frappe.db.set_value("Stock Entry", stock_entry.name, "posting_time", self.posting_time)
                
                # Reload the document to get updated values
                stock_entry.reload()
                
                # Debug prints after database update
                print("=== DEBUG AFTER DB UPDATE ===")
                print(f"Stock Entry posting_date after db update: {stock_entry.posting_date}")
                print(f"Stock Entry posting_time after db update: {stock_entry.posting_time}")
                print(f"Stock Entry name: {stock_entry.name}")
                print("=== END DEBUG AFTER DB UPDATE ===")
                
                # Update issued_qty to reflect that this quantity has been processed
                row.issued_qty = row.qty
                row.remaining_qty = 0
                row.transfer_status = "Fully Transferred"
                
                # stock_entry.submit()
                
                frappe.msgprint(f"Stock Entry created for {row.item} (Qty: {row.qty}): {stock_entry.name}")
        
        if not self.stock_entry_item_table:
            frappe.throw("No items found in Stock Entry Item Table")
        
        # Update raw materials issued_qty as well
        for row in self.stock_entry_required_item_table:
            row.issued_qty = row.qty
            row.remaining_qty = 0
            row.transfer_status = "Fully Transferred"
        
        # Create Transfer Form after all Stock Entries are created
        self.create_transfer_form()

    # --- Helper methods for cross-document remaining calculations ---
    
    def _get_so_totals_by_item(self):
        """Return a dict of item_code -> ordered qty from the linked Sales Order. Returns {} if no Sales Order."""
        print(f"DEBUG: _get_so_totals_by_item called for sales_order: {getattr(self, 'sales_order', None)}")
        if not getattr(self, 'sales_order', None):
            print("DEBUG: No sales_order found, returning empty dict")
            return {}
        totals = {}
        so_items = frappe.get_all(
            "Sales Order Item",
            filters={"parent": self.sales_order},
            fields=["item_code", "qty"],
        )
        print(f"DEBUG: Found {len(so_items)} Sales Order items")
        for it in so_items:
            totals[it.item_code] = totals.get(it.item_code, 0) + (it.qty or 0)
            print(f"DEBUG: SO Item {it.item_code}: qty {it.qty}, running total: {totals[it.item_code]}")
        print(f"DEBUG: Final SO totals: {totals}")
        return totals
    
    def _get_processed_totals_by_item(self):
        """Return a dict of item_code -> processed qty from submitted Stock Entry Against BOM documents for same Sales Order, excluding current doc."""
        print(f"DEBUG: _get_processed_totals_by_item called for sales_order: {getattr(self, 'sales_order', None)}")
        if not getattr(self, 'sales_order', None):
            print("DEBUG: No sales_order found, returning empty dict")
            return {}
        processed = {}
        parents = frappe.get_all(
            "Stock Entry Against BOM",
            filters={
                "sales_order": self.sales_order,
                "docstatus": 1,
                "name": ["!=", self.name or ""],
            },
            pluck="name",
        )
        print(f"DEBUG: Found {len(parents)} submitted SEAB documents: {parents}")
        if not parents:
            print("DEBUG: No submitted SEAB documents found, returning empty dict")
            return {}
        # Sum finished items' qty from child table
        child_rows = frappe.get_all(
            "Stock Entry Item Table",
            filters={"parent": ["in", parents]},
            fields=["item", "qty"],
        )
        print(f"DEBUG: Found {len(child_rows)} finished item rows from submitted SEABs")
        for r in child_rows:
            if not r.item:
                continue
            processed[r.item] = processed.get(r.item, 0) + (r.qty or 0)
            print(f"DEBUG: Processed item {r.item}: qty {r.qty}, running total: {processed[r.item]}")
        print(f"DEBUG: Final processed totals: {processed}")
        return processed
    
    def _get_remaining_by_item(self):
        """Return cross-document remaining qty per item based on Sales Order minus processed in submitted docs."""
        print(f"DEBUG: _get_remaining_by_item called")
        so_totals = self._get_so_totals_by_item()
        if not so_totals:
            print("DEBUG: No SO totals found, returning empty dict")
            return {}
        processed = self._get_processed_totals_by_item()
        remaining = {}
        for item_code, ordered in so_totals.items():
            done = processed.get(item_code, 0)
            bal = (ordered or 0) - (done or 0)
            remaining[item_code] = bal if bal > 0 else 0
            print(f"DEBUG: Item {item_code}: ordered={ordered}, processed={done}, remaining={remaining[item_code]}")
        print(f"DEBUG: Final remaining totals: {remaining}")
        return remaining
    
    def _enforce_cross_document_remaining(self):
        """Allow any quantities - no capping or restrictions."""
        print(f"DEBUG: _enforce_cross_document_remaining called - NO RESTRICTIONS")
        print("DEBUG: Allowing all quantities without any capping or restrictions")
        # No enforcement - allow any quantities
        return

    def create_transfer_form(self):
        """Create Transfer Form document with items from stock_entry_required_item_table"""
        try:
            # Create new Transfer Form document
            transfer_form = frappe.new_doc("Transfer Form")
            transfer_form.posting_date = self.posting_date
            transfer_form.posting_time = self.posting_time
            transfer_form.sales_order = self.sales_order
            transfer_form.reference = "Stock Entry Against BOM"
            transfer_form.document = self.name
            
            # Add items from stock_entry_required_item_table
            total_items = 0
            total_quantity = 0
            
            for row in self.stock_entry_required_item_table:
                if row.item and row.qty:
                    transfer_form.append("transfer_form_item", {
                        "item": row.item,
                        "quantity": row.qty,
                        "uom": frappe.db.get_value("Item", row.item, "stock_uom")
                    })
                    total_items += 1
                    total_quantity += row.qty
            
            # Set totals
            transfer_form.total_items = total_items
            transfer_form.total_quantity = total_quantity
            
            # Save the Transfer Form
            transfer_form.save(ignore_permissions=True)
            
            frappe.msgprint(f"Transfer Form created: {transfer_form.name}")
            
        except Exception as e:
            frappe.logger().error(f"Error creating Transfer Form: {str(e)}")
            frappe.throw(f"Error creating Transfer Form: {str(e)}")


@frappe.whitelist()
def show_transfer_dialog(docname):
    """Return available items for transfer dialog"""
    try:
        doc = frappe.get_doc("Stock Entry Against BOM", docname)
        
        finished_items = []
        raw_materials = []
        
        # Cross-document remaining for finished items
        remaining_by_item = doc._get_remaining_by_item()
        
        for row in doc.stock_entry_item_table:
            # Use only intra-doc remaining (no cross-doc capping)
            available = row.remaining_qty
            
            if available > 0:
                finished_items.append({
                    'item': row.item,
                    'available_qty': available,
                    'total_qty': row.qty,
                    'issued_qty': row.issued_qty
                })
        
        for row in doc.stock_entry_required_item_table:
            if row.remaining_qty > 0:
                raw_materials.append({
                    'item': row.item,
                    'available_qty': row.remaining_qty,
                    'total_qty': row.qty,
                    'issued_qty': row.issued_qty
                })
        
        return {
            'finished_items': finished_items,
            'raw_materials': raw_materials
        }
    except Exception as e:
        frappe.log_error(f"Error in show_transfer_dialog: {str(e)}", "Transfer Dialog Error")
        frappe.throw(f"Error showing transfer dialog: {str(e)}")

@frappe.whitelist()
def create_transfer_stock_entry(docname, item_code, qty_to_transfer, item_type="finished"):
    """Create and submit Stock Entry for item transfer"""
    try:
        doc = frappe.get_doc("Stock Entry Against BOM", docname)
        return doc.create_transfer_stock_entry(item_code, qty_to_transfer, item_type)
    except Exception as e:
        frappe.log_error(f"Error in create_transfer_stock_entry: {str(e)}", "Transfer Stock Entry Error")
        frappe.throw(f"Error creating transfer Stock Entry: {str(e)}")


def get_remaining_quantity_for_so_item(so_item):
    """Helper function to calculate remaining quantity for a Sales Order item"""
    ordered_qty = so_item.qty or 0
    delivered_qty = so_item.delivered_qty or 0
    remaining_qty = ordered_qty - delivered_qty
    
    # Debug information
    print(f"DEBUG: Item {so_item.item_code}: Ordered={ordered_qty}, Delivered={delivered_qty}, Remaining={remaining_qty}")
    
    return max(0, remaining_qty)  # Ensure non-negative quantity

@frappe.whitelist()
def get_remaining_quantities_from_stock_entries(sales_order):
    """Get remaining quantities by checking actual stock entries created from BOM documents"""
    print(f"DEBUG: Getting remaining quantities from stock entries for Sales Order: {sales_order}")
    
    # First, get the ordered quantities from Sales Order
    so_items = frappe.get_all("Sales Order Item", 
        filters={"parent": sales_order}, 
        fields=["item_code", "qty"]
    )
    
    ordered_by_item = {}
    for so_item in so_items:
        ordered_by_item[so_item.item_code] = so_item.qty or 0
    
    print(f"DEBUG: Ordered quantities from Sales Order: {ordered_by_item}")
    
    # Get all submitted Stock Entry Against BOM documents for this Sales Order
    bom_docs = frappe.get_all("Stock Entry Against BOM", 
        filters={
            "sales_order": sales_order,
            "docstatus": 1  # Only submitted documents
        },
        fields=["name"]
    )
    
    print(f"DEBUG: Found {len(bom_docs)} submitted BOM documents")
    print(f"DEBUG: BOM document names: {[doc.name for doc in bom_docs]}")
    
    # Calculate total processed quantities from actual Stock Entry documents
    processed_by_item = {}
    
    # Get all Stock Entry documents that are manufacturing entries
    stock_entries = frappe.get_all("Stock Entry", 
        filters={
            "docstatus": 1,  # Only submitted stock entries
            "purpose": "Manufacture"  # Only manufacturing stock entries
        },
        fields=["name", "from_bom", "bom_no"]
    )
    
    print(f"DEBUG: Found {len(stock_entries)} manufacturing stock entries")
    
    for se in stock_entries:
        # Check if this stock entry is related to our Sales Order
        is_related = False
        
        # Check if BOM is related to our Sales Order
        if se.bom_no:
            bom_doc = frappe.get_doc("BOM", se.bom_no)
            if bom_doc.item in ordered_by_item:
                is_related = True
                print(f"DEBUG: Stock Entry {se.name} is related via BOM {se.bom_no} for item {bom_doc.item}")
        
        if is_related:
            # Get the stock entry details
            se_doc = frappe.get_doc("Stock Entry", se.name)
            
            # Look for finished goods in the stock entry
            for item in se_doc.items:
                if item.t_warehouse and not item.s_warehouse:  # This is a finished good (target warehouse only)
                    item_code = item.item_code
                    qty = item.qty or 0
                    
                    if item_code in ordered_by_item:
                        processed_by_item[item_code] = processed_by_item.get(item_code, 0) + qty
                        print(f"DEBUG: Found {qty} of {item_code} manufactured in Stock Entry {se.name}")
    
    print(f"DEBUG: Total processed quantities from actual Stock Entries: {processed_by_item}")
    
    # Calculate remaining quantities: Ordered - Processed (but not less than 0)
    remaining_by_item = {}
    excess_by_item = {}
    
    for item_code, ordered_qty in ordered_by_item.items():
        processed_qty = processed_by_item.get(item_code, 0)
        remaining_qty = max(0, ordered_qty - processed_qty)
        excess_qty = max(0, processed_qty - ordered_qty)
        
        remaining_by_item[item_code] = remaining_qty
        excess_by_item[item_code] = excess_qty
        
        print(f"DEBUG: Item {item_code}: Ordered={ordered_qty}, Processed={processed_qty}, Remaining={remaining_qty}, Excess={excess_qty}")
        
        # If processed more than ordered, show excess info
        if excess_qty > 0:
            print(f"DEBUG: EXCESS: Item {item_code} has {excess_qty} excess (processed {processed_qty} but ordered only {ordered_qty})")
    
    print(f"DEBUG: Final remaining quantities: {remaining_by_item}")
    print(f"DEBUG: Final excess quantities: {excess_by_item}")
    return remaining_by_item, excess_by_item

@frappe.whitelist()
def get_items_and_raw_materials(sales_order, production_qty_type="Under Order Qty", custom_quantities=None):
    items = []
    raw_materials_map = {}
    
    print(f"DEBUG: Fetching items for Sales Order: {sales_order}")

    # Get remaining quantities and excess quantities from actual stock entries
    remaining_by_item, excess_by_item = get_remaining_quantities_from_stock_entries(sales_order)
    
    # Fetch Sales Order Items to get BOM information
    so_items = frappe.get_all("Sales Order Item", 
        filters={"parent": sales_order}, 
        fields=["item_code", "bom_no", "qty", "delivered_qty", "name"]
    )
    
    print(f"DEBUG: Found {len(so_items)} Sales Order items")
    print(f"DEBUG: Remaining quantities from stock entries: {remaining_by_item}")
    print(f"DEBUG: Excess quantities from stock entries: {excess_by_item}")
    
    for so_item in so_items:
        ordered_qty = so_item.qty or 0
        delivered_qty = so_item.delivered_qty or 0
        
        # Get remaining quantity and excess quantity from stock entries
        remaining_qty = remaining_by_item.get(so_item.item_code, 0)
        excess_qty = excess_by_item.get(so_item.item_code, 0)
        
        # Use remaining quantity from stock entries, but show all items
        qty_to_use = remaining_qty
        
        # Show all items, even if fully completed (qty_to_use = 0)
        if True:  # Always show all items
            bom_no = so_item.bom_no
            # If bom_no is empty, fetch default BOM for the item
            if not bom_no:
                bom_no = frappe.db.get_value("BOM", {"item": so_item.item_code, "is_default": 1, "is_active": 1}, "name")
            
            # Calculate issued quantity (ordered - remaining)
            issued_qty = max(0, ordered_qty - remaining_qty)
            
            print(f"DEBUG: Item {so_item.item_code}: Ordered={ordered_qty}, Remaining={remaining_qty}, Issued={issued_qty}")
            
            items.append({
                "item": so_item.item_code,
                "bom": bom_no,
                "qty": qty_to_use,
                "ordered_qty": ordered_qty,  # Original ordered quantity from Sales Order
                "delivered_qty": delivered_qty,  # Delivered quantity from Sales Order
                "issued_qty": issued_qty,  # Already issued/transferred quantity
                "remaining_qty": remaining_qty,  # Remaining quantity to be processed
                "excess_qty": excess_qty,  # Excess quantity if any
                "source": "stock_entries"  # Indicate source
            })
            
            print(f"DEBUG: Added item {so_item.item_code} with qty {qty_to_use} from stock entries (excess: {excess_qty})")
            
            # Fetch BOM Raw Materials based on calculated quantity
            if bom_no:
                bom_doc = frappe.get_doc("BOM", bom_no)
                for rm in bom_doc.items:
                    # Calculate required qty based on calculated qty and BOM qty
                    required_qty = (rm.qty / bom_doc.quantity) * qty_to_use
                    key = (rm.item_code, rm.uom)
                    if key in raw_materials_map:
                        raw_materials_map[key]["qty"] += required_qty
                    else:
                        raw_materials_map[key] = {
                            "item": rm.item_code,
                            "qty": required_qty,
                            "uom": rm.uom
                        }

    print(f"DEBUG: Returning {len(items)} items from stock entries")
    print(f"DEBUG: Returning {len(raw_materials_map)} raw material types")

    return {
        "items": items,
        "raw_materials": list(raw_materials_map.values()),
        "source": "stock_entries",
        "excess_quantities": excess_by_item
    }


@frappe.whitelist()
def recalculate_raw_materials(items):
    """
    Recalculate raw materials based on current items in stock_entry_item_table
    """
    import json
    
    frappe.logger().debug(f"recalculate_raw_materials called with items: {items}")
    
    # Handle items parameter - it might be a JSON string or already a list
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            frappe.throw("Invalid items data format")
    
    raw_materials_map = {}
    
    for item in items:
        if item.get('bom'):
            try:
                bom_doc = frappe.get_doc("BOM", item['bom'])
                for rm in bom_doc.items:
                    # Calculate required qty based on item qty and BOM qty
                    required_qty = (rm.qty / bom_doc.quantity) * item['qty']
                    key = (rm.item_code, rm.uom)
                    if key in raw_materials_map:
                        raw_materials_map[key]["qty"] += required_qty
                    else:
                        raw_materials_map[key] = {
                            "item": rm.item_code,
                            "qty": required_qty,
                            "uom": rm.uom
                        }
            except Exception as e:
                frappe.logger().error(f"Error processing BOM {item['bom']}: {str(e)}")
    
    result = {
        "raw_materials": list(raw_materials_map.values())
    }
    frappe.logger().debug(f"recalculate_raw_materials returning: {result}")
    return result


@frappe.whitelist()
def get_sales_order_items_for_custom_quantities(sales_order):
    """Get Sales Order items for custom quantity dialog"""
    try:
        print(f"DEBUG: Getting Sales Order items for custom quantities: {sales_order}")
        
        # Fetch Sales Order Items with delivered quantities
        so_items = frappe.get_all("Sales Order Item", 
            filters={"parent": sales_order}, 
            fields=["item_code", "item_name", "qty", "delivered_qty", "name"]
        )
        
        items = []
        for so_item in so_items:
            remaining_qty = get_remaining_quantity_for_so_item(so_item)
            ordered_qty = so_item.qty or 0
            
            items.append({
                "item_code": so_item.item_code,
                "item_name": so_item.item_name,
                "ordered_qty": ordered_qty,
                "delivered_qty": so_item.delivered_qty or 0,
                "remaining_qty": remaining_qty,
                "will_be_included": ordered_qty > 0  # All items with quantity > 0 can be included
            })
        
        print(f"DEBUG: Found {len(items)} items for custom quantities")
        
        return {
            "success": True,
            "items": items,
            "total_items": len(items)
        }
        
    except Exception as e:
        print(f"DEBUG: Error getting Sales Order items: {str(e)}")
        frappe.log_error(f"Error getting Sales Order items for custom quantities: {str(e)}", "Sales Order Items Error")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def get_sales_order_remaining_quantities(sales_order, production_qty_type="Under Order Qty"):
    """Get detailed remaining quantities for all items in a Sales Order"""
    try:
        print(f"DEBUG: Getting remaining quantities for Sales Order: {sales_order}")
        print(f"DEBUG: Production Qty Type: {production_qty_type}")
        
        # Fetch Sales Order Items with delivered quantities
        so_items = frappe.get_all("Sales Order Item", 
            filters={"parent": sales_order}, 
            fields=["item_code", "item_name", "qty", "delivered_qty", "name"]
        )
        
        remaining_items = []
        for so_item in so_items:
            remaining_qty = get_remaining_quantity_for_so_item(so_item)
            ordered_qty = so_item.qty or 0
            
            # Determine what quantity would be used based on production_qty_type
            if production_qty_type == "Under Order Qty":
                qty_to_use = remaining_qty if remaining_qty > 0 else 0
                will_be_included = remaining_qty > 0
            elif production_qty_type == "Over Order Qty":
                qty_to_use = ordered_qty
                will_be_included = ordered_qty > 0
            else:
                qty_to_use = remaining_qty if remaining_qty > 0 else 0
                will_be_included = remaining_qty > 0
            
            remaining_items.append({
                "item_code": so_item.item_code,
                "item_name": so_item.item_name,
                "ordered_qty": ordered_qty,
                "delivered_qty": so_item.delivered_qty or 0,
                "remaining_qty": remaining_qty,
                "qty_to_use": qty_to_use,
                "has_remaining": remaining_qty > 0,
                "will_be_included": will_be_included,
                "production_qty_type": production_qty_type
            })
        
        included_items = len([item for item in remaining_items if item['will_be_included']])
        print(f"DEBUG: Found {included_items} items that will be included with {production_qty_type}")
        
        return {
            "success": True,
            "items": remaining_items,
            "total_items": len(remaining_items),
            "items_with_remaining": len([item for item in remaining_items if item['has_remaining']]),
            "items_to_be_included": included_items,
            "production_qty_type": production_qty_type
        }
        
    except Exception as e:
        print(f"DEBUG: Error getting remaining quantities: {str(e)}")
        frappe.log_error(f"Error getting Sales Order remaining quantities: {str(e)}", "Sales Order Remaining Quantities Error")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def get_default_expense_account(stock_entry_type):
    """Get expense account from Stock Entry Type's custom_account field"""
    expense_account = None
    if stock_entry_type:
        doc = frappe.get_doc("Stock Entry Type", stock_entry_type)
        expense_account = doc.custom_account
    return {"expense_account": expense_account}

@frappe.whitelist()
def create_transfer_form_from_bom(bom_docname):
    """Create a Transfer Form from Stock Entry Against BOM, pre-filling only remaining quantities and linking back to BOM."""
    try:
        print(f"DEBUG: ===== CREATING TRANSFER FORM FROM BOM =====")
        print(f"DEBUG: BOM Document Name: {bom_docname}")
        
        bom_doc = frappe.get_doc("Stock Entry Against BOM", bom_docname)
        print(f"DEBUG: BOM document loaded successfully")
        print(f"DEBUG: BOM document has {len(bom_doc.stock_entry_required_item_table)} raw material items")
        
        # Check current database values
        bom_doc.check_database_values()
        
        # Ensure tracking fields are initialized and force update database
        bom_doc.ensure_tracking_fields_initialized()
        bom_doc.force_update_tracking_fields()
        
        # Check database values again after updates
        bom_doc.check_database_values()
        
        transfer_form = frappe.new_doc("Transfer Form")
        transfer_form.stock_entry_against_bom = bom_docname
        # Copy posting date and time
        if hasattr(bom_doc, 'posting_date'):
            transfer_form.posting_date = bom_doc.posting_date
        if hasattr(bom_doc, 'posting_time'):
            transfer_form.posting_time = bom_doc.posting_time
        # Copy warehouse information
        if hasattr(bom_doc, 'source_warehouse'):
            transfer_form.source_warehouse = bom_doc.source_warehouse
        if hasattr(bom_doc, 'target_warehouse'):
            transfer_form.target_warehouse = bom_doc.target_warehouse
        # Add items with only remaining qty
        print(f"DEBUG: Processing {len(bom_doc.stock_entry_required_item_table)} raw material items")
        for i, row in enumerate(bom_doc.stock_entry_required_item_table):
            total_qty = row.qty or 0
            issued_qty = row.issued_qty or 0
            remaining = total_qty - issued_qty
            print(f"DEBUG: Item {i}: {row.item}")
            print(f"DEBUG:   Total qty: {total_qty}")
            print(f"DEBUG:   Issued qty: {issued_qty}")
            print(f"DEBUG:   Remaining qty: {remaining}")
            print(f"DEBUG:   Row data - qty: {row.qty}, issued_qty: {row.issued_qty}, remaining_qty: {row.remaining_qty}")
            if remaining > 0:
                transfer_form.append("transfer_form_item", {
                    "item": row.item,
                    "quantity": remaining,
                    "uom": row.uom
                })
                print(f"DEBUG:   Added item {row.item} with quantity {remaining}")
            else:
                print(f"DEBUG:   Skipped item {row.item} - no remaining quantity")
        transfer_form.save(ignore_permissions=True)
        print(f"DEBUG: Transfer form saved: {transfer_form.name}")
        frappe.msgprint(f"Transfer Form {transfer_form.name} created from BOM {bom_docname}.")
        print(f"DEBUG: ===== COMPLETED CREATING TRANSFER FORM =====")
        return transfer_form.name
    except Exception as e:
        print(f"DEBUG: ERROR in create_transfer_form_from_bom: {str(e)}")
        frappe.log_error(f"Error creating Transfer Form from BOM: {str(e)}", "Create Transfer Form from BOM Error")
        frappe.throw(f"Error creating Transfer Form from BOM: {str(e)}")

