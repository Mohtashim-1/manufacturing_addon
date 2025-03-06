import frappe

@frappe.whitelist()
def create_order_sheet(sales_order):
    """Creates an Order Sheet for a given Sales Order and adds items to child table"""
    try:
        # Fetch the Sales Order document
        so_doc = frappe.get_doc("Sales Order", sales_order)

        # Create the Order Sheet document
        order_sheet = frappe.get_doc({
            "doctype": "Order Sheet",
            "sales_order": so_doc.name,  # Store Sales Order name
            "order_sheet_ct": []  # Initialize child table
        })

        # Loop through Sales Order Items and add them to Order Sheet Child Table
        for item in so_doc.items:
            order_sheet.append("order_sheet_ct", {
                "so_item": item.item_code,  # Store item code in child table field
                "quantity": item.qty,  # Store UOM in child table field
            })

        # Insert the new Order Sheet document
        order_sheet.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"order_sheet": order_sheet.name}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Order Sheet Creation Failed")
        return {"error": str(e)}
