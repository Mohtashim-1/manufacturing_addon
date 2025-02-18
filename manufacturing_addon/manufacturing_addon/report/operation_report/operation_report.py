import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    # Fetching Parent Data (Operation Report)
    conditions = []
    if filters.get("from_date"):
        conditions.append(f"opr.date >= '{filters.get('from_date')}'")
    if filters.get("to_date"):
        conditions.append(f"opr.date <= '{filters.get('to_date')}'")
    if filters.get("order_sheet"):
        conditions.append(f"opr.order_sheet = '{filters.get('order_sheet')}'")

    condition_query = " AND ".join(conditions) if conditions else "1=1"

    # Modified parent query to exclude 'customer'
    operation_reports = frappe.db.sql(f"""
        SELECT 
            opr.name, opr.date, opr.time, opr.order_sheet, opr.ordered_qty, opr.ready_qty, opr.percentage
        FROM `tabOperation Report` opr
        WHERE {condition_query}
        ORDER BY opr.date DESC
    """, as_dict=True)

    # Fetching Child Table Data (Operation Report CT)
    operation_report_names = [or_data["name"] for or_data in operation_reports]
    if not operation_report_names:
        return [], []

    child_conditions = ""
    if filters.get("finished_size"):
        child_conditions += f" AND or_ct.finished_size LIKE '%{filters.get('finished_size')}%'"

    # Modified child query to include 'customer'
    child_data = frappe.db.sql(f"""
        SELECT 
            or_ct.parent, or_ct.finished_size, or_ct.customer
        FROM `tabOperation Report CT` or_ct
        WHERE or_ct.parent IN ({', '.join(['%s'] * len(operation_report_names))}) {child_conditions}
    """, tuple(operation_report_names), as_dict=True)

    # Formatting the data
    data = []
    for or_data in operation_reports:
        child_records = [cd for cd in child_data if cd["parent"] == or_data["name"]]
        if not child_records:
            # No child data for this row
            data.append([or_data["name"], or_data["date"], or_data["time"], or_data["order_sheet"], or_data["ordered_qty"], or_data["ready_qty"], or_data["percentage"], "", "", ""])
        else:
            # Loop through child records and correctly map finished_size and customer
            for child in child_records:
                data.append([or_data["name"], or_data["date"], or_data["time"], or_data["order_sheet"], or_data["ordered_qty"], or_data["ready_qty"], or_data["percentage"], child["finished_size"], child["customer"]])

    # Column headers (including customer column)
    columns = [
        {"label": _("Report ID"), "fieldname": "name", "fieldtype": "Link", "options": "Operation Report", "width": 180},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 110},
        {"label": _("Time"), "fieldname": "time", "fieldtype": "Time", "width": 80},
        {"label": _("Order Sheet"), "fieldname": "order_sheet", "fieldtype": "Link", "options": "Order Sheet", "width": 190},
       
        {"label": _("Ordered Qty"), "fieldname": "ordered_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Ready Qty"), "fieldname": "ready_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Percentage"), "fieldname": "percentage", "fieldtype": "Percent", "width": 80},
        {"label": _("Finished Size"), "fieldname": "finished_size", "fieldtype": "Data", "width": 120},
		 {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 190},
    ]

    return columns, data
