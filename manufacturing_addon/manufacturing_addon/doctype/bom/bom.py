import frappe
from frappe import _
from erpnext.stock.get_item_details import get_conversion_factor
from frappe.utils import flt

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

def update_bom_stock_qty(doc, method):
    """Custom method to fix conversion_factor calculation bug
    Fixes the issue where conversion_factor is incorrectly set to 1.0
    when UOM doesn't match stock UOM
    """
    for m in doc.get("items"):
        # If UOM doesn't match stock UOM and conversion_factor is 1.0, recalculate
        # This fixes cases where conversion_factor was incorrectly defaulted to 1.0
        if m.uom and m.stock_uom and m.uom != m.stock_uom:
            if not m.conversion_factor or m.conversion_factor == 1.0:
                calculated_factor = flt(get_conversion_factor(m.item_code, m.uom)["conversion_factor"])
                # Only update if the calculated factor is different from 1.0
                if calculated_factor and calculated_factor != 1.0:
                    m.conversion_factor = calculated_factor
                elif not m.conversion_factor:
                    m.conversion_factor = calculated_factor or 1
        elif not m.conversion_factor:
            m.conversion_factor = flt(get_conversion_factor(m.item_code, m.uom)["conversion_factor"])
        
        # Calculate stock qty
        if m.uom and m.qty:
            m.stock_qty = flt(m.conversion_factor) * flt(m.qty)
        if not m.uom and m.stock_uom:
            m.uom = m.stock_uom
            m.qty = m.stock_qty
