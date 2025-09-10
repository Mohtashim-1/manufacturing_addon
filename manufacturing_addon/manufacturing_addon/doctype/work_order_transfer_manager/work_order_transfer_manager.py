import frappe
from frappe import _
from frappe.utils import flt
from rq.job import Job
from rq.command import send_stop_job_command
from frappe.utils.background_jobs import get_redis_conn

class WorkOrderTransferManager(frappe.model.document.Document):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._totals_calculated = False
        
        # Ensure company is set during initialization
        if not self.company:
            self.company = frappe.defaults.get_global_default("company")
            print(f"🔍 DEBUG: Set company in __init__: {self.company}")

    def validate(self):
        print(f"🔍 DEBUG: validate() called for document: {self.name}")
        if not self._totals_calculated:
            self.calculate_totals()
            self._totals_calculated = True
        
        # Ensure company is set in all child tables BEFORE validation
        self.ensure_company_in_child_tables()
        
        # Additional validation to catch any missing company fields
        if self.transfer_items:
            for i, item in enumerate(self.transfer_items):
                if not item.company:
                    # Try to set company one more time before throwing error
                    if self.company:
                        item.company = self.company
                        print(f"🔍 DEBUG: Set company for transfer item {i+1} ({item.item_code}) during validation: {item.company}")
                    else:
                        frappe.throw(f"Company field is missing for transfer item {i+1} ({item.item_code}). Please ensure all items have a company set.")
        
        if self.work_order_details:
            for i, item in enumerate(self.work_order_details):
                if hasattr(item, "company"):
                    if not item.company:
                        # Try to set company one more time before throwing error
                        if self.company:
                            item.company = self.company
                            print(f"🔍 DEBUG: Set company for work order detail {i+1} ({item.work_order}) during validation: {item.company}")
                        else:
                            frappe.throw(f"Company field is missing for work order detail {i+1} ({item.work_order}). Please ensure all items have a company set.")
        
        if self.work_order_summary:
            for i, item in enumerate(self.work_order_summary):
                if hasattr(item, "company"):
                    if not item.company:
                        # Try to set company one more time before throwing error
                        if self.company:
                            item.company = self.company
                            print(f"🔍 DEBUG: Set company for work order summary {i+1} ({item.item_code}) during validation: {item.company}")
                        else:
                            frappe.throw(f"Company field is missing for work order summary {i+1} ({item.item_code}). Please ensure all items have a company set.")

    def ensure_company_in_child_tables(self):
        """Ensure all child table items have the company field set"""
        if not self.company:
            self.company = frappe.defaults.get_global_default("company")
            print(f"🔍 DEBUG: Set company on parent document: {self.company}")
        
        # Ensure company is set in all child tables
        if self.transfer_items:
            for item in self.transfer_items:
                if not item.company:
                    item.company = self.company
                    print(f"🔍 DEBUG: Set company for transfer item {item.item_code}: {item.company}")
                elif item.company != self.company:
                    # If company is set but different, update it
                    item.company = self.company
                    print(f"🔍 DEBUG: Updated company for transfer item {item.item_code}: {item.company}")
        
        if self.work_order_details:
            for item in self.work_order_details:
                if hasattr(item, "company"):
                    if not item.company:
                        item.company = self.company
                        print(f"🔍 DEBUG: Set company for work order detail {item.work_order}: {item.company}")
                    elif item.company != self.company:
                        # If company is set but different, update it
                        item.company = self.company
                        print(f"🔍 DEBUG: Updated company for work order detail {item.work_order}: {item.company}")
        
        if self.work_order_summary:
            for item in self.work_order_summary:
                if hasattr(item, "company"):
                    if not item.company:
                        item.company = self.company
                        print(f"🔍 DEBUG: Set company for work order summary {item.item_code}: {item.company}")
                    elif item.company != self.company:
                        # If company is set but different, update it
                        item.company = self.company
                        print(f"🔍 DEBUG: Updated company for work order summary {item.item_code}: {item.company}")

    def before_save(self):
        print(f"🔍 DEBUG: before_save() called for document: {self.name}")
        self._totals_calculated = False
        
        # Ensure company is set on parent document
        if not self.company:
            self.company = frappe.defaults.get_global_default("company")
            print(f"🔍 DEBUG: Set company in before_save: {self.company}")
        
        # Ensure company is set in all child tables before saving
        self.ensure_company_in_child_tables()

    def before_submit(self):
        print(f"🔍 DEBUG: before_submit() called for document: {self.name}")
        if not self._totals_calculated:
            self.calculate_totals()
            self._totals_calculated = True

        # Ensure company is set on parent document
        if not self.company:
            self.company = frappe.defaults.get_global_default("company")
            print(f"🔍 DEBUG: Set company in before_submit: {self.company}")

        # Ensure company is set in all child tables before submitting
        self.ensure_company_in_child_tables()

        if not self.work_order_details:
            frappe.throw("Please fetch work orders before submitting")

        if not self.transfer_items:
            frappe.throw("No raw materials found. Please fetch work orders first.")

    def validate_sales_order(self):
        print(f"🔍 DEBUG: validate_sales_order() called")
        if self.sales_order:
            so_doc = frappe.get_doc("Sales Order", self.sales_order)
            self.customer = so_doc.customer
            
            # Ensure company is set from sales order if not already set
            if not self.company and so_doc.company:
                self.company = so_doc.company
                print(f"🔍 DEBUG: Set company from sales order: {self.company}")

    def calculate_totals(self):
        print(f"🔍 DEBUG: calculate_totals() called")
        
        # Ensure company is set
        if not self.company:
            self.company = frappe.defaults.get_global_default("company")
            print(f"🔍 DEBUG: Set company in calculate_totals: {self.company}")
        
        total_ordered, total_delivered, total_pending = 0, 0, 0

        if hasattr(self, 'work_order_details') and self.work_order_details:
            for row in self.work_order_details:
                total_ordered += flt(row.ordered_qty or 0)
                total_delivered += flt(row.delivered_qty or 0)
                total_pending += flt(row.pending_qty or 0)

        if hasattr(self, 'total_ordered_qty'):
            self.total_ordered_qty = total_ordered
        if hasattr(self, 'total_delivered_qty'):
            self.total_delivered_qty = total_delivered
        if hasattr(self, 'total_pending_qty'):
            self.total_pending_qty = total_pending

        print(f"🔍 DEBUG: Totals calculated - Ordered: {total_ordered}, Delivered: {total_delivered}, Pending: {total_pending}")

    def on_submit(self):
        print(f"🔍 DEBUG: on_submit() called for document: {self.name}")
        
        # Ensure company is set
        if not self.company:
            self.company = frappe.defaults.get_global_default("company")
            print(f"🔍 DEBUG: Set company in on_submit: {self.company}")
        
        print(f"🔍 DEBUG: Document submitted successfully")

    def on_cancel(self):
        print(f"🔍 DEBUG: on_cancel() called for document: {self.name}")
        
        # Ensure company is set
        if not self.company:
            self.company = frappe.defaults.get_global_default("company")
            print(f"🔍 DEBUG: Set company in on_cancel: {self.company}")
        
        existing_transfers = frappe.get_all(
            "Raw Material Transfer",
            filters={"work_order_transfer_manager": self.name, "docstatus": 1}
        )
        if existing_transfers:
            frappe.throw("Cannot cancel this document as transfers have already been created from it.")


def get_transfer_status(transferred_qty, ordered_qty):
    transferred_qty = flt(transferred_qty)
    ordered_qty = flt(ordered_qty)
    if transferred_qty == 0:
        return "Pending"
    elif transferred_qty >= ordered_qty:
        return "Fully Transferred"
    else:
        return "Partially Transferred"


@frappe.whitelist()
def populate_work_order_tables(sales_order, doc_name):
    """Populate WOTM: finished items, work orders, and raw materials"""
    print(f"🔍 DEBUG: Starting populate_work_order_tables for sales_order: {sales_order}, doc_name: {doc_name}")
    
    # Ensure we have a valid company
    company = frappe.defaults.get_global_default("company")
    if not company:
        frappe.throw("Company is not set in global defaults. Please set a default company.")
    
    print(f"🔍 DEBUG: Using company: {company}")

    # if doc_name.company:
    #     for i in doc_name:

    try:
        # Check if WOTM already exists for this sales order (only active ones)
        existing_wotm = frappe.db.exists("Work Order Transfer Manager", {"sales_order": sales_order, "docstatus": ["!=", 2]})
        if existing_wotm and existing_wotm == doc_name:
            print(f"🔍 DEBUG: Active WOTM already exists for sales order {sales_order}: {existing_wotm}")
            doc = frappe.get_doc("Work Order Transfer Manager", existing_wotm)
            
            # Fix existing child table rows with missing company field
            print(f"🔍 DEBUG: Fixing existing child table rows with missing company field")
            
            # Fix transfer items
            if doc.transfer_items:
                for item in doc.transfer_items:
                    if not item.company:
                        item.company = frappe.defaults.get_global_default("company")
                        print(f"🔍 DEBUG: Fixed company for existing transfer item {item.item_code}")
            
            # Fix work order details
            if doc.work_order_details:
                for item in doc.work_order_details:
                    if hasattr(item, "company") and not item.company:
                        item.company = frappe.defaults.get_global_default("company")
                        print(f"🔍 DEBUG: Fixed company for existing work order detail {item.work_order}")
            
            # Fix work order summary
            if doc.work_order_summary:
                for item in doc.work_order_summary:
                    if hasattr(item, "company") and not item.company:
                        item.company = frappe.defaults.get_global_default("company")
                        print(f"🔍 DEBUG: Fixed company for existing work order summary {item.item_code}")
            
            # Ensure required fields are set (only for draft documents)
            if doc.docstatus == 0:
                if not getattr(doc, 'company', None):
                    doc.company = frappe.defaults.get_global_default("company")
                if not getattr(doc, 'stock_entry_type', None):
                    doc.stock_entry_type = "Material Transfer for Manufacture"
                if not getattr(doc, 'source_warehouse', None) or not getattr(doc, 'target_warehouse', None):
                    company = doc.company or frappe.defaults.get_global_default("company")
                    if company:
                        warehouses = frappe.db.sql("""
                            SELECT name FROM `tabWarehouse`
                            WHERE company = %s AND is_group = 0
                            ORDER BY name ASC LIMIT 2
                        """, (company,), as_dict=True)
                        if warehouses:
                            if not getattr(doc, 'source_warehouse', None):
                                doc.source_warehouse = warehouses[0].name
                            if not getattr(doc, 'target_warehouse', None):
                                if len(warehouses) > 1:
                                    doc.target_warehouse = warehouses[1].name
                                else:
                                    doc.target_warehouse = warehouses[0].name
            else:
                # Submitted: required fields must already exist
                required_missing = []
                if not getattr(doc, 'stock_entry_type', None):
                    required_missing.append('Stock Entry Type')
                if not getattr(doc, 'source_warehouse', None):
                    required_missing.append('Source Warehouse')
                if not getattr(doc, 'target_warehouse', None):
                    required_missing.append('Target Warehouse')
                if required_missing:
                    frappe.throw("Submitted Work Order Transfer Manager is missing required fields: " + ", ".join(required_missing))
            
            # Save the document with fixed child table rows
            try:
                doc.save()
                print(f"🔍 DEBUG: Saved existing WOTM with company: {doc.company}")
            except Exception as save_error:
                print(f"❌ DEBUG: Error saving existing WOTM: {save_error}")
                # If save fails, try to fix the child table rows directly in the database
                print(f"🔍 DEBUG: Attempting to fix child table rows directly in database")
                
                # Fix transfer items directly in database
                frappe.db.sql("""
                    UPDATE `tabWork Order Transfer Items Table`
                    SET company = %s
                    WHERE parent = %s AND (company IS NULL OR company = '')
                """, (frappe.defaults.get_global_default("company"), existing_wotm))
                
                # Note: Work Order Details and Summary tables don't have company column
                # Skip direct database updates for these tables
                print(f"🔍 DEBUG: Skipping direct database updates for work order details/summary (no company column)")
                
                # Commit the changes
                frappe.db.commit()
                print(f"🔍 DEBUG: Fixed child table rows directly in database")
                
                # Reload the document
                doc = frappe.get_doc("Work Order Transfer Manager", existing_wotm)
        else:
            # If existing WOTM exists but is not the requested doc_name, prefer the requested draft/new doc
            # Check if there's a cancelled document
            cancelled_wotm = frappe.db.exists("Work Order Transfer Manager", {"sales_order": sales_order, "docstatus": 2})
            if cancelled_wotm:
                print(f"🔍 DEBUG: Found cancelled WOTM for sales order {sales_order}: {cancelled_wotm}, creating new document")
            
            # Create new document (either no existing WOTM or only cancelled ones exist)
            if not frappe.db.exists("Work Order Transfer Manager", doc_name):
                print(f"🔍 DEBUG: Document {doc_name} not found, creating new document")
                doc = frappe.new_doc("Work Order Transfer Manager")
                doc.sales_order = sales_order
                doc.posting_date = frappe.utils.today()
                doc.posting_time = frappe.utils.nowtime()

                # Set required defaults
                try:
                    # Set company
                    doc.company = frappe.defaults.get_global_default("company")
                    
                    # Set stock entry type (only for new documents)
                    if doc.docstatus == 0:
                        doc.stock_entry_type = "Material Transfer for Manufacture"
                    
                    # Set warehouses
                    if doc.company:
                        warehouses = frappe.db.sql("""
                            SELECT name FROM `tabWarehouse`
                            WHERE company = %s AND is_group = 0
                            ORDER BY name ASC LIMIT 2
                        """, (doc.company,), as_dict=True)
                        if warehouses:
                            doc.source_warehouse = warehouses[0].name
                            if len(warehouses) > 1:
                                doc.target_warehouse = warehouses[1].name
                            else:
                                doc.target_warehouse = warehouses[0].name
                            print(f"🔍 DEBUG: source={doc.source_warehouse}, target={doc.target_warehouse}")
                except Exception as e:
                    print(f"🔍 DEBUG: Error setting defaults: {e}")

                print(f"🔍 DEBUG: About to insert new document")
                doc.insert()
                print(f"🔍 DEBUG: Created new document with name: {doc.name}")
                
                # Ensure company is set after insert
                if not doc.company:
                    doc.company = frappe.defaults.get_global_default("company")
                    doc.save()
                    print(f"🔍 DEBUG: Set company after insert: {doc.company}")
            else:
                print(f"🔍 DEBUG: Found existing document: {doc_name}")
                doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
                
                # Fix existing child table rows with missing company field
                print(f"🔍 DEBUG: Fixing existing child table rows with missing company field for document: {doc_name}")
                
                # Fix transfer items
                if doc.transfer_items:
                    for item in doc.transfer_items:
                        if not item.company:
                            item.company = frappe.defaults.get_global_default("company")
                            print(f"🔍 DEBUG: Fixed company for existing transfer item {item.item_code}")
                
                # Fix work order details
                if doc.work_order_details:
                    for item in doc.work_order_details:
                        if hasattr(item, "company") and not item.company:
                            item.company = frappe.defaults.get_global_default("company")
                            print(f"🔍 DEBUG: Fixed company for existing work order detail {item.work_order}")
                
                # Fix work order summary
                if doc.work_order_summary:
                    for item in doc.work_order_summary:
                        if hasattr(item, "company") and not item.company:
                            item.company = frappe.defaults.get_global_default("company")
                            print(f"🔍 DEBUG: Fixed company for existing work order summary {item.item_code}")
                
                if not getattr(doc, 'company', None):
                    doc.company = frappe.defaults.get_global_default("company")
                
                # Save the document with fixed child table rows
                try:
                    doc.save()
                    print(f"🔍 DEBUG: Set company on existing document: {doc.company}")
                except Exception as save_error:
                    print(f"❌ DEBUG: Error saving existing document: {save_error}")
                    # If save fails, try to fix the child table rows directly in the database
                    print(f"🔍 DEBUG: Attempting to fix child table rows directly in database for document: {doc_name}")
                    
                    # Fix transfer items directly in database
                    frappe.db.sql("""
                        UPDATE `tabWork Order Transfer Items Table`
                        SET company = %s
                        WHERE parent = %s AND (company IS NULL OR company = '')
                    """, (frappe.defaults.get_global_default("company"), doc_name))
                    
                    # Note: Work Order Details and Summary tables don't have company column
                    # Skip direct database updates for these tables
                    print(f"🔍 DEBUG: Skipping direct database updates for work order details/summary (no company column)")
                    
                    # Commit the changes
                    frappe.db.commit()
                    print(f"🔍 DEBUG: Fixed child table rows directly in database for document: {doc_name}")
                    
                    # Reload the document
                    doc = frappe.get_doc("Work Order Transfer Manager", doc_name)

        # Ensure company is set on the parent document
        if not doc.company:
            doc.company = company
            print(f"🔍 DEBUG: Set company on parent document: {doc.company}")
        
        # Double-check company is set
        if not doc.company:
            doc.company = frappe.defaults.get_global_default("company")
            print(f"🔍 DEBUG: Set company to: {doc.company}")
        
        # Clear tables
        print(f"🔍 DEBUG: Clearing existing tables")
        
        # Clear tables by setting them to empty lists
        # This will remove all existing child table rows
        doc.work_order_details = []
        doc.work_order_summary = []
        doc.transfer_items = []
        
        # Force a save to clear the existing child table rows
        try:
            doc.save()
            print(f"🔍 DEBUG: Cleared existing child table rows")
        except Exception as clear_error:
            print(f"❌ DEBUG: Error clearing child table rows: {clear_error}")
            # If clearing fails, try to delete the child table rows directly
            print(f"🔍 DEBUG: Attempting to delete child table rows directly from database")
            
            # Delete transfer items directly from database
            frappe.db.sql("""
                DELETE FROM `tabWork Order Transfer Items Table`
                WHERE parent = %s
            """, (doc.name,))
            
            # Delete work order details directly from database
            frappe.db.sql("""
                DELETE FROM `tabWork Order Details Table`
                WHERE parent = %s
            """, (doc.name,))
            
            # Delete work order summary directly from database
            frappe.db.sql("""
                DELETE FROM `tabWork Order Summary Table`
                WHERE parent = %s
            """, (doc.name,))
            
            # Commit the changes
            frappe.db.commit()
            print(f"🔍 DEBUG: Deleted child table rows directly from database")
            
            # Reload the document
            doc = frappe.get_doc("Work Order Transfer Manager", doc.name)
        
        # Final check - ensure company is set
        if not doc.company:
            frappe.throw("Company is required. Please set the company field.")

        # Fetch work orders (submitted)
        work_orders = frappe.db.sql("""
            SELECT
                name, production_item, item_name, qty,
                material_transferred_for_manufacturing, produced_qty,
                status, creation
            FROM `tabWork Order`
            WHERE sales_order = %s AND docstatus = 1
            ORDER BY creation ASC
        """, (sales_order,), as_dict=True)
        print(f"🔍 DEBUG: Retrieved {len(work_orders)} work orders")

        item_summary = {}
        raw_material_summary = {}
        
        # Precompute already transferred quantities per item from submitted Raw Material Transfers
        transferred_map = {}
        try:
            existing_transfers = frappe.get_all(
                "Raw Material Transfer",
                filters={"work_order_transfer_manager": doc.name, "docstatus": 1},
                fields=["name"]
            )
            for t in existing_transfers:
                tdoc = frappe.get_doc("Raw Material Transfer", t.name)
                for ri in tdoc.raw_materials:
                    transferred_map[ri.item_code] = transferred_map.get(ri.item_code, 0) + flt(ri.transfer_qty)
        except Exception as e:
            print(f"❌ DEBUG: Error precomputing transferred_map: {e}")
            transferred_map = {}

        for wo in work_orders:
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
            pending_qty = max(ordered_qty - transferred_qty, 0)

            item_summary[wo.production_item]["total_ordered_qty"] += ordered_qty
            item_summary[wo.production_item]["total_transferred_qty"] += transferred_qty
            item_summary[wo.production_item]["total_pending_qty"] += pending_qty
            item_summary[wo.production_item]["work_orders"].append(wo)

            # Detail row
            detail_data = {
                "work_order": wo.name,
                "item_code": wo.production_item,
                "item_name": wo.item_name,
                "ordered_qty": ordered_qty,
                "transferred_qty": transferred_qty,
                "pending_qty": pending_qty,
                "work_order_status": wo.status,
                "transfer_status": get_transfer_status(transferred_qty, ordered_qty),
                "company": doc.company
            }
            detail_row = doc.append("work_order_details", detail_data)
            
            # Ensure company is set
            if hasattr(detail_row, "company") and not detail_row.company:
                detail_row.company = doc.company
                print(f"🔍 DEBUG: Set company for work order detail {wo.name}: {detail_row.company}")

            # Raw materials for pending qty only
            if pending_qty > 0:
                try:
                    bom = frappe.db.get_value("BOM", {"item": wo.production_item, "is_active": 1, "is_default": 1})
                    if bom:
                        bom_doc = frappe.get_doc("BOM", bom)
                        for bi in bom_doc.items:
                            raw_code = bi.item_code
                            raw_name = frappe.db.get_value("Item", raw_code, "item_name") or raw_code
                            raw_needed = flt(pending_qty) * flt(bi.qty) / flt(bom_doc.quantity)

                            if raw_code not in raw_material_summary:
                                raw_material_summary[raw_code] = {
                                    "item_code": raw_code,
                                    "item_name": raw_name,
                                    "uom": bi.uom,
                                    "total_qty_needed": 0,
                                    "work_orders": []
                                }
                            raw_material_summary[raw_code]["total_qty_needed"] += raw_needed
                            raw_material_summary[raw_code]["work_orders"].append({
                                "work_order": wo.name,
                                "finished_item": wo.production_item,
                                "pending_qty": pending_qty,
                                "raw_qty_needed": raw_needed,
                                "creation": wo.creation
                            })
                except Exception as e:
                    print(f"❌ DEBUG: Error calculating raw materials: {e}")

        print(f"🔍 DEBUG: Processed {len(item_summary)} unique finished items")
        print(f"🔍 DEBUG: Found {len(raw_material_summary)} unique raw materials")

        # Summary rows
        for item_code, summary in item_summary.items():
            summary_data = {
                "item_code": summary["item_code"],
                "item_name": summary["item_name"],
                "total_ordered_qty": summary["total_ordered_qty"],
                "total_transferred_qty": summary["total_transferred_qty"],
                "total_pending_qty": summary["total_pending_qty"],
                "work_order_count": len(summary["work_orders"]),
                "transfer_status": get_transfer_status(summary["total_transferred_qty"], summary["total_ordered_qty"]),
                "company": doc.company
            }
            summary_row = doc.append("work_order_summary", summary_data)
            
            # Ensure company is set
            if hasattr(summary_row, "company") and not summary_row.company:
                summary_row.company = doc.company
                print(f"🔍 DEBUG: Set company for work order summary {item_code}: {summary_row.company}")

        # Transfer items (respect already-transferred from submitted RMT)
        for raw_item_code, raw_summary in raw_material_summary.items():
            try:
                source_warehouse = doc.source_warehouse or ""
                actual_qty_at_warehouse = 0
                if source_warehouse:
                    actual_qty = frappe.db.sql("""
                        SELECT actual_qty FROM `tabBin`
                        WHERE item_code = %s AND warehouse = %s
                    """, (raw_item_code, source_warehouse), as_dict=True)
                    actual_qty_at_warehouse = flt(actual_qty[0].actual_qty) if actual_qty else 0

                actual_company_qty = 0
                if doc.company:
                    company_bins = frappe.db.sql("""
                        SELECT SUM(b.actual_qty) AS qty
                        FROM `tabBin` b
                        JOIN `tabWarehouse` w ON w.name = b.warehouse
                        WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                    """, (raw_item_code, doc.company), as_dict=True)
                    actual_company_qty = flt(company_bins[0].qty) if company_bins and company_bins[0].qty is not None else 0

                # Use precomputed transferred_map aggregated from submitted Raw Material Transfers
                transferred_so_far = flt(transferred_map.get(raw_item_code, 0))
                total_required = flt(raw_summary["total_qty_needed"])
                remaining = max(total_required - transferred_so_far, 0)

                # Ensure we have a valid company
                company_value = doc.company or company
                if not company_value:
                    frappe.throw("Company is required. Please set the company field.")
                
                print(f"🔍 DEBUG: Using company value for {raw_item_code}: {company_value}")
                
                # Calculate initial status and percentage for this item
                item_status, item_percentage = calculate_transfer_status_and_percentage(transferred_so_far, total_required)
                
                # Create the transfer item data with company explicitly set
                transfer_item_data = {
                    "item_code": raw_item_code,
                    "item_name": raw_summary["item_name"],
                    "total_required_qty": total_required,
                    "pending_qty": remaining,
                    "transfer_qty": transferred_so_far,  # Set to same value as transferred_qty_so_far
                    "transferred_qty_so_far": transferred_so_far,
                    "item_transfer_status": item_status,
                    "item_transfer_percentage": item_percentage,
                    "actual_qty_at_warehouse": actual_qty_at_warehouse,
                    "actual_qty_at_company": actual_company_qty,
                    "uom": raw_summary["uom"],
                    "warehouse": source_warehouse,
                    "company": company_value
                }
                
                transfer_item = doc.append("transfer_items", transfer_item_data)
                
                # Double-check that company is set
                if not transfer_item.company:
                    transfer_item.company = company_value
                    print(f"🔍 DEBUG: Set company for {raw_item_code} after append: {transfer_item.company}")
                
                # Verify company is set
                if not transfer_item.company:
                    print(f"❌ DEBUG: Company still not set for {raw_item_code} after setting it!")
                    # Try one more time
                    transfer_item.company = company_value
                else:
                    print(f"🔍 DEBUG: Added transfer item for {raw_item_code} with company: {transfer_item.company}")
            except Exception as e:
                print(f"❌ DEBUG: Error appending raw material to transfer_items: {e}")
                print(f"❌ DEBUG: Raw item code: {raw_item_code}")
                print(f"❌ DEBUG: Raw summary: {raw_summary}")
                raise e

        # Ensure company is set in all child tables before saving
        doc.ensure_company_in_child_tables()
        
        # Double-check all transfer items have company set
        for i, item in enumerate(doc.transfer_items):
            if not item.company:
                print(f"🔍 DEBUG: Setting company for item {i+1} ({item.item_code})")
                item.company = doc.company
        
        # Double-check all work order details have company set
        for i, item in enumerate(doc.work_order_details):
            if hasattr(item, "company") and not item.company:
                print(f"🔍 DEBUG: Setting company for work order detail {i+1} ({item.work_order})")
                item.company = doc.company
        
        # Double-check all work order summary items have company set
        for i, item in enumerate(doc.work_order_summary):
            if hasattr(item, "company") and not item.company:
                print(f"🔍 DEBUG: Setting company for work order summary {i+1} ({item.item_code})")
                item.company = doc.company
        
        # Final validation - ensure all items have company set
        missing_company_items = []
        for i, item in enumerate(doc.transfer_items):
            if not item.company:
                missing_company_items.append(f"Transfer Item {i+1} ({item.item_code})")
        
        for i, item in enumerate(doc.work_order_details):
            if hasattr(item, "company") and not item.company:
                missing_company_items.append(f"Work Order Detail {i+1} ({item.work_order})")
        
        for i, item in enumerate(doc.work_order_summary):
            if hasattr(item, "company") and not item.company:
                missing_company_items.append(f"Work Order Summary {i+1} ({item.item_code})")
        
        if missing_company_items:
            error_msg = f"The following items are missing company field: {', '.join(missing_company_items)}"
            print(f"❌ DEBUG: {error_msg}")
            frappe.throw(error_msg)
        
        # Save
        print(f"🔍 DEBUG: Calling doc.save()...")
        try:
            doc.save()
            print(f"🔍 DEBUG: Document saved successfully with {len(doc.work_order_details)} details, {len(doc.work_order_summary)} summary, {len(doc.transfer_items)} raw material transfer items")
        except Exception as final_save_error:
            print(f"❌ DEBUG: Error in final save: {final_save_error}")
            # If the final save fails, try to save the child table rows directly
            print(f"🔍 DEBUG: Attempting to save child table rows directly to database")
            
            # Save transfer items directly to database
            for i, item in enumerate(doc.transfer_items):
                frappe.db.sql("""
                    INSERT INTO `tabWork Order Transfer Items Table`
                    (name, parent, parentfield, parenttype, idx, item_code, item_name, 
                     total_required_qty, pending_qty, transfer_qty, transferred_qty_so_far,
                     item_transfer_status, item_transfer_percentage,
                     actual_qty_at_warehouse, actual_qty_at_company, uom, warehouse, company)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    item.name or f"transfer_item_{i+1}",
                    doc.name,
                    "transfer_items",
                    "Work Order Transfer Manager",
                    i+1,
                    item.item_code,
                    item.item_name,
                    item.total_required_qty,
                    item.pending_qty,
                    item.transfer_qty,
                    item.transferred_qty_so_far,
                    getattr(item, 'item_transfer_status', 'Pending'),
                    getattr(item, 'item_transfer_percentage', 0),
                    item.actual_qty_at_warehouse,
                    item.actual_qty_at_company,
                    item.uom,
                    item.warehouse,
                    item.company
                ))
            
            # Note: Work Order Details and Summary tables don't have transferred_qty and company columns
            # Skip direct database inserts for these tables
            print(f"🔍 DEBUG: Skipping direct database inserts for work order details/summary (missing columns)")
            
            # Commit the changes
            frappe.db.commit()
            print(f"🔍 DEBUG: Saved child table rows directly to database")
            
            # Reload the document
            doc = frappe.get_doc("Work Order Transfer Manager", doc.name)

        # Calculate and set overall WOTM status and percentage
        overall_status, overall_percentage = calculate_overall_wotm_status(doc)
        doc.transfer_status = overall_status
        doc.transfer_percentage = overall_percentage
        doc.save()
        
        return {
            "success": True,
            "message": f"Populated {len(doc.work_order_details)} work order details, {len(doc.work_order_summary)} summary items, {len(doc.transfer_items)} raw material transfer items",
            "doc_name": doc.name
        }

    except Exception as e:
        print(f"❌ DEBUG: Error in populate_work_order_tables: {str(e)}")
        import traceback
        print(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")
        error_msg = str(e)
        if len(error_msg) > 70:
            error_msg = error_msg[:67] + "..."
        full_message = f"Error populating work order tables for sales order {sales_order}: {error_msg}"
        if len(full_message) > 140:
            sales_order_short = sales_order[:20] + "..." if len(sales_order) > 23 else sales_order
            full_message = f"Error populating work order tables for sales order {sales_order_short}: {error_msg}"
            if len(full_message) > 140:
                full_message = f"Error populating work order tables: {error_msg[:50]}..."
        frappe.log_error(full_message)
        return {"success": False, "message": f"Error: {str(e)}"}


@frappe.whitelist()
def create_raw_material_transfer_doc(doc_name):
    """Create a new Raw Material Transfer with selected rows"""
    print(f"🔍 DEBUG: Starting create_raw_material_transfer_doc for doc_name: {doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        
        # Ensure company is set
        if not doc.company:
            doc.company = frappe.defaults.get_global_default("company")
            doc.save()
            print(f"🔍 DEBUG: Set company in create_raw_material_transfer_doc: {doc.company}")
        selected_items = [i for i in doc.transfer_items if i.select_for_transfer and flt(i.transfer_qty) > 0]
        if not selected_items:
            frappe.throw("Please select raw materials and enter transfer quantities")

        raw_transfer_doc = frappe.new_doc("Raw Material Transfer")
        raw_transfer_doc.sales_order = doc.sales_order
        raw_transfer_doc.work_order_transfer_manager = doc.name
        raw_transfer_doc.posting_date = doc.posting_date
        raw_transfer_doc.posting_time = doc.posting_time
        raw_transfer_doc.company = doc.company
        raw_transfer_doc.warehouse = doc.source_warehouse
        raw_transfer_doc.stock_entry_type = doc.stock_entry_type

        for item in selected_items:
            # Actuals
            awh = 0
            if doc.source_warehouse:
                bin_qty = frappe.db.sql("""
                    SELECT actual_qty FROM `tabBin`
                    WHERE item_code = %s AND warehouse = %s
                """, (item.item_code, doc.source_warehouse), as_dict=True)
                awh = flt(bin_qty[0].actual_qty) if bin_qty else 0

            acomp = 0
            if doc.company:
                comp_bins = frappe.db.sql("""
                    SELECT SUM(b.actual_qty) AS qty
                    FROM `tabBin` b
                    JOIN `tabWarehouse` w ON w.name = b.warehouse
                    WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                """, (item.item_code, doc.company), as_dict=True)
                acomp = flt(comp_bins[0].qty) if comp_bins and comp_bins[0].qty is not None else 0

            # Calculate the correct quantities:
            # total_required_qty = original requirement (from WOTM total_required_qty)
            # transferred_so_far = already transferred (from WOTM transferred_qty_so_far)
            # pending_qty = remaining to be transferred (from WOTM pending_qty)
            # transfer_qty = what we're transferring now
            
            total_required = flt(item.total_required_qty) or (flt(item.pending_qty) + flt(item.transferred_qty_so_far or 0))
            transferred_so_far = flt(item.transferred_qty_so_far or 0)
            pending_qty = flt(item.pending_qty)  # This is the actual remaining amount
            
            # Set transfer_qty to pending_qty by default (what's left to transfer)
            transfer_qty = flt(item.transfer_qty) if flt(item.transfer_qty) > 0 else pending_qty
            
            # Ensure transfer_qty doesn't exceed pending_qty
            if transfer_qty > pending_qty:
                transfer_qty = pending_qty
            
            raw_transfer_doc.append("raw_materials", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "total_required_qty": total_required,  # Original requirement (712.310)
                "pending_qty": pending_qty,  # This is the actual remaining amount (312.3)
                "transfer_qty": transfer_qty,
                "transferred_qty_so_far": transferred_so_far,  # Already transferred (400)
                "uom": item.uom,
                "warehouse": doc.source_warehouse,
                "source_warehouse": doc.source_warehouse,
                "target_warehouse": doc.target_warehouse,
                "actual_qty_at_warehouse": awh,
                "actual_qty_at_company": acomp
            })

        raw_transfer_doc.insert()

        # Update WOTM after creation (may still change on submit once SE is posted)
        update_transfer_quantities(doc_name, raw_transfer_doc.name)

        return {
            "success": True,
            "message": f"Raw Material Transfer document created: {raw_transfer_doc.name}",
            "doc_name": raw_transfer_doc.name
        }

    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 60:
            error_msg = error_msg[:57] + "..."
        full_message = f"Error creating raw material transfer document: {error_msg}"
        if len(full_message) > 140:
            full_message = f"Error creating raw material transfer: {error_msg[:50]}..."
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def create_all_pending_transfer(doc_name):
    """Create a new Raw Material Transfer with ALL remaining items"""
    print(f"🔍 DEBUG: Starting create_all_pending_transfer for doc_name: {doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        
        # Ensure company is set
        if not doc.company:
            doc.company = frappe.defaults.get_global_default("company")
            doc.save()
            print(f"🔍 DEBUG: Set company in create_all_pending_transfer: {doc.company}")
        if doc.docstatus != 1:
            frappe.throw("Please submit the Work Order Transfer Manager document first")

        pending_items = [i for i in doc.transfer_items if flt(i.pending_qty) > 0]
        if not pending_items:
            frappe.throw("No raw materials with pending quantities found")

        raw_transfer_doc = frappe.new_doc("Raw Material Transfer")
        raw_transfer_doc.sales_order = doc.sales_order
        raw_transfer_doc.work_order_transfer_manager = doc.name
        raw_transfer_doc.posting_date = doc.posting_date
        raw_transfer_doc.posting_time = doc.posting_time
        raw_transfer_doc.company = doc.company
        raw_transfer_doc.warehouse = doc.source_warehouse
        raw_transfer_doc.stock_entry_type = doc.stock_entry_type

        for item in pending_items:
            # Actuals
            awh = 0
            if doc.source_warehouse:
                bin_qty = frappe.db.sql("""
                    SELECT actual_qty FROM `tabBin`
                    WHERE item_code = %s AND warehouse = %s
                """, (item.item_code, doc.source_warehouse), as_dict=True)
                awh = flt(bin_qty[0].actual_qty) if bin_qty else 0

            acomp = 0
            if doc.company:
                comp_bins = frappe.db.sql("""
                    SELECT SUM(b.actual_qty) AS qty
                    FROM `tabBin` b
                    JOIN `tabWarehouse` w ON w.name = b.warehouse
                    WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                """, (item.item_code, doc.company), as_dict=True)
                acomp = flt(comp_bins[0].qty) if comp_bins and comp_bins[0].qty is not None else 0

            # Calculate the correct quantities:
            # total_required_qty = original requirement (from WOTM total_required_qty)
            # transferred_so_far = already transferred (from WOTM transferred_qty_so_far)
            # pending_qty = remaining to be transferred (from WOTM pending_qty)
            # transfer_qty = what we're transferring now
            
            total_required = flt(item.total_required_qty) or (flt(item.pending_qty) + flt(item.transferred_qty_so_far or 0))
            transferred_so_far = flt(item.transferred_qty_so_far or 0)
            pending_qty = flt(item.pending_qty)  # This is the actual remaining amount
            
            raw_transfer_doc.append("raw_materials", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "total_required_qty": total_required,  # Original requirement (712.310)
                "pending_qty": pending_qty,  # This is the actual remaining amount (312.3)
                "transfer_qty": pending_qty,  # Transfer the full remaining amount
                "transferred_qty_so_far": transferred_so_far,  # Already transferred (400)
                "uom": item.uom,
                "warehouse": doc.source_warehouse,
                "source_warehouse": doc.source_warehouse,
                "target_warehouse": doc.target_warehouse,
                "actual_qty_at_warehouse": awh,
                "actual_qty_at_company": acomp
            })

        raw_transfer_doc.insert()

        # Update WOTM after creation (pre-submit)
        update_transfer_quantities(doc_name, raw_transfer_doc.name)

        return {
            "success": True,
            "message": f"Raw Material Transfer document created with {len(pending_items)} items: {raw_transfer_doc.name}",
            "doc_name": raw_transfer_doc.name
        }

    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 60:
            error_msg = error_msg[:57] + "..."
        full_message = f"Error creating all pending transfer: {error_msg}"
        if len(full_message) > 140:
            full_message = f"Error creating all pending transfer: {error_msg[:50]}..."
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def create_all_pending_transfer_background(doc_name):
	"""Create a new Raw Material Transfer with ALL remaining items in background and return job id"""
	print(f"🔍 DEBUG: Starting create_all_pending_transfer_background for doc_name: {doc_name}")
	try:
		job = frappe.enqueue(
			"manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.create_all_pending_transfer_job",
			doc_name=doc_name,
			queue="long",
			timeout=600,
			job_name=f"create_raw_material_transfer_{doc_name}"
		)
		job_id = job.get_id() if job else None
		return {"success": True, "message": "Background job started.", "job_started": True, "job_id": job_id, "job_name": f"create_raw_material_transfer_{doc_name}"}
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
	print(f"🔍 DEBUG: Background job started for doc_name: {doc_name}")
	channel = f"raw_material_transfer_job_{doc_name}"
	try:
		# reuse foreground creator
		out = create_all_pending_transfer(doc_name)
		print(f"🔍 DEBUG: Background job result: {out}")
		try:
			frappe.publish_realtime(event=channel, message={"success": True, "result": out}, user=frappe.session.user)
		except Exception:
			pass
		return out
	except Exception as e:
		error_msg = str(e)
		if len(error_msg) > 60:
			error_msg = error_msg[:57] + "..."
		full_message = f"Error in background job: {error_msg}"
		if len(full_message) > 140:
			full_message = f"Error in background job: {error_msg[:50]}..."
		frappe.log_error(full_message)
		try:
			frappe.publish_realtime(event=channel, message={"success": False, "message": error_msg}, user=frappe.session.user)
		except Exception:
			pass

@frappe.whitelist()
def create_all_pending_transfer_direct(doc_name):
	"""Synchronous version: create ALL pending transfer in the same request (no background)."""
	print(f"🔍 DEBUG: Starting create_all_pending_transfer_direct for doc_name: {doc_name}")
	return create_all_pending_transfer(doc_name)


@frappe.whitelist()
def get_remaining_pending_items(doc_name):
    """Accurate remaining items using submitted transfers only"""
    print(f"🔍 DEBUG: get_remaining_pending_items called for: {doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        
        # Ensure company is set
        if not doc.company:
            doc.company = frappe.defaults.get_global_default("company")
            doc.save()
            print(f"🔍 DEBUG: Set company in get_remaining_pending_items: {doc.company}")

        existing_transfers = frappe.get_all(
            "Raw Material Transfer",
            filters={"work_order_transfer_manager": doc_name, "docstatus": 1},
            fields=["name"]
        )

        # Build totals by item
        transferred_map = {}
        for t in existing_transfers:
            tr_doc = frappe.get_doc("Raw Material Transfer", t.name)
            for ri in tr_doc.raw_materials:
                transferred_map[ri.item_code] = transferred_map.get(ri.item_code, 0) + flt(ri.transfer_qty)

        remaining_items = []
        for item in doc.transfer_items:
            # The pending_qty in WOTM is already the remaining amount after previous transfers
            remaining_qty = flt(item.pending_qty)
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
    """Create a Stock Entry directly for selected raw materials"""
    print(f"🔍 DEBUG: Starting create_selective_transfer for doc_name: {doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        
        # Ensure company is set
        if not doc.company:
            doc.company = frappe.defaults.get_global_default("company")
            doc.save()
            print(f"🔍 DEBUG: Set company in create_selective_transfer: {doc.company}")
        selected_items = [i for i in doc.transfer_items if i.select_for_transfer and flt(i.transfer_qty) > 0]
        if not selected_items:
            frappe.throw("Please select items and enter transfer quantities")

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Transfer for Manufacture"
        stock_entry.posting_date = doc.posting_date
        stock_entry.posting_time = doc.posting_time
        stock_entry.company = doc.company
        stock_entry.from_warehouse = doc.source_warehouse
        stock_entry.to_warehouse = doc.target_warehouse

        for item in selected_items:
            stock_entry.append("items", {
                "item_code": item.item_code,
                "qty": flt(item.transfer_qty),
                "uom": item.uom,
                "from_warehouse": doc.source_warehouse,
                "to_warehouse": doc.target_warehouse,
                "is_finished_item": 0
            })

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit(ignore_permissions=True)

        frappe.msgprint(f"Stock Entry {stock_entry.name} created successfully")
        return {"success": True, "stock_entry": stock_entry.name}

    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 70:
            error_msg = error_msg[:67] + "..."
        full_message = f"Error creating selective transfer: {error_msg}"
        if len(full_message) > 140:
            full_message = f"Error creating selective transfer: {error_msg[:50]}..."
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)}


def calculate_transfer_status_and_percentage(transferred_qty, total_required_qty):
    """
    Calculate transfer status and percentage based on transferred vs total required quantities
    """
    # Ensure we have valid numbers
    transferred_qty = flt(transferred_qty or 0)
    total_required_qty = flt(total_required_qty or 0)
    
    if total_required_qty <= 0:
        return "Pending", 0
    
    percentage = (transferred_qty / total_required_qty) * 100
    
    # Ensure percentage is a valid number
    if percentage is None or percentage == float('inf') or percentage == float('-inf') or percentage != percentage:  # NaN check
        percentage = 0
    
    if percentage >= 100:
        return "Completed", 100
    elif percentage > 0:
        return "In Progress", percentage
    else:
        return "Pending", 0


def calculate_overall_wotm_status(doc):
    """
    Calculate overall WOTM status and percentage based on all transfer items
    """
    if not doc.transfer_items:
        return "Pending", 0
    
    total_required = 0
    total_transferred = 0
    
    for item in doc.transfer_items:
        total_required += flt(item.total_required_qty or 0)
        total_transferred += flt(item.transferred_qty_so_far or 0)
    
    if total_required <= 0:
        return "Pending", 0
    
    percentage = (total_transferred / total_required) * 100
    
    # Ensure percentage is a valid number
    if percentage is None or percentage == float('inf') or percentage == float('-inf') or percentage != percentage:  # NaN check
        percentage = 0
    
    if percentage >= 100:
        return "Completed", 100
    elif percentage > 0:
        return "In Progress", percentage
    else:
        return "Pending", 0


@frappe.whitelist()
def update_transfer_quantities(doc_name, transfer_doc_name=None):
    """
    Recompute transferred & remaining for WOTM from ALL submitted Raw Material Transfers.
    Also refresh stock snapshots. Works for submitted parents via direct child updates.
    """
    print(f"🔍 DEBUG: Starting update_transfer_quantities for doc_name: {doc_name}, transfer_doc_name: {transfer_doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)

        # Permission: only users with write on this doc can recompute
        if not frappe.has_permission("Work Order Transfer Manager", ptype="write", doc=doc, user=frappe.session.user):
            return {"success": False, "message": "Not permitted to update transfer quantities"}
        
        # Ensure company is set
        if not doc.company:
            doc.company = frappe.defaults.get_global_default("company")
            doc.save()
            print(f"🔍 DEBUG: Set company in update_transfer_quantities: {doc.company}")

        # Check if document is submitted - if so, use direct database approach
        if doc.docstatus == 1:
            print(f"🔍 DEBUG: Document is submitted, using direct database approach")
            return update_transfer_quantities_submitted(doc_name, transfer_doc_name)

        # Aggregate transfers from all SUBMITTED Raw Material Transfers
        item_total_transferred = {}
        existing_transfers = frappe.get_all(
            "Raw Material Transfer",
            filters={"work_order_transfer_manager": doc_name, "docstatus": 1},
            fields=["name"],
        )
        for tr in existing_transfers:
            tr_doc = frappe.get_doc("Raw Material Transfer", tr.name)
            for ti in tr_doc.raw_materials:
                item_total_transferred[ti.item_code] = item_total_transferred.get(ti.item_code, 0) + flt(ti.transfer_qty)

        # Update each child row with proper error handling
        for row in doc.transfer_items:
            try:
                total_trans = flt(item_total_transferred.get(row.item_code, 0))
                
                # Validate that the row exists in the database before updating
                if not row.name or not frappe.db.exists("Work Order Transfer Items Table", row.name):
                    print(f"⚠️ WARNING: Row {row.name} for item {row.item_code} does not exist, skipping...")
                    continue
                
                # Ensure company is set before updating
                if not row.company:
                    try:
                        frappe.db.set_value("Work Order Transfer Items Table", row.name, "company", doc.company)
                    except Exception as e:
                        print(f"⚠️ WARNING: Could not set company for row {row.name}: {e}")
                
                # Update transferred_qty_so_far
                try:
                    frappe.db.set_value("Work Order Transfer Items Table", row.name, "transferred_qty_so_far", total_trans)
                except Exception as e:
                    print(f"⚠️ WARNING: Could not update transferred_qty_so_far for row {row.name}: {e}")
                
                # Also update transfer_qty with the same value as transferred_qty_so_far
                try:
                    frappe.db.set_value("Work Order Transfer Items Table", row.name, "transfer_qty", total_trans)
                except Exception as e:
                    print(f"⚠️ WARNING: Could not update transfer_qty for row {row.name}: {e}")

                # Use total_required_qty to compute remaining; if missing, infer (backward compatible)
                total_required = flt(getattr(row, "total_required_qty", 0))
                if not total_required:
                    # If total_required_qty is not set, calculate it from pending + transferred
                    total_required = flt(row.pending_qty) + total_trans
                    # Also update the total_required_qty field
                    try:
                        frappe.db.set_value("Work Order Transfer Items Table", row.name, "total_required_qty", total_required)
                    except Exception as e:
                        print(f"⚠️ WARNING: Could not update total_required_qty for row {row.name}: {e}")
                
                remaining = max(total_required - total_trans, 0)
                try:
                    frappe.db.set_value("Work Order Transfer Items Table", row.name, "pending_qty", remaining)
                except Exception as e:
                    print(f"⚠️ WARNING: Could not update pending_qty for row {row.name}: {e}")
                
                # Calculate and update item transfer status and percentage
                item_status, item_percentage = calculate_transfer_status_and_percentage(total_trans, total_required)
                try:
                    frappe.db.set_value("Work Order Transfer Items Table", row.name, "item_transfer_status", item_status)
                    frappe.db.set_value("Work Order Transfer Items Table", row.name, "item_transfer_percentage", item_percentage)
                except Exception as e:
                    print(f"⚠️ WARNING: Could not update status/percentage for row {row.name}: {e}")

                # Refresh stock snapshots
                if getattr(doc, 'source_warehouse', None):
                    try:
                        bin_qty = frappe.db.sql("""
                            SELECT actual_qty FROM `tabBin` WHERE item_code=%s AND warehouse=%s
                        """, (row.item_code, doc.source_warehouse), as_dict=True)
                        frappe.db.set_value(
                            "Work Order Transfer Items Table",
                            row.name,
                            "actual_qty_at_warehouse",
                            flt(bin_qty[0].actual_qty) if bin_qty else 0,
                        )
                    except Exception as e:
                        print(f"⚠️ WARNING: Could not update warehouse stock for row {row.name}: {e}")

                if getattr(doc, 'company', None):
                    try:
                        company_bins = frappe.db.sql("""
                            SELECT SUM(b.actual_qty) AS qty
                            FROM `tabBin` b
                            JOIN `tabWarehouse` w ON w.name = b.warehouse
                            WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                        """, (row.item_code, doc.company), as_dict=True)
                        frappe.db.set_value(
                            "Work Order Transfer Items Table",
                            row.name,
                            "actual_qty_at_company",
                            flt(company_bins[0].qty) if company_bins and company_bins[0].qty is not None else 0,
                        )
                    except Exception as e:
                        print(f"⚠️ WARNING: Could not update company stock for row {row.name}: {e}")
                        
            except Exception as row_error:
                print(f"❌ ERROR processing row for item {row.item_code}: {row_error}")
                continue

        # Calculate overall WOTM status and percentage
        overall_status, overall_percentage = calculate_overall_wotm_status(doc)
        frappe.db.set_value("Work Order Transfer Manager", doc.name, "transfer_status", overall_status)
        frappe.db.set_value("Work Order Transfer Manager", doc.name, "transfer_percentage", overall_percentage)

        print("🔍 DEBUG: Quantities updated on child rows (no parent save needed)")
        return {"success": True}

    except Exception as e:
        print(f"❌ DEBUG: Error updating transfer quantities: {e}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_existing_wotm_for_sales_order(sales_order):
    """Get existing WOTM for a sales order if it exists"""
    try:
        existing_wotm = frappe.db.exists("Work Order Transfer Manager", {"sales_order": sales_order})
        
        # If WOTM exists, ensure it has company set
        if existing_wotm:
            doc = frappe.get_doc("Work Order Transfer Manager", existing_wotm)
            if not doc.company:
                doc.company = frappe.defaults.get_global_default("company")
                doc.save()
                print(f"🔍 DEBUG: Set company in get_existing_wotm_for_sales_order: {doc.company}")
        if existing_wotm:
            return {
                "success": True,
                "exists": True,
                "wotm_name": existing_wotm
            }
        else:
            return {
                "success": True,
                "exists": False,
                "wotm_name": None
            }
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def fix_missing_company_fields():
    """Utility function to fix missing company fields in existing WOTM documents"""
    try:
        print(f"🔍 DEBUG: Starting fix_missing_company_fields")
        
        # Get all WOTM documents
        wotm_docs = frappe.get_all("Work Order Transfer Manager", fields=["name"])
        
        fixed_count = 0
        for wotm in wotm_docs:
            try:
                doc = frappe.get_doc("Work Order Transfer Manager", wotm.name)
                company = frappe.defaults.get_global_default("company")
                
                # Fix parent document company
                if not doc.company:
                    doc.company = company
                    print(f"🔍 DEBUG: Fixed company for parent document: {doc.name}")
                
                # Fix transfer items
                if doc.transfer_items:
                    for item in doc.transfer_items:
                        if not item.company:
                            item.company = company
                            print(f"🔍 DEBUG: Fixed company for transfer item {item.item_code} in {doc.name}")
                
                # Fix work order details
                if doc.work_order_details:
                    for item in doc.work_order_details:
                        if hasattr(item, "company") and not item.company:
                            item.company = company
                            print(f"🔍 DEBUG: Fixed company for work order detail {item.work_order} in {doc.name}")
                
                # Fix work order summary
                if doc.work_order_summary:
                    for item in doc.work_order_summary:
                        if hasattr(item, "company") and not item.company:
                            item.company = company
                            print(f"🔍 DEBUG: Fixed company for work order summary {item.item_code} in {doc.name}")
                
                # Save the document
                doc.save()
                fixed_count += 1
                print(f"🔍 DEBUG: Fixed document: {doc.name}")
                
            except Exception as doc_error:
                print(f"❌ DEBUG: Error fixing document {wotm.name}: {doc_error}")
                # Try direct database fix
                try:
                    company = frappe.defaults.get_global_default("company")
                    
                    # Fix transfer items directly
                    frappe.db.sql("""
                        UPDATE `tabWork Order Transfer Items Table`
                        SET company = %s
                        WHERE parent = %s AND (company IS NULL OR company = '')
                    """, (company, wotm.name))
                    
                    # Note: Work Order Details and Summary tables don't have company column
                    # Skip direct database updates for these tables
                    print(f"🔍 DEBUG: Skipping direct database updates for work order details/summary (no company column)")
                    
                    # Fix parent document
                    frappe.db.sql("""
                        UPDATE `tabWork Order Transfer Manager`
                        SET company = %s
                        WHERE name = %s AND (company IS NULL OR company = '')
                    """, (company, wotm.name))
                    
                    frappe.db.commit()
                    fixed_count += 1
                    print(f"🔍 DEBUG: Fixed document directly in database: {wotm.name}")
                    
                except Exception as db_error:
                    print(f"❌ DEBUG: Error fixing document in database {wotm.name}: {db_error}")
        
        print(f"🔍 DEBUG: Fixed {fixed_count} documents")
        return {"success": True, "message": f"Fixed {fixed_count} documents"}
        
    except Exception as e:
        print(f"❌ DEBUG: Error in fix_missing_company_fields: {e}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def populate_work_order_tables_background(sales_order, doc_name):
    print(f"🔍 DEBUG: Starting populate_work_order_tables_background for sales_order: {sales_order}, doc_name: {doc_name}")
    try:
        job = frappe.enqueue(
            "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.populate_work_order_tables_job",
            sales_order=sales_order,
            doc_name=doc_name,
            queue="long",
            timeout=1200,
            job_name=f"populate_work_order_tables_{doc_name}"
        )
        job_id = job.get_id() if job else None
        return {"success": True, "message": "Background job started.", "job_started": True, "job_id": job_id, "job_name": f"populate_work_order_tables_{doc_name}"}
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 60:
            error_msg = error_msg[:57] + "..."
        full_message = f"Error starting background job: {error_msg}"
        if len(full_message) > 140:
            full_message = f"Error starting background job: {error_msg[:50]}..."
        frappe.log_error(full_message)
        return {"success": False, "message": str(e)}


def populate_work_order_tables_job(sales_order, doc_name):
    print(f"🔍 DEBUG: Background job started for populate_work_order_tables: sales_order={sales_order}, doc_name={doc_name}")
    try:
        out = populate_work_order_tables(sales_order, doc_name)
        print(f"🔍 DEBUG: Background job result for populate_work_order_tables: {out}")
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 60:
            error_msg = error_msg[:57] + "..."
        full_message = f"Error in populate_work_order_tables background job: {error_msg}"
        if len(full_message) > 140:
            full_message = f"Error in populate background job: {error_msg[:50]}..."
        frappe.log_error(full_message)

@frappe.whitelist()
def get_background_job_status(job_id: str = None, job_name: str = None):
    """Return status for a background job by job_id or job_name."""
    try:
        conn = get_redis_conn()
        job = None
        if job_id:
            job = Job.fetch(job_id, connection=conn)
        elif job_name:
            # Try to resolve job by name from RQ Job doctype
            jq = frappe.get_all("RQ Job", filters={"job_name": job_name}, fields=["name", "job_id", "status"], order_by="creation desc", limit=1)
            if jq:
                job = Job.fetch(jq[0].job_id, connection=conn)
        if not job:
            return {"success": False, "message": "Job not found"}
        return {
            "success": True,
            "status": job.get_status(),
            "is_finished": job.is_finished,
            "is_failed": job.is_failed,
            "enqueued_at": str(getattr(job, "enqueued_at", None)),
            "ended_at": str(getattr(job, "ended_at", None)),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def cancel_background_job(job_id: str):
    """Attempt to cancel a running/enqueued RQ job"""
    try:
        conn = get_redis_conn()
        job = Job.fetch(job_id, connection=conn)
        # Ask workers to stop this job if running
        send_stop_job_command(conn, job_id)
        # Also mark as canceled if possible
        try:
            job.cancel()
        except Exception:
            pass
        return {"success": True, "message": "Cancellation signal sent."}
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_wotm_dashboard_data(doc_name):
    """Get dashboard data for Work Order Transfer Manager"""
    print(f"🔍 DEBUG: get_wotm_dashboard_data called with doc_name: {doc_name}")
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        print(f"🔍 DEBUG: Successfully loaded WOTM document: {doc.name}")
        
        # Get customer name
        customer_name = ""
        if doc.customer:
            customer_name = frappe.db.get_value("Customer", doc.customer, "customer_name") or doc.customer
            print(f"🔍 DEBUG: Customer name: {customer_name}")
        
        # Calculate totals from work order summary
        total_work_orders = len(doc.work_order_details) if doc.work_order_details else 0
        total_transferred = 0
        total_pending = 0
        completed_work_orders = 0
        
        print(f"🔍 DEBUG: Total work orders: {total_work_orders}")
        print(f"🔍 DEBUG: Work order summary count: {len(doc.work_order_summary) if doc.work_order_summary else 0}")
        print(f"🔍 DEBUG: Transfer items count: {len(doc.transfer_items) if doc.transfer_items else 0}")
        
        work_order_summary_data = []
        if doc.work_order_summary:
            for item in doc.work_order_summary:
                total_transferred += flt(item.total_transferred_qty or 0)
                total_pending += flt(item.total_pending_qty or 0)
                
                # Calculate progress percentage
                total_ordered = flt(item.total_ordered_qty or 0)
                progress_percentage = 0
                if total_ordered > 0:
                    progress_percentage = (flt(item.total_transferred_qty or 0) / total_ordered) * 100
                
                work_order_summary_data.append({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "total_ordered_qty": total_ordered,
                    "total_transferred_qty": flt(item.total_transferred_qty or 0),
                    "total_pending_qty": flt(item.total_pending_qty or 0),
                    "progress_percentage": round(progress_percentage, 1)
                })
        
        # Count completed work orders
        if doc.work_order_details:
            for item in doc.work_order_details:
                # Work Order Details Table does not have transferred_qty; use pending_qty to infer completion
                if flt(getattr(item, "pending_qty", 0) or 0) <= 0:
                    completed_work_orders += 1
        
        # Calculate work order progress percentage
        work_order_progress_percentage = 0
        if total_work_orders > 0:
            work_order_progress_percentage = (completed_work_orders / total_work_orders) * 100
        
        # Get raw materials data
        raw_materials_data = []
        total_raw_materials = 0
        if doc.transfer_items:
            total_raw_materials = len(doc.transfer_items)
            for item in doc.transfer_items:
                raw_materials_data.append({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "total_required_qty": flt(item.total_required_qty or 0),
                    "transferred_qty_so_far": flt(item.transferred_qty_so_far or 0),
                    "pending_qty": flt(item.pending_qty or 0),
                    "item_transfer_status": item.item_transfer_status or "Pending",
                    "item_transfer_percentage": flt(item.item_transfer_percentage or 0)
                })
        
        # Calculate overall transfer percentage
        overall_transfer_percentage = flt(doc.transfer_percentage or 0)
        
        # Determine status info
        status_info = {
            "status": doc.transfer_status or "Pending",
            "message": "Transfer in progress",
            "status_color": "#d32f2f"  # Default red
        }
        
        if doc.transfer_status == "Completed":
            status_info["message"] = "All transfers completed"
            status_info["status_color"] = "#2e7d32"  # Green
        elif doc.transfer_status == "In Progress":
            status_info["message"] = f"Transfer {overall_transfer_percentage:.1f}% complete"
            status_info["status_color"] = "#f57c00"  # Orange
        else:
            status_info["message"] = "No transfers started"
            status_info["status_color"] = "#d32f2f"  # Red
        
        result_data = {
            "wotm_name": doc.name,
            "customer": doc.customer,
            "customer_name": customer_name,
            "sales_order": doc.sales_order,
            "posting_date": doc.posting_date,
            "total_work_orders": total_work_orders,
            "total_transferred": total_transferred,
            "total_pending": total_pending,
            "total_raw_materials": total_raw_materials,
            "completed_work_orders": completed_work_orders,
            "overall_transfer_percentage": round(overall_transfer_percentage, 1),
            "work_order_progress_percentage": round(work_order_progress_percentage, 1),
            "status_info": status_info,
            "work_order_summary": work_order_summary_data,
            "raw_materials": raw_materials_data
        }
        
        print(f"🔍 DEBUG: Returning dashboard data: {result_data}")
        return result_data
        
    except Exception as e:
        print(f"❌ DEBUG: Error in get_wotm_dashboard_data: {str(e)}")
        import traceback
        print(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")
        frappe.log_error(f"Error getting WOTM dashboard data: {str(e)}")
        return None

@frappe.whitelist()
def get_stock_snapshots_only(doc_name):
    """
    Get stock snapshots for WOTM items without modifying the document.
    This is a read-only method to prevent timestamp mismatch errors.
    """
    try:
        doc = frappe.get_doc("Work Order Transfer Manager", doc_name)
        stock_data = []
        
        if doc.transfer_items and doc.source_warehouse:
            for item in doc.transfer_items:
                # Get warehouse stock
                warehouse_qty = 0
                if doc.source_warehouse:
                    bin_qty = frappe.db.sql("""
                        SELECT actual_qty FROM `tabBin`
                        WHERE item_code = %s AND warehouse = %s
                    """, (item.item_code, doc.source_warehouse), as_dict=True)
                    warehouse_qty = flt(bin_qty[0].actual_qty) if bin_qty else 0

                # Get company stock
                company_qty = 0
                if doc.company:
                    company_bins = frappe.db.sql("""
                        SELECT SUM(b.actual_qty) AS qty
                        FROM `tabBin` b
                        JOIN `tabWarehouse` w ON w.name = b.warehouse
                        WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                    """, (item.item_code, doc.company), as_dict=True)
                    company_qty = flt(company_bins[0].qty) if company_bins and company_bins[0].qty is not None else 0

                stock_data.append({
                    "item_code": item.item_code,
                    "actual_qty_at_warehouse": warehouse_qty,
                    "actual_qty_at_company": company_qty
                })
        
        return {
            "success": True,
            "stock_data": stock_data
        }
        
    except Exception as e:
        print(f"❌ DEBUG: Error getting stock snapshots: {e}")
        return {"success": False, "message": str(e)}

def update_transfer_quantities_submitted(doc_name, transfer_doc_name=None):
    """
    Update transfer quantities for submitted WOTM documents using direct database queries.
    This avoids issues with child table access in submitted documents.
    """
    print(f"🔍 DEBUG: Starting update_transfer_quantities_submitted for doc_name: {doc_name}")
    try:
        # Get document info
        doc_info = frappe.db.get_value("Work Order Transfer Manager", doc_name, 
                                      ["company", "source_warehouse", "docstatus"], as_dict=True)
        
        if not doc_info:
            print(f"❌ ERROR: Document {doc_name} not found")
            return {"success": False, "message": "Document not found"}
        
        # Ensure company is set
        if not doc_info.company:
            company = frappe.defaults.get_global_default("company")
            frappe.db.set_value("Work Order Transfer Manager", doc_name, "company", company)
            doc_info.company = company
            print(f"🔍 DEBUG: Set company in update_transfer_quantities_submitted: {company}")

        # Aggregate transfers from all SUBMITTED Raw Material Transfers
        item_total_transferred = {}
        existing_transfers = frappe.get_all(
            "Raw Material Transfer",
            filters={"work_order_transfer_manager": doc_name, "docstatus": 1},
            fields=["name"],
        )
        
        for tr in existing_transfers:
            tr_doc = frappe.get_doc("Raw Material Transfer", tr.name)
            for ti in tr_doc.raw_materials:
                item_total_transferred[ti.item_code] = item_total_transferred.get(ti.item_code, 0) + flt(ti.transfer_qty)

        # Get all transfer items from database
        transfer_items = frappe.db.get_all(
            "Work Order Transfer Items Table",
            filters={"parent": doc_name},
            fields=["name", "item_code", "total_required_qty", "pending_qty", "transferred_qty_so_far"]
        )
        
        print(f"🔍 DEBUG: Found {len(transfer_items)} transfer items to update")
        
        if not transfer_items:
            print(f"⚠️ WARNING: No transfer items found for document {doc_name}")
            return {"success": False, "message": "No transfer items found"}
        
        # Update each transfer item
        for item in transfer_items:
            try:
                # Verify the item still exists in the database
                if not frappe.db.exists("Work Order Transfer Items Table", item.name):
                    print(f"⚠️ WARNING: Transfer item {item.name} for {item.item_code} no longer exists, skipping...")
                    continue
                    
                total_trans = flt(item_total_transferred.get(item.item_code, 0))
                
                # Use total_required_qty to compute remaining; if missing, infer (backward compatible)
                total_required = flt(item.total_required_qty or 0)
                if not total_required:
                    # If total_required_qty is not set, calculate it from pending + transferred
                    total_required = flt(item.pending_qty or 0) + total_trans
                    # Also update the total_required_qty field
                    frappe.db.set_value("Work Order Transfer Items Table", item.name, "total_required_qty", total_required)
                
                remaining = max(total_required - total_trans, 0)
                
                # Calculate item transfer status and percentage
                item_status, item_percentage = calculate_transfer_status_and_percentage(total_trans, total_required)
                
                # Update all fields at once
                update_data = {
                    "transferred_qty_so_far": total_trans,
                    "transfer_qty": total_trans,
                    "pending_qty": remaining,
                    "item_transfer_status": item_status,
                    "item_transfer_percentage": item_percentage,
                    "company": doc_info.company
                }
                
                # Update warehouse stock if source_warehouse is set
                if doc_info.source_warehouse:
                    bin_qty = frappe.db.sql("""
                        SELECT actual_qty FROM `tabBin` WHERE item_code=%s AND warehouse=%s
                    """, (item.item_code, doc_info.source_warehouse), as_dict=True)
                    update_data["actual_qty_at_warehouse"] = flt(bin_qty[0].actual_qty) if bin_qty else 0

                # Update company stock
                if doc_info.company:
                    company_bins = frappe.db.sql("""
                        SELECT SUM(b.actual_qty) AS qty
                        FROM `tabBin` b
                        JOIN `tabWarehouse` w ON w.name = b.warehouse
                        WHERE b.item_code = %s AND w.company = %s AND w.is_group = 0
                    """, (item.item_code, doc_info.company), as_dict=True)
                    update_data["actual_qty_at_company"] = flt(company_bins[0].qty) if company_bins and company_bins[0].qty is not None else 0
                
                # Update the record
                frappe.db.set_value("Work Order Transfer Items Table", item.name, update_data)
                
            except Exception as item_error:
                print(f"❌ ERROR processing item {item.item_code}: {item_error}")
                continue

        # Calculate overall WOTM status and percentage
        # Get updated data for calculation
        updated_items = frappe.db.get_all(
            "Work Order Transfer Items Table",
            filters={"parent": doc_name},
            fields=["total_required_qty", "transferred_qty_so_far", "pending_qty"]
        )
        
        total_required = sum(flt(item.total_required_qty or 0) for item in updated_items)
        total_transferred = sum(flt(item.transferred_qty_so_far or 0) for item in updated_items)
        
        overall_status, overall_percentage = calculate_overall_wotm_status_from_data(total_required, total_transferred)
        
        frappe.db.set_value("Work Order Transfer Manager", doc_name, {
            "transfer_status": overall_status,
            "transfer_percentage": overall_percentage
        })

        print("🔍 DEBUG: Quantities updated successfully for submitted document")
        return {"success": True}

    except Exception as e:
        print(f"❌ DEBUG: Error updating transfer quantities for submitted document: {e}")
        return {"success": False, "message": str(e)}


def calculate_overall_wotm_status_from_data(total_required, total_transferred):
    """
    Calculate overall WOTM status and percentage from raw data.
    """
    if total_required == 0:
        return "Pending", 0
    
    percentage = (total_transferred / total_required) * 100
    
    if percentage >= 100:
        return "Completed", 100
    elif percentage > 0:
        return "In Progress", percentage
    else:
        return "Pending", 0

@frappe.whitelist()
def create_from_production_plan(pp_name: str, sales_order: str, source_warehouse: str | None = None, target_warehouse: str | None = None, posting_date: str | None = None, company: str | None = None):
    """Create a Work Order Transfer Manager from a Production Plan and a selected Sales Order.
    Returns { success: bool, doc_name?: str, message?: str }
    """
    try:
        if not sales_order:
            return {"success": False, "message": "Sales Order is required"}

        # Resolve company and posting date
        if not company and pp_name:
            try:
                pp = frappe.get_doc("Production Plan", pp_name)
                company = company or getattr(pp, "company", None)
                posting_date = posting_date or str(getattr(pp, "posting_date", ""))
            except Exception:
                pass

        company = company or frappe.defaults.get_global_default("company")
        posting_date = posting_date or str(frappe.utils.today())

        # Create the WOTM doc
        doc = frappe.new_doc("Work Order Transfer Manager")
        doc.company = company
        doc.posting_date = posting_date
        doc.sales_order = sales_order
        # Fetch and set customer from Sales Order (required)
        try:
            doc.customer = frappe.db.get_value("Sales Order", sales_order, "customer")
        except Exception:
            doc.customer = None
        # Set defaults for required fields
        doc.stock_entry_type = "Material Transfer for Manufacture"

        # Set warehouses if provided; otherwise pick the first two real warehouses from the company
        if source_warehouse:
            doc.source_warehouse = source_warehouse
        if target_warehouse:
            doc.target_warehouse = target_warehouse

        if not getattr(doc, "source_warehouse", None) or not getattr(doc, "target_warehouse", None):
            if company:
                warehouses = frappe.db.sql(
                    """
                    SELECT name FROM `tabWarehouse`
                    WHERE company = %s AND is_group = 0
                    ORDER BY name ASC LIMIT 2
                    """,
                    (company,),
                    as_dict=True,
                )
                if warehouses:
                    doc.source_warehouse = doc.source_warehouse or warehouses[0].name
                    if len(warehouses) > 1:
                        doc.target_warehouse = doc.target_warehouse or warehouses[1].name
                    else:
                        doc.target_warehouse = doc.target_warehouse or warehouses[0].name

        doc.insert(ignore_permissions=True)

        # Populate tables for the selected Sales Order BEFORE submit
        out = populate_work_order_tables(sales_order, doc.name)
        if isinstance(out, dict) and not out.get("success", True):
            # Keep as draft so user can review/fix
            return {"success": False, "message": out.get("message", "Populate failed"), "doc_name": doc.name}

        # Reload to ensure child tables are attached
        try:
            doc = frappe.get_doc("Work Order Transfer Manager", doc.name)
        except Exception:
            pass

        # If nothing populated, keep as draft and inform
        has_rows = bool(getattr(doc, "transfer_items", None)) or bool(getattr(doc, "work_order_details", None))
        if not has_rows:
            return {"success": True, "doc_name": doc.name, "message": "Created as Draft. No work orders/raw materials found to populate."}

        # Submit after successful populate
        doc.flags.ignore_permissions = True
        doc.submit()

        return {"success": True, "doc_name": doc.name}

    except Exception as e:
        frappe.log_error(f"Error creating WOTM from Production Plan {pp_name}: {str(e)}")
        return {"success": False, "message": str(e)}
