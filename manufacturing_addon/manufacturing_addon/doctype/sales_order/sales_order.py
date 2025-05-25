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