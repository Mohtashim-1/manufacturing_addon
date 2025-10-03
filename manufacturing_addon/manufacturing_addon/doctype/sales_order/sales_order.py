import frappe
from frappe import _

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

def close_cost_center_when_sales_order_is_closed(doc, method):
    if doc.status == "Closed" and doc.cost_center:
        frappe.msgprint("Closing cost center")
        try:
            cost_center = frappe.get_doc("Cost Center", doc.cost_center)
            if not cost_center.disabled:
                cost_center.disabled = 1
                cost_center.save()
                frappe.msgprint(f"Cost Center {doc.cost_center} has been closed.")
        except frappe.DoesNotExistError:
            frappe.msgprint(f"Cost Center {doc.cost_center} not found.")
        except Exception as e:
            frappe.msgprint(f"Error closing cost center: {str(e)}")
    else:
        frappe.msgprint("Cost Center is not closed.")

@frappe.whitelist()
def close_sales_order_and_cost_center(sales_order_name):
    """Close Sales Order and disable its cost center"""
    try:
        # Get the Sales Order document
        sales_order = frappe.get_doc("Sales Order", sales_order_name)
        
        # Check if already closed
        if sales_order.status == "Closed":
            frappe.msgprint("Sales Order is already closed.")
            return {"status": "already_closed"}
        
        # Use the proper ERPNext method to update status to Closed
        sales_order.update_status("Closed")
        
        # Disable cost center if it exists
        if sales_order.cost_center:
            try:
                cost_center = frappe.get_doc("Cost Center", sales_order.cost_center)
                if not cost_center.disabled:
                    cost_center.disabled = 1
                    cost_center.save()
                    frappe.msgprint(f"Sales Order closed and Cost Center {sales_order.cost_center} has been disabled.")
                else:
                    frappe.msgprint("Sales Order closed. Cost Center was already disabled.")
            except frappe.DoesNotExistError:
                frappe.msgprint("Sales Order closed. Cost Center not found.")
        else:
            frappe.msgprint("Sales Order closed. No cost center to disable.")
        
        return {"status": "success", "message": "Sales Order closed successfully"}
        
    except Exception as e:
        frappe.msgprint(f"Error closing Sales Order: {str(e)}")
        return {"status": "error", "message": str(e)}