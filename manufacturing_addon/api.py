
import frappe
from frappe import _
import json

@frappe.whitelist() 
def create_order_sheet(sales_order): 
    """Creates an Order Sheet for a given Sales Order and adds items to child table""" 
    try:
        # Fetch the Sales Order document
        so_doc = frappe.get_doc("Sales Order", sales_order)

        # Create the Order Sheet document
        order_sheet = frappe.get_doc({
            "doctype": "Order Sheet",
            # "customer": "test",  # FIXED: Removed quotes
            # "shipment_date": so_doc.delivery_date,  # FIXED: Removed quotes
            
            "sales_order": so_doc.name,  # Store Sales Order name
            "order_no":so_doc.name,
            "order_sheet_ct": []  # Initialize child table
        })

        # Loop through Sales Order Items and add them to Order Sheet Child Table
        for item in so_doc.items:
            # Fetch Item Document to check custom_is_product_combo
            item_doc = frappe.get_doc("Item", item.item_code)

            if item_doc.custom_is_product_combo == 1:
                # If item is a product combo, get items from child table
                for combo_item in item_doc.custom_product_combo_item:
                    order_sheet.append("order_sheet_ct", {
                        "so_item": item.item_code,
                        "combo_item": combo_item.item,  # Store combo item in child table
                        "quantity": item.qty * combo_item.pcs,  # Multiply with parent item quantity
                        "product_combo": 1  # Mark as part of a product combo
                    })
            else:
                order_sheet.append("order_sheet_ct", {
                    "so_item": item.item_code,  # Store item code in child table
                    "quantity": item.qty,  # Store quantity
                    "product_combo": 0  # Mark as non-combo item
                })

        # Insert the new Order Sheet document
        order_sheet.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"order_sheet": order_sheet.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Order Sheet Creation Failed")
        return {"error": str(e)}


def add_parameter(doc, method):
    # Get custom_item_category from the Item's Item Group
    if doc.item_group:
        item_group = frappe.get_doc("Item Group", doc.item_group)
        if hasattr(item_group, 'custom_item_category') and item_group.custom_item_category and not doc.custom_item_parameter:
            category = frappe.get_doc("Item Category", item_group.custom_item_category)
            for param in category.custom_item_parameter:
                row = doc.append("custom_item_parameter", {})
                row.parameter = param.parameter



#  item query 


@frappe.whitelist()
def filter_items_by_customer(doctype, txt, searchfield, start, page_len, filters):
    customer = filters.get("custom_customer")
    if not customer:
        return []

    return frappe.db.sql("""
        SELECT i.name, i.item_name
        FROM `tabItem` i
        INNER JOIN `tabAllowed Customer` cac ON cac.parent = i.name
        WHERE cac.customer = %(customer)s
        AND (i.name LIKE %(txt)s OR i.item_name LIKE %(txt)s)
        AND i.disabled = 0
        GROUP BY i.name
        ORDER BY i.name ASC
        LIMIT %(limit)s OFFSET %(offset)s
    """, {
        "txt": f"%{txt}%",
        "limit": page_len,
        "offset": start,
        "customer": customer
    })


@frappe.whitelist()
def filter_items_by_party_rules(doctype, txt, searchfield, start, page_len, filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    customer = filters.get("custom_customer")
    if not customer:
        return []

    item_groups = frappe.db.sql("""
        SELECT DISTINCT based_on_value
        FROM `tabParty Specific Item`
        WHERE party_type = 'Customer'
          AND restrict_based_on = 'Item Group'
          AND party = %s
    """, (customer,), as_list=1)

    if not item_groups:
        return []

    item_group_list = [row[0] for row in item_groups]

    # ✅ Convert start and page_len to integers
    start = int(start)
    page_len = int(page_len)

    return frappe.db.sql("""
        SELECT i.name, i.item_name
        FROM `tabItem` i
        WHERE i.item_group IN %(item_groups)s
          AND (i.name LIKE %(txt)s OR i.item_name LIKE %(txt)s)
        LIMIT %(page_len)s OFFSET %(start)s
    """, {
        "item_groups": tuple(item_group_list),
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    })


@frappe.whitelist()
def get_party_specific_item_group(customer):
    if not customer:
        return None

    result = frappe.db.get_value(
        "Party Specific Item",
        {
            "party": customer,
            "restrict_based_on": "Item Group"
        },
        "based_on_value"
    )

    return result



def validate_sales_order(doc, method):
    for item in doc.items:
        item_doc = frappe.get_doc("Item", item.item_code)

        # Skip global items
        if item_doc.custom_global_item == 1:
            continue

        allowed_customers = item_doc.custom_allowed_customers or []
        if not any(c.customer == doc.customer for c in allowed_customers):
            frappe.throw(_(
                f"🚫 Restricted Item!\n\n❌ The item <b>{item.item_code}</b> cannot be sold to <b>{doc.customer}</b>.\n🔒 Please select another item or contact the administrator."
            ))


# New Bulk Work Order Management APIs

@frappe.whitelist()
def get_bulk_work_order_summary(sales_order):
    """Get comprehensive summary of work orders for bulk management"""
    if not sales_order:
        return {"error": "Sales Order is required"}
    
    try:
        # Get all work orders for the sales order
        work_orders = frappe.get_all(
            "Work Order",
            filters={
                "sales_order": sales_order,
                "docstatus": 1
            },
            fields=["name", "item_code", "item_name", "qty", "produced_qty", "status", "posting_date"]
        )
        
        if not work_orders:
            return {"message": "No work orders found for this sales order"}
        
        # Group by item
        item_summary = {}
        total_stats = {
            "total_work_orders": len(work_orders),
            "total_ordered_qty": 0,
            "total_delivered_qty": 0,
            "total_pending_qty": 0
        }
        
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
            
            delivered_qty = frappe.utils.flt(wo.produced_qty)
            pending_qty = frappe.utils.flt(wo.qty) - delivered_qty
            
            item_summary[item_code]["total_ordered_qty"] += frappe.utils.flt(wo.qty)
            item_summary[item_code]["total_delivered_qty"] += delivered_qty
            item_summary[item_code]["total_pending_qty"] += pending_qty
            item_summary[item_code]["work_order_count"] += 1
            item_summary[item_code]["work_orders"].append({
                "name": wo.name,
                "ordered_qty": wo.qty,
                "delivered_qty": delivered_qty,
                "pending_qty": pending_qty,
                "status": wo.status,
                "posting_date": wo.posting_date
            })
            
            # Update totals
            total_stats["total_ordered_qty"] += frappe.utils.flt(wo.qty)
            total_stats["total_delivered_qty"] += delivered_qty
            total_stats["total_pending_qty"] += pending_qty
        
        # Calculate completion percentages
        for item_code, summary in item_summary.items():
            if summary["total_ordered_qty"] > 0:
                summary["completion_percentage"] = (summary["total_delivered_qty"] / summary["total_ordered_qty"]) * 100
            else:
                summary["completion_percentage"] = 0
        
        total_stats["completion_percentage"] = (total_stats["total_delivered_qty"] / total_stats["total_ordered_qty"] * 100) if total_stats["total_ordered_qty"] > 0 else 0
        
        return {
            "success": True,
            "item_summary": list(item_summary.values()),
            "total_stats": total_stats,
            "sales_order": sales_order
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_bulk_work_order_summary: {str(e)}")
        return {"error": str(e)}


@frappe.whitelist()
def bulk_allocate_delivery(sales_order, delivery_data):
    """Bulk allocate delivery quantities to work orders"""
    if not sales_order or not delivery_data:
        return {"error": "Sales Order and delivery data are required"}
    
    try:
        if isinstance(delivery_data, str):
            delivery_data = json.loads(delivery_data)
        
        # Validate delivery data
        for item_data in delivery_data:
            if not item_data.get("item_code") or not item_data.get("delivery_qty"):
                return {"error": "Invalid delivery data format"}
        
        # Get work orders for the sales order
        work_orders = frappe.get_all(
            "Work Order",
            filters={
                "sales_order": sales_order,
                "docstatus": 1
            },
            fields=["name", "item_code", "qty", "produced_qty"],
            order_by="creation_date"
        )
        
        allocation_results = []
        
        for item_data in delivery_data:
            item_code = item_data["item_code"]
            delivery_qty = frappe.utils.flt(item_data["delivery_qty"])
            
            # Find work orders for this item
            item_work_orders = [wo for wo in work_orders if wo.item_code == item_code]
            
            remaining_qty = delivery_qty
            item_allocation = {
                "item_code": item_code,
                "total_delivery_qty": delivery_qty,
                "allocated_qty": 0,
                "work_orders": []
            }
            
            for wo in item_work_orders:
                if remaining_qty <= 0:
                    break
                
                pending_qty = frappe.utils.flt(wo.qty) - frappe.utils.flt(wo.produced_qty)
                if pending_qty <= 0:
                    continue
                
                # Allocate quantity to this work order
                allocation_qty = min(remaining_qty, pending_qty)
                
                # Update work order
                new_produced_qty = frappe.utils.flt(wo.produced_qty) + allocation_qty
                frappe.db.set_value("Work Order", wo.name, "produced_qty", new_produced_qty)
                
                item_allocation["work_orders"].append({
                    "work_order": wo.name,
                    "allocated_qty": allocation_qty,
                    "new_produced_qty": new_produced_qty
                })
                
                item_allocation["allocated_qty"] += allocation_qty
                remaining_qty -= allocation_qty
            
            allocation_results.append(item_allocation)
            
            if remaining_qty > 0:
                frappe.msgprint(_("Warning: {0} units of {1} could not be allocated").format(
                    remaining_qty, item_code
                ), indicator="orange")
        
        frappe.db.commit()
        
        return {
            "success": True,
            "allocation_results": allocation_results,
            "message": "Bulk allocation completed successfully"
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Error in bulk_allocate_delivery: {str(e)}")
        return {"error": str(e)}


@frappe.whitelist()
def get_work_order_delivery_status(sales_order):
    """Get detailed delivery status for work orders"""
    if not sales_order:
        return {"error": "Sales Order is required"}
    
    try:
        # Get work orders with delivery status
        work_orders = frappe.db.sql("""
            SELECT 
                wo.name,
                wo.item_code,
                wo.item_name,
                wo.qty as ordered_qty,
                wo.produced_qty as delivered_qty,
                (wo.qty - wo.produced_qty) as pending_qty,
                wo.status,
                CASE 
                    WHEN wo.produced_qty = 0 THEN 'Pending'
                    WHEN wo.produced_qty >= wo.qty THEN 'Fully Delivered'
                    ELSE 'Partially Delivered'
                END as delivery_status,
                wo.posting_date
            FROM `tabWork Order` wo
            WHERE wo.sales_order = %s AND wo.docstatus = 1
            ORDER BY wo.posting_date DESC
        """, (sales_order,), as_dict=True)
        
        # Calculate summary statistics
        total_ordered = sum(wo.ordered_qty for wo in work_orders)
        total_delivered = sum(wo.delivered_qty for wo in work_orders)
        total_pending = sum(wo.pending_qty for wo in work_orders)
        
        # Group by delivery status
        status_summary = {}
        for wo in work_orders:
            status = wo.delivery_status
            if status not in status_summary:
                status_summary[status] = {
                    "count": 0,
                    "total_ordered": 0,
                    "total_delivered": 0,
                    "total_pending": 0
                }
            
            status_summary[status]["count"] += 1
            status_summary[status]["total_ordered"] += wo.ordered_qty
            status_summary[status]["total_delivered"] += wo.delivered_qty
            status_summary[status]["total_pending"] += wo.pending_qty
        
        return {
            "success": True,
            "work_orders": work_orders,
            "summary": {
                "total_work_orders": len(work_orders),
                "total_ordered_qty": total_ordered,
                "total_delivered_qty": total_delivered,
                "total_pending_qty": total_pending,
                "completion_percentage": (total_delivered / total_ordered * 100) if total_ordered > 0 else 0
            },
            "status_summary": status_summary
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_work_order_delivery_status: {str(e)}")
        return {"error": str(e)}


@frappe.whitelist()
def create_bulk_stock_entry(sales_order, delivery_items, stock_entry_type=None, auto_detect=True):
    """Create a stock entry for bulk delivery"""
    if not sales_order or not delivery_items:
        return {"error": "Sales Order and delivery items are required"}
    
    try:
        if isinstance(delivery_items, str):
            delivery_items = json.loads(delivery_items)
        
        # Get sales order details
        so_doc = frappe.get_doc("Sales Order", sales_order)
        
        # Determine stock entry type
        if auto_detect and not stock_entry_type:
            stock_entry_type = determine_stock_entry_type_from_items(delivery_items)
        else:
            stock_entry_type = stock_entry_type or "Material Transfer for Manufacture"
        
        # Create stock entry
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = stock_entry_type
        stock_entry.posting_date = frappe.utils.nowdate()
        stock_entry.posting_time = frappe.utils.nowtime()
        
        # Add items based on stock entry type
        if stock_entry_type == "Manufacture":
            add_items_for_manufacture(stock_entry, delivery_items)
        else:
            add_items_for_material_transfer(stock_entry, delivery_items)
        
        stock_entry.save()
        stock_entry.submit()
        
        return {
            "success": True,
            "stock_entry": stock_entry.name,
            "stock_entry_type": stock_entry_type,
            "message": f"Bulk stock entry ({stock_entry_type}) created successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error in create_bulk_stock_entry: {str(e)}")
        return {"error": str(e)}

def determine_stock_entry_type_from_items(delivery_items):
    """Determine stock entry type based on items"""
    for item_data in delivery_items:
        if frappe.utils.flt(item_data.get("delivery_qty", 0)) > 0:
            # Check if this is a finished good (has BOM)
            bom_exists = frappe.db.exists("BOM", {
                "item": item_data["item_code"],
                "is_active": 1,
                "is_default": 1
            })
            
            if bom_exists:
                return "Manufacture"
    
    return "Material Transfer for Manufacture"

def add_items_for_material_transfer(stock_entry, delivery_items):
    """Add items for Material Transfer for Manufacture stock entry"""
    for item_data in delivery_items:
        if frappe.utils.flt(item_data.get("delivery_qty", 0)) > 0:
            stock_entry.append("items", {
                "item_code": item_data["item_code"],
                "item_name": item_data.get("item_name", ""),
                "qty": item_data["delivery_qty"],
                "uom": item_data.get("uom", "Nos"),
                "s_warehouse": item_data.get("warehouse", ""),
                "t_warehouse": "",
                "is_finished_item": 0  # Raw material
            })

def add_items_for_manufacture(stock_entry, delivery_items):
    """Add items for Manufacture stock entry (finished goods)"""
    for item_data in delivery_items:
        if frappe.utils.flt(item_data.get("delivery_qty", 0)) > 0:
            stock_entry.append("items", {
                "item_code": item_data["item_code"],
                "item_name": item_data.get("item_name", ""),
                "qty": item_data["delivery_qty"],
                "uom": item_data.get("uom", "Nos"),
                "s_warehouse": "",
                "t_warehouse": item_data.get("warehouse", ""),
                "is_finished_item": 1  # Finished good
            })