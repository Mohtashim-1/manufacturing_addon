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
