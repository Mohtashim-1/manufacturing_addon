// Copyright (c) 2026, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.query_reports["Container Loading"] = {
	filters: [
		{
			fieldname: "order_sheet",
			label: __("Order Sheet"),
			fieldtype: "Link",
			options: "Order Sheet",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "packing_report",
			label: __("Packing Report"),
			fieldtype: "Link",
			options: "Packing Report",
			get_query() {
				const order_sheet = frappe.query_report.get_filter_value("order_sheet");
				if (!order_sheet) {
					return { filters: { docstatus: 1 } };
				}
				return { filters: { order_sheet, docstatus: 1 } };
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "only_pending",
			label: __("Only Pending"),
			fieldtype: "Check",
			default: 0,
		},
	],
};
