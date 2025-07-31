# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StockEntryAgainstBOM(Document):
    def validate(self):
        self.calculate_total_qty()
        self.calculate_total_qty_raw_materials()
        self.initialize_tracking_fields()

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
            stock_entry.custom_cost_center = f"{self.sales_order} - SAH"
            
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
        for row in self.stock_entry_item_table:
            if row.bom and row.qty:
                stock_entry = frappe.new_doc("Stock Entry")
                stock_entry.stock_entry_type = self.stock_entry_type
                stock_entry.from_bom = 1
                stock_entry.use_multi_level_bom = 0
                stock_entry.fg_completed_qty = row.qty
                stock_entry.bom_no = row.bom
                stock_entry.custom_cost_center = f"{self.sales_order} - SAH"
                
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
                
                # stock_entry.submit()
                
                frappe.msgprint(f"Stock Entry created for {row.item} (Qty: {row.qty}): {stock_entry.name}")
        
        if not self.stock_entry_item_table:
            frappe.throw("No items found in Stock Entry Item Table")
        
        # Create Transfer Form after all Stock Entries are created
        self.create_transfer_form()

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
        
        for row in doc.stock_entry_item_table:
            if row.remaining_qty > 0:
                finished_items.append({
                    'item': row.item,
                    'available_qty': row.remaining_qty,
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


@frappe.whitelist()
def get_items_and_raw_materials(sales_order):
    items = []
    raw_materials_map = {}

    # Fetch Sales Order Items
    so_items = frappe.get_all("Sales Order Item", filters={"parent": sales_order}, fields=["item_code", "bom_no", "qty"])
    for so_item in so_items:
        bom_no = so_item.bom_no
        # If bom_no is empty, fetch default BOM for the item
        if not bom_no:
            bom_no = frappe.db.get_value("BOM", {"item": so_item.item_code, "is_default": 1, "is_active": 1}, "name")
        items.append({
            "item": so_item.item_code,
            "bom": bom_no,
            "qty": so_item.qty
        })
        # Fetch BOM Raw Materials
        if bom_no:
            bom_doc = frappe.get_doc("BOM", bom_no)
            for rm in bom_doc.items:
                # Calculate required qty based on SO qty and BOM qty
                required_qty = (rm.qty / bom_doc.quantity) * so_item.qty
                key = (rm.item_code, rm.uom)
                if key in raw_materials_map:
                    raw_materials_map[key]["qty"] += required_qty
                else:
                    raw_materials_map[key] = {
                        "item": rm.item_code,
                        "qty": required_qty,
                        "uom": rm.uom
                    }

    return {
        "items": items,
        "raw_materials": list(raw_materials_map.values())
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

