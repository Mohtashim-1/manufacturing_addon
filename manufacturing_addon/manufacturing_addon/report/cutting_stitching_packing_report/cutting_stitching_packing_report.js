// Copyright (c) 2026, SAH Exports and contributors
// For license information, please see license.txt

frappe.query_reports["Cutting Stitching Packing Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "operation",
			label: __("Operation"),
			fieldtype: "Select",
			options: ["All", "Cutting", "Stitching", "Packing"].join("\n"),
			default: "All",
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Manufacturing Contractor",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "order_sheet",
			label: __("Order Sheet"),
			fieldtype: "Link",
			options: "Order Sheet",
		},
		{
			fieldname: "so_item",
			label: __("SO Item"),
			fieldtype: "Link",
			options: "Item",
		},
	],
};
