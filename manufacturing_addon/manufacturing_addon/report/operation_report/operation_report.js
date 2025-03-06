// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.query_reports["Operation Report"] = {
	"filters": [
		{
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
		{
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "order_sheet",
            "label": __("Order Sheet"),
            "fieldtype": "Link",
            "options": "Order Sheet"
        },
		{
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "finished_size",
            "label": __("Finished Size"),
            "fieldtype": "Data",
        }			
	],
	onload: function(report) {
        let chartData = report.chart_data;
        if (chartData) {
            new frappe.Chart("#chart-container", {
                title: "Ordered Qty vs Ready Qty",
                type: 'bar',
                data: chartData,
                height: 300,
                colors: ['#00B4A2', '#F4B400'],
            });
        }
    }
};
