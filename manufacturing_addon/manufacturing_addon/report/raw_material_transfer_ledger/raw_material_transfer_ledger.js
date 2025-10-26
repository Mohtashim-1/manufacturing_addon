frappe.query_reports["Raw Material Transfer Ledger"] = {
    "filters": [
        {
            "fieldname": "raw_material_transfer",
            "label": __("Raw Material Transfer"),
            "fieldtype": "Link",
            "options": "Raw Material Transfer",
            "get_query": function() {
                return {
                    filters: {
                        "docstatus": 1
                    }
                }
            }
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_start()
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "item_code",
            "label": __("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "get_query": function() {
                return {
                    filters: {
                        "is_stock_item": 1
                    }
                }
            }
        },
        {
            "fieldname": "work_order",
            "label": __("Work Order"),
            "fieldtype": "Link",
            "options": "Work Order"
        }
    ]
};

