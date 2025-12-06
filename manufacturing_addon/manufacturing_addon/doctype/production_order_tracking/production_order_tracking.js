// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Order Tracking", {
	refresh(frm) {
		// Add button to open custom page
		if (frm.doc.name) {
			frm.add_custom_button(
				__("Open Spreadsheet View"),
				function() {
					// Use route_options to pass document name
					frappe.route_options = {
						docname: frm.doc.name
					};
					// Navigate to the page - for Page doctype, use just the page name
					frappe.set_route('production-order-tra');
				},
				__("View")
			);
		} else {
			// Add button to create new spreadsheet
			frm.add_custom_button(
				__("Open Spreadsheet View"),
				function() {
					frappe.route_options = {};
					frappe.set_route('production-order-tra');
				},
				__("View")
			);
		}
		
		// Add button to fetch items from Sales Order
		if (frm.doc.sales_order) {
			frm.add_custom_button(
				__("Fetch Items from Sales Order"),
				function() {
					frm.events.fetch_items_from_sales_order(frm);
				},
				__("Actions")
			);
		}
		
		// Set query for sales_order to filter by customer
		frm.set_query("sales_order", function() {
			return {
				filters: {
					customer: frm.doc.customer || undefined,
					docstatus: ["!=", 2]
				}
			};
		});
	},
	
	customer(frm) {
		// Clear sales_order when customer changes
		if (frm.doc.sales_order) {
			frm.set_value("sales_order", "");
		}
		// Clear items table when customer changes
		if (frm.doc.items_table && frm.doc.items_table.length > 0) {
			frm.clear_table("items_table");
			frm.refresh_field("items_table");
		}
	},
	
	sales_order(frm) {
		// When sales order is selected, offer to fetch items
		if (frm.doc.sales_order && (!frm.doc.items_table || frm.doc.items_table.length === 0)) {
			frappe.confirm(
				__("Do you want to fetch items from this Sales Order?"),
				function() {
					// User confirmed
					frm.events.fetch_items_from_sales_order(frm);
				},
				function() {
					// User cancelled
				}
			);
		} else if (frm.doc.sales_order && frm.doc.items_table && frm.doc.items_table.length > 0) {
			// If items already exist, ask if user wants to replace them
			frappe.confirm(
				__("Items already exist. Do you want to replace them with items from this Sales Order?"),
				function() {
					// User confirmed
					frm.events.fetch_items_from_sales_order(frm);
				},
				function() {
					// User cancelled
				}
			);
		}
	},
	
	fetch_items_from_sales_order(frm) {
		if (!frm.doc.customer) {
			frappe.msgprint({
				message: __("Please select a Customer first"),
				indicator: "orange",
				title: __("Customer Required")
			});
			return;
		}
		
		if (!frm.doc.sales_order) {
			frappe.msgprint({
				message: __("Please select a Sales Order first"),
				indicator: "orange",
				title: __("Sales Order Required")
			});
			return;
		}
		
		frappe.call({
			method: "manufacturing_addon.manufacturing_addon.doctype.production_order_tracking.production_order_tracking.get_items_from_sales_order",
			args: {
				sales_order: frm.doc.sales_order
			},
			freeze: true,
			freeze_message: __("Fetching items from Sales Order..."),
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					// Clear existing items if needed
					if (frm.doc.items_table && frm.doc.items_table.length > 0) {
						frappe.confirm(
							__("This will replace existing items. Do you want to continue?"),
							function() {
								// User confirmed, proceed with replacing items
								frm.clear_table("items_table");
								frm.events.add_items_to_table(frm, r.message);
							},
							function() {
								// User cancelled
							}
						);
					} else {
						// No existing items, just add new ones
						frm.events.add_items_to_table(frm, r.message);
					}
				} else {
					frappe.msgprint({
						message: __("No items found in the selected Sales Order"),
						indicator: "orange",
						title: __("No Items Found")
					});
				}
			},
			error: function(r) {
				frappe.msgprint({
					message: __("Error fetching items from Sales Order"),
					indicator: "red",
					title: __("Error")
				});
			}
		});
	},
	
	add_items_to_table(frm, items) {
		if (items && items.length > 0) {
			items.forEach(function(item) {
				let row = frm.add_child("items_table");
				row.item = item.item || "";
				row.dessin = item.dessin || "";
				row.size_cm = item.size_cm || "";
				row.color = item.color || "";
				row.ean_code = item.ean_code || "";
				row.quantity = item.quantity || 0;
			});
			
			frm.refresh_field("items_table");
			frappe.show_alert({
				message: __("Items fetched successfully"),
				indicator: "green"
			});
		}
	},
	
	items_table_add(frm, cdt, cdn) {
		// Auto-calculate total_cartons when quantity or qty_ctn changes
		let row = locals[cdt][cdn];
		if (row.quantity && row.qty_ctn) {
			if (row.qty_ctn > 0) {
				row.total_cartons = row.quantity / row.qty_ctn;
			}
		}
		frm.refresh_field("items_table");
	},
	
	quantity(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.quantity && row.qty_ctn) {
			if (row.qty_ctn > 0) {
				row.total_cartons = row.quantity / row.qty_ctn;
			}
		}
		if (row.quantity && row.packing_pcs) {
			if (row.quantity > 0) {
				row.packing_percentage = (row.packing_pcs / row.quantity) * 100;
			}
		}
		frm.refresh_field("items_table");
	},
	
	qty_ctn(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.quantity && row.qty_ctn) {
			if (row.qty_ctn > 0) {
				row.total_cartons = row.quantity / row.qty_ctn;
			}
		}
		frm.refresh_field("items_table");
	},
	
	packing_pcs(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.quantity && row.packing_pcs) {
			if (row.quantity > 0) {
				row.packing_percentage = (row.packing_pcs / row.quantity) * 100;
			}
		}
		frm.refresh_field("items_table");
	}
});

