import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate, nowtime
import json

class BulkWorkOrderManager(Document):
    def validate(self):
        self.validate_sales_order()
        self.calculate_totals()
    
    def before_save(self):
        # Only calculate totals, don't auto-fetch work orders
        self.calculate_totals()
    
    def validate_sales_order(self):
        if self.sales_order:
            so_doc = frappe.get_doc("Sales Order", self.sales_order)
            self.customer = so_doc.customer
    

    
    def update_summary(self):
        """Update work order summary by aggregating data by item"""
        if not self.work_order_details:
            return
        
        # Group by item_code
        item_summary = {}
        for row in self.work_order_details:
            item_code = row.item_code
            if item_code not in item_summary:
                item_summary[item_code] = {
                    "item_code": item_code,
                    "item_name": row.item_name,
                    "total_ordered_qty": 0,
                    "total_delivered_qty": 0,
                    "total_pending_qty": 0,
                    "work_order_count": 0
                }
            
            item_summary[item_code]["total_ordered_qty"] += flt(row.ordered_qty)
            item_summary[item_code]["total_delivered_qty"] += flt(row.delivered_qty)
            item_summary[item_code]["total_pending_qty"] += flt(row.pending_qty)
            item_summary[item_code]["work_order_count"] += 1
        
        # Clear and populate summary
        self.work_order_summary = []
        for item_code, summary in item_summary.items():
            self.append("work_order_summary", {
                "item_code": item_code,
                "item_name": summary["item_name"],
                "total_ordered_qty": summary["total_ordered_qty"],
                "total_delivered_qty": summary["total_delivered_qty"],
                "total_pending_qty": summary["total_pending_qty"],
                "work_order_count": summary["work_order_count"],
                "status": self.get_delivery_status(summary["total_delivered_qty"], summary["total_ordered_qty"])
            })
        
        # Populate bulk delivery items
        self.populate_bulk_delivery_items()
    
    def populate_bulk_delivery_items(self):
        """Populate bulk delivery items table with pending items"""
        self.bulk_delivery_items = []
        
        for summary in self.work_order_summary:
            if flt(summary.total_pending_qty) > 0:
                # Get UOM from item
                uom = frappe.db.get_value("Item", summary.item_code, "stock_uom")
                
                self.append("bulk_delivery_items", {
                    "item_code": summary.item_code,
                    "item_name": summary.item_name,
                    "total_pending_qty": summary.total_pending_qty,
                    "delivery_qty": 0,  # User will enter this
                    "uom": uom,
                    "warehouse": ""  # User will select
                })
    
    def calculate_totals(self):
        """Calculate totals for the document"""
        total_ordered = 0
        total_delivered = 0
        total_pending = 0
        
        for summary in self.work_order_summary:
            total_ordered += flt(summary.total_ordered_qty)
            total_delivered += flt(summary.total_delivered_qty)
            total_pending += flt(summary.total_pending_qty)
        
        self.total_ordered_qty = total_ordered
        self.total_delivered_qty = total_delivered
        self.total_pending_qty = total_pending
    
    def get_delivery_status(self, delivered_qty, ordered_qty):
        """Get delivery status based on delivered vs ordered quantity"""
        if flt(delivered_qty) == 0:
            return "Pending"
        elif flt(delivered_qty) >= flt(ordered_qty):
            return "Fully Delivered"
        else:
            return "Partially Delivered"
    
    def on_submit(self):
        """Process bulk delivery when document is submitted"""
        self.process_bulk_delivery()
    
    def process_bulk_delivery(self):
        """Process the bulk delivery by creating stock entries and updating work orders"""
        if not self.bulk_delivery_items:
            frappe.throw(_("No delivery items to process"))
        
        # Validate delivery quantities
        self.validate_delivery_quantities()
        
        # Create stock entry
        stock_entry = self.create_stock_entry()
        
        # Update work orders with delivered quantities
        self.update_work_orders(stock_entry.name)
        
        frappe.msgprint(_("Bulk delivery processed successfully. Stock Entry: {0}").format(
            frappe.get_desk_link("Stock Entry", stock_entry.name)
        ))
    
    def validate_delivery_quantities(self):
        """Validate that delivery quantities don't exceed pending quantities"""
        for item in self.bulk_delivery_items:
            if flt(item.delivery_qty) > flt(item.total_pending_qty):
                frappe.throw(_("Delivery quantity for {0} ({1}) cannot exceed pending quantity ({2})").format(
                    item.item_code, item.delivery_qty, item.total_pending_qty
                ))
            
            if flt(item.delivery_qty) <= 0:
                frappe.throw(_("Delivery quantity for {0} must be greater than 0").format(item.item_code))
            
            if not item.warehouse:
                frappe.throw(_("Warehouse is required for {0}").format(item.item_code))
    
    def create_stock_entry(self):
        """Create a stock entry for the bulk delivery"""
        # Determine stock entry type based on the process
        # If we're delivering finished goods, use "Manufacture"
        # If we're transferring materials, use "Material Transfer for Manufacture"
        
        stock_entry_type = self.determine_stock_entry_type()
        
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = stock_entry_type
        stock_entry.posting_date = self.posting_date
        stock_entry.posting_time = self.posting_time
        stock_entry.reference_doctype = "Bulk Work Order Manager"
        stock_entry.reference_document = self.name
        
        # Add items to stock entry based on type
        if stock_entry_type == "Material Transfer for Manufacture":
            self.add_items_for_material_transfer(stock_entry)
        else:  # Manufacture
            self.add_items_for_manufacture(stock_entry)
        
        stock_entry.save()
        stock_entry.submit()
        
        return stock_entry
    
    def determine_stock_entry_type(self):
        """Determine the appropriate stock entry type based on the process"""
        # If auto-detect is enabled, determine based on item BOM
        if self.auto_detect_type:
            for item in self.bulk_delivery_items:
                if flt(item.delivery_qty) > 0:
                    # Check if this is a finished good (has BOM)
                    bom_exists = frappe.db.exists("BOM", {
                        "item": item.item_code,
                        "is_active": 1,
                        "is_default": 1
                    })
                    
                    if bom_exists:
                        # This is a finished good, so use "Manufacture"
                        return "Manufacture"
            
            # Default to "Material Transfer for Manufacture" for raw materials
            return "Material Transfer for Manufacture"
        else:
            # Use user-selected stock entry type
            return self.stock_entry_type or "Material Transfer for Manufacture"
    
    def add_items_for_material_transfer(self, stock_entry):
        """Add items for Material Transfer for Manufacture stock entry"""
        for item in self.bulk_delivery_items:
            if flt(item.delivery_qty) > 0:
                stock_entry.append("items", {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "qty": item.delivery_qty,
                    "uom": item.uom,
                    "s_warehouse": item.warehouse,  # Source warehouse
                    "t_warehouse": "",  # Target warehouse (will be set by work order)
                    "is_finished_item": 0  # Raw material
                })
        
        stock_entry.save()
        stock_entry.submit()
        
        return stock_entry
    
    def update_work_orders(self, stock_entry_name):
        """Update work orders with delivered quantities using smart allocation"""
        # Create a map of item_code -> delivery_qty
        delivery_map = {}
        for item in self.bulk_delivery_items:
            if flt(item.delivery_qty) > 0:
                delivery_map[item.item_code] = flt(item.delivery_qty)
        
        # Update work orders with smart allocation
        for item_code, total_delivery_qty in delivery_map.items():
            self.allocate_delivery_to_work_orders(item_code, total_delivery_qty, stock_entry_name)
    
    def allocate_delivery_to_work_orders(self, item_code, total_delivery_qty, stock_entry_name):
        """Smart allocation of delivery quantity to work orders"""
        # Get work orders for this item that have pending quantities
        work_orders = frappe.get_all(
            "Work Order",
            filters={
                "sales_order": self.sales_order,
                "item_code": item_code,
                "docstatus": 1
            },
            fields=["name", "qty", "produced_qty"],
            order_by="creation_date"  # First created work orders get priority
        )
        
        remaining_delivery_qty = total_delivery_qty
        
        for wo in work_orders:
            if remaining_delivery_qty <= 0:
                break
            
            pending_qty = flt(wo.qty) - flt(wo.produced_qty)
            if pending_qty <= 0:
                continue
            
            # Allocate delivery quantity to this work order
            allocation_qty = min(remaining_delivery_qty, pending_qty)
            
            # Update work order produced quantity
            new_produced_qty = flt(wo.produced_qty) + allocation_qty
            frappe.db.set_value("Work Order", wo.name, "produced_qty", new_produced_qty)
            
            # Create stock entry for the allocation
            self.create_stock_entry_for_allocation(wo.name, item_code, allocation_qty, stock_entry_name)
            
            remaining_delivery_qty -= allocation_qty
        
        if remaining_delivery_qty > 0:
            frappe.msgprint(_("Warning: {0} units of {1} could not be allocated to work orders").format(
                remaining_delivery_qty, item_code
            ), indicator="orange")
    
    def create_stock_entry_for_allocation(self, work_order_name, item_code, qty, stock_entry_name):
        """Create stock entry to record the allocation to work order"""
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Manufacture"
        stock_entry.posting_date = self.posting_date
        stock_entry.posting_time = self.posting_time
        stock_entry.work_order = work_order_name
        stock_entry.reference_doctype = "Stock Entry"
        stock_entry.reference_document = stock_entry_name
        
        # Add the item
        stock_entry.append("items", {
            "item_code": item_code,
            "qty": qty,
            "s_warehouse": "",  # Will be set by system
            "t_warehouse": "",  # Will be set by system
            "is_finished_item": 1
        })
        
        stock_entry.save()
        stock_entry.submit()


@frappe.whitelist()
def get_work_order_summary(sales_order):
    """Get work order summary for a sales order"""
    if not sales_order:
        return {}
    
    # Get all work orders for the sales order
    work_orders = frappe.get_all(
        "Work Order",
        filters={
            "sales_order": sales_order,
            "docstatus": 1
        },
        fields=["name", "item_code", "item_name", "qty", "produced_qty", "status"]
    )
    
    # Group by item
    item_summary = {}
    for wo in work_orders:
        item_code = wo.item_code
        if item_code not in item_summary:
            item_summary[item_code] = {
                "item_code": item_code,
                "item_name": wo.item_name,
                "total_ordered_qty": 0,
                "total_delivered_qty": 0,
                "total_pending_qty": 0,
                "work_order_count": 0,
                "work_orders": []
            }
        
        delivered_qty = flt(wo.produced_qty)
        pending_qty = flt(wo.qty) - delivered_qty
        
        item_summary[item_code]["total_ordered_qty"] += flt(wo.qty)
        item_summary[item_code]["total_delivered_qty"] += delivered_qty
        item_summary[item_code]["total_pending_qty"] += pending_qty
        item_summary[item_code]["work_order_count"] += 1
        item_summary[item_code]["work_orders"].append({
            "name": wo.name,
            "ordered_qty": wo.qty,
            "delivered_qty": delivered_qty,
            "pending_qty": pending_qty,
            "status": wo.status
        })
    
    return {
        "summary": list(item_summary.values()),
        "total_work_orders": len(work_orders)
    }


@frappe.whitelist()
def get_work_orders_for_sales_order(sales_order):
    """Get work orders for a sales order"""
    print(f"🔍 DEBUG: Starting get_work_orders_for_sales_order for sales_order: {sales_order}")
    try:
        # Quick check if work orders exist
        print(f"🔍 DEBUG: Checking if work orders exist...")
        count = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabWork Order` 
            WHERE sales_order = %s AND docstatus = 1
        """, (sales_order,), as_dict=True)[0]['count']
        
        print(f"🔍 DEBUG: Found {count} work orders")
        
        if count == 0:
            print(f"🔍 DEBUG: No work orders found, returning empty list")
            return []
        
        # Use direct SQL for better performance
        print(f"🔍 DEBUG: Fetching work order details...")
        work_orders = frappe.db.sql("""
            SELECT 
                name, 
                production_item, 
                item_name, 
                qty, 
                produced_qty, 
                status
            FROM `tabWork Order` 
            WHERE sales_order = %s AND docstatus = 1
            ORDER BY creation DESC
        """, (sales_order,), as_dict=True)
        
        print(f"🔍 DEBUG: Retrieved {len(work_orders)} work orders:")
        for wo in work_orders:
            print(f"  - {wo['name']}: {wo['production_item']} ({wo['qty']} qty, {wo['produced_qty']} produced)")
        
        return work_orders
    except Exception as e:
        print(f"❌ DEBUG: Error in get_work_orders_for_sales_order: {str(e)}")
        
        # Create a much shorter error message to fit in Error Log title field (max 140 chars)
        error_msg = str(e)
        if len(error_msg) > 60:  # Be more conservative to ensure it fits
            error_msg = error_msg[:57] + "..."
        
        # Ensure the total message doesn't exceed 140 chars
        full_message = f"Error fetching work orders for sales order {sales_order}: {error_msg}"
        if len(full_message) > 140:
            # If still too long, truncate the sales order name too
            sales_order_short = sales_order[:20] + "..." if len(sales_order) > 23 else sales_order
            full_message = f"Error fetching work orders for sales order {sales_order_short}: {error_msg}"
            if len(full_message) > 140:
                # Final fallback - very short message
                full_message = f"Error fetching work orders: {error_msg[:50]}..."
        
        frappe.log_error(full_message)
        frappe.throw(f"Error fetching work orders: {str(e)}")


@frappe.whitelist()
def create_bulk_work_order_manager(sales_order):
    """Create a new bulk work order manager for a sales order"""
    if not sales_order:
        frappe.throw(_("Sales Order is required"))
    
    # Check if one already exists
    existing = frappe.get_all(
        "Bulk Work Order Manager",
        filters={"sales_order": sales_order, "docstatus": 0},
        limit=1
    )
    
    if existing:
        frappe.throw(_("A draft Bulk Work Order Manager already exists for this Sales Order"))
    
    # Create new document
    doc = frappe.new_doc("Bulk Work Order Manager")
    doc.sales_order = sales_order
    doc.posting_date = nowdate()
    doc.posting_time = nowtime()
    
    # Fetch work orders
    doc.fetch_work_orders()
    
    doc.save()
    
    return doc.name


@frappe.whitelist()
def get_live_status(sales_order):
    """Get live status of work orders for a sales order"""
    if not sales_order:
        return {}
    
    # Get current status
    summary = get_work_order_summary(sales_order)
    
    # Calculate totals
    total_ordered = sum(item["total_ordered_qty"] for item in summary["summary"])
    total_delivered = sum(item["total_delivered_qty"] for item in summary["summary"])
    total_pending = sum(item["total_pending_qty"] for item in summary["summary"])
    
    return {
        "summary": summary["summary"],
        "totals": {
            "ordered": total_ordered,
            "delivered": total_delivered,
            "pending": total_pending,
            "completion_percentage": (total_delivered / total_ordered * 100) if total_ordered > 0 else 0
        },
        "work_order_count": summary["total_work_orders"]
    } 

@frappe.whitelist()
def populate_work_order_tables(sales_order, doc_name):
    """Populate work order tables directly on server"""
    print(f"🔍 DEBUG: Starting populate_work_order_tables for sales_order: {sales_order}, doc_name: {doc_name}")
    try:
        # Check if document exists, if not create a new one
        if not frappe.db.exists("Bulk Work Order Manager", doc_name):
            print(f"🔍 DEBUG: Document {doc_name} not found, creating new document")
            doc = frappe.new_doc("Bulk Work Order Manager")
            doc.sales_order = sales_order
            doc.posting_date = frappe.utils.today()
            doc.posting_time = frappe.utils.nowtime()
            
            # Set default warehouse from company settings
            company = getattr(doc, 'company', None) or frappe.defaults.get_global_default("company")
            if company:
                default_warehouse = frappe.db.get_value("Company", company, "default_warehouse")
                if default_warehouse:
                    doc.warehouse = default_warehouse
            
            doc.insert()
            print(f"🔍 DEBUG: Created new document with name: {doc.name}")
        else:
            print(f"🔍 DEBUG: Found existing document: {doc_name}")
            doc = frappe.get_doc("Bulk Work Order Manager", doc_name)
        
        # Clear existing data
        doc.work_order_details = []
        doc.work_order_summary = []
        doc.bulk_delivery_items = []
        
        print(f"🔍 DEBUG: Cleared existing tables")
        
        # Get work orders
        work_orders = frappe.db.sql("""
            SELECT 
                name, 
                production_item, 
                item_name, 
                qty, 
                produced_qty, 
                status
            FROM `tabWork Order` 
            WHERE sales_order = %s AND docstatus = 1
            ORDER BY creation DESC
        """, (sales_order,), as_dict=True)
        
        print(f"🔍 DEBUG: Retrieved {len(work_orders)} work orders")
        
        # Group work orders by item
        item_summary = {}
        
        for wo in work_orders:
            if wo.production_item not in item_summary:
                item_summary[wo.production_item] = {
                    "item_code": wo.production_item,
                    "item_name": wo.item_name,
                    "total_ordered_qty": 0,
                    "total_delivered_qty": 0,
                    "total_pending_qty": 0,
                    "work_orders": []
                }
            
            ordered_qty = flt(wo.qty)
            delivered_qty = flt(wo.produced_qty)
            pending_qty = ordered_qty - delivered_qty
            
            item_summary[wo.production_item]["total_ordered_qty"] += ordered_qty
            item_summary[wo.production_item]["total_delivered_qty"] += delivered_qty
            item_summary[wo.production_item]["total_pending_qty"] += pending_qty
            item_summary[wo.production_item]["work_orders"].append(wo)
            
            # Add to work order details
            doc.append("work_order_details", {
                "work_order": wo.name,
                "item_code": wo.production_item,
                "item_name": wo.item_name,
                "ordered_qty": ordered_qty,
                "delivered_qty": delivered_qty,
                "pending_qty": pending_qty,
                "work_order_status": wo.status
            })
        
        print(f"🔍 DEBUG: Processed {len(item_summary)} unique items")
        
        # Add to work order summary
        for item_code, summary in item_summary.items():
            doc.append("work_order_summary", {
                "item_code": summary["item_code"],
                "item_name": summary["item_name"],
                "total_ordered_qty": summary["total_ordered_qty"],
                "total_delivered_qty": summary["total_delivered_qty"],
                "total_pending_qty": summary["total_pending_qty"],
                "work_order_count": len(summary["work_orders"]),
                "status": get_delivery_status(summary["total_delivered_qty"], summary["total_ordered_qty"])
            })
            
            # Add to bulk delivery items if there's pending quantity
            if summary["total_pending_qty"] > 0:
                doc.append("bulk_delivery_items", {
                    "item_code": summary["item_code"],
                    "item_name": summary["item_name"],
                    "total_pending_qty": summary["total_pending_qty"],
                    "delivery_qty": 0,
                    "uom": "Nos",
                    "warehouse": doc.warehouse or ""
                })
        
        # Save the document
        doc.save()
        
        print(f"🔍 DEBUG: Document saved successfully with {len(doc.work_order_details)} details, {len(doc.work_order_summary)} summary, {len(doc.bulk_delivery_items)} delivery items")
        
        return {
            "success": True,
            "message": f"Populated {len(doc.work_order_details)} work order details, {len(doc.work_order_summary)} summary items, {len(doc.bulk_delivery_items)} delivery items",
            "doc_name": doc.name
        }
        
    except Exception as e:
        print(f"❌ DEBUG: Error in populate_work_order_tables: {str(e)}")
        
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

def get_delivery_status(delivered_qty, ordered_qty):
    delivered_qty = flt(delivered_qty)
    ordered_qty = flt(ordered_qty)
    
    if delivered_qty == 0:
        return "Pending"
    elif delivered_qty >= ordered_qty:
        return "Fully Delivered"
    else:
        return "Partially Delivered" 