
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
    if doc.custom_item_category and not doc.custom_item_parameter:
        category = frappe.get_doc("Item Category", doc.custom_item_category)
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
