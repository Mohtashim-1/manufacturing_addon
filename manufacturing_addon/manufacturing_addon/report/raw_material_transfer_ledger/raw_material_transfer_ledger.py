import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}
    
    # Get columns
    columns = get_columns()
    
    # Get data
    data = get_data(filters)
    
    # Get summary
    summary = get_summary(data)
    
    return columns, data, None, None

def get_columns():
    return [
        {
            "label": _("Raw Material Transfer"),
            "fieldname": "rmt_name",
            "fieldtype": "Link",
            "options": "Raw Material Transfer",
            "width": 150
        },
        {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": _("Stock Entry"),
            "fieldname": "stock_entry",
            "fieldtype": "Link",
            "options": "Stock Entry",
            "width": 120
        },
        {
            "label": _("Work Order"),
            "fieldname": "work_order",
            "fieldtype": "Link",
            "options": "Work Order",
            "width": 120
        },
        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("UOM"),
            "fieldname": "uom",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 60
        },
        {
            "label": _("Quantity"),
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("Source Warehouse"),
            "fieldname": "s_warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150
        },
        {
            "label": _("Target Warehouse"),
            "fieldname": "t_warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 150
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        }
    ]

def get_data(filters):
    """
    Get all stock entries and their items for raw material transfers
    This report shows all stock entries created when submitting an RMT
    """
    conditions = ["rmt.docstatus = 1"]
    
    if filters.get("raw_material_transfer"):
        conditions.append(f"rmt.name = '{filters.get('raw_material_transfer')}'")
    
    if filters.get("from_date"):
        conditions.append(f"rmt.posting_date >= '{filters.get('from_date')}'")
    
    if filters.get("to_date"):
        conditions.append(f"rmt.posting_date <= '{filters.get('to_date')}'")
    
    condition_str = " AND ".join(conditions) if conditions else "1=1"
    
    # First, try to query from the child table (new method with multiple stock entries)
    query_child = f"""
        SELECT 
            rmt.name as rmt_name,
            rmt.posting_date,
            rmt.posting_time,
            rmt.company,
            rmt.sales_order,
            rmt_se.stock_entry,
            rmt_se.work_order,
            rmt_se.status,
            se_item.item_code,
            se_item.item_name,
            se_item.uom,
            se_item.qty,
            se_item.s_warehouse,
            se_item.t_warehouse
        FROM `tabRaw Material Transfer` rmt
        INNER JOIN `tabRMT Stock Entry` rmt_se ON rmt_se.parent = rmt.name
        INNER JOIN `tabStock Entry` se ON se.name = rmt_se.stock_entry
        INNER JOIN `tabStock Entry Detail` se_item ON se_item.parent = se.name
        WHERE {condition_str}
    """
    
    # Add item code filter if specified
    if filters.get("item_code"):
        query_child += f" AND se_item.item_code = '{filters.get('item_code')}'"
    
    # Add work order filter if specified
    if filters.get("work_order"):
        query_child += f" AND rmt_se.work_order = '{filters.get('work_order')}'"
    
    query_child += " ORDER BY rmt.posting_date DESC, rmt_se.stock_entry, se_item.item_code"
    
    data = frappe.db.sql(query_child, as_dict=True)
    
    # If no data from child table, fallback to old method with single stock_entry field
    if not data and filters.get("raw_material_transfer"):
        # Fallback query using the old stock_entry field
        query_fallback = f"""
            SELECT 
                rmt.name as rmt_name,
                rmt.posting_date,
                rmt.posting_time,
                rmt.company,
                rmt.sales_order,
                se.name as stock_entry,
                se.work_order as work_order,
                'Submitted' as status,
                se_item.item_code,
                se_item.item_name,
                se_item.uom,
                se_item.qty,
                se_item.s_warehouse,
                se_item.t_warehouse
            FROM `tabRaw Material Transfer` rmt
            INNER JOIN `tabStock Entry` se ON se.name = rmt.stock_entry
            INNER JOIN `tabStock Entry Detail` se_item ON se_item.parent = se.name
            WHERE {condition_str}
        """
        
        if filters.get("item_code"):
            query_fallback += f" AND se_item.item_code = '{filters.get('item_code')}'"
        
        if filters.get("work_order"):
            query_fallback += f" AND se.work_order = '{filters.get('work_order')}'"
        
        query_fallback += " ORDER BY rmt.posting_date DESC, se.name, se_item.item_code"
        
        data = frappe.db.sql(query_fallback, as_dict=True)
    
    return data

def get_summary(data):
    """
    Calculate summary statistics
    """
    if not data:
        return []
    
    summary = []
    
    # Count unique transfers, stock entries, and items
    unique_rmt = set()
    unique_stock_entries = set()
    item_quantities = {}
    
    for row in data:
        unique_rmt.add(row.rmt_name)
        unique_stock_entries.add(row.stock_entry)
        
        if row.item_code not in item_quantities:
            item_quantities[row.item_code] = 0
        item_quantities[row.item_code] += flt(row.qty)
    
    total_qty = sum(item_quantities.values())
    avg_qty = total_qty / len(item_quantities) if item_quantities else 0
    
    summary.append({
        "label": _("Total Raw Material Transfers"),
        "value": len(unique_rmt),
        "indicator": "blue"
    })
    
    summary.append({
        "label": _("Total Stock Entries"),
        "value": len(unique_stock_entries),
        "indicator": "green"
    })
    
    summary.append({
        "label": _("Total Items Transferred"),
        "value": len(item_quantities),
        "indicator": "orange"
    })
    
    summary.append({
        "label": _("Total Quantity Transferred"),
        "value": f"{total_qty:,.2f}",
        "indicator": "purple"
    })
    
    summary.append({
        "label": _("Average Quantity per Item"),
        "value": f"{avg_qty:,.2f}",
        "indicator": "gray"
    })
    
    return summary

