# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StockEntryAgainstBOM(Document):
	def on_submit(self):
		# Create Stock Entry for each finished item using BOM
		for row in self.stock_entry_item_table:
			if row.bom and row.qty:
				stock_entry = frappe.new_doc("Stock Entry")
				stock_entry.stock_entry_type = "Material Transfer for Manufacture"
				stock_entry.from_bom = 1
				stock_entry.use_multi_level_bom = 1
				stock_entry.fg_completed_qty = row.qty
				stock_entry.bom_no = row.bom
				stock_entry.custom_cost_center = f"{self.sales_order} - SAH"
				
				# Set source and target warehouses from the document
				if hasattr(self, 'source_warehouse') and self.source_warehouse:
					stock_entry.from_warehouse = self.source_warehouse
				if hasattr(self, 'target_warehouse') and self.target_warehouse:
					stock_entry.to_warehouse = self.target_warehouse

				# Add finished item as an item row
				stock_entry.append("items", {
					"item_code": row.item,
					"qty": row.qty,
					"t_warehouse": self.target_warehouse if hasattr(self, "target_warehouse") and self.target_warehouse else None,
					"s_warehouse": self.source_warehouse if hasattr(self, "source_warehouse") and self.source_warehouse else None,
				})

				# Save the Stock Entry first
				stock_entry.save(ignore_permissions=True)
				
				# Trigger the built-in "Get Items" functionality to fetch raw materials from BOM
				stock_entry.get_items()
				
				# Save again with the raw materials
				stock_entry.save(ignore_permissions=True)
				# stock_entry.submit()
				
				frappe.msgprint(f"Stock Entry created for {row.item} (Qty: {row.qty}): {stock_entry.name}")
		
		if not self.stock_entry_item_table:
			frappe.throw("No items found in Stock Entry Item Table")


@frappe.whitelist()
def get_items_and_raw_materials(sales_order):
    items = []
    raw_materials_map = {}

    # Fetch Sales Order Items
    so_items = frappe.get_all("Sales Order Item", filters={"parent": sales_order}, fields=["item_code", "bom_no", "qty"])
    for so_item in so_items:
        bom_no = so_item.bom_no
        # If bom_no is empty, fetch default BOM for the item
        if not bom_no:
            bom_no = frappe.db.get_value("BOM", {"item": so_item.item_code, "is_default": 1, "is_active": 1}, "name")
        items.append({
            "item": so_item.item_code,
            "bom": bom_no,
            "qty": so_item.qty
        })
        # Fetch BOM Raw Materials
        if bom_no:
            bom_doc = frappe.get_doc("BOM", bom_no)
            for rm in bom_doc.items:
                # Calculate required qty based on SO qty and BOM qty
                required_qty = (rm.qty / bom_doc.quantity) * so_item.qty
                key = (rm.item_code, rm.uom)
                if key in raw_materials_map:
                    raw_materials_map[key]["qty"] += required_qty
                else:
                    raw_materials_map[key] = {
                        "item": rm.item_code,
                        "qty": required_qty,
                        "uom": rm.uom
                    }

    return {
        "items": items,
        "raw_materials": list(raw_materials_map.values())
    }


@frappe.whitelist()
def recalculate_raw_materials(items):
    """
    Recalculate raw materials based on current items in stock_entry_item_table
    """
    import json
    
    frappe.logger().debug(f"recalculate_raw_materials called with items: {items}")
    
    # Handle items parameter - it might be a JSON string or already a list
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            frappe.throw("Invalid items data format")
    
    raw_materials_map = {}
    
    for item in items:
        if item.get('bom'):
            try:
                bom_doc = frappe.get_doc("BOM", item['bom'])
                for rm in bom_doc.items:
                    # Calculate required qty based on item qty and BOM qty
                    required_qty = (rm.qty / bom_doc.quantity) * item['qty']
                    key = (rm.item_code, rm.uom)
                    if key in raw_materials_map:
                        raw_materials_map[key]["qty"] += required_qty
                    else:
                        raw_materials_map[key] = {
                            "item": rm.item_code,
                            "qty": required_qty,
                            "uom": rm.uom
                        }
            except Exception as e:
                frappe.logger().error(f"Error processing BOM {item['bom']}: {str(e)}")
    
    result = {
        "raw_materials": list(raw_materials_map.values())
    }
    frappe.logger().debug(f"recalculate_raw_materials returning: {result}")
    return result