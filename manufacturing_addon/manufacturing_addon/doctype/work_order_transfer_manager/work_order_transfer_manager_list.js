frappe.listview_settings['Work Order Transfer Manager'] = {
	add_fields: ["transfer_status", "transfer_percentage"],

	get_indicator: function(doc) {
		if (doc.transfer_status === "Completed") {
			return [__("Completed"), "green", "transfer_status,=,Completed"];
		} else if (doc.transfer_status === "In Progress") {
			return [__("In Progress") + ` (${doc.transfer_percentage || 0}%)`, "orange", "transfer_status,=,In Progress"];
		} else {
			return [__("Pending"), "red", "transfer_status,=,Pending"];
		}
	},

	formatters: {
		transfer_percentage: function(value, df, doc) {
			if (value === null || value === undefined || isNaN(value)) return "0.0%";
			const percentage = parseFloat(value);
			if (isNaN(percentage)) return "0.0%";
			let color = "red";
			if (percentage >= 100) {
				color = "green";
			} else if (percentage > 0) {
				color = "orange";
			}
			return `<div style="text-align: center; width: 100%;"><span style="color: ${color}; font-weight: bold;">${percentage.toFixed(1)}%</span></div>`;
		},

		transfer_status: function(value, df, doc) {
			if (!value) return "";
			let color = "red";
			let icon = "";
			switch(value) {
				case "Completed":
					color = "green"; icon = "✓"; break;
				case "In Progress":
					color = "orange"; icon = "⟳"; break;
				case "Pending":
					color = "red"; icon = "⏳"; break;
			}
			return `<div style="text-align: center; width: 100%;"><span style="color: ${color}; font-weight: bold;">${icon} ${value}</span></div>`;
		}
	},

	// IMPORTANT: Do not set default filters here to avoid corrupting saved list filters.
	// Users can add filters via the UI. Leaving this empty prevents "filter is not iterable" errors.

	onload: function(listview) {
		const style = document.createElement('style');
		style.textContent = `
			.list-view .list-row-header .list-row-col[data-fieldname="transfer_status"],
			.list-view .list-row-header .list-row-col[data-fieldname="transfer_percentage"] { text-align: center !important; }
			.list-view .list-row .list-row-col[data-fieldname="transfer_status"],
			.list-view .list-row .list-row-col[data-fieldname="transfer_percentage"] { text-align: center !important; }
		`;
		document.head.appendChild(style);

		// Optional: add a visual progress bar column (read-only)
		if (!listview.columns.find(col => col.fieldname === "progress_bar")) {
			listview.columns.push({
				fieldname: "progress_bar",
				label: __("Progress"),
				width: 120,
				formatter: function(value, df, doc) {
					const percentage = parseFloat(doc.transfer_percentage || 0);
					if (isNaN(percentage)) return "0.0%";
					const status = doc.transfer_status || "Pending";
					let color = "#ff6b6b"; // red
					if (status === "Completed") color = "#51cf66"; // green
					else if (status === "In Progress") color = "#ffd43b"; // orange
					return `
						<div style="width: 100px; height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden;">
							<div style="width: ${percentage}%; height: 100%; background: ${color}; transition: width 0.3s ease;"></div>
						</div>
						<div style="font-size: 10px; color: #6c757d; margin-top: 2px;">${percentage.toFixed(1)}%</div>
					`;
				}
			});
		}
	}
}; 