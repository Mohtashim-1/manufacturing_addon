// Copyright (c) 2024, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order Sheet", {
	setup(frm) {
		// Ensure bulk edit is enabled for order_sheet_ct field
		frappe.model.with_doctype("Order Sheet", () => {
			let df = frappe.meta.get_docfield("Order Sheet", "order_sheet_ct");
			if (df) {
				df.allow_bulk_edit = 1;
			}
		});
	},

	onload(frm) {
		// Show download/upload buttons after form loads
		frm.trigger("show_bulk_edit_buttons");
	},

	refresh(frm) {
		// Show download/upload buttons on refresh
		frm.trigger("show_bulk_edit_buttons");

		// Add button to fetch items from Sales Order
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				__("Get Items from Sales Order"),
				function() {
					frm.events.get_items_from_sales_order(frm);
				},
				__("Get Items From")
			);
		}

		// Add button to create Production Plan
		if (frm.doc.docstatus === 1 && frm.doc.order_sheet_ct && frm.doc.order_sheet_ct.length > 0) {
			frm.add_custom_button(
				__("Create Production Plan"),
				function() {
					frm.events.create_production_plan(frm);
				},
				__("Create")
			);
		}
	},

	get_items_from_sales_order: function(frm) {
		if (!frm.doc.customer) {
			frappe.msgprint({
				message: __("Please select a Customer first"),
				indicator: "orange",
				title: __("Customer Required")
			});
			return;
		}

		// Show dialog to select Sales Order
		let dialog = new frappe.ui.Dialog({
			title: __("Select Sales Order"),
			fields: [
				{
					fieldtype: "Link",
					fieldname: "sales_order",
					label: __("Sales Order"),
					options: "Sales Order",
					get_query: function() {
						return {
							filters: {
								customer: frm.doc.customer,
								docstatus: 1,
								status: ["not in", ["Closed", "On Hold"]],
								per_delivered: ["<", 99.99]
							}
						};
					},
					reqd: 1
				}
			],
			primary_action_label: __("Get Items"),
			primary_action: function() {
				let values = dialog.get_values();
				if (values.sales_order) {
					dialog.hide();
					frm.events.fetch_items_from_sales_order(frm, values.sales_order);
				}
			}
		});

		dialog.show();
	},

	fetch_items_from_sales_order: function(frm, sales_order) {
		frappe.call({
			method: "manufacturing_addon.manufacturing_addon.doctype.order_sheet.order_sheet.get_items_from_sales_order",
			args: {
				sales_order: sales_order
			},
			freeze: true,
			freeze_message: __("Fetching items from Sales Order..."),
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					// Clear existing items if needed
					if (frm.doc.order_sheet_ct && frm.doc.order_sheet_ct.length > 0) {
						frappe.confirm(
							__("This will replace existing items. Do you want to continue?"),
							function() {
								// User confirmed, proceed with replacing items
								frm.clear_table("order_sheet_ct");
								frm.events.add_items_to_table(frm, r.message, sales_order);
							},
							function() {
								// User cancelled
							}
						);
					} else {
						// No existing items, just add new ones
						frm.events.add_items_to_table(frm, r.message, sales_order);
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

	add_items_to_table: function(frm, items, sales_order) {
		if (items && items.length > 0) {
			// Set the sales_order field if not already set
			if (!frm.doc.sales_order && sales_order) {
				frm.set_value("sales_order", sales_order);
			}

			items.forEach(function(item) {
				let row = frm.add_child("order_sheet_ct");
				row.so_item = item.item_code;
				row.order_qty = item.qty;
				// Set planned_qty to same as order_qty initially
				row.planned_qty = item.qty;
				
				// Map variant attributes to Order Sheet CT fields
				if (item.design) {
					row.design = item.design;
				}
				if (item.ean) {
					row.ean = item.ean;
				}
				if (item.colour) {
					row.colour = item.colour;
				}
				if (item.stitching_article_no) {
					row.stitching_article_no = item.stitching_article_no;
				}
				if (item.size) {
					row.size = item.size;
				}
				if (item.gsm) {
					row.gsm = item.gsm;
				}
			});
			frm.refresh_field("order_sheet_ct");
			frappe.show_alert({
				message: __("{0} items fetched from Sales Order", [items.length]),
				indicator: "green"
			}, 3);
		}
	},

	create_production_plan: function(frm) {
		if (!frm.doc.order_sheet_ct || frm.doc.order_sheet_ct.length === 0) {
			frappe.msgprint({
				message: __("Please add items to Order Sheet first"),
				indicator: "orange",
				title: __("No Items")
			});
			return;
		}

		frappe.call({
			method: "manufacturing_addon.manufacturing_addon.doctype.order_sheet.order_sheet.create_production_plan_from_order_sheet",
			args: {
				order_sheet: frm.doc.name
			},
			freeze: true,
			freeze_message: __("Creating Production Plan..."),
			callback: function(r) {
				if (r.message) {
					frappe.show_alert({
						message: __("Production Plan {0} created successfully", [r.message.name]),
						indicator: "green"
					}, 5);
					frappe.set_route("Form", "Production Plan", r.message.name);
				}
			},
			error: function(r) {
				frappe.msgprint({
					message: __("Error creating Production Plan"),
					indicator: "red",
					title: __("Error")
				});
			}
		});
	},

	show_bulk_edit_buttons(frm) {
		// Function to show download and upload buttons for order_sheet_ct
		if (!frm.fields_dict.order_sheet_ct) return;
		
		let check_and_show = () => {
			if (frm.fields_dict.order_sheet_ct && frm.fields_dict.order_sheet_ct.grid) {
				let grid = frm.fields_dict.order_sheet_ct.grid;
				if (grid && grid.wrapper) {
					let $download = grid.wrapper.find(".grid-download");
					let $upload = grid.wrapper.find(".grid-upload");
					
					// Show buttons if they exist
					if ($download.length) {
						$download.removeClass("hidden");
					}
					if ($upload.length) {
						$upload.removeClass("hidden");
					}
					
					// If buttons don't exist, try to setup bulk edit
					if (!$download.length && grid.setup_allow_bulk_edit) {
						// Force allow_bulk_edit on the field definition
						if (grid.df) {
							grid.df.allow_bulk_edit = 1;
						}
						grid.setup_allow_bulk_edit();
					}
				}
			}
		};
		
		// Try immediately
		check_and_show();
		
		// Also try after a short delay to ensure grid is fully initialized
		setTimeout(check_and_show, 300);
		setTimeout(check_and_show, 1000);
	}
});
