# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TransferForm(Document):
    def validate(self):
        # self.total_items = len(self.transfer_form_item)
        self.total_qty()
        self.calculate_total_items()
        self.populate_linked_bom_info()
        
    def before_submit(self):
        """Validate required fields before submit"""
        if not self.source_warehouse:
            frappe.throw("Source Warehouse is mandatory")
        if not self.target_warehouse:
            frappe.throw("Target Warehouse is mandatory")
        if not self.transfer_form_item:
            frappe.throw("At least one item is required")
        
    def total_qty(self):
        total_qty = 0
        for item in self.transfer_form_item:
            total_qty += item.quantity
        self.total_quantity = total_qty
        
    def calculate_total_items(self):
        count = len(self.transfer_form_item)
        self.total_items = count
    
    def populate_linked_bom_info(self):
        """Populate linked BOM information"""
        if self.stock_entry_against_bom:
            try:
                bom_doc = frappe.get_doc("Stock Entry Against BOM", self.stock_entry_against_bom)
                info_html = f"""
                <div style="padding: 10px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;">
                    <h4>Linked Stock Entry Against BOM: {self.stock_entry_against_bom}</h4>
                    <p><strong>Sales Order:</strong> {bom_doc.sales_order or 'N/A'}</p>
                    <p><strong>Stock Entry Type:</strong> {bom_doc.stock_entry_type or 'N/A'}</p>
                    <p><strong>Total Items:</strong> {len(bom_doc.stock_entry_item_table)}</p>
                    <p><strong>Total Raw Materials:</strong> {len(bom_doc.stock_entry_required_item_table)}</p>
                </div>
                """
                self.linked_bom_info = info_html
            except Exception as e:
                self.linked_bom_info = f"<p style='color: red;'>Error loading BOM information: {str(e)}</p>"
        else:
            self.linked_bom_info = "<p>No linked Stock Entry Against BOM</p>"
        
    def on_submit(self):
        # Create Stock Entry on Transfer Form submit
        try:
            print(f"DEBUG: ===== TRANSFER FORM ON_SUBMIT =====")
            print(f"DEBUG: Transfer Form: {self.name}")
            print(f"DEBUG: Stock Entry Against BOM: {self.stock_entry_against_bom}")
            
            # Validate warehouses before creating stock entry
            if not self.source_warehouse:
                frappe.throw("Source Warehouse is mandatory for creating Stock Entry")
            if not self.target_warehouse:
                frappe.throw("Target Warehouse is mandatory for creating Stock Entry")
            
            print(f"DEBUG: Warehouses validated - Source: {self.source_warehouse}, Target: {self.target_warehouse}")
            
            stock_entry = frappe.new_doc("Stock Entry")
            stock_entry.stock_entry_type = "Material Transfer for Manufacture"
            stock_entry.posting_date = self.posting_date if hasattr(self, 'posting_date') else frappe.utils.nowdate()
            stock_entry.posting_time = self.posting_time if hasattr(self, 'posting_time') else frappe.utils.nowtime()
            stock_entry.from_warehouse = self.source_warehouse
            stock_entry.to_warehouse = self.target_warehouse
            
            # Add reference information
            if self.stock_entry_against_bom:
                stock_entry.reference = "Stock Entry Against BOM"
                stock_entry.document = self.stock_entry_against_bom

            print(f"DEBUG: Adding {len(self.transfer_form_item)} items to stock entry")
            for item in self.transfer_form_item:
                stock_entry.append("items", {
                    "item_code": item.item,
                    "qty": item.quantity,
                    "s_warehouse": self.source_warehouse,
                    "t_warehouse": self.target_warehouse,
                    "uom": item.uom or frappe.db.get_value("Item", item.item, "stock_uom") or "Nos"
                })
                print(f"DEBUG: Added item {item.item} with quantity {item.quantity}")

            stock_entry.save(ignore_permissions=True)
            print(f"DEBUG: Stock entry saved: {stock_entry.name}")
            stock_entry.submit()
            print(f"DEBUG: Stock entry submitted: {stock_entry.name}")
            
            # Update tracking fields in the original Stock Entry Against BOM
            print(f"DEBUG: About to update BOM tracking fields")
            self.update_bom_tracking_fields()
            print(f"DEBUG: BOM tracking fields updated")
            
            frappe.msgprint(f"Stock Entry {stock_entry.name} created and submitted for Transfer Form {self.name}.")
            print(f"DEBUG: ===== COMPLETED TRANSFER FORM ON_SUBMIT =====")
        except Exception as e:
            print(f"DEBUG: ERROR in transfer form on_submit: {str(e)}")
            frappe.log_error(f"Error creating Stock Entry on Transfer Form submit: {str(e)}", "Transfer Form Submit Error")
            frappe.throw(f"Error creating Stock Entry: {str(e)}")
    
    def update_bom_tracking_fields(self):
        """Update tracking fields in the original Stock Entry Against BOM"""
        try:
            if self.stock_entry_against_bom:
                print(f"DEBUG: ===== STARTING UPDATE BOM TRACKING FIELDS =====")
                print(f"DEBUG: Transfer Form: {self.name}")
                print(f"DEBUG: BOM Document: {self.stock_entry_against_bom}")
                
                bom_doc = frappe.get_doc("Stock Entry Against BOM", self.stock_entry_against_bom)
                print(f"DEBUG: BOM document loaded successfully")
                
                # Ensure tracking fields are initialized
                bom_doc.ensure_tracking_fields_initialized()
                print(f"DEBUG: Tracking fields initialized")
                
                print(f"DEBUG: Transfer form has {len(self.transfer_form_item)} items")
                for transfer_item in self.transfer_form_item:
                    print(f"DEBUG: Processing transfer item {transfer_item.item} with quantity {transfer_item.quantity}")
                    
                    # Update finished goods table (stock_entry_item_table)
                    found_in_finished = False
                    print(f"DEBUG: Checking {len(bom_doc.stock_entry_item_table)} finished items")
                    for bom_item in bom_doc.stock_entry_item_table:
                        print(f"DEBUG: Comparing {transfer_item.item} with {bom_item.item}")
                        if bom_item.item == transfer_item.item:
                            old_issued_qty = bom_item.issued_qty or 0
                            new_issued_qty = old_issued_qty + transfer_item.quantity
                            new_remaining_qty = (bom_item.qty or 0) - new_issued_qty
                            
                            # Update transfer status
                            if new_remaining_qty == 0:
                                new_transfer_status = "Fully Transferred"
                            elif new_issued_qty > 0:
                                new_transfer_status = "Partially Transferred"
                            else:
                                new_transfer_status = "Pending"
                            
                            print(f"DEBUG: Updated finished item {transfer_item.item}")
                            print(f"DEBUG:   Old issued_qty: {old_issued_qty}")
                            print(f"DEBUG:   New issued_qty: {new_issued_qty}")
                            print(f"DEBUG:   New remaining_qty: {new_remaining_qty}")
                            print(f"DEBUG:   Transfer status: {new_transfer_status}")
                            
                            # Direct database update for finished goods
                            if hasattr(bom_item, 'name') and bom_item.name:
                                frappe.db.set_value("Stock Entry Item Table", bom_item.name, "issued_qty", new_issued_qty)
                                frappe.db.set_value("Stock Entry Item Table", bom_item.name, "remaining_qty", new_remaining_qty)
                                frappe.db.set_value("Stock Entry Item Table", bom_item.name, "transfer_status", new_transfer_status)
                                # Also update the in-memory object
                                bom_item.issued_qty = new_issued_qty
                                bom_item.remaining_qty = new_remaining_qty
                                bom_item.transfer_status = new_transfer_status
                                print(f"DEBUG:   Updated database for finished item {bom_item.name}")
                            
                            found_in_finished = True
                            break
                    
                    if not found_in_finished:
                        print(f"DEBUG: Item {transfer_item.item} not found in finished goods table")
                    
                    # Update raw materials table (stock_entry_required_item_table)
                    found_in_raw = False
                    print(f"DEBUG: Checking {len(bom_doc.stock_entry_required_item_table)} raw material items")
                    for bom_item in bom_doc.stock_entry_required_item_table:
                        print(f"DEBUG: Comparing {transfer_item.item} with {bom_item.item}")
                        if bom_item.item == transfer_item.item:
                            old_issued_qty = bom_item.issued_qty or 0
                            new_issued_qty = old_issued_qty + transfer_item.quantity
                            new_remaining_qty = (bom_item.qty or 0) - new_issued_qty
                            
                            # Update transfer status
                            if new_remaining_qty == 0:
                                new_transfer_status = "Fully Transferred"
                            elif new_issued_qty > 0:
                                new_transfer_status = "Partially Transferred"
                            else:
                                new_transfer_status = "Pending"
                            
                            print(f"DEBUG: Updated raw material {transfer_item.item}")
                            print(f"DEBUG:   Old issued_qty: {old_issued_qty}")
                            print(f"DEBUG:   New issued_qty: {new_issued_qty}")
                            print(f"DEBUG:   New remaining_qty: {new_remaining_qty}")
                            print(f"DEBUG:   Transfer status: {new_transfer_status}")
                            
                            # Direct database update for raw materials
                            if hasattr(bom_item, 'name') and bom_item.name:
                                frappe.db.set_value("Stock Entry Required Item Table", bom_item.name, "issued_qty", new_issued_qty)
                                frappe.db.set_value("Stock Entry Required Item Table", bom_item.name, "remaining_qty", new_remaining_qty)
                                frappe.db.set_value("Stock Entry Required Item Table", bom_item.name, "transfer_status", new_transfer_status)
                                # Also update the in-memory object
                                bom_item.issued_qty = new_issued_qty
                                bom_item.remaining_qty = new_remaining_qty
                                bom_item.transfer_status = new_transfer_status
                                print(f"DEBUG:   Updated database for raw material {bom_item.name}")
                            
                            found_in_raw = True
                            break
                    
                    if not found_in_raw:
                        print(f"DEBUG: Item {transfer_item.item} not found in raw materials table")
                
                # Save the document to persist the changes
                bom_doc.save(ignore_permissions=True)
                # Reload the document to reflect the database changes
                bom_doc.reload()
                print(f"DEBUG: ===== COMPLETED UPDATE BOM TRACKING FIELDS =====")
                frappe.msgprint(f"Updated tracking fields in {self.stock_entry_against_bom}")
                
        except Exception as e:
            print(f"DEBUG: ERROR in update_bom_tracking_fields: {str(e)}")
            frappe.log_error(f"Error updating BOM tracking fields: {str(e)}", "BOM Tracking Update Error")
            frappe.throw(f"Error updating BOM tracking fields: {str(e)}")
