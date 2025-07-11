import frappe
from frappe import _

def duplicate_item(doc, method):
    item_codes = {}
    for item in doc.items:
        if item.item_code in item_codes:
            frappe.throw(
                _(f"Duplicate not allowed: <b>{item.item_code}</b> is already present in the BOM at row <b>{item_codes[item.item_code]}</b> and again at row <b>{item.idx}</b>. Please ensure each item is only listed once in the BOM. Remove the duplicate entry to proceed.")
            )
        item_codes[item.item_code] = item.idx
        