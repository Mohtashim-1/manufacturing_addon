// Copyright (c) 2026, mohtashim and contributors
// For license information, please see license.txt

frappe.query_reports["Order Target Dashboard"] = {
	"filters": [
		{
			"fieldname": "report_date",
			"label": __("Report Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"description": "Used to determine today's production figures"
		},
		{
			"fieldname": "from_shipment",
			"label": __("Shipment Date From"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "to_shipment",
			"label": __("Shipment Date To"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), 3)
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname": "order_sheet",
			"label": __("Order Sheet"),
			"fieldtype": "Link",
			"options": "Order Sheet"
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nAll\nNot Started\nOn Track\nBehind\nOverdue\nCompleted",
			"default": "All"
		}
	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (!data) return value;

		// ── Status pill ──────────────────────────────────────────
		if (column.fieldname === "status" && data.status) {
			const color_map = {
				"Completed":   "green",
				"On Track":    "blue",
				"Behind":      "orange",
				"Overdue":     "red",
				"Not Started": "gray"
			};
			const color = color_map[data.status] || "gray";
			value = `<span class="indicator-pill ${color}"
				style="font-size:11px;padding:2px 8px;">${data.status}</span>`;
		}

		// ── Days remaining coloring ───────────────────────────────
		if (column.fieldname === "days_remaining") {
			const days = data.days_remaining;
			if (days !== undefined && days !== null) {
				if (days < 0) {
					value = `<b style="color:#e74c3c;">${days}</b>`;
				} else if (days <= 7) {
					value = `<b style="color:#e67e22;">${days}</b>`;
				} else {
					value = `<span style="color:#27ae60;">${days}</span>`;
				}
			}
		}

		// ── Percentage column coloring ────────────────────────────
		const pct_fields = ["cut_pct", "stitch_pct", "check_pct", "pack_pct"];
		if (pct_fields.includes(column.fieldname)) {
			const pct = data[column.fieldname];
			if (pct !== undefined && pct !== null) {
				let color = "#e74c3c";          // red  < 40 %
				if (pct >= 100)  color = "#27ae60";  // green
				else if (pct >= 70) color = "#2980b9";  // blue
				else if (pct >= 40) color = "#e67e22";  // orange
				const formatted = frappe.utils.formatNumber(pct, null, 1);
				value = `<span style="color:${color};font-weight:600;">${formatted}%</span>`;
			}
		}

		// ── Highlight today's production if > 0 ──────────────────
		const today_fields = ["today_cut", "today_stitch", "today_check", "today_pack"];
		if (today_fields.includes(column.fieldname)) {
			const qty = data[column.fieldname];
			if (qty && qty > 0) {
				value = `<b style="color:#2980b9;">${frappe.utils.formatNumber(qty, null, 0)}</b>`;
			}
		}

		// ── Bold daily / weekly target ────────────────────────────
		if (column.fieldname === "daily_target" || column.fieldname === "weekly_target") {
			const qty = data[column.fieldname];
			if (qty && qty > 0) {
				value = `<b>${frappe.utils.formatNumber(qty, null, 0)}</b>`;
			}
		}

		return value;
	},

	"onload": function (report) {
		report.page.add_inner_button(__("Refresh"), function () {
			report.refresh();
		});
	}
};
