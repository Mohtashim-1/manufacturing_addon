frappe.listview_settings['Raw Material Transfer Planning'] = {
	add_fields: ["status", "sales_order", "total_transfer_percentage", "total_required_percentage", "total_planned_qty", "total_issued_qty", "total_pending_qty"],

	get_indicator: function(doc) {
		if (doc.status === "Completed") {
			return [__("Completed"), "green", "status,=,Completed"];
		} else if (doc.status === "Partially Issued") {
			const transfer_pct = doc.total_transfer_percentage || 0;
			return [__("Partially Issued") + ` (${transfer_pct.toFixed(1)}%)`, "orange", "status,=,Partially Issued"];
		} else if (doc.status === "Cancelled") {
			return [__("Cancelled"), "red", "status,=,Cancelled"];
		} else {
			return [__("Draft"), "gray", "status,=,Draft"];
		}
	},

	formatters: {
		total_transfer_percentage: function(value, df, doc) {
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

		total_required_percentage: function(value, df, doc) {
			if (value === null || value === undefined || isNaN(value)) return "100.0%";
			const percentage = parseFloat(value);
			return `<div style="text-align: center; width: 100%;"><span style="color: #6c757d; font-weight: bold;">${percentage.toFixed(1)}%</span></div>`;
		},

		status: function(value, df, doc) {
			if (!value) return "";
			let color = "gray";
			let icon = "";
			switch(value) {
				case "Completed":
					color = "green"; icon = "✓"; break;
				case "Partially Issued":
					color = "orange"; icon = "⟳"; break;
				case "Draft":
					color = "gray"; icon = "○"; break;
				case "Cancelled":
					color = "red"; icon = "✗"; break;
			}
			return `<div style="text-align: center; width: 100%;"><span style="color: ${color}; font-weight: bold;">${icon} ${value}</span></div>`;
		},

		sales_order: function(value, df, doc) {
			// Handle edge cases where sales_order might be undefined, null, or have unusual format
			// Check both the value parameter and doc.sales_order in case of inconsistencies
			let sales_order_value = value !== undefined && value !== null ? value : (doc && doc.sales_order);
			
			// Convert to string and check for "undefined" or "null" strings
			let str_value = String(sales_order_value || "").trim();
			
			// Handle null, undefined, empty string, or string "undefined"/"null"
			if (!sales_order_value || 
			    str_value === "undefined" || 
			    str_value === "null" ||
			    str_value === "" ||
			    sales_order_value === null ||
			    sales_order_value === undefined ||
			    (typeof sales_order_value === "string" && sales_order_value.trim() === "")) {
				// Return dash for empty values - never show "undefined"
				return `<span class="ellipsis">-</span>`;
			}
			
			// If it's a string with comma-separated values or starts with dash, show the first one
			if (typeof sales_order_value === "string") {
				let cleaned_value = sales_order_value.trim();
				// Remove leading dash if present (e.g., '-6616,6658,6715')
				if (cleaned_value.startsWith('-')) {
					cleaned_value = cleaned_value.substring(1);
				}
				// Take first sales order if multiple (comma-separated)
				if (cleaned_value.includes(',')) {
					cleaned_value = cleaned_value.split(',')[0].trim();
				}
				// Return proper Link field HTML format
				if (cleaned_value && cleaned_value !== "undefined" && cleaned_value !== "null") {
					return `<a class="filterable ellipsis" data-filter="sales_order,=,${frappe.utils.escape_html(cleaned_value)}">${frappe.utils.escape_html(cleaned_value)}</a>`;
				}
				return `<span class="ellipsis">-</span>`;
			}
			
			// Return proper Link field HTML format for valid values
			if (sales_order_value && String(sales_order_value) !== "undefined" && String(sales_order_value) !== "null") {
				let so_val = String(sales_order_value);
				return `<a class="filterable ellipsis" data-filter="sales_order,=,${frappe.utils.escape_html(so_val)}">${frappe.utils.escape_html(so_val)}</a>`;
			}
			return `<span class="ellipsis">-</span>`;
		}
	},

	onload: function(listview) {
		// Add custom styling for percentage and status columns
		const style = document.createElement('style');
		style.textContent = `
			.list-view .list-row-header .list-row-col[data-fieldname="total_transfer_percentage"],
			.list-view .list-row-header .list-row-col[data-fieldname="total_required_percentage"],
			.list-view .list-row-header .list-row-col[data-fieldname="status"] { 
				text-align: center !important; 
			}
			.list-view .list-row .list-row-col[data-fieldname="total_transfer_percentage"],
			.list-view .list-row .list-row-col[data-fieldname="total_required_percentage"],
			.list-view .list-row .list-row-col[data-fieldname="status"] { 
				text-align: center !important; 
			}
		`;
		document.head.appendChild(style);

		// Also add a post-processing step to ensure "undefined" never appears in Sales Order column
		// This is a fallback in case the formatter doesn't catch all cases
		// Use MutationObserver for better performance
		const observer = new MutationObserver(function(mutations) {
			mutations.forEach(function(mutation) {
				mutation.addedNodes.forEach(function(node) {
					if (node.nodeType === 1) { // Element node
						const $node = $(node);
						// Check if it's a list row or contains list rows
						if ($node.hasClass('list-row') || $node.find('.list-row').length > 0) {
							$node.find('.list-row-col[data-fieldname="sales_order"]').each(function() {
								const $cell = $(this);
								const cellText = $cell.text().trim();
								if (cellText === "undefined" || cellText === "null") {
									$cell.html('<span class="ellipsis">-</span>');
								}
							});
						}
					}
				});
			});
		});
		
		// Observe the list view container for changes
		if (listview.$wrapper && listview.$wrapper.length > 0) {
			observer.observe(listview.$wrapper[0], {
				childList: true,
				subtree: true
			});
		}
		
		// Also run immediately after a delay
		setTimeout(function() {
			$('.list-row-col[data-fieldname="sales_order"]').each(function() {
				const $cell = $(this);
				const cellText = $cell.text().trim();
				if (cellText === "undefined" || cellText === "null") {
					$cell.html('<span class="ellipsis">-</span>');
				}
			});
		}, 1000);

		// Optional: Add a visual progress bar column
		if (!listview.columns.find(col => col.fieldname === "progress_bar")) {
			listview.columns.push({
				fieldname: "progress_bar",
				label: __("Progress"),
				width: 120,
				formatter: function(value, df, doc) {
					const percentage = parseFloat(doc.total_transfer_percentage || 0);
					if (isNaN(percentage)) return "";
					const status = doc.status || "Draft";
					let color = "#ff6b6b"; // red
					if (status === "Completed") color = "#51cf66"; // green
					else if (status === "Partially Issued") color = "#ffd43b"; // orange
					else if (status === "Cancelled") color = "#adb5bd"; // gray
					
					return `
						<div style="width: 100px; height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden; margin: 0 auto;">
							<div style="width: ${Math.min(percentage, 100)}%; height: 100%; background: ${color}; transition: width 0.3s ease;"></div>
						</div>
						<div style="font-size: 10px; color: #6c757d; margin-top: 2px; text-align: center;">${percentage.toFixed(1)}%</div>
					`;
				}
			});
		}
	}
};

