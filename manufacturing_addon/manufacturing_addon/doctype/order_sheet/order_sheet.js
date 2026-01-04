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

		// Render embedded dashboard in the Dashboard tab
		if (frm.fields_dict.dashboard) {
			if (!frm.doc.name) {
				frm.fields_dict.dashboard.$wrapper.html(__("Save the Order Sheet to load the dashboard."));
			} else {
				orderSheetDashboard.render(frm);
			}
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

const orderSheetDashboard = {
	render(frm) {
		const wrapper = frm.fields_dict.dashboard.$wrapper;
		wrapper.empty().append(this.get_layout_html());

		this.setup_filters(frm, wrapper);
		this.setup_search(wrapper);
		this.load_data(frm, wrapper);
	},

	get_layout_html() {
		return `
			<div class="order-tracking-dashboard" style="padding: 20px;">
				<div class="dashboard-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 10px; margin-bottom: 25px; color: white;">
					<div class="row">
						<div class="col-md-12">
							<h2 style="color: white; margin: 0; font-weight: 600;">
								<i class="fa fa-dashboard"></i> Order Tracking Dashboard
							</h2>
							<p style="color: rgba(255,255,255,0.9); margin: 5px 0 0 0;">Track your manufacturing orders across all stages</p>
						</div>
					</div>
				</div>

				<div class="filters-section" style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
					<div class="row">
						<div class="col-md-3">
							<div id="os-filter_customer_field"></div>
						</div>
						<div class="col-md-3">
							<div id="os-filter_sales_order_field"></div>
						</div>
						<div class="col-md-3">
							<div id="os-filter_order_sheet_field"></div>
						</div>
						<div class="col-md-3">
							<label style="font-weight: 600; font-size: 13px; color: #495057; margin-bottom: 5px;">&nbsp;</label>
							<div>
								<button class="btn btn-primary btn-block" id="os-refresh-dashboard">
									<i class="fa fa-refresh"></i> Refresh
								</button>
							</div>
						</div>
					</div>
				</div>

				<div class="summary-cards row" id="os-summary-cards" style="margin-bottom: 25px;"></div>

				<div class="progress-section" style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
					<h4 style="margin-bottom: 20px; color: #495057;">
						<i class="fa fa-line-chart"></i> Production Progress Overview
					</h4>
					<div id="os-progress-charts" class="row"></div>
				</div>

				<div class="detailed-table-section" style="background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
					<div class="d-flex justify-content-between align-items-center" style="margin-bottom: 20px;">
						<h4 style="margin: 0; color: #495057;">
							<i class="fa fa-table"></i> Order Details
						</h4>
						<div style="width: 300px;">
							<input type="text" id="os-table-search-input" class="form-control" placeholder="Search orders, items, sizes, colors..." style="font-size: 13px;" />
						</div>
					</div>
					<div class="table-responsive" style="max-height: 600px; overflow-y: auto;">
						<table class="table table-bordered table-hover table-sm" id="os-order-details-table" style="font-size: 12px;">
							<thead style="position: sticky; top: 0; background-color: #f8f9fa; z-index: 10;">
								<tr>
									<th>Order Sheet</th>
									<th>Item</th>
									<th>Size</th>
									<th>Color</th>
									<th>Order Qty</th>
									<th>Planned Qty</th>
									<th>PCS</th>
									<th colspan="4" class="text-center bg-info text-white">CUTTING</th>
									<th colspan="4" class="text-center bg-warning text-white">STITCHING</th>
									<th colspan="4" class="text-center bg-success text-white">PACKING</th>
								</tr>
								<tr>
									<th></th><th></th><th></th><th></th><th></th><th></th><th></th>
									<th class="bg-info text-white">Qty</th>
									<th class="bg-info text-white">Finished</th>
									<th class="bg-info text-white">%</th>
									<th class="bg-info text-white">Status</th>
									<th class="bg-warning text-white">Qty</th>
									<th class="bg-warning text-white">Finished</th>
									<th class="bg-warning text-white">%</th>
									<th class="bg-warning text-white">Status</th>
									<th class="bg-success text-white">Qty</th>
									<th class="bg-success text-white">Finished</th>
									<th class="bg-success text-white">%</th>
									<th class="bg-success text-white">Status</th>
								</tr>
							</thead>
							<tbody id="os-order-details-body">
								<tr>
									<td colspan="20" class="text-center text-muted" style="padding: 40px;">
										<i class="fa fa-spinner fa-spin fa-2x"></i><br>
										Loading dashboard data...
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>
		`;
	},

	setup_filters(frm, wrapper) {
		const customerWrapper = wrapper.find("#os-filter_customer_field");
		const salesOrderWrapper = wrapper.find("#os-filter_sales_order_field");
		const orderSheetWrapper = wrapper.find("#os-filter_order_sheet_field");

		this.customer_field = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				fieldname: "customer",
				options: "Customer",
				placeholder: "Select Customer",
				label: __("Customer"),
				default: frm.doc.customer || ""
			},
			parent: customerWrapper,
			render_input: true,
		});
		this.customer_field.make_input();

		this.sales_order_field = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				fieldname: "sales_order",
				options: "Sales Order",
				placeholder: "Select Sales Order",
				label: __("Sales Order"),
				get_query: () => {
					const customer = this.customer_field ? this.customer_field.get_value() : "";
					let filters = { docstatus: ["!=", 2] };
					if (customer) filters.customer = customer;
					return { filters };
				},
				default: frm.doc.sales_order || ""
			},
			parent: salesOrderWrapper,
			render_input: true,
		});
		this.sales_order_field.make_input();

		this.order_sheet_field = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				fieldname: "order_sheet",
				options: "Order Sheet",
				placeholder: "Select Order Sheet",
				label: __("Order Sheet"),
				get_query: () => {
					const salesOrder = this.sales_order_field ? this.sales_order_field.get_value() : "";
					return { filters: salesOrder ? { sales_order: salesOrder } : {} };
				},
				default: frm.doc.name || ""
			},
			parent: orderSheetWrapper,
			render_input: true,
		});
		this.order_sheet_field.make_input();

		// Set initial values from the document
		if (frm.doc.customer) this.customer_field.set_value(frm.doc.customer);
		if (frm.doc.sales_order) this.sales_order_field.set_value(frm.doc.sales_order);
		if (frm.doc.name) this.order_sheet_field.set_value(frm.doc.name);

		wrapper.find("#os-refresh-dashboard").on("click", () => {
			this.load_data(frm, wrapper);
		});
	},

	setup_search(wrapper) {
		wrapper.on("keyup", "#os-table-search-input", (e) => {
			const searchTerm = (e.target.value || "").toLowerCase();
			this.filter_table_rows(wrapper, searchTerm);
		});
	},

	load_data(frm, wrapper) {
		const customer = this.customer_field ? this.customer_field.get_value() : "";
		const salesOrder = this.sales_order_field ? this.sales_order_field.get_value() : "";
		const orderSheet = this.order_sheet_field ? this.order_sheet_field.get_value() : frm.doc.name;

		frappe.call({
			method: "manufacturing_addon.manufacturing_addon.page.order_tracking.order_tracking.get_dashboard_data",
			args: {
				customer: customer || null,
				sales_order: salesOrder || null,
				order_sheet: orderSheet || null
			},
			freeze: true,
			freeze_message: __("Loading dashboard data..."),
			callback: (r) => {
				if (r.message) {
					this.render_dashboard(wrapper, r.message);
				}
			},
			error: () => {
				frappe.msgprint({
					message: __("Error loading dashboard data"),
					indicator: "red",
					title: __("Error")
				});
			}
		});
	},

	render_dashboard(wrapper, data) {
		this.render_summary_cards(wrapper, data.summary || {});
		this.render_progress_charts(wrapper, data.summary || {});
		this.render_detailed_table(wrapper, data.details || []);
	},

	render_summary_cards(wrapper, summary) {
		const cardsHtml = `
			<div class="col-md-3 mb-3">
				<div class="card text-white" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border: none; border-radius: 10px;">
					<div class="card-body">
						<div class="d-flex justify-content-between align-items-center">
							<div>
								<h6 class="card-subtitle mb-2" style="opacity: 0.9;">Total Orders</h6>
								<h2 class="mb-0" style="font-weight: 700;">${summary.total_orders || 0}</h2>
							</div>
							<div style="font-size: 40px; opacity: 0.5;"><i class="fa fa-file-text"></i></div>
						</div>
					</div>
				</div>
			</div>
			<div class="col-md-3 mb-3">
				<div class="card text-white" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border: none; border-radius: 10px;">
					<div class="card-body">
						<div class="d-flex justify-content-between align-items-center">
							<div>
								<h6 class="card-subtitle mb-2" style="opacity: 0.9;">Total Order Qty</h6>
								<h2 class="mb-0" style="font-weight: 700;">${this.format_number(summary.total_order_qty || 0)}</h2>
							</div>
							<div style="font-size: 40px; opacity: 0.5;"><i class="fa fa-cubes"></i></div>
						</div>
					</div>
				</div>
			</div>
			<div class="col-md-3 mb-3">
				<div class="card text-white" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border: none; border-radius: 10px;">
					<div class="card-body">
						<div class="d-flex justify-content-between align-items-center">
							<div>
								<h6 class="card-subtitle mb-2" style="opacity: 0.9;">Cutting Progress</h6>
								<h2 class="mb-0" style="font-weight: 700;">${this.format_percentage(summary.cutting_progress || 0)}%</h2>
							</div>
							<div style="font-size: 40px; opacity: 0.5;"><i class="fa fa-scissors"></i></div>
						</div>
					</div>
				</div>
			</div>
			<div class="col-md-3 mb-3">
				<div class="card text-white" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); border: none; border-radius: 10px;">
					<div class="card-body">
						<div class="d-flex justify-content-between align-items-center">
							<div>
								<h6 class="card-subtitle mb-2" style="opacity: 0.9;">Packing Progress</h6>
								<h2 class="mb-0" style="font-weight: 700;">${this.format_percentage(summary.packing_progress || 0)}%</h2>
							</div>
							<div style="font-size: 40px; opacity: 0.5;"><i class="fa fa-archive"></i></div>
						</div>
					</div>
				</div>
			</div>
		`;

		wrapper.find("#os-summary-cards").html(cardsHtml);
	},

	render_progress_charts(wrapper, summary) {
		const chartsHtml = `
			<div class="col-md-6 mb-3">
				<div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
					<h6 style="color: #495057; margin-bottom: 15px;">Cutting Progress</h6>
					<div class="progress" style="height: 30px; border-radius: 15px;">
						<div class="progress-bar bg-info" role="progressbar"
							style="width: ${summary.cutting_progress || 0}%; line-height: 30px; font-weight: 600;">
							${this.format_percentage(summary.cutting_progress || 0)}%
						</div>
					</div>
					<div class="mt-2" style="font-size: 12px; color: #6c757d;">
						Finished: ${this.format_number(summary.cutting_finished || 0)} / Planned: ${this.format_number(summary.cutting_planned || 0)}
					</div>
				</div>
			</div>
			<div class="col-md-6 mb-3">
				<div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
					<h6 style="color: #495057; margin-bottom: 15px;">Stitching Progress</h6>
					<div class="progress" style="height: 30px; border-radius: 15px;">
						<div class="progress-bar bg-warning" role="progressbar"
							style="width: ${summary.stitching_progress || 0}%; line-height: 30px; font-weight: 600;">
							${this.format_percentage(summary.stitching_progress || 0)}%
						</div>
					</div>
					<div class="mt-2" style="font-size: 12px; color: #6c757d;">
						Finished: ${this.format_number(summary.stitching_finished || 0)} / Planned: ${this.format_number(summary.stitching_planned || 0)}
					</div>
				</div>
			</div>
			<div class="col-md-6 mb-3">
				<div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
					<h6 style="color: #495057; margin-bottom: 15px;">Packing Progress</h6>
					<div class="progress" style="height: 30px; border-radius: 15px;">
						<div class="progress-bar bg-success" role="progressbar"
							style="width: ${summary.packing_progress || 0}%; line-height: 30px; font-weight: 600;">
							${this.format_percentage(summary.packing_progress || 0)}%
						</div>
					</div>
					<div class="mt-2" style="font-size: 12px; color: #6c757d;">
						Finished: ${this.format_number(summary.packing_finished || 0)} / Planned: ${this.format_number(summary.packing_planned || 0)}
					</div>
				</div>
			</div>
			<div class="col-md-6 mb-3">
				<div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
					<h6 style="color: #495057; margin-bottom: 15px;">Overall Progress</h6>
					<div class="progress" style="height: 30px; border-radius: 15px;">
						<div class="progress-bar" role="progressbar"
							style="width: ${summary.overall_progress || 0}%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); line-height: 30px; font-weight: 600;">
							${this.format_percentage(summary.overall_progress || 0)}%
						</div>
					</div>
					<div class="mt-2" style="font-size: 12px; color: #6c757d;">
						Complete: ${this.format_number(summary.packing_finished_finished_items || summary.packing_finished || 0)} / Total: ${this.format_number(summary.total_order_qty || 0)}
					</div>
				</div>
			</div>
		`;

		wrapper.find("#os-progress-charts").html(chartsHtml);
	},

	render_detailed_table(wrapper, details) {
		const tbody = wrapper.find("#os-order-details-body");
		tbody.empty();
		wrapper.find("#os-table-search-input").val("");

		if (!details || details.length === 0) {
			tbody.append(`
				<tr>
					<td colspan="20" class="text-center text-muted" style="padding: 40px;">
						<i class="fa fa-info-circle fa-2x"></i><br>
						No data found for the selected filters
					</td>
				</tr>
			`);
			return;
		}

		const parentOrderQtyMap = {};
		details.forEach((row) => {
			if (row.is_parent === true) {
				const key = `${row.order_sheet}||${row.item}`;
				parentOrderQtyMap[key] = row.order_qty || 0;
			}
		});

		details.forEach((row) => {
			let orderQty = row.order_qty || 0;
			if (row.bundle_item && row.bundle_item !== null) {
				const parentKey = `${row.order_sheet}||${row.item}`;
				orderQty = parentOrderQtyMap[parentKey] || 0;
			}

			let cuttingFinished = row.cutting_finished || 0;
			if (row.pcs && row.pcs > 0 && row.bundle_item) {
				cuttingFinished = cuttingFinished * row.pcs;
			}
			const cuttingPercent = orderQty > 0 ? (cuttingFinished / orderQty) * 100 : 0;

			let stitchingFinished = row.stitching_finished || 0;
			if (row.pcs && row.pcs > 0 && row.bundle_item) {
				stitchingFinished = stitchingFinished * row.pcs;
			}
			const stitchingPercent = orderQty > 0 ? (stitchingFinished / orderQty) * 100 : 0;

			const packingPercent = orderQty > 0 ? ((row.packing_finished || 0) / orderQty) * 100 : 0;

			const isParent = row.is_parent === true;
			const isBundleItem = row.bundle_item && row.bundle_item !== null;

			let rowClass = "";
			let rowStyle = "";
			if (isParent) {
				rowClass = "font-weight-bold";
				rowStyle = "background-color: #f8f9fa;";
			} else if (isBundleItem) {
				rowStyle = "background-color: #ffffff; padding-left: 30px;";
			}

			let displayItem = row.item || "";
			if (isBundleItem) {
				displayItem = `  └─ ${row.bundle_item || ""}`;
			}

			const tr = $(`
				<tr class="${rowClass}" style="${rowStyle}">
					<td>${isBundleItem ? "" : (row.order_sheet || "")}</td>
					<td>${displayItem}</td>
					<td>${isBundleItem ? "" : (row.size || "")}</td>
					<td>${isBundleItem ? "" : (row.color || "")}</td>
					<td class="text-right">${isBundleItem ? "" : this.format_number(row.order_qty || 0)}</td>
					<td class="text-right">${isBundleItem ? "" : this.format_number(row.planned_qty || 0)}</td>
					<td class="text-right">${this.format_number(row.pcs || 0)}</td>
					<td class="text-right ${isBundleItem ? "" : "bg-info text-white"}">${this.format_number(row.cutting_qty || 0)}</td>
					<td class="text-right ${isBundleItem ? "" : "bg-info text-white"}">${this.format_number(row.cutting_finished || 0)}</td>
					<td class="text-right ${isBundleItem ? "" : "bg-info text-white"}">${this.format_percentage(cuttingPercent)}%</td>
					<td class="text-center ${isBundleItem ? "" : "bg-info text-white"}">${this.get_status_badge(cuttingPercent)}</td>
					<td class="text-right ${isBundleItem ? "" : "bg-warning text-white"}">${this.format_number(row.stitching_qty || 0)}</td>
					<td class="text-right ${isBundleItem ? "" : "bg-warning text-white"}">${this.format_number(row.stitching_finished || 0)}</td>
					<td class="text-right ${isBundleItem ? "" : "bg-warning text-white"}">${this.format_percentage(stitchingPercent)}%</td>
					<td class="text-center ${isBundleItem ? "" : "bg-warning text-white"}">${this.get_status_badge(stitchingPercent)}</td>
					<td class="text-right ${isBundleItem ? "" : "bg-success text-white"}">${isBundleItem ? "-" : this.format_number(row.packing_qty || 0)}</td>
					<td class="text-right ${isBundleItem ? "" : "bg-success text-white"}">${isBundleItem ? "-" : this.format_number(row.packing_finished || 0)}</td>
					<td class="text-right ${isBundleItem ? "" : "bg-success text-white"}">${isBundleItem ? "-" : this.format_percentage(packingPercent) + "%"}</td>
					<td class="text-center ${isBundleItem ? "" : "bg-success text-white"}">${isBundleItem ? "-" : this.get_status_badge(packingPercent)}</td>
				</tr>
			`);
			tbody.append(tr);
		});
	},

	filter_table_rows(wrapper, searchTerm) {
		const rows = wrapper.find("#os-order-details-body tr");

		if (!searchTerm || searchTerm.trim() === "") {
			rows.show();
			wrapper.find("#os-order-details-body tr.no-results").remove();
			return;
		}

		let visibleCount = 0;
		rows.each(function() {
			const $row = $(this);
			const rowText = $row.text().toLowerCase();
			if (rowText.includes(searchTerm)) {
				$row.show();
				visibleCount++;
			} else {
				$row.hide();
			}
		});

		if (visibleCount === 0) {
			const tbody = wrapper.find("#os-order-details-body");
			if (tbody.find("tr.no-results").length === 0) {
				tbody.append(`
					<tr class="no-results">
						<td colspan="20" class="text-center text-muted" style="padding: 40px;">
							<i class="fa fa-search fa-2x"></i><br>
							No results found for "${searchTerm}"
						</td>
					</tr>
				`);
			}
		} else {
			wrapper.find("#os-order-details-body tr.no-results").remove();
		}
	},

	get_status_badge(percent) {
		if (percent >= 100) {
			if (percent > 100) {
				return `<span class="badge badge-success" style="background-color: #28a745;">Complete (${this.format_percentage(percent)}%)</span>`;
			}
			return '<span class="badge badge-success">Complete</span>';
		} else if (percent >= 75) {
			return '<span class="badge badge-info">In Progress</span>';
		} else if (percent > 0) {
			return '<span class="badge badge-warning">Started</span>';
		}
		return '<span class="badge badge-secondary">Not Started</span>';
	},

	format_number(num) {
		if (num == null || num === "") return "0";
		return parseFloat(num).toLocaleString("en-US", { maximumFractionDigits: 0 });
	},

	format_percentage(num) {
		if (num == null || num === "") return "0";
		return parseFloat(num).toFixed(1);
	}
};
