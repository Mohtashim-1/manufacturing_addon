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
        
@frappe.whitelist()
def get_bom_items_from_bom_template(doc, method):
    if doc.custom_bom_template:
        bom_template = frappe.get_doc("BOM Template", doc.custom_bom_template)
        for item in bom_template.raw_material_table:
            doc.append("items", {
                "item_code": item.item,
                "qty": item.qty,
                "uom": item.uom,
                "rate": item.rate if hasattr(item, 'rate') else 0,
                "custom_frozen_from_template": 1 if hasattr(item, 'freeze') and item.freeze == 1 else 0,
            })

@frappe.whitelist()
def get_bom_items_from_template_api(bom_name):
    """API method to get BOM items from template"""
    if not bom_name:
        frappe.throw("BOM name is required")
    
    bom_doc = frappe.get_doc("BOM", bom_name)
    if not bom_doc.custom_bom_template:
        frappe.throw("No BOM Template selected")
    
    bom_template = frappe.get_doc("BOM Template", bom_doc.custom_bom_template)
    
    # Clear existing items
    bom_doc.items = []
    
    # Add items from template
    for item in bom_template.raw_material_table:
        bom_doc.append("items", {
            "item_code": item.item,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate if hasattr(item, 'rate') else 0,
            "custom_frozen_from_template": 1 if hasattr(item, 'freeze') and item.freeze == 1 else 0,
        })
    
    bom_doc.save()
    return "Items fetched from BOM Template successfully"
