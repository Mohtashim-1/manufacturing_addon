import frappe
from frappe import _
from frappe.utils import flt

class WorkOrderTransferManager(frappe.model.document.Document):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._totals_calculated = False
    
    def validate(self):
        print(f"🔍 DEBUG: validate() called for document: {self.name}")
        # Only calculate totals if not already calculated during this save/submit cycle
        if not self._totals_calculated:
            self.calculate_totals()
            self._totals_calculated = True
    
    def before_save(self):
        print(f"🔍 DEBUG: before_save() called for document: {self.name}")
        # Reset the flag for next save cycle
        self._totals_calculated = False
    
    def before_submit(self):
        """Called before document is submitted"""
        print(f"🔍 DEBUG: before_submit() called for document: {self.name}")
        # Calculate totals only if not already calculated
        if not self._totals_calculated:
            self.calculate_totals()
            self._totals_calculated = True
        
        # Validate that we have data
        if not self.work_order_details:
            frappe.throw("Please fetch work orders before submitting")
        
        if not self.transfer_items:
            frappe.throw("No raw materials found. Please fetch work orders first.")
    
    def validate_sales_order(self):
        print(f"🔍 DEBUG: validate_sales_order() called")
        if self.sales_order:
            so_doc = frappe.get_doc("Sales Order", self.sales_order)
            self.customer = so_doc.customer
    
    def calculate_totals(self):
        """Calculate totals from child tables"""
        print(f"🔍 DEBUG: calculate_totals() called")
        total_ordered = 0
        total_delivered = 0
        total_pending = 0
        
        if hasattr(self, 'work_order_details') and self.work_order_details:
            for row in self.work_order_details:
                total_ordered += flt(row.ordered_qty or 0)
                total_delivered += flt(row.delivered_qty or 0)
                total_pending += flt(row.pending_qty or 0)
        
        # Only set totals if the fields exist in the doctype
        if hasattr(self, 'total_ordered_qty'):
            self.total_ordered_qty = total_ordered
        if hasattr(self, 'total_delivered_qty'):
            self.total_delivered_qty = total_delivered
        if hasattr(self, 'total_pending_qty'):
            self.total_pending_qty = total_pending
            
        print(f"🔍 DEBUG: Totals calculated - Ordered: {total_ordered}, Delivered: {total_delivered}, Pending: {total_pending}")
    
    def on_submit(self):
        """Called when document is submitted"""
        print(f"🔍 DEBUG: on_submit() called for document: {self.name}")
        # Validation is already done in before_submit()
        print(f"🔍 DEBUG: Document submitted successfully")
    
    def on_cancel(self):
        """Called when document is cancelled"""
        print(f"🔍 DEBUG: on_cancel() called for document: {self.name}")
        # Check if any transfers have been created
        existing_transfers = frappe.get_all("Raw Material Transfer", 
            filters={"work_order_transfer_manager": self.name, "docstatus": 1})
        
        if existing_transfers:
            frappe.throw("Cannot cancel this document as transfers have already been created from it.")

@frappe.whitelist()
def populate_work_order_tables(sales_order, doc_name):
    """Populate work order tables with three sections: finished items, work orders, and raw materials"""
    print(f"🔍 DEBUG: Starting populate_work_order_tables for sales_order: {sales_order}, doc_name: {doc_name}")
    try:
        # Check if document exists, if not create a new one
        if not frappe.db.exists("Work Order Transfer Manager", doc_name):
            print(f"🔍 DEBUG: Document {doc_name} not found, creating new document")
            doc = frappe.new_doc("Work Order Transfer Manager")
            doc.sales_order = sales_order
            doc.posting_date = frappe.utils.today()
            doc.posting_time = frappe.utils.nowtime()
            
            # Set default warehouses - simplified approach
            print(f"🔍 DEBUG: Setting default warehouses")
            try:
                # Ensure company is set on the document
                company = getattr(doc, 'company', None) or frappe.defaults.get_global_default("company")
                if company and not getattr(doc, 'company', None):
                    doc.company = company
                
                # Try to get a default warehouse from company settings
                if company:
                    # Get the first available warehouse for the company
                    warehouses = frappe.db.sql("""
                        SELECT name FROM `tabWarehouse` 
                        WHERE company = %s AND is_group = 0
                        ORDER BY name ASC 
                        LIMIT 2
                    """, (company,), as_dict=True)
                    
                    if warehouses:
                        # Set source warehouse (first warehouse)
                        doc.source_warehouse = warehouses[0].name
                        print(f"🔍 DEBUG: Set source_warehouse to: {doc.source_warehouse}")
                        
                        # Set target warehouse (second warehouse if available, otherwise same as source)
                        if len(warehouses) > 1:
                            doc.target_warehouse = warehouses[1].name
                        else:
                            doc.target_warehouse = warehouses[0].name
                        print(f"🔍 DEBUG: Set target_warehouse to: {doc.target_warehouse}")
                    else:
                        print(f"🔍 DEBUG: No warehouses found for company: {company}")
                else:
                    print(f"🔍 DEBUG: No company found")
            except Exception as e:
                print(f"🔍 DEBUG: Error setting warehouses: {e}")
                # Continue without setting warehouses - user can set them manually
            
            print(f"🔍 DEBUG: About to insert new document")
            doc.insert()
            print(f"🔍 DEBUG: Created new document with name: {doc.name}")
        else:
            print(f"🔍 DEBUG: Found existing document: {doc_name}")
            doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
            # Ensure company exists on existing docs as well
            if not getattr(doc, 'company', None):
                doc.company = frappe.defaults.get_global_default("company")
                doc.save()
        
        # Clear existing data
        print(f"🔍 DEBUG: Clearing existing tables")
        doc.work_order_details = []
        doc.work_order_summary = []
        doc.transfer_items = []
        
        print(f"🔍 DEBUG: Cleared existing tables")
        
        # Get work orders
        print(f"🔍 DEBUG: About to fetch work orders from database")
        work_orders = frappe.db.sql("""
            SELECT 
                name, 
                production_item, 
                item_name, 
                qty, 
                material_transferred_for_manufacturing,
                produced_qty, 
                status,
                creation
            FROM `tabWork Order` 
            WHERE sales_order = %s AND docstatus = 1
            ORDER BY creation ASC
        """, (sales_order,), as_dict=True)
        
        print(f"🔍 DEBUG: Retrieved {len(work_orders)} work orders")
        
        # Group work orders by item
        item_summary = {}
        raw_material_summary = {}
        
        for wo in work_orders:
            print(f"🔍 DEBUG: Processing work order: {wo.name}")
            print(f"🔍 DEBUG: Work order data: {wo}")
            
            if wo.production_item not in item_summary:
                item_summary[wo.production_item] = {
                    "item_code": wo.production_item,
                    "item_name": wo.item_name,
                    "total_ordered_qty": 0,
                    "total_transferred_qty": 0,
                    "total_pending_qty": 0,
                    "work_orders": []
                }
            
            ordered_qty = flt(wo.qty)
            transferred_qty = flt(wo.material_transferred_for_manufacturing)
            pending_qty = ordered_qty - transferred_qty
            
            item_summary[wo.production_item]["total_ordered_qty"] += ordered_qty
            item_summary[wo.production_item]["total_transferred_qty"] += transferred_qty
            item_summary[wo.production_item]["total_pending_qty"] += pending_qty
            item_summary[wo.production_item]["work_orders"].append(wo)
            
            # Add to work order details
            print(f"🔍 DEBUG: About to append to work_order_details")
            try:
                work_order_detail_data = {
                    "work_order": wo.name,
                    "item_code": wo.production_item,
                    "item_name": wo.item_name,
                    "ordered_qty": ordered_qty,
                    "transferred_qty": transferred_qty,
                    "pending_qty": pending_qty,
                    "work_order_status": wo.status,
                    "transfer_status": get_transfer_status(transferred_qty, ordered_qty)
                }
                print(f"🔍 DEBUG: Work order detail data to append: {work_order_detail_data}")
                
                doc.append("work_order_details", work_order_detail_data)
                print(f"🔍 DEBUG: Successfully appended to work_order_details")
            except Exception as e:
                print(f"❌ DEBUG: Error appending to work_order_details: {e}")
                print(f"❌ DEBUG: Work order: {wo.name}")
                print(f"❌ DEBUG: Work order detail data: {work_order_detail_data}")
                raise e
            
            # Calculate raw materials for this work order
            if pending_qty > 0:
                print(f"🔍 DEBUG: Calculating raw materials for work order: {wo.name}")
                try:
                    # Get BOM for the production item
                    bom = frappe.db.get_value("BOM", {"item": wo.production_item, "is_active": 1, "is_default": 1})
                    if bom:
                        bom_doc = frappe.get_doc("BOM", bom)
                        for bom_item in bom_doc.items:
                            raw_item_code = bom_item.item_code
                            raw_item_name = frappe.db.get_value("Item", raw_item_code, "item_name") or raw_item_code
                            
                            # Calculate raw material quantity needed
                            raw_qty_needed = flt(pending_qty) * flt(bom_item.qty) / flt(bom_doc.quantity)
                            
                            # Add to raw material summary
                            if raw_item_code not in raw_material_summary:
                                raw_material_summary[raw_item_code] = {
                                    "item_code": raw_item_code,
                                    "item_name": raw_item_name,
                                    "uom": bom_item.uom,
                                    "total_qty_needed": 0,
                                    "work_orders": []
                                }
                            
                            raw_material_summary[raw_item_code]["total_qty_needed"] += raw_qty_needed
                            raw_material_summary[raw_item_code]["work_orders"].append({
                                "work_order": wo.name,
                                "finished_item": wo.production_item,
                                "pending_qty": pending_qty,
                                "raw_qty_needed": raw_qty_needed,
                                "creation": wo.creation
                            })
                            
                            print(f"🔍 DEBUG: Raw material {raw_item_code} needs {raw_qty_needed} {bom_item.uom}")
                    else:
                        print(f"🔍 DEBUG: No BOM found for item: {wo.production_item}")
                except Exception as e:
                    print(f"❌ DEBUG: Error calculating raw materials: {e}")
        
        print(f"🔍 DEBUG: Processed {len(item_summary)} unique finished items")
        print(f"🔍 DEBUG: Found {len(raw_material_summary)} unique raw materials")
        
        # Add to work order summary (finished items)
        print(f"🔍 DEBUG: Starting to add {len(item_summary)} items to work_order_summary")
        for item_code, summary in item_summary.items():
            print(f"🔍 DEBUG: About to append to work_order_summary for item: {item_code}")
            print(f"🔍 DEBUG: Summary data: {summary}")
            
            try:
                work_order_summary_data = {
                    "item_code": summary["item_code"],
                    "item_name": summary["item_name"],
                    "total_ordered_qty": summary["total_ordered_qty"],
                    "total_transferred_qty": summary["total_transferred_qty"],
                    "total_pending_qty": summary["total_pending_qty"],
                    "work_order_count": len(summary["work_orders"]),
                    "transfer_status": get_transfer_status(summary["total_transferred_qty"], summary["total_ordered_qty"])
                }
                print(f"🔍 DEBUG: Work order summary data to append: {work_order_summary_data}")
                
                doc.append("work_order_summary", work_order_summary_data)
                print(f"🔍 DEBUG: Successfully appended to work_order_summary")
            except Exception as e:
                print(f"❌ DEBUG: Error appending to work_order_summary: {e}")
                print(f"❌ DEBUG: Item code: {item_code}")
                print(f"❌ DEBUG: Summary: {summary}")
                raise e
        
        # Add to transfer items (raw material summary)
        print(f"🔍 DEBUG: Starting to add {len(raw_material_summary)} raw materials to transfer_items")
        for raw_item_code, raw_summary in raw_material_summary.items():
            print(f"🔍 DEBUG: About to append raw material to transfer_items: {raw_item_code}")
            print(f"🔍 DEBUG: Raw material data: {raw_summary}")
            
            try:
                # Get actual quantity at source warehouse
                source_warehouse = doc.source_warehouse or ""
                actual_qty_at_warehouse = 0
                
                if source_warehouse:
                    actual_qty = frappe.db.sql("""
                        SELECT actual_qty FROM `tabBin` 
                        WHERE item_code = %s AND warehouse = %s
                    """, (raw_item_code, source_warehouse), as_dict=True)
                    
                    actual_qty_at_warehouse = flt(actual_qty[0].actual_qty) if actual_qty else 0
                
                # Company-wide qty for this item (sum of all non-group warehouses for company)
                actual_company_qty = 0
                if doc.company:
                    company_bins = frappe.db.sql(
                        """
                        SELECT SUM(b.actual_qty) AS qty
                        FROM `tabBin` b
                        JOIN `tabWarehouse` w ON w.name = b.warehouse
                        WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                        """,
                        (raw_item_code, doc.company), as_dict=True
                    )
                    actual_company_qty = flt(company_bins[0].qty) if company_bins and company_bins[0].qty is not None else 0
                
                # Already transferred so far for this item from this manager
                transferred_so_far = 0
                existing_transfers = frappe.get_all(
                    "Raw Material Transfer",
                    filters={"work_order_transfer_manager": doc.name},
                    fields=["name"]
                )
                for t in existing_transfers:
                    tdoc = frappe.get_doc("Raw Material Transfer", t.name)
                    for rt in tdoc.raw_materials:
                        if rt.item_code == raw_item_code:
                            transferred_so_far += flt(rt.transfer_qty)
                
                transfer_item_data = {
                    "item_code": raw_item_code,
                    "item_name": raw_summary["item_name"],
                    "pending_qty": raw_summary["total_qty_needed"],
                    "transfer_qty": 0,
                    "transferred_qty_so_far": transferred_so_far,
                    "actual_qty_at_warehouse": actual_qty_at_warehouse,
                    "actual_qty_at_company": actual_company_qty,
                    "uom": raw_summary["uom"],
                    "warehouse": source_warehouse,
                    "company": doc.company or ""
                }
                print(f"🔍 DEBUG: Transfer item data to append: {transfer_item_data}")
                
                doc.append("transfer_items", transfer_item_data)
                print(f"🔍 DEBUG: Successfully appended raw material to transfer_items")
            except Exception as e:
                print(f"❌ DEBUG: Error appending raw material to transfer_items: {e}")
                print(f"❌ DEBUG: Raw item code: {raw_item_code}")
                print(f"❌ DEBUG: Raw summary: {raw_summary}")
                raise e
        
        # Save the document
        print(f"🔍 DEBUG: About to save document")
        print(f"🔍 DEBUG: Document has {len(doc.work_order_details)} work_order_details rows")
        print(f"🔍 DEBUG: Document has {len(doc.work_order_summary)} work_order_summary rows")
        print(f"🔍 DEBUG: Document has {len(doc.transfer_items)} transfer_items rows")
        
        # Debug: Print first few rows of each table to check for issues
        if doc.work_order_details:
            print(f"🔍 DEBUG: First work_order_details row: {doc.work_order_details[0].as_dict()}")
        if doc.work_order_summary:
            print(f"🔍 DEBUG: First work_order_summary row: {doc.work_order_summary[0].as_dict()}")
        if doc.transfer_items:
            print(f"🔍 DEBUG: First transfer_items row: {doc.transfer_items[0].as_dict()}")
        
        try:
            print(f"🔍 DEBUG: Calling doc.save()...")
            doc.save()
            print(f"🔍 DEBUG: Document saved successfully with {len(doc.work_order_details)} details, {len(doc.work_order_summary)} summary, {len(doc.transfer_items)} raw material transfer items")
        except Exception as e:
            print(f"❌ DEBUG: Error saving document: {e}")
            print(f"❌ DEBUG: Error type: {type(e)}")
            print(f"❌ DEBUG: Error args: {e.args}")
            import traceback
            print(f"❌ DEBUG: Save error traceback: {traceback.format_exc()}")
            raise e
        
        return {
            "success": True,
            "message": f"Populated {len(doc.work_order_details)} work order details, {len(doc.work_order_summary)} summary items, {len(doc.transfer_items)} raw material transfer items",
            "doc_name": doc.name
        }
        
    except Exception as e:
        print(f"❌ DEBUG: Error in populate_work_order_tables: {str(e)}")
        import traceback
        print(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")
        
        # Create a much shorter error message to fit in Error Log title field (max 140 chars)
        # The prefix "Error populating work order tables for sales order {sales_order}: " is about 60 chars
        # So we have about 80 chars left for the error message
        error_msg = str(e)
        if len(error_msg) > 70:  # Be more conservative to ensure it fits
            error_msg = error_msg[:67] + "..."
        
        # Ensure the total message doesn't exceed 140 chars
        full_message = f"Error populating work order tables for sales order {sales_order}: {error_msg}"
        if len(full_message) > 140:
            # If still too long, truncate the sales order name too
            sales_order_short = sales_order[:20] + "..." if len(sales_order) > 23 else sales_order
            full_message = f"Error populating work order tables for sales order {sales_order_short}: {error_msg}"
            if len(full_message) > 140:
                # Final fallback - very short message
                full_message = f"Error populating work order tables: {error_msg[:50]}..."
        
        frappe.log_error(full_message)
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

@frappe.whitelist()
def create_raw_material_transfer_doc(doc_name):
    """Create a new Raw Material Transfer document with selected raw materials"""
    print(f"🔍 DEBUG: Starting create_raw_material_transfer_doc for doc_name: {doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        
        # Get selected raw materials
        selected_items = [item for item in doc.transfer_items if item.select_for_transfer and flt(item.transfer_qty) > 0]
        
        if not selected_items:
            frappe.throw("Please select raw materials and enter transfer quantities")
        
        # Create new Raw Material Transfer document
        raw_transfer_doc = frappe.new_doc("Raw Material Transfer")
        raw_transfer_doc.sales_order = doc.sales_order
        raw_transfer_doc.work_order_transfer_manager = doc.name
        raw_transfer_doc.posting_date = doc.posting_date
        raw_transfer_doc.posting_time = doc.posting_time
        raw_transfer_doc.company = doc.company
        raw_transfer_doc.source_warehouse = doc.source_warehouse
        raw_transfer_doc.target_warehouse = doc.target_warehouse
        raw_transfer_doc.stock_entry_type = doc.stock_entry_type
        
        # Add selected raw materials
        for item in selected_items:
            # Get actual quantities
            actual_qty_at_warehouse = 0
            actual_qty_at_company = 0
            
            if doc.source_warehouse:
                bin_qty = frappe.db.sql("""
                    SELECT actual_qty FROM `tabBin` 
                    WHERE item_code = %s AND warehouse = %s
                """, (item.item_code, doc.source_warehouse), as_dict=True)
                actual_qty_at_warehouse = flt(bin_qty[0].actual_qty) if bin_qty else 0
            
            if doc.company:
                company_bins = frappe.db.sql("""
                    SELECT SUM(b.actual_qty) AS qty
                    FROM `tabBin` b
                    JOIN `tabWarehouse` w ON w.name = b.warehouse
                    WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                """, (item.item_code, doc.company), as_dict=True)
                actual_qty_at_company = flt(company_bins[0].qty) if company_bins and company_bins[0].qty is not None else 0
            
            raw_transfer_doc.append("raw_materials", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "pending_qty": item.pending_qty,
                "transfer_qty": item.transfer_qty or item.pending_qty,  # Use transfer_qty if set, otherwise use pending_qty
                "uom": item.uom,
                "warehouse": doc.source_warehouse,
                "actual_qty_at_warehouse": actual_qty_at_warehouse,
                "actual_qty_at_company": actual_qty_at_company
            })
        
        raw_transfer_doc.insert()
        
        # Update transfer quantities in the work order transfer manager
        update_transfer_quantities(doc_name, raw_transfer_doc.name)
        
        return {
            "success": True,
            "message": f"Raw Material Transfer document created: {raw_transfer_doc.name}",
            "doc_name": raw_transfer_doc.name
        }
        
    except Exception as e:
        # Create a much shorter error message to fit in Error Log title field (max 140 chars)
        error_msg = str(e)
        if len(error_msg) > 60:  # Be more conservative to ensure it fits
            error_msg = error_msg[:57] + "..."
        
        # Ensure the total message doesn't exceed 140 chars
        full_message = f"Error creating raw material transfer document: {error_msg}"
        if len(full_message) > 140:
            # Final fallback - very short message
            full_message = f"Error creating raw material transfer: {error_msg[:50]}..."
        
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def create_all_pending_transfer(doc_name):
    """Create a new Raw Material Transfer document with ALL pending raw materials"""
    print(f"🔍 DEBUG: Starting create_all_pending_transfer for doc_name: {doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        
        # Check if document is submitted
        if doc.docstatus != 1:
            frappe.throw("Please submit the Work Order Transfer Manager document first")
        
        # Get items that still have pending quantities (not fully issued)
        pending_items = []
        for item in doc.transfer_items:
            if flt(item.pending_qty) > 0:
                pending_items.append(item)
        
        if not pending_items:
            frappe.throw("No raw materials with pending quantities found")
        
        # Create new Raw Material Transfer document
        raw_transfer_doc = frappe.new_doc("Raw Material Transfer")
        raw_transfer_doc.sales_order = doc.sales_order
        raw_transfer_doc.work_order_transfer_manager = doc.name
        raw_transfer_doc.posting_date = doc.posting_date
        raw_transfer_doc.posting_time = doc.posting_time
        raw_transfer_doc.company = doc.company
        raw_transfer_doc.source_warehouse = doc.source_warehouse
        raw_transfer_doc.target_warehouse = doc.target_warehouse
        raw_transfer_doc.stock_entry_type = doc.stock_entry_type
        
        # Add pending raw materials (set transfer quantities to pending quantities by default)
        for item in pending_items:
            # Get actual quantities
            actual_qty_at_warehouse = 0
            actual_qty_at_company = 0
            
            if doc.source_warehouse:
                bin_qty = frappe.db.sql("""
                    SELECT actual_qty FROM `tabBin` 
                    WHERE item_code = %s AND warehouse = %s
                """, (item.item_code, doc.source_warehouse), as_dict=True)
                actual_qty_at_warehouse = flt(bin_qty[0].actual_qty) if bin_qty else 0
            
            if doc.company:
                company_bins = frappe.db.sql("""
                    SELECT SUM(b.actual_qty) AS qty
                    FROM `tabBin` b
                    JOIN `tabWarehouse` w ON w.name = b.warehouse
                    WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                """, (item.item_code, doc.company), as_dict=True)
                actual_qty_at_company = flt(company_bins[0].qty) if company_bins and company_bins[0].qty is not None else 0
            
            raw_transfer_doc.append("raw_materials", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "pending_qty": item.pending_qty,
                "transfer_qty": item.pending_qty,  # Set to pending quantity by default
                "uom": item.uom,
                "warehouse": doc.source_warehouse,
                "actual_qty_at_warehouse": actual_qty_at_warehouse,
                "actual_qty_at_company": actual_qty_at_company
            })
        
        raw_transfer_doc.insert()
        
        # Update transfer quantities in the work order transfer manager
        update_transfer_quantities(doc_name, raw_transfer_doc.name)
        
        return {
            "success": True,
            "message": f"Raw Material Transfer document created with {len(pending_items)} items: {raw_transfer_doc.name}",
            "doc_name": raw_transfer_doc.name
        }
        
    except Exception as e:
        # Create a much shorter error message to fit in Error Log title field (max 140 chars)
        error_msg = str(e)
        if len(error_msg) > 60:  # Be more conservative to ensure it fits
            error_msg = error_msg[:57] + "..."
        
        # Ensure the total message doesn't exceed 140 chars
        full_message = f"Error creating all pending transfer: {error_msg}"
        if len(full_message) > 140:
            # Final fallback - very short message
            full_message = f"Error creating all pending transfer: {error_msg[:50]}..."
        
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def create_all_pending_transfer_background(doc_name):
    """Create a new Raw Material Transfer document with ALL pending raw materials using background job"""
    print(f"🔍 DEBUG: Starting create_all_pending_transfer_background for doc_name: {doc_name}")
    
    try:
        # Enqueue the job
        frappe.enqueue(
            "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.create_all_pending_transfer_job",
            doc_name=doc_name,
            queue="long",
            timeout=600,  # 10 minutes timeout
            job_name=f"create_raw_material_transfer_{doc_name}"
        )
        
        return {
            "success": True,
            "message": "Background job started. You will be notified when the Raw Material Transfer document is created.",
            "job_started": True
        }
        
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 60:
            error_msg = error_msg[:57] + "..."
        
        full_message = f"Error starting background job: {error_msg}"
        if len(full_message) > 140:
            full_message = f"Error starting background job: {error_msg[:50]}..."
        
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)}

def create_all_pending_transfer_job(doc_name):
    """Background job to create Raw Material Transfer document"""
    print(f"🔍 DEBUG: Background job started for doc_name: {doc_name}")
    
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        
        # Check if document is submitted
        if doc.docstatus != 1:
            frappe.throw("Please submit the Work Order Transfer Manager document first")
        
        # Get items that still have pending quantities (not fully issued)
        pending_items = []
        for item in doc.transfer_items:
            if flt(item.pending_qty) > 0:
                pending_items.append(item)
        
        if not pending_items:
            frappe.throw("No raw materials with pending quantities found")
        
        # Create new Raw Material Transfer document
        raw_transfer_doc = frappe.new_doc("Raw Material Transfer")
        raw_transfer_doc.sales_order = doc.sales_order
        raw_transfer_doc.work_order_transfer_manager = doc.name
        raw_transfer_doc.posting_date = doc.posting_date
        raw_transfer_doc.posting_time = doc.posting_time
        raw_transfer_doc.company = doc.company
        raw_transfer_doc.source_warehouse = doc.source_warehouse
        raw_transfer_doc.target_warehouse = doc.target_warehouse
        raw_transfer_doc.stock_entry_type = doc.stock_entry_type
        
        # Add pending raw materials (set transfer quantities to pending quantities by default)
        for item in pending_items:
            raw_transfer_doc.append("raw_materials", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "pending_qty": item.pending_qty,
                "transfer_qty": item.pending_qty,  # Set to pending quantity by default
                "uom": item.uom,
                "warehouse": doc.source_warehouse
            })
        
        raw_transfer_doc.insert()
        
        # Send notification to user
        frappe.publish_realtime(
            'raw_material_transfer_created',
            user=doc.owner,
            message={
                'doc_name': raw_transfer_doc.name,
                'message': f'Raw Material Transfer document created successfully: {raw_transfer_doc.name}',
                'success': True
            }
        )
        
        print(f"🔍 DEBUG: Background job completed successfully. Created: {raw_transfer_doc.name}")
        
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 60:
            error_msg = error_msg[:57] + "..."
        
        full_message = f"Error in background job: {error_msg}"
        if len(full_message) > 140:
            full_message = f"Error in background job: {error_msg[:50]}..."
        
        frappe.log_error(full_message)
        
        # Send error notification to user
        frappe.publish_realtime(
            'raw_material_transfer_error',
            user=doc.owner if 'doc' in locals() else None,
            message={
                'message': f'Error creating Raw Material Transfer: {str(e)}',
                'success': False
            }
        )

@frappe.whitelist()
def get_remaining_pending_items(doc_name):
    """Get items that still have pending quantities after previous transfers"""
    print(f"🔍 DEBUG: get_remaining_pending_items called for: {doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        
        # Get all raw material transfers created from this work order transfer manager
        existing_transfers = frappe.get_all("Raw Material Transfer", 
            filters={"work_order_transfer_manager": doc_name, "docstatus": 1},
            fields=["name"])
        
        # Calculate remaining pending quantities
        remaining_items = []
        
        for item in doc.transfer_items:
            original_pending = flt(item.pending_qty)
            transferred_qty = 0
            
            # Sum up all transferred quantities from previous transfers
            for transfer in existing_transfers:
                transfer_doc = frappe.get_doc("Raw Material Transfer", transfer.name)
                for transfer_item in transfer_doc.raw_materials:
                    if transfer_item.item_code == item.item_code:
                        transferred_qty += flt(transfer_item.transfer_qty)
            
            remaining_qty = original_pending - transferred_qty
            
            if remaining_qty > 0:
                remaining_items.append({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "pending_qty": remaining_qty,
                    "uom": item.uom,
                    "warehouse": doc.source_warehouse
                })
        
        print(f"🔍 DEBUG: Found {len(remaining_items)} items with remaining pending quantities")
        return remaining_items
        
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 60:
            error_msg = error_msg[:57] + "..."
        full_message = f"Error getting remaining pending items: {error_msg}"
        if len(full_message) > 140:
            full_message = f"Error getting remaining pending items: {error_msg[:50]}..."
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def create_selective_transfer(doc_name):
    """Create stock entry for selected raw materials"""
    print(f"🔍 DEBUG: Starting create_selective_transfer for doc_name: {doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        
        # Get selected items
        selected_items = [item for item in doc.transfer_items if item.select_for_transfer and flt(item.transfer_qty) > 0]
        
        if not selected_items:
            frappe.throw("Please select items and enter transfer quantities")
        
        # Create stock entry
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Transfer for Manufacture"
        stock_entry.posting_date = doc.posting_date
        stock_entry.posting_time = doc.posting_time
        stock_entry.company = doc.company
        stock_entry.from_warehouse = doc.source_warehouse
        stock_entry.to_warehouse = doc.target_warehouse
        
        # Add raw materials directly
        for item in selected_items:
            stock_entry.append("items", {
                "item_code": item.item_code,
                "qty": flt(item.transfer_qty),
                "uom": item.uom,
                "from_warehouse": doc.source_warehouse,
                "to_warehouse": doc.target_warehouse,
                "is_finished_item": 0
            })
        
        stock_entry.insert()
        stock_entry.submit()
        
        # Update work orders (this is simplified - in real scenario you'd need to track which work orders were affected)
        # For now, we'll just create the stock entry
        
        frappe.msgprint(f"Stock Entry {stock_entry.name} created successfully")
        return {"success": True, "stock_entry": stock_entry.name}
        
    except Exception as e:
        # Create a much shorter error message to fit in Error Log title field (max 140 chars)
        error_msg = str(e)
        if len(error_msg) > 70:  # Be more conservative to ensure it fits
            error_msg = error_msg[:67] + "..."
        
        # Ensure the total message doesn't exceed 140 chars
        full_message = f"Error creating selective transfer: {error_msg}"
        if len(full_message) > 140:
            # Final fallback - very short message
            full_message = f"Error creating selective transfer: {error_msg[:50]}..."
        
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def update_transfer_quantities(doc_name, transfer_doc_name):
    """Update transfer quantities in Work Order Transfer Manager after a transfer is created"""
    print(f"🔍 DEBUG: Starting update_transfer_quantities for doc_name: {doc_name}, transfer_doc_name: {transfer_doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        
        # If transfer_doc_name is empty, recompute from existing transfers
        if not transfer_doc_name:
            print(f"🔍 DEBUG: transfer_doc_name is empty, recomputing from existing transfers")
            existing_transfers = frappe.get_all("Raw Material Transfer", 
                filters={"work_order_transfer_manager": doc_name, "docstatus": 1},
                fields=["name"])
            
            item_to_delta = {}
            for transfer in existing_transfers:
                transfer_doc = frappe.get_doc("Raw Material Transfer", transfer.name)
                for ti in transfer_doc.raw_materials:
                    item_to_delta[ti.item_code] = item_to_delta.get(ti.item_code, 0) + flt(ti.transfer_qty)
            
            # Update rows
            for row in doc.transfer_items:
                if row.item_code in item_to_delta:
                    row.transferred_qty_so_far = flt(row.transferred_qty_so_far) + item_to_delta[row.item_code]
                    # also bump transfer_qty if this row was selected for transfer (visual feedback)
                    if row.select_for_transfer:
                        row.transfer_qty = 0
                # refresh current stock snapshots
                if getattr(doc, 'source_warehouse', None):
                    bin_qty = frappe.db.sql(
                        """
                        SELECT actual_qty FROM `tabBin` WHERE item_code=%s AND warehouse=%s
                        """,
                        (row.item_code, doc.source_warehouse), as_dict=True
                    )
                    row.actual_qty_at_warehouse = flt(bin_qty[0].actual_qty) if bin_qty else 0
                if getattr(doc, 'company', None):
                    company_bins = frappe.db.sql(
                        """
                        SELECT SUM(b.actual_qty) AS qty
                        FROM `tabBin` b
                        JOIN `tabWarehouse` w ON w.name = b.warehouse
                        WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                        """,
                        (row.item_code, doc.company), as_dict=True
                    )
                    row.actual_qty_at_company = flt(company_bins[0].qty) if company_bins and company_bins[0].qty is not None else 0
        else:
            # If transfer_doc_name is provided, get the specific transfer document
            transfer_doc = frappe.get_doc("Raw Material Transfer", transfer_doc_name)
            
            # Build item -> delta map from the specific transfer document
            item_to_delta = {}
            for ti in transfer_doc.raw_materials:
                item_to_delta[ti.item_code] = item_to_delta.get(ti.item_code, 0) + flt(ti.transfer_qty)
            
            # Update rows
            for row in doc.transfer_items:
                if row.item_code in item_to_delta:
                    row.transferred_qty_so_far = flt(row.transferred_qty_so_far) + item_to_delta[row.item_code]
                    # also bump transfer_qty if this row was selected for transfer (visual feedback)
                    if row.select_for_transfer:
                        row.transfer_qty = 0
                # refresh current stock snapshots
                if getattr(doc, 'source_warehouse', None):
                    bin_qty = frappe.db.sql(
                        """
                        SELECT actual_qty FROM `tabBin` WHERE item_code=%s AND warehouse=%s
                        """,
                        (row.item_code, doc.source_warehouse), as_dict=True
                    )
                    row.actual_qty_at_warehouse = flt(bin_qty[0].actual_qty) if bin_qty else 0
                if getattr(doc, 'company', None):
                    company_bins = frappe.db.sql(
                        """
                        SELECT SUM(b.actual_qty) AS qty
                        FROM `tabBin` b
                        JOIN `tabWarehouse` w ON w.name = b.warehouse
                        WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                        """,
                        (row.item_code, doc.company), as_dict=True
                    )
                    row.actual_qty_at_company = flt(company_bins[0].qty) if company_bins and company_bins[0].qty is not None else 0
        
        # Only save if there are actual changes (when transfer_doc_name is provided)
        # For stock snapshot refresh (empty transfer_doc_name), don't save to avoid timestamp conflicts
        if transfer_doc_name:
            doc.save()
            print("🔍 DEBUG: Quantities updated on parent doc and saved")
        else:
            print("🔍 DEBUG: Stock snapshots refreshed (no save to avoid timestamp conflicts)")
        
        return {"success": True}
    except Exception as e:
        print(f"❌ DEBUG: Error updating transfer quantities: {e}")
        return {"success": False, "message": str(e)}

def get_transfer_status(transferred_qty, ordered_qty):
    transferred_qty = flt(transferred_qty)
    ordered_qty = flt(ordered_qty)
    
    if transferred_qty == 0:
        return "Pending"
    elif transferred_qty >= ordered_qty:
        return "Fully Transferred"
    else:
        return "Partially Transferred" 