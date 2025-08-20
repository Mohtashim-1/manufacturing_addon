frappe.listview_settings['Work Order Transfer Manager'] = {
	add_fields: ["transfer_status", "transfer_percentage"],
	get_indicator: function(doc) {
		// Return indicator based on transfer status
		if (doc.transfer_status === "Completed") {
			return [__("Completed"), "green", "transfer_status,=,Completed"];
		} else if (doc.transfer_status === "In Progress") {
			return [__("In Progress") + ` (${doc.transfer_percentage || 0}%)`, "orange", "transfer_status,=,In Progress"];
		} else {
			return [__("Pending"), "red", "transfer_status,=,Pending"];
		}
	},
	
	// Add custom formatter for percentage column
	formatters: {
		transfer_percentage: function(value, df, doc) {
			if (value === null || value === undefined) return "";
			
			const percentage = parseFloat(value);
			let color = "red";
			
			if (percentage >= 100) {
				color = "green";
			} else if (percentage > 0) {
				color = "orange";
			}
			
			return `<span style="color: ${color}; font-weight: bold;">${percentage.toFixed(1)}%</span>`;
		},
		
		transfer_status: function(value, df, doc) {
			if (!value) return "";
			
			let color = "red";
			let icon = "";
			
			switch(value) {
				case "Completed":
					color = "green";
					icon = "✓";
					break;
				case "In Progress":
					color = "orange";
					icon = "⟳";
					break;
				case "Pending":
					color = "red";
					icon = "⏳";
					break;
			}
			
			return `<span style="color: ${color}; font-weight: bold;">${icon} ${value}</span>`;
		}
	},
	
	// Add filters for status
	filters: [
		{
			fieldname: "transfer_status",
			label: __("Transfer Status"),
			options: "Work Order Transfer Manager",
			get_query: function() {
				return {
					filters: {
						"transfer_status": ["in", ["Pending", "In Progress", "Completed"]]
					}
				}
			}
		}
	],
	
	// Add custom button to refresh status
	button: {
		show: function(doc) {
			return doc.transfer_status !== "Completed";
		},
		get_label: function() {
			return __("Refresh Status");
		},
		get_description: function(doc) {
			return __("Update transfer status and percentage");
		},
		action: function(doc) {
			frappe.call({
				method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.update_transfer_quantities",
				args: { doc_name: doc.name },
				callback: function(r) {
					if (r.message && r.message.success) {
						frappe.show_alert(__("Status updated successfully"), "green");
						frappe.set_route("List", "Work Order Transfer Manager");
					} else {
						frappe.show_alert(__("Error updating status"), "red");
					}
				}
			});
		}
	},
	
	// Add custom field for progress bar
	onload: function(listview) {
		// Add progress bar column if not exists
		if (!listview.columns.find(col => col.fieldname === "progress_bar")) {
			listview.columns.push({
				fieldname: "progress_bar",
				label: __("Progress"),
				width: 120,
				formatter: function(value, df, doc) {
					const percentage = parseFloat(doc.transfer_percentage || 0);
					const status = doc.transfer_status || "Pending";
					
					let color = "#ff6b6b"; // red
					if (status === "Completed") {
						color = "#51cf66"; // green
					} else if (status === "In Progress") {
						color = "#ffd43b"; // orange
					}
					
					return `
						<div style="width: 100px; height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden;">
							<div style="width: ${percentage}%; height: 100%; background: ${color}; transition: width 0.3s ease;"></div>
						</div>
						<div style="font-size: 10px; color: #6c757d; margin-top: 2px;">${percentage.toFixed(1)}%</div>
					`;
				}
			});
		}
	},
	
	// Add refresh button to list view
	refresh: function(listview) {
		listview.page.add_inner_button(__("Refresh All Status"), function() {
			frappe.confirm(__("This will refresh the status of all Work Order Transfer Managers. Continue?"), function() {
				frappe.show_progress(__("Updating status..."), 0, 100);
				
				// Get all WOTM documents
				frappe.call({
					method: "frappe.client.get_list",
					args: {
						doctype: "Work Order Transfer Manager",
						fields: ["name"]
					},
					callback: function(r) {
						if (r.message) {
							let processed = 0;
							const total = r.message.length;
							
							r.message.forEach(function(doc) {
								frappe.call({
									method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.update_transfer_quantities",
									args: { doc_name: doc.name },
									callback: function() {
										processed++;
										frappe.show_progress(__("Updating status..."), processed, total);
										
										if (processed === total) {
											frappe.hide_progress();
											frappe.show_alert(__("All status updated successfully"), "green");
											listview.refresh();
										}
									}
								});
							});
						}
					}
				});
			});
		});
	}
}; 