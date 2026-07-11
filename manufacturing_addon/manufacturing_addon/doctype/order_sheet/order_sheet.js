// Copyright (c) 2024, mohtashim and contributors
// For license information, please see license.txt

function toFloat(value) {
	const n = parseFloat(value);
	return Number.isFinite(n) ? n : 0;
}

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

		compute_order_sheet_header_totals(frm);

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Recalculate Totals"), () => {
				frappe.call({
					method: "manufacturing_addon.manufacturing_addon.doctype.order_sheet.order_sheet.recalculate_summary_totals",
					args: { order_sheet: frm.doc.name },
					freeze: true,
					freeze_message: __("Recalculating totals..."),
					callback: () => frm.reload_doc(),
				});
			}, __("Actions"));
		}

		if (frm.doc.docstatus < 2 && frm.doc.order_sheet_ct && frm.doc.order_sheet_ct.length > 0) {
			frm.add_custom_button(__("Refresh BOM & Carton Details"), () => {
				frappe.call({
					method:
						"manufacturing_addon.manufacturing_addon.doctype.order_sheet.order_sheet.refresh_order_sheet_bom_carton",
					args: { order_sheet: frm.doc.name },
					freeze: true,
					freeze_message: __("Refreshing BOM and carton details..."),
					callback(r) {
						if (!r.exc) {
							const msg = r.message || {};
							frappe.show_alert({
								message: __(
									"Updated {0} row(s); {1} BOM change(s) detected",
									[msg.updated_rows || 0, msg.bom_changed_rows || 0]
								),
								indicator: "green",
							}, 5);
						}
						frm.reload_doc();
					},
				});
			}, __("Actions"));
		}

		// ── Intercept GridView column saves so doc field stays current without a full save ──
		// grid_row.js calls frappe.model.user_settings.save("Order Sheet","GridView",{...}) after
		// the user applies Configure Columns. We wrap it here to also persist the selection to
		// order_sheet_print_column_order immediately (server-side set_value), so Print/PDF always
		// reflects the latest column choice even without an explicit doc save.
		const _origSave = frappe.model.user_settings.save;
		frappe.model.user_settings.save = function(doctype, key, value) {
			const ret = _origSave.apply(this, arguments);
			if (doctype === frm.doc.doctype && key === "GridView") {
				const child_dt = "Order Sheet CT";
				const cols = value?.[child_dt] || [];
				if (cols.length) {
					const names = cols.map((r) => (typeof r === "string" ? r : r.fieldname)).filter(Boolean);
					if (names.length) {
						frm.doc.order_sheet_print_column_order = JSON.stringify(names);
						// Persist to DB immediately so the server can read it without a session.
						if (frm.doc.name && !frm.doc.__islocal) {
							frappe.db.set_value(
								frm.doc.doctype,
								frm.doc.name,
								"order_sheet_print_column_order",
								JSON.stringify(names)
							).catch(() => {});
						}
					}
				}
			}
			return ret;
		};

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

		// Production Plan — create or open linked plan(s)
		if (frm.doc.docstatus === 1 && frm.doc.order_sheet_ct && frm.doc.order_sheet_ct.length > 0) {
			frm.add_custom_button(
				__("Create Production Plan"),
				function() {
					frm.events.create_production_plan(frm);
				},
				__("Production Plan")
			);
			frappe.call({
				method:
					"manufacturing_addon.manufacturing_addon.doctype.order_sheet.order_sheet.get_linked_production_plans",
				args: { order_sheet: frm.doc.name },
				callback(r) {
					const plans = (r.message && r.message.plans) || [];
					if (!plans.length) return;
					if (plans.length === 1) {
						frm.add_custom_button(
							plans[0].name,
							() => frappe.set_route("Form", "Production Plan", plans[0].name),
							__("Production Plan")
						);
					} else {
						frm.add_custom_button(
							__("View Production Plans ({0})", [plans.length]),
							() => {
								frappe.route_options = { custom_order_sheet: frm.doc.name };
								frappe.set_route("List", "Production Plan");
							},
							__("Production Plan")
						);
					}
				},
			});
		}

		if (frm.fields_dict.dashboard) {
			orderSheetDashboard.render(frm);
		}
		if (frm.fields_dict.contractor_dasbhaord) {
			orderSheetContractorDashboard.render(frm);
			orderSheetContractorDashboard.bind_tab_refresh(frm);
		}
		if (frm.fields_dict.quality_dashboard) {
			qualityDashboardInForm.render(frm);
		}
		if (frm.fields_dict.daily_checking_dashboard) {
			dailyCheckingDashboardInForm.render(frm);
		}
		if (frm.fields_dict.inline_stitching_dashboard) {
			inlineStitchingDashboardInForm.render(frm);
		}
	},

	before_save(frm) {
		// Persist Configure Columns on the document for PDF/print (server has no grid UI).
		// Prefer live grid.user_defined_columns (same source as the visible table); then user settings.
		const child_dt = "Order Sheet CT";
		let names = [];
		const grid = frm.fields_dict.order_sheet_ct?.grid;
		if (grid?.user_defined_columns?.length) {
			names = grid.user_defined_columns.map((df) => df.fieldname).filter(Boolean);
		}
		if (!names.length) {
			const gv = frappe.get_user_settings("Order Sheet", "GridView") || {};
			const cols = gv[child_dt];
			if (cols?.length) {
				names = cols.map((r) => r.fieldname).filter(Boolean);
			}
		}
		if (!names.length && frappe.model.user_settings?.["Order Sheet"]?.GridView?.[child_dt]) {
			const cols = frappe.model.user_settings["Order Sheet"].GridView[child_dt];
			names = cols.map((r) => r.fieldname).filter(Boolean);
		}
		if (names.length) {
			// Direct assignment so the value is always in the doc payload (set_value can be async).
			frm.doc.order_sheet_print_column_order = JSON.stringify(names);
		}
	},

	recalculate_total_cartoons(frm) {
		if (!frm.doc.order_sheet_ct || !frm.doc.order_sheet_ct.length) return;
		(frm.doc.order_sheet_ct || []).forEach((row) => {
			if (!row.name) return;
			update_total_cartoons_for_row(row.doctype || "Order Sheet CT", row.name);
		});
		compute_order_sheet_header_totals(frm);
	},

	order_sheet_ct(frm) {
		compute_order_sheet_header_totals(frm);
	},

	sales_order(frm) {
		if (!frm.doc.sales_order) return;
		frappe.db.get_value("Sales Order", frm.doc.sales_order, ["customer", "delivery_date", "po_no", "custom_instructions"], function(r) {
			if (!r) return;
			if (r.customer) frm.set_value("customer", r.customer);
			if (r.delivery_date) frm.set_value("shipment_date", r.delivery_date);
			if (r.po_no) frm.set_value("order_no", r.po_no);
			if (!frm.doc.instructions && r.custom_instructions) {
				frm.set_value("instructions", r.custom_instructions);
			}
		});
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
				row.instructions = item.custom_instructions || "";
				
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
				row.default_bom = item.default_bom || "";
				row.active_bom = item.active_bom || "";
				row.carton_item = item.carton_item || "";
				row.carton_dimension = item.carton_dimension || "";
				row.so_item_weight_per_unit = item.so_item_weight_per_unit || 0;
				row.carton_weight_per_unit = item.carton_weight_per_unit || 0;
				if (item.qty_ctn) {
					row.qty_ctn = item.qty_ctn;
				}
			});
			frm.refresh_field("order_sheet_ct");
			compute_order_sheet_header_totals(frm);
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

/** Sum child-table logistics columns into parent summary fields (matches server validate). */
function compute_order_sheet_header_totals(frm) {
	if (!frm || !frm.doc || frm.doc.order_sheet_ct == null) return;
	// Submitted documents cannot be mutated from client-side refresh handlers.
	// Use the server-side "Recalculate Totals" action for docstatus=1.
	if (cint(frm.doc.docstatus) === 1) return;
	let orderQty = 0;
	let plannedQty = 0;
	let totalCart = 0;
	let totalPlannedCtn = 0;
	let qtyPerCtn = 0;
	let consumption = 0;
	let orderCbm = 0;
	let plannedCbm = 0;
	let netW = 0;
	let grossW = 0;
	for (const row of frm.doc.order_sheet_ct || []) {
		orderQty += toFloat(row.order_qty);
		plannedQty += toFloat(row.planned_qty);
		totalCart += toFloat(row.total_carton);
		totalPlannedCtn += toFloat(row.total_planned_ctn);
		qtyPerCtn += toFloat(row.qty_ctn);
		consumption += toFloat(row.total_consumption);
		orderCbm += toFloat(row.order_cbm);
		plannedCbm += toFloat(row.planned_cbm);
		netW += toFloat(row.net_weight);
		grossW += toFloat(row.gross_weight);
	}
	const legacyQty = plannedQty > 0 ? plannedQty : orderQty;
	const pairs = [
		["total_order_qty", orderQty],
		["total_planned_qty", plannedQty],
		["total_quantity", legacyQty],
		["total_cartoon", totalCart],
		["total_planned_cartoon", totalPlannedCtn],
		["total_quantity_per_cartoon", qtyPerCtn],
		["total_consumption", consumption],
		["total_order_cbm", orderCbm],
		["total_planned_cbm", plannedCbm],
		["total_net_weight", netW],
		["total_gross_weight", grossW]
	];
	for (const [fn, val] of pairs) {
		frappe.model.set_value(frm.doctype, frm.doc.name, fn, val);
	}
}

function update_total_cartoons_for_row(cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row) return;
	const qtyCtn = toFloat(row.qty_ctn);
	const orderQty = toFloat(row.order_qty);
	const plannedQty = toFloat(row.planned_qty);
	const qtyForPlanned = plannedQty || orderQty;
	const total = qtyCtn > 0 ? (orderQty / qtyCtn) : 0;
	const totalPlanned = qtyCtn > 0 ? (qtyForPlanned / qtyCtn) : 0;
	const dimensions = parse_carton_dimensions(row.carton_dimension);
	const soWeightPerUnit = toFloat(row.so_item_weight_per_unit);
	const cartonWeightPerUnit = toFloat(row.carton_weight_per_unit);
	const perCartonCbm = dimensions ? (dimensions.length * dimensions.width * dimensions.height) / 1000000 : 0;
	const orderCbm = perCartonCbm * total;
	const plannedCbm = perCartonCbm * totalPlanned;
	const netWeight = qtyForPlanned * soWeightPerUnit;
	const grossWeight = netWeight + (total * cartonWeightPerUnit);

	frappe.model.set_value(cdt, cdn, "total_carton", total);
	frappe.model.set_value(cdt, cdn, "total_planned_ctn", totalPlanned);
	frappe.model.set_value(cdt, cdn, "order_cbm", orderCbm);
	frappe.model.set_value(cdt, cdn, "planned_cbm", plannedCbm);
	frappe.model.set_value(cdt, cdn, "net_weight", netWeight);
	frappe.model.set_value(cdt, cdn, "gross_weight", grossWeight);

	if (cur_frm && cur_frm.doctype === "Order Sheet") {
		compute_order_sheet_header_totals(cur_frm);
	}
}

function parse_carton_dimensions(dimensionText) {
	if (!dimensionText) return null;
	const match = String(dimensionText).match(/(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)/);
	if (!match) return null;
	return {
		length: toFloat(match[1]),
		width: toFloat(match[2]),
		height: toFloat(match[3])
	};
}

frappe.ui.form.on("Order Sheet CT", {
	so_item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.so_item) {
			frappe.model.set_value(cdt, cdn, "default_bom", "");
			frappe.model.set_value(cdt, cdn, "active_bom", "");
			frappe.model.set_value(cdt, cdn, "carton_item", "");
			frappe.model.set_value(cdt, cdn, "carton_dimension", "");
			frappe.model.set_value(cdt, cdn, "so_item_weight_per_unit", 0);
			frappe.model.set_value(cdt, cdn, "carton_weight_per_unit", 0);
			update_total_cartoons_for_row(cdt, cdn);
			return;
		}

		frappe.call({
			method: "manufacturing_addon.manufacturing_addon.doctype.order_sheet.order_sheet.get_bom_carton_details_for_item",
			args: {
				item_code: row.so_item
			},
			callback: function(r) {
				if (!r.message) return;
				frappe.model.set_value(cdt, cdn, "default_bom", r.message.default_bom || "");
				frappe.model.set_value(cdt, cdn, "active_bom", r.message.active_bom || "");
				frappe.model.set_value(cdt, cdn, "carton_item", r.message.carton_item || "");
				frappe.model.set_value(cdt, cdn, "carton_dimension", r.message.carton_dimension || "");
				frappe.model.set_value(cdt, cdn, "so_item_weight_per_unit", r.message.so_item_weight_per_unit || 0);
				frappe.model.set_value(cdt, cdn, "carton_weight_per_unit", r.message.carton_weight_per_unit || 0);
				if (r.message.qty_ctn) {
					frappe.model.set_value(cdt, cdn, "qty_ctn", r.message.qty_ctn);
				}
				update_total_cartoons_for_row(cdt, cdn);
			}
		});
	},

	planned_qty(frm, cdt, cdn) {
		update_total_cartoons_for_row(cdt, cdn);
	},

	order_qty(frm, cdt, cdn) {
		update_total_cartoons_for_row(cdt, cdn);
	},

	qty_ctn(frm, cdt, cdn) {
		update_total_cartoons_for_row(cdt, cdn);
	}
});

const orderSheetDashboard = {
	_originalDetails: [],
	_setup_done_for: null,

	render(frm) {
		if (frm.doc.docstatus !== 1) {
			frm.fields_dict.dashboard.$wrapper.html(`
				<div style="padding: 40px; text-align: center;">
					<i class="fa fa-info-circle fa-3x" style="color: #6c757d; margin-bottom: 20px;"></i>
					<h4 style="color: #495057; margin-bottom: 10px;">Dashboard Not Available</h4>
					<p style="color: #6c757d;">Please submit the Order Sheet to view the dashboard.</p>
				</div>
			`);
			this._setup_done_for = null;
			return;
		}

		const $wrapper = frm.fields_dict.dashboard.$wrapper;

		// Guard: only build layout+filters once per document name
		if (this._setup_done_for === frm.doc.name) {
			this._load_data(frm, $wrapper);
			return;
		}
		this._setup_done_for = frm.doc.name;

		this._originalDetails = [];
		$wrapper.empty().append(this._get_layout_html());
		this._setup_filters(frm, $wrapper);
		this._setup_events($wrapper);
		this._load_data(frm, $wrapper);
	},

	_get_layout_html() {
		return `
			<div class="osd-wrap" style="padding: 20px;">
				<!-- Filters -->
				<div style="background:#f8f9fa; padding:20px; border-radius:8px; margin-bottom:25px; box-shadow:0 2px 4px rgba(0,0,0,.1);">
					<div class="row">
						<div class="col-md-3">
							<label style="font-weight:600;font-size:13px;color:#495057;margin-bottom:5px;">${__("Customer")}</label>
							<input type="text" class="form-control osd-customer-input" placeholder="${__("Customer")}" />
						</div>
						<div class="col-md-3">
							<label style="font-weight:600;font-size:13px;color:#495057;margin-bottom:5px;">${__("Sales Order")}</label>
							<input type="text" class="form-control osd-sales-order-input" placeholder="${__("Sales Order")}" />
						</div>
						<div class="col-md-3">
							<label style="font-weight:600;font-size:13px;color:#495057;margin-bottom:5px;">${__("Order Sheet")}</label>
							<input type="text" class="form-control osd-order-sheet-input" placeholder="${__("Order Sheet")}" />
						</div>
						<div class="col-md-3" style="display:flex; align-items:flex-end;">
							<button class="btn btn-primary btn-block osd-refresh-btn">
								<i class="fa fa-refresh"></i> Refresh
							</button>
						</div>
					</div>
				</div>

				<!-- Summary cards -->
				<div class="row osd-summary-cards" style="margin-bottom:25px;"></div>

				<!-- Progress bars -->
				<div style="background:#fff; padding:20px; border-radius:8px; margin-bottom:25px; box-shadow:0 2px 4px rgba(0,0,0,.1);">
					<h4 style="margin-bottom:20px; color:#495057;"><i class="fa fa-line-chart"></i> Production Progress Overview</h4>
					<div class="row osd-progress-charts"></div>
				</div>

				<!-- Table -->
				<div style="background:#fff; padding:20px; border-radius:8px; box-shadow:0 2px 4px rgba(0,0,0,.1);">
					<div class="d-flex justify-content-between align-items-center" style="margin-bottom:20px;">
						<h4 style="margin:0; color:#495057;"><i class="fa fa-table"></i> Order Details</h4>
						<div class="d-flex align-items-center" style="gap:8px;">
							<button class="btn btn-outline-secondary btn-sm osd-expand-btn">Expand All</button>
							<button class="btn btn-outline-secondary btn-sm osd-collapse-btn">Collapse All</button>
							<div style="width:300px;">
								<input type="text" class="form-control osd-search-input" placeholder="Search orders, items, sizes, colors..." style="font-size:13px;" />
							</div>
						</div>
					</div>
					<div class="table-responsive" style="max-height:600px; overflow-y:auto;">
						<table class="table table-bordered table-hover table-sm osd-table" style="font-size:12px;">
							<thead style="position:sticky; top:0; background:#f8f9fa; z-index:10;">
								<tr>
									<th>Order Sheet</th><th>Item</th><th>Size</th><th>Color</th>
									<th>Order Qty</th><th>Planned Qty</th><th>PCS</th>
									<th colspan="4" class="text-center bg-info text-white">CUTTING</th>
									<th colspan="4" class="text-center bg-warning text-white">STITCHING</th>
									<th colspan="4" class="text-center bg-success text-white">PACKING</th>
								</tr>
								<tr>
									<th></th><th></th><th></th><th></th><th></th><th></th><th></th>
									<th class="bg-info text-white">Total Cutting</th>
									<th class="bg-info text-white">Planned %</th>
									<th class="bg-info text-white">Qty %</th>
									<th class="bg-info text-white">Status</th>
									<th class="bg-warning text-white">Total Stitching</th>
									<th class="bg-warning text-white">Planned %</th>
									<th class="bg-warning text-white">Qty %</th>
									<th class="bg-warning text-white">Status</th>
									<th class="bg-success text-white">Total Packing</th>
									<th class="bg-success text-white">Planned %</th>
									<th class="bg-success text-white">Qty %</th>
									<th class="bg-success text-white">Status</th>
								</tr>
							</thead>
							<tbody class="osd-tbody">
								<tr><td colspan="19" class="text-center text-muted" style="padding:40px;">
									<i class="fa fa-spinner fa-spin fa-2x"></i><br>Loading...
								</td></tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>
		`;
	},

	_setup_filters(frm, $wrapper) {
		this._customer_input = $wrapper.find(".osd-customer-input");
		this._sales_order_input = $wrapper.find(".osd-sales-order-input");
		this._order_sheet_input = $wrapper.find(".osd-order-sheet-input");

		this._customer_input.val(frm.doc.customer || "");
		this._sales_order_input.val(frm.doc.sales_order || "");
		this._order_sheet_input.val(frm.doc.name || "");

		const triggerRefresh = frappe.utils.debounce(() => this._load_data(frm, $wrapper), 250);
		$wrapper.find(".osd-customer-input, .osd-sales-order-input, .osd-order-sheet-input").on("change", triggerRefresh);
		$wrapper.find(".osd-refresh-btn").on("click", () => this._load_data(frm, $wrapper));
	},

	_setup_events($wrapper) {
		const self = this;

		// Search
		$wrapper.on("keyup", ".osd-search-input", function () {
			self._filter_rows($wrapper, $(this).val().toLowerCase());
		});

		// Expand / Collapse all
		$wrapper.on("click", ".osd-expand-btn", () => {
			$wrapper.find("tr.osd-child").show();
			$wrapper.find(".osd-toggle").attr("data-exp", "1").find(".osd-icon").text("▾");
		});
		$wrapper.on("click", ".osd-collapse-btn", () => {
			$wrapper.find("tr.osd-child").hide();
			$wrapper.find(".osd-toggle").attr("data-exp", "0").find(".osd-icon").text("▸");
		});

		// Row toggle
		$wrapper.on("click", ".osd-toggle", function () {
			const key = $(this).attr("data-group");
			const exp = $(this).attr("data-exp") === "1";
			$wrapper.find(`tr.osd-child[data-pg="${key}"]`).toggle(!exp);
			$(this).attr("data-exp", exp ? "0" : "1").find(".osd-icon").text(exp ? "▸" : "▾");
		});

		// Audit drill-down
		$wrapper.on("click", ".osd-audit", function () {
			const audit = $(this).data("audit");
			if (!audit) return;
			frappe.call({
				method: "manufacturing_addon.manufacturing_addon.page.order_tracking.order_tracking.get_stage_voucher_details",
				args: { stage: audit.stage.toLowerCase(), order_sheet: audit.order_sheet, so_item: audit.group_item, bundle_item: audit.bundle_item || "" },
				freeze: true,
				freeze_message: __("Loading details..."),
				callback: (r) => self._show_audit(audit, r.message || {}),
			});
		});
	},

	_load_data(frm, $wrapper) {
		const self = this;
		frappe.call({
			method: "manufacturing_addon.manufacturing_addon.page.order_tracking.order_tracking.get_dashboard_data",
			args: {
				customer: cstr(self._customer_input && self._customer_input.val()).trim() || null,
				sales_order: cstr(self._sales_order_input && self._sales_order_input.val()).trim() || null,
				order_sheet: cstr(self._order_sheet_input && self._order_sheet_input.val()).trim() || frm.doc.name || null,
			},
			freeze: true,
			freeze_message: __("Loading dashboard data..."),
			callback: (r) => {
				if (!r.message) return;
				self._render_summary($wrapper, r.message.summary || {});
				self._render_progress($wrapper, r.message.summary || {});
				self._render_table($wrapper, r.message.details || []);
			},
		});
	},

	_render_summary($wrapper, s) {
		const plannedQty = s.total_planned_qty || s.cutting_planned || 0;
		$wrapper.find(".osd-summary-cards").html(`
			<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
				<div class="card text-white" style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border:none;border-radius:10px;">
					<div class="card-body"><div class="d-flex justify-content-between align-items-center">
						<div><h6 style="opacity:.9;">Total Orders</h6><h2 style="font-weight:700;">${s.total_orders || 0}</h2></div>
						<div style="font-size:40px;opacity:.5;"><i class="fa fa-file-text"></i></div>
					</div></div>
				</div>
			</div>
			<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
				<div class="card text-white" style="background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%);border:none;border-radius:10px;">
					<div class="card-body"><div class="d-flex justify-content-between align-items-center">
						<div><h6 style="opacity:.9;">Total Order Qty</h6><h2 style="font-weight:700;">${this._fmt_num(s.total_order_qty || 0)}</h2></div>
						<div style="font-size:40px;opacity:.5;"><i class="fa fa-cubes"></i></div>
					</div></div>
				</div>
			</div>
			<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
				<div class="card text-white" style="background:linear-gradient(135deg,#7f5af0 0%,#2cb67d 100%);border:none;border-radius:10px;">
					<div class="card-body"><div class="d-flex justify-content-between align-items-center">
						<div><h6 style="opacity:.9;">Total Planned Qty</h6><h2 style="font-weight:700;">${this._fmt_num(plannedQty)}</h2></div>
						<div style="font-size:40px;opacity:.5;"><i class="fa fa-list-ol"></i></div>
					</div></div>
				</div>
			</div>
			<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
				<div class="card text-white" style="background:linear-gradient(135deg,#4facfe 0%,#00f2fe 100%);border:none;border-radius:10px;">
					<div class="card-body"><div class="d-flex justify-content-between align-items-center">
						<div><h6 style="opacity:.9;">Cutting Progress</h6><h2 style="font-weight:700;">${this._fmt_pct(s.cutting_progress || 0)}%</h2></div>
						<div style="font-size:40px;opacity:.5;"><i class="fa fa-scissors"></i></div>
					</div></div>
				</div>
			</div>
			<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
				<div class="card text-white" style="background:linear-gradient(135deg,#f6d365 0%,#fda085 100%);border:none;border-radius:10px;">
					<div class="card-body"><div class="d-flex justify-content-between align-items-center">
						<div><h6 style="opacity:.9;">Stitching Progress</h6><h2 style="font-weight:700;">${this._fmt_pct(s.stitching_progress || 0)}%</h2></div>
						<div style="font-size:40px;opacity:.5;"><i class="fa fa-cogs"></i></div>
					</div></div>
				</div>
			</div>
			<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
				<div class="card text-white" style="background:linear-gradient(135deg,#43e97b 0%,#38f9d7 100%);border:none;border-radius:10px;">
					<div class="card-body"><div class="d-flex justify-content-between align-items-center">
						<div><h6 style="opacity:.9;">Packing Progress</h6><h2 style="font-weight:700;">${this._fmt_pct(s.packing_progress || 0)}%</h2></div>
						<div style="font-size:40px;opacity:.5;"><i class="fa fa-archive"></i></div>
					</div></div>
				</div>
			</div>
		`);
	},

	_render_progress($wrapper, s) {
		const bar = (label, pct, fin, planned, cls) => `
			<div class="col-md-6 mb-3">
				<div style="background:#f8f9fa;padding:15px;border-radius:8px;">
					<h6 style="color:#495057;margin-bottom:15px;">${label}</h6>
					<div class="progress" style="height:30px;border-radius:15px;">
						<div class="progress-bar ${cls}" role="progressbar" style="width:${Math.min(pct,100)}%;line-height:30px;font-weight:600;">
							${this._fmt_pct(pct)}%
						</div>
					</div>
					<div class="mt-2" style="font-size:12px;color:#6c757d;">
						Finished: ${this._fmt_num(fin)} / Planned: ${this._fmt_num(planned)}
					</div>
				</div>
			</div>`;
		$wrapper.find(".osd-progress-charts").html(
			bar("Cutting Progress", s.cutting_progress || 0, s.cutting_finished || 0, s.cutting_planned || 0, "bg-info") +
			bar("Stitching Progress", s.stitching_progress || 0, s.stitching_finished || 0, s.stitching_planned || 0, "bg-warning") +
			bar("Packing Progress", s.packing_progress || 0, s.packing_finished || 0, s.packing_planned || 0, "bg-success") +
			`<div class="col-md-6 mb-3">
				<div style="background:#f8f9fa;padding:15px;border-radius:8px;">
					<h6 style="color:#495057;margin-bottom:15px;">Overall Progress</h6>
					<div class="progress" style="height:30px;border-radius:15px;">
						<div class="progress-bar" role="progressbar" style="width:${Math.min(s.overall_progress||0,100)}%;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);line-height:30px;font-weight:600;">
							${this._fmt_pct(s.overall_progress || 0)}%
						</div>
					</div>
					<div class="mt-2" style="font-size:12px;color:#6c757d;">
						Complete: ${this._fmt_num(s.packing_finished_finished_items || s.packing_finished || 0)} / Planned: ${this._fmt_num(s.total_planned_qty || 0)}
					</div>
				</div>
			</div>`
		);
	},

	_render_table($wrapper, details) {
		this._originalDetails = details;
		const $tbody = $wrapper.find(".osd-tbody");
		$wrapper.find(".osd-search-input").val("");
		$tbody.empty();

		if (!details.length) {
			$tbody.html(`<tr><td colspan="19" class="text-center text-muted" style="padding:40px;">
				<i class="fa fa-info-circle fa-2x"></i><br>No data found
			</td></tr>`);
			return;
		}

		const parentQtyMap = {};
		const childCountMap = {};
		details.forEach((r) => {
			const k = `${r.order_sheet}||${r.item}`;
			if (r.is_parent) { parentQtyMap[k] = r.order_qty || 0; childCountMap[k] = 0; }
			else if (r.bundle_item) { childCountMap[k] = (childCountMap[k] || 0) + 1; }
		});

		details.forEach((row) => {
			const isParent = row.is_parent === true;
			const isBundle = !!(row.bundle_item);
			const gk = `${row.order_sheet}||${row.item}`;
			const orderQty = isBundle ? (parentQtyMap[gk] || 0) : (row.order_qty || 0);
			const rowPcs = row.pcs || 1;
			const hasChildren = isParent && (childCountMap[gk] || 0) > 0;
			const canDrillDown = (childCountMap[gk] || 0) > 1;

			// Keep flat rows when parent has only one article.
			if (isBundle && !canDrillDown) return;

			const cFin = row.cutting_finished || 0;
			const sFin = row.stitching_finished || 0;
			const pFin = row.packing_finished || 0;

			const cBase = isParent ? cFin : (cFin / rowPcs);
			const sBase = isParent ? sFin : (sFin / rowPcs);
			const pBase = isParent ? pFin : (pFin / rowPcs);

			const cPlan = isParent ? (row.planned_qty || row.cutting_planned || 0) : (row.cutting_planned || row.planned_qty || 0);
			const sPlan = isParent ? (row.planned_qty || row.stitching_planned || 0) : (row.stitching_planned || row.planned_qty || 0);
			const pPlan = row.planned_qty || row.packing_planned || 0;

			const cPlanPct = cPlan > 0 ? (cBase / cPlan * 100) : 0;
			const cQtyPct  = orderQty > 0 ? (cBase / orderQty * 100) : 0;
			const sPlanPct = sPlan > 0 ? (sBase / sPlan * 100) : 0;
			const sQtyPct  = orderQty > 0 ? (sBase / orderQty * 100) : 0;
			const pPlanPct = pPlan > 0 ? (pBase / pPlan * 100) : 0;
			const pQtyPct  = orderQty > 0 ? (pBase / orderQty * 100) : 0;

			let itemCell = row.item || "";
			if (isBundle) {
				itemCell = `  └─ ${row.bundle_item}`;
			} else if (hasChildren && canDrillDown) {
				itemCell = `<span class="osd-toggle" data-group="${gk}" data-exp="0" style="cursor:pointer;user-select:none;">
					<span class="osd-icon">▸</span> ${itemCell}
				</span>`;
			}

			const auditData = (stage) => JSON.stringify({
				stage, order_sheet: row.order_sheet || "", group_item: row.item || "",
				bundle_item: row.bundle_item || "", item: row.bundle_item || row.item || "",
				order_qty: orderQty, planned_qty: stage === "Cutting" ? cPlan : stage === "Stitching" ? sPlan : pPlan,
				total_qty: stage === "Cutting" ? cFin : stage === "Stitching" ? sFin : pFin,
				base_qty: stage === "Cutting" ? cBase : stage === "Stitching" ? sBase : pBase,
				qty_percent: stage === "Cutting" ? cQtyPct : stage === "Stitching" ? sQtyPct : pQtyPct,
				planned_percent: stage === "Cutting" ? cPlanPct : stage === "Stitching" ? sPlanPct : pPlanPct,
				pcs: rowPcs, is_bundle_item: isBundle,
			});

			const ic = isBundle ? "" : "bg-info text-white";
			const wc = isBundle ? "" : "bg-warning text-white";
			const gc = isBundle ? "" : "bg-success text-white";
			const auditStyle = "cursor:pointer;text-decoration:underline;";
			const auditEnabled = !isBundle && canDrillDown;

			const $tr = $(`
				<tr class="${isParent ? "font-weight-bold" : ""} ${isBundle ? "osd-child" : "osd-parent"}"
					data-pg="${gk}"
					style="${isParent ? "background:#f8f9fa;" : ""}${isBundle ? "display:none;" : ""}">
					<td>${isBundle ? "" : (row.order_sheet || "")}</td>
					<td>${itemCell}</td>
					<td>${isBundle ? "" : (row.size || "")}</td>
					<td>${isBundle ? "" : (row.color || "")}</td>
					<td class="text-right">${isBundle ? "" : this._fmt_num(row.order_qty || 0)}</td>
					<td class="text-right">${isBundle ? "" : this._fmt_num(row.planned_qty || 0)}</td>
					<td class="text-right">${this._fmt_num(rowPcs)}</td>
					<td class="text-right ${ic} ${auditEnabled ? "osd-audit" : ""}" style="${auditEnabled ? auditStyle : ""}">${this._fmt_num(cFin)}</td>
					<td class="text-right ${ic}">${this._fmt_pct(cPlanPct)}%</td>
					<td class="text-right ${ic}">${this._fmt_pct(cQtyPct)}%</td>
					<td class="text-center ${ic}">${this._badge(cQtyPct)}</td>
					<td class="text-right ${wc} ${auditEnabled ? "osd-audit" : ""}" style="${auditEnabled ? auditStyle : ""}">${this._fmt_num(sFin)}</td>
					<td class="text-right ${wc}">${this._fmt_pct(sPlanPct)}%</td>
					<td class="text-right ${wc}">${this._fmt_pct(sQtyPct)}%</td>
					<td class="text-center ${wc}">${this._badge(sQtyPct)}</td>
					<td class="text-right ${gc} ${auditEnabled ? "osd-audit" : ""}" style="${auditEnabled ? auditStyle : ""}">${isBundle ? "-" : this._fmt_num(pFin)}</td>
					<td class="text-right ${gc}">${isBundle ? "-" : this._fmt_pct(pPlanPct) + "%"}</td>
					<td class="text-right ${gc}">${isBundle ? "-" : this._fmt_pct(pQtyPct) + "%"}</td>
					<td class="text-center ${gc}">${isBundle ? "-" : this._badge(pQtyPct)}</td>
				</tr>
			`);

			// Attach audit data only when drill-down is allowed (2+ articles).
			if (auditEnabled) {
				$tr.find(".osd-audit").eq(0).data("audit", JSON.parse(auditData("Cutting")));
				$tr.find(".osd-audit").eq(1).data("audit", JSON.parse(auditData("Stitching")));
				$tr.find(".osd-audit").eq(2).data("audit", JSON.parse(auditData("Packing")));
			}

			$tbody.append($tr);
		});
	},

	_filter_rows($wrapper, term) {
		const $rows = $wrapper.find(".osd-tbody tr").not(".osd-no-results");
		if (!term) {
			$wrapper.find(".osd-tbody tr.osd-no-results").remove();
			$rows.show();
			$wrapper.find("tr.osd-child").hide();
			$wrapper.find(".osd-toggle").attr("data-exp", "0").find(".osd-icon").text("▸");
			return;
		}
		let count = 0;
		$rows.hide();
		$rows.each(function () {
			const $r = $(this);
			if ($r.text().toLowerCase().includes(term)) {
				$r.show(); count++;
				if ($r.hasClass("osd-child")) {
					const pg = $r.attr("data-pg");
					$wrapper.find(`tr.osd-parent[data-pg="${pg}"]`).show();
					$wrapper.find(`.osd-toggle[data-group="${pg}"]`).attr("data-exp", "1").find(".osd-icon").text("▾");
				}
				if ($r.hasClass("osd-parent")) {
					const pg = $r.attr("data-pg");
					$wrapper.find(`tr.osd-child[data-pg="${pg}"]`).show();
					count += $wrapper.find(`tr.osd-child[data-pg="${pg}"]`).length;
				}
			}
		});
		$wrapper.find(".osd-tbody tr.osd-no-results").remove();
		if (!count) {
			$wrapper.find(".osd-tbody").append(
				`<tr class="osd-no-results"><td colspan="19" class="text-center text-muted" style="padding:40px;">No results for "${term}"</td></tr>`
			);
		}
	},

	_show_audit(audit, vd) {
		const self = this;
		const label = audit.is_bundle_item ? `${audit.item} (Bundle Item)` : audit.item;
		const auditRows = self._get_audit_rows(audit);
		const rowsHtml = auditRows.length
			? auditRows.map((r) => `<tr>
				<td>${frappe.utils.escape_html(r.item_label)}</td>
				<td class="text-right">${self._fmt_num(r.pcs)}</td>
				<td class="text-right">${self._fmt_num(r.order_qty)}</td>
				<td class="text-right">${self._fmt_num(r.planned_qty)}</td>
				<td class="text-right">${self._fmt_num(r.total_qty)}</td>
				<td class="text-right">${self._fmt_num(r.base_qty)}</td>
				<td class="text-right">${self._fmt_pct(r.planned_percent)}%</td>
				<td class="text-right">${self._fmt_pct(r.qty_percent)}%</td>
			</tr>`).join("")
			: `<tr><td colspan="8" class="text-center text-muted">${__("No rows found")}</td></tr>`;

		const vRows = vd.rows || [];
		const grouped = vRows.reduce((acc, r) => {
			const k = r.combo_item || r.so_item || "Unknown";
			(acc[k] = acc[k] || []).push(r);
			return acc;
		}, {});
		const vHtml = vRows.length
			? Object.entries(grouped).map(([item, rows]) => {
				const total = rows.reduce((s, r) => s + Number(r.qty || 0), 0);
				return `<div style="margin-top:12px;">
					<h6 style="margin:0 0 6px;">${__("Against Item")}: ${frappe.utils.escape_html(item)}</h6>
					<table class="table table-bordered" style="margin:0;font-size:12px;">
						<thead><tr><th>${__("Voucher")}</th><th>${__("Child Row")}</th><th class="text-right">${__("Qty")}</th></tr></thead>
						<tbody>
							${rows.map((r) => `<tr>
								<td><a href="/app/${encodeURIComponent(vd.parent_doctype || "")}/${encodeURIComponent(r.voucher || "")}" target="_blank">${frappe.utils.escape_html(r.voucher || "")}</a></td>
								<td>${frappe.utils.escape_html(r.child_row_name || "")}</td>
								<td class="text-right">${self._fmt_num(r.qty || 0)}</td>
							</tr>`).join("")}
							<tr style="font-weight:600;background:#f8fafc;"><td colspan="2">${__("Total")}</td><td class="text-right">${self._fmt_num(total)}</td></tr>
						</tbody>
					</table>
				</div>`;
			}).join("")
			: `<table class="table table-bordered" style="font-size:12px;"><tbody><tr><td class="text-center text-muted">${__("No voucher rows found")}</td></tr></tbody></table>`;

		const grandTotal = vRows.reduce((s, r) => s + Number(r.qty || 0), 0);

		frappe.msgprint({
			title: __(`${audit.stage} Audit Drill-Down`),
			wide: true,
			message: `
				<table class="table table-bordered" style="font-size:12px;">
					<tr><th style="width:180px;">${__("Order Sheet")}</th><td>${frappe.utils.escape_html(audit.order_sheet || "")}</td></tr>
					<tr><th>${__("Item")}</th><td>${frappe.utils.escape_html(label || "")}</td></tr>
					<tr><th>${__("PCS")}</th><td>${self._fmt_num(audit.pcs || 0)}</td></tr>
					<tr><th>${__("Order Qty")}</th><td>${self._fmt_num(audit.order_qty || 0)}</td></tr>
					<tr><th>${__("Planned Qty")}</th><td>${self._fmt_num(audit.planned_qty || 0)}</td></tr>
					<tr><th>${__("Total Qty")}</th><td>${self._fmt_num(audit.total_qty || 0)}</td></tr>
					<tr><th>${__("Base Qty For %")}</th><td>${self._fmt_num(audit.base_qty || 0)}</td></tr>
					<tr><th>${__("Planned %")}</th><td>${self._fmt_pct(audit.planned_percent || 0)}%</td></tr>
					<tr><th>${__("Qty %")}</th><td>${self._fmt_pct(audit.qty_percent || 0)}%</td></tr>
				</table>
				<div style="margin-top:16px;">
					<h5>${__("Row-wise Data")}</h5>
					<table class="table table-bordered" style="font-size:12px;">
						<thead><tr>
							<th>${__("Row")}</th><th class="text-right">${__("PCS")}</th><th class="text-right">${__("Order Qty")}</th>
							<th class="text-right">${__("Planned Qty")}</th><th class="text-right">${__("Total Qty")}</th>
							<th class="text-right">${__("Base Qty")}</th><th class="text-right">${__("Planned %")}</th><th class="text-right">${__("Qty %")}</th>
						</tr></thead>
						<tbody>${rowsHtml}</tbody>
					</table>
				</div>
				<div style="margin-top:16px;">
					<h5>${__("Voucher-wise Source Rows")}</h5>
					${vHtml}
					${vRows.length ? `<table class="table table-bordered" style="margin-top:12px;font-size:12px;"><tbody>
						<tr style="font-weight:600;background:#eef2ff;"><td colspan="2">${__("Grand Total")}</td><td class="text-right">${self._fmt_num(grandTotal)}</td></tr>
					</tbody></table>` : ""}
				</div>`,
		});
	},

	_get_audit_rows(audit) {
		const parentQtyMap = {};
		(this._originalDetails || []).forEach((r) => {
			if (r.is_parent) parentQtyMap[`${r.order_sheet}||${r.item}`] = r.order_qty || 0;
		});
		return (this._originalDetails || [])
			.filter((r) => {
				if ((r.order_sheet || "") !== audit.order_sheet) return false;
				if ((r.item || "") !== audit.group_item) return false;
				return audit.bundle_item ? (r.bundle_item || "") === audit.bundle_item : true;
			})
			.map((r) => {
				const isParent = r.is_parent === true;
				const isBundle = !!(r.bundle_item);
				const pcs = r.pcs || 1;
				const orderQty = isBundle ? (parentQtyMap[`${r.order_sheet}||${r.item}`] || 0) : (r.order_qty || 0);
				let total = 0, planned = 0, base = 0;
				if (audit.stage === "Cutting") {
					total = r.cutting_finished || 0;
					planned = isParent ? (r.planned_qty || r.cutting_planned || 0) : (r.cutting_planned || r.planned_qty || 0);
					base = isParent ? total : (total / pcs);
				} else if (audit.stage === "Stitching") {
					total = r.stitching_finished || 0;
					planned = isParent ? (r.planned_qty || r.stitching_planned || 0) : (r.stitching_planned || r.planned_qty || 0);
					base = isParent ? total : (total / pcs);
				} else {
					total = r.packing_finished || 0;
					planned = r.planned_qty || r.packing_planned || 0;
					base = isParent ? total : (total / pcs);
				}
				return {
					item_label: isBundle ? `└─ ${r.bundle_item}` : (r.item || ""),
					pcs, order_qty: orderQty, planned_qty: planned, total_qty: total, base_qty: base,
					planned_percent: planned > 0 ? (base / planned * 100) : 0,
					qty_percent: orderQty > 0 ? (base / orderQty * 100) : 0,
				};
			});
	},

	_badge(pct) {
		if (pct >= 100) return `<span class="badge badge-success" style="background:#28a745;">Complete (${this._fmt_pct(pct)}%)</span>`;
		if (pct >= 75) return `<span class="badge badge-info">In Progress</span>`;
		if (pct > 0) return `<span class="badge badge-warning">Started</span>`;
		return `<span class="badge badge-secondary">Not Started</span>`;
	},

	_fmt_num(n) { return n == null ? "0" : parseFloat(n).toLocaleString("en-US", { maximumFractionDigits: 0 }); },
	_fmt_pct(n) { return n == null ? "0" : parseFloat(n).toFixed(1); },

	// legacy stubs kept so old references don't throw
	get_layout_html() { return this._get_layout_html(); },
	setup_filters(frm, w) { return this._setup_filters(frm, w); },
	setup_search(w) {},
	load_data(frm, w) { return this._load_data(frm, w); },
	render_dashboard(w, d) {},
	render_summary_cards(w, s) { return this._render_summary(w, s); },
	render_progress_charts(w, s) { return this._render_progress(w, s); },
	render_detailed_table(w, d) { return this._render_table(w, d); },
	filter_table_rows(w, t) { return this._filter_rows(w, t); },
	get_status_badge(p) { return this._badge(p); },
	format_number(n) { return this._fmt_num(n); },
	format_percentage(n) { return this._fmt_pct(n); },
};

const orderSheetContractorDashboard = {
	bind_tab_refresh(frm) {
		if (frm._cp_contractor_tab_bound) return;
		frm._cp_contractor_tab_bound = true;
		const tabField = "contractor_dashbaord_tab";
		frm.$wrapper.on("shown.bs.tab", `.nav-link[data-fieldname="${tabField}"]`, () => {
			orderSheetContractorDashboard.render(frm);
		});
	},

	render(frm) {
		const $wrapper = frm.fields_dict.contractor_dasbhaord?.$wrapper;
		if (!$wrapper) return;

		if (!frm.doc.name || frm.doc.__islocal) {
			$wrapper.html(
				`<div class="text-muted text-center p-4">${__("Save the document to load the contractor dashboard.")}</div>`
			);
			return;
		}

		if (!manufacturing_addon.contractor_performance?.render_panel) {
			$wrapper.html(
				`<div class="alert alert-warning">${__("Contractor dashboard script not loaded. Run bench build.")}</div>`
			);
			return;
		}

		manufacturing_addon.contractor_performance.render_panel($wrapper, {
			order_sheet: frm.doc.name,
			customer: frm.doc.customer,
			title: __("Contractor performance"),
			show_filters: false,
			all_dates: true,
		});
	},
};

function loadOrderSheetQualityChartJS() {
	return frappe.require([
		"/assets/quality_addon/js/chart.min.js",
		"/assets/quality_addon/js/quality_chartjs.js",
	]).then(() => {
		if (typeof quality_addon !== "undefined" && quality_addon.chartjs) {
			return quality_addon.chartjs.load();
		}
		if (typeof Chart !== "undefined") {
			return Chart;
		}
		throw new Error("Chart.js not available");
	});
}

function osQualityCreateChart(key, canvasId, config) {
	const helper = typeof quality_addon !== "undefined" ? quality_addon.chartjs : null;
	if (helper) {
		return helper.create(key, canvasId, config);
	}
	const canvas = document.getElementById(canvasId);
	if (!canvas || typeof Chart === "undefined") {
		return null;
	}
	return new Chart(canvas.getContext("2d"), config);
}

function osQualityDestroyCharts() {
	const helper = typeof quality_addon !== "undefined" ? quality_addon.chartjs : null;
	if (helper && helper.instances) {
		Object.keys(helper.instances).forEach((key) => {
			if (key.startsWith("osQ_")) {
				helper.destroy(key);
			}
		});
	}
}

function osQualityScheduleCharts(fn) {
	requestAnimationFrame(() => {
		setTimeout(fn, 120);
	});
}

function osQualitySumDefects(defects) {
	return Object.values(defects || {}).reduce((s, v) => s + (Number(v) || 0), 0);
}

function osQualityDefectLabel(key) {
	return (key || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function osQualityInjectDashStyles() {
	if (document.getElementById("os-quality-dash-styles")) {
		return;
	}
	const style = document.createElement("style");
	style.id = "os-quality-dash-styles";
	style.textContent = `
		.os-order-sheet-quality.daily-stitching-dashboard { padding: 12px 4px 20px; }
		.os-order-sheet-quality .summary-card { border: none; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,.1); margin-bottom: 16px; transition: transform .2s; }
		.os-order-sheet-quality .summary-card:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,.12); }
		.os-order-sheet-quality .summary-card .card-body { padding: 18px; }
		.os-order-sheet-quality .summary-card .card-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
		.os-order-sheet-quality .summary-card h3 { font-size: 26px; font-weight: 700; margin: 0; }
		.os-order-sheet-quality .gradient-header { background: linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:#fff; border:none; padding:14px 18px; border-radius:10px 10px 0 0; }
		.os-order-sheet-quality .gradient-header h5, .os-order-sheet-quality .gradient-header h6 { margin:0; font-weight:600; }
		.os-order-sheet-quality .gradient-header-success { background: linear-gradient(135deg,#4facfe 0%,#00f2fe 100%); color:#fff; }
		.os-order-sheet-quality .gradient-header-warning { background: linear-gradient(135deg,#fa709a 0%,#fee140 100%); color:#fff; }
		.os-order-sheet-quality .gradient-header-info { background: linear-gradient(135deg,#a8edea 0%,#fed6e3 100%); color:#333; }
		.os-order-sheet-quality .gradient-header-danger { background: linear-gradient(135deg,#ff9a9e 0%,#fecfef 100%); color:#333; }
		.os-order-sheet-quality .card { border:none; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,.1); margin-bottom:20px; }
		.os-order-sheet-quality .chart-container { position:relative; height:260px; width:100%; background:#fff; padding:12px; border-radius:0 0 10px 10px; }
		.os-order-sheet-quality .chart-container--sm { height:220px; }
		.os-order-sheet-quality .chart-container canvas { display:block!important; width:100%!important; height:100%!important; }
		.os-order-sheet-quality .defect-breakdown-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr)); gap:12px; }
		.os-order-sheet-quality .defect-item { background:#f8f9fa; padding:12px; border-radius:8px; text-align:center; border:1px solid #e9ecef; }
		.os-order-sheet-quality .defect-item .defect-count { font-size:22px; font-weight:700; color:#dc3545; }
		.os-order-sheet-quality .os-q-empty-chart { display:flex; align-items:center; justify-content:center; height:100%; color:#6c757d; font-size:13px; text-align:center; padding:16px; }
		.os-order-sheet-quality .dashboard-table .table thead th { background:#f8f9fa; font-weight:600; }
		.os-order-sheet-quality .os-q-op-worst { background:#f8d7da !important; }
		.os-order-sheet-quality .os-q-op-high { background:#fff3cd !important; }
		.os-order-sheet-quality .os-q-op-badge-worst { background:#dc3545; color:#fff; }
		.os-order-sheet-quality .os-q-op-badge-high { background:#ffc107; color:#333; }
		.os-order-sheet-quality .os-q-op-badge-ok { background:#28a745; color:#fff; }
		.os-order-sheet-quality .os-q-inspection-totals td { font-weight:600; }
		.os-order-sheet-quality .chart-container.chart-sm { height:220px; }
		.os-order-sheet-quality .qd-op-worst, .os-order-sheet-quality .os-q-op-worst { background:#f8d7da !important; }
		.os-order-sheet-quality .qd-op-high, .os-order-sheet-quality .os-q-op-high { background:#fff3cd !important; }
		.os-order-sheet-quality .qd-badge-worst, .os-order-sheet-quality .os-q-op-badge-worst { background:#dc3545; color:#fff; }
		.os-order-sheet-quality .qd-badge-high, .os-order-sheet-quality .os-q-op-badge-high { background:#ffc107; color:#333; }
		.os-order-sheet-quality .qd-badge-ok, .os-order-sheet-quality .os-q-op-badge-ok { background:#28a745; color:#fff; }
	`;
	document.head.appendChild(style);
}

const qualityDashboardInForm = {
	render(frm) {
		const $wrapper = frm.fields_dict.quality_dashboard?.$wrapper;
		if (!$wrapper) return;

		osQualityInjectDashStyles();

		if (!frm.doc.name || frm.doc.__islocal) {
			$wrapper.html(`<div class="text-muted text-center p-4">${__("Save the document to load the quality dashboard.")}</div>`);
			return;
		}

		$wrapper.html(`
			<div class="daily-stitching-dashboard os-order-sheet-quality">
				<div class="text-center text-muted p-4"><i class="fa fa-spinner fa-spin"></i> ${__("Loading quality dashboard...")}</div>
			</div>
		`);

		loadOrderSheetQualityChartJS()
			.then(() => this.load(frm, $wrapper))
			.catch(() => {
				$wrapper.html(`<div class="alert alert-warning">${__("Could not load Chart.js.")}</div>`);
			});
	},

	load(frm, $wrapper) {
		frappe.call({
			method: "quality_addon.api.order_sheet_quality_dashboard.get_order_sheet_quality_dashboard",
			args: { order_sheet: frm.doc.name },
			callback: (r) => this.render_dashboard(frm, $wrapper, r.message || {}),
			error: () => {
				$wrapper.html(`<div class="alert alert-danger">${__("Failed to load quality dashboard.")}</div>`);
			},
		});
	},

	summary_card(title, value, icon, colorClass, sub) {
		return `
			<div class="col-md-2 col-sm-4 col-xs-6">
				<div class="card summary-card">
					<div class="card-body">
						<div class="d-flex justify-content-between">
							<div>
								<h6 class="card-title text-muted">${title}</h6>
								<h3 class="mb-0 ${colorClass || ""}">${value}</h3>
								${sub ? `<small class="text-muted">${sub}</small>` : ""}
							</div>
							<div class="align-self-center"><i class="fa ${icon} fa-2x ${colorClass || "text-primary"}"></i></div>
						</div>
					</div>
				</div>
			</div>
		`;
	},

	render_inspection_summary_table(ins) {
		const bySrc = ins.by_source || {};
		const rows = [
			["Daily Checking", bySrc["Daily Checking"] || {}],
			["Inline Stitching", bySrc["Inline Stitching"] || {}],
			["Final Inspection", bySrc["Final Inspection"] || {}],
		];
		return `
			<table class="table table-bordered table-sm os-q-inspection-totals mb-0">
				<thead>
					<tr>
						<th>${__("Source")}</th>
						<th class="text-right">${__("Pcs Checked")}</th>
						<th class="text-right">${__("Major")}</th>
						<th class="text-right">${__("Minor")}</th>
						<th class="text-right">${__("Critical")}</th>
						<th class="text-right">${__("Total Defects")}</th>
						<th class="text-right">${__("Defect %")}</th>
					</tr>
				</thead>
				<tbody>
					${rows.map(([label, r]) => {
						const pcs = Number(r.pcs_checked) || 0;
						const def = Number(r.defect_qty) || 0;
						const rate = pcs ? (def / pcs * 100).toFixed(1) : "0.0";
						return `<tr>
							<td>${frappe.utils.escape_html(label)}</td>
							<td class="text-right">${this.fmt(pcs)}</td>
							<td class="text-right text-danger">${this.fmt(r.major)}</td>
							<td class="text-right text-warning">${this.fmt(r.minor)}</td>
							<td class="text-right">${this.fmt(r.critical)}</td>
							<td class="text-right">${this.fmt(def)}</td>
							<td class="text-right">${rate}%</td>
						</tr>`;
					}).join("")}
					<tr style="background:#f0f4ff;font-weight:700;">
						<td>${__("Grand Total")}</td>
						<td class="text-right">${this.fmt(ins.pcs_checked)}</td>
						<td class="text-right text-danger">${this.fmt(ins.major)}</td>
						<td class="text-right text-warning">${this.fmt(ins.minor)}</td>
						<td class="text-right">${this.fmt(ins.critical)}</td>
						<td class="text-right">${this.fmt(ins.total_defects)}</td>
						<td class="text-right">${this.pct(ins.defect_rate)}%</td>
					</tr>
				</tbody>
			</table>
		`;
	},

	render_operator_table(opData, worstName) {
		const operators = opData.operators || [];
		if (!operators.length) {
			return `<p class="text-muted text-center mb-0" style="padding:16px;">${__(
				"No operator or checker data for this order sheet. Inline Stitching uses Operator Name; Daily Checking uses Checker Name."
			)}</p>`;
		}
		return `
			${worstName ? `<div class="alert alert-danger py-2 mb-3"><i class="fa fa-exclamation-triangle"></i> <strong>${__("Worst performer")}:</strong> ${frappe.utils.escape_html(worstName)} — ${__("highest defect rate in this order sheet.")}</div>` : ""}
			<table class="table table-bordered table-sm table-hover mb-0">
				<thead>
					<tr>
						<th>${__("Rank")}</th>
						<th>${__("Operator / Checker")}</th>
						<th>${__("Source")}</th>
						<th class="text-right">${__("Pcs Checked")}</th>
						<th class="text-right">${__("Major")}</th>
						<th class="text-right">${__("Minor")}</th>
						<th class="text-right">${__("Critical")}</th>
						<th class="text-right">${__("Total Defects")}</th>
						<th class="text-right">${__("Defect %")}</th>
						<th class="text-center">${__("Status")}</th>
					</tr>
				</thead>
				<tbody>
					${operators.map((op) => {
						const sk = op.status_key || "ok";
						const rowCls = sk === "worst" ? "os-q-op-worst" : (sk === "high" ? "os-q-op-high" : "");
						let badgeCls = "os-q-op-badge-ok";
						if (sk === "worst") badgeCls = "os-q-op-badge-worst";
						else if (sk === "high") badgeCls = "os-q-op-badge-high";
						else if (sk === "watch") badgeCls = "badge badge-warning";
						return `<tr class="${rowCls}">
							<td class="text-center">${op.rank}</td>
							<td><strong>${frappe.utils.escape_html(op.operator)}</strong></td>
							<td><small>${frappe.utils.escape_html(op.sources)}</small></td>
							<td class="text-right">${this.fmt(op.pcs_checked)}</td>
							<td class="text-right">${this.fmt(op.major)}</td>
							<td class="text-right">${this.fmt(op.minor)}</td>
							<td class="text-right">${this.fmt(op.critical)}</td>
							<td class="text-right"><strong>${this.fmt(op.defect_qty)}</strong></td>
							<td class="text-right"><strong>${this.pct(op.defect_rate)}%</strong></td>
							<td class="text-center"><span class="badge ${badgeCls}" style="font-size:11px;">${frappe.utils.escape_html(op.status)}</span></td>
						</tr>`;
					}).join("")}
				</tbody>
			</table>
		`;
	},

	defect_items_grid(defects, total) {
		const keys = Object.keys(defects || {}).filter((k) => defects[k] > 0);
		if (!keys.length) {
			return `<p class="text-muted text-center mb-0">${__("No defects recorded.")}</p>`;
		}
		return `<div class="defect-breakdown-grid">${keys.map((key) => {
			const pct = total > 0 ? (defects[key] / total * 100).toFixed(1) : 0;
			return `
				<div class="defect-item">
					<h6>${osQualityDefectLabel(key)}</h6>
					<div class="defect-count">${this.fmt(defects[key])}</div>
					<small class="text-muted">${pct}%</small>
				</div>
			`;
		}).join("")}</div>`;
	},

	render_dashboard(frm, $wrapper, data) {
		const s = data.summary || {};
		const cats = data.defect_categories || {};
		const weaving = cats.weaving || {};
		const finishing = cats.finishing || {};
		const sewing = cats.sewing || {};
		const totals = cats.totals || {};
		const tw = totals.weaving || 0;
		const tf = totals.finishing || 0;
		const ts = totals.sewing || 0;
		const tall = totals.all || 0;
		const details = data.details || [];
		const docs = data.documents || {};
		const ins = data.inspection_summary || {};
		const opData = data.operator_performance || {};
		const hasDocs = (s.daily_checking_count || 0) + (s.inline_stitching_count || 0) + (s.final_inspection_count || 0) > 0;

		$wrapper.html(`
			<div class="daily-stitching-dashboard os-order-sheet-quality">
				<div class="row dashboard-summary">
					${this.summary_card(__("Plan Qty"), this.fmt(s.plan_qty), "fa-calendar-check-o", "text-primary")}
					${this.summary_card(__("Inspected"), this.fmt(s.inspected_qty), "fa-search", "text-info")}
					${this.summary_card(__("Pcs Checked"), this.fmt(ins.pcs_checked), "fa-check-square", "text-primary")}
					${this.summary_card(__("Major"), this.fmt(ins.major), "fa-times-circle", "text-danger")}
					${this.summary_card(__("Minor"), this.fmt(ins.minor), "fa-exclamation-circle", "text-warning")}
					${this.summary_card(__("Critical"), this.fmt(ins.critical), "fa-ban", "text-danger")}
				</div>
				<div class="row dashboard-summary">
					${this.summary_card(__("Total Defects"), this.fmt(ins.total_defects || s.defect_qty), "fa-exclamation-triangle", "text-warning")}
					${this.summary_card(__("Defect Rate"), `${this.pct(ins.defect_rate)}%`, "fa-percent", "text-danger")}
					${this.summary_card(__("Progress"), `${this.pct(s.progress_pct)}%`, "fa-line-chart", "text-success")}
					${this.summary_card(__("Daily Checking"), s.daily_checking_count || 0, "fa-clipboard", "text-primary", __("docs"))}
					${this.summary_card(__("Inline Stitching"), s.inline_stitching_count || 0, "fa-scissors", "text-warning", __("docs"))}
					${this.summary_card(__("Final Inspection"), s.final_inspection_count || 0, "fa-check-square-o", "text-success", __("docs"))}
				</div>

				<div class="row">
					<div class="col-md-12">
						<div class="card dashboard-table">
							<div class="card-header gradient-header">
								<h5><i class="fa fa-table"></i> ${__("Inspection Summary — Pcs Checked & Severity")}</h5>
							</div>
							<div class="card-body table-responsive">
								${this.render_inspection_summary_table(ins)}
							</div>
						</div>
					</div>
				</div>

				<div class="row">
					<div class="col-md-12">
						<div class="card dashboard-table">
							<div class="card-header gradient-header-danger">
								<h5><i class="fa fa-user"></i> ${__("Operator / Checker Performance")} <small style="opacity:.85;font-weight:400;">(${__("worst first")})</small></h5>
							</div>
							<div class="card-body table-responsive" style="max-height:420px;overflow:auto;">
								${this.render_operator_table(opData, opData.worst_operator)}
							</div>
						</div>
					</div>
				</div>

				<div class="row dashboard-charts">
					<div class="col-md-6">
						<div class="card">
							<div class="card-header gradient-header-success">
								<h5><i class="fa fa-pie-chart"></i> ${__("Inspection by Source")}</h5>
							</div>
							<div class="card-body p-0">
								<div class="chart-container" id="os_q_source_pie_wrap"><canvas id="os_q_source_pie"></canvas></div>
							</div>
						</div>
					</div>
					<div class="col-md-6">
						<div class="card">
							<div class="card-header gradient-header">
								<h5><i class="fa fa-bar-chart"></i> ${__("Plan vs Inspected")}</h5>
							</div>
							<div class="card-body p-0">
								<div class="chart-container" id="os_q_plan_wrap"><canvas id="os_q_plan_bar"></canvas></div>
							</div>
						</div>
					</div>
				</div>

				<div class="row">
					<div class="col-md-12">
						<div class="card">
							<div class="card-header gradient-header-warning">
								<h5><i class="fa fa-line-chart"></i> ${__("Quality Activity Trend")}</h5>
							</div>
							<div class="card-body p-0">
								<div class="chart-container" style="height:280px;" id="os_q_trend_wrap"><canvas id="os_q_trend_line"></canvas></div>
							</div>
						</div>
					</div>
				</div>

				<div class="row">
					<div class="col-md-12">
						<div class="card">
							<div class="card-header gradient-header-danger">
								<h5><i class="fa fa-bug"></i> ${__("Detailed Defect Breakdown")}</h5>
							</div>
							<div class="card-body">
								<div class="row mb-4 qa-defect-breakdown-charts">
									<div class="col-md-4">
										<div class="card h-100 border-0 bg-light">
											<div class="card-body">
												<h6 class="text-muted mb-2"><i class="fa fa-pie-chart"></i> ${__("Defects by Category")}</h6>
												<div class="chart-container chart-container--sm" id="os_q_cat_pie_wrap"><canvas id="os_q_category_pie"></canvas></div>
											</div>
										</div>
									</div>
									<div class="col-md-8">
										<div class="card h-100 border-0 bg-light">
											<div class="card-body">
												<h6 class="text-muted mb-2"><i class="fa fa-bar-chart"></i> ${__("Top Defect Types")}</h6>
												<div class="chart-container chart-container--sm" id="os_q_top_wrap"><canvas id="os_q_top_bar"></canvas></div>
											</div>
										</div>
									</div>
								</div>
								<div class="row mb-4">
									<div class="col-md-4">
										<div class="card h-100 border-0 bg-light">
											<div class="card-body">
												<h6 class="text-muted mb-2"><i class="fa fa-th"></i> ${__("Weaving")}</h6>
												<div class="chart-container chart-container--sm" id="os_q_weaving_wrap"><canvas id="os_q_weaving_bar"></canvas></div>
											</div>
										</div>
									</div>
									<div class="col-md-4">
										<div class="card h-100 border-0 bg-light">
											<div class="card-body">
												<h6 class="text-muted mb-2"><i class="fa fa-cog"></i> ${__("Finishing")}</h6>
												<div class="chart-container chart-container--sm" id="os_q_finishing_wrap"><canvas id="os_q_finishing_bar"></canvas></div>
											</div>
										</div>
									</div>
									<div class="col-md-4">
										<div class="card h-100 border-0 bg-light">
											<div class="card-body">
												<h6 class="text-muted mb-2"><i class="fa fa-scissors"></i> ${__("Sewing")}</h6>
												<div class="chart-container chart-container--sm" id="os_q_sewing_wrap"><canvas id="os_q_sewing_bar"></canvas></div>
											</div>
										</div>
									</div>
								</div>
								${!tall ? `<div class="alert alert-info text-center"><i class="fa fa-info-circle"></i> ${__("Link Daily Checking, Inline Stitching, or Final Inspection documents to this Order Sheet to see defect charts.")}</div>` : ""}
								<div class="row">
									<div class="col-md-12 mb-4">
										<div class="card">
											<div class="card-header gradient-header-warning">
												<h6><i class="fa fa-th"></i> ${__("Weaving Defects")} (${tw} — ${tall > 0 ? (tw / tall * 100).toFixed(1) : 0}%)</h6>
											</div>
											<div class="card-body">${this.defect_items_grid(weaving, tw)}</div>
										</div>
									</div>
									<div class="col-md-12 mb-4">
										<div class="card">
											<div class="card-header gradient-header-info">
												<h6><i class="fa fa-cog"></i> ${__("Finishing Defects")} (${tf} — ${tall > 0 ? (tf / tall * 100).toFixed(1) : 0}%)</h6>
											</div>
											<div class="card-body">${this.defect_items_grid(finishing, tf)}</div>
										</div>
									</div>
									<div class="col-md-12 mb-4">
										<div class="card">
											<div class="card-header gradient-header-danger">
												<h6><i class="fa fa-scissors"></i> ${__("Sewing Defects")} (${ts} — ${tall > 0 ? (ts / tall * 100).toFixed(1) : 0}%)</h6>
											</div>
											<div class="card-body">${this.defect_items_grid(sewing, ts)}</div>
										</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>

				<div class="row dashboard-table">
					<div class="col-md-12">
						<div class="card">
							<div class="card-header gradient-header">
								<h5><i class="fa fa-table"></i> ${__("Quality Detail by Article")}</h5>
							</div>
							<div class="card-body table-responsive" style="max-height:380px;">
								${this.render_details_table(details, hasDocs)}
							</div>
						</div>
					</div>
				</div>

				<div class="row">
					${this.render_doc_cards(docs)}
				</div>
			</div>
		`);

		osQualityScheduleCharts(() => this.render_charts(data, s, weaving, finishing, sewing));
	},

	render_details_table(details, hasDocs) {
		if (!details.length) {
			return `<p class="text-muted text-center">${hasDocs
				? __("No article-level rows yet.")
				: __("No quality documents linked. Set Order Sheet on Daily Checking / Inline Stitching / Final Inspection.")}</p>`;
		}
		return `
			<table class="table table-bordered table-sm table-hover">
				<thead><tr>
					<th>${__("Source")}</th><th>${__("Article")}</th><th>${__("Size")}</th><th>${__("Color")}</th>
					<th>${__("Design")}</th><th>${__("Operator")}</th>
					<th class="text-right">${__("Plan")}</th><th class="text-right">${__("Inspected")}</th>
					<th class="text-right">${__("Defects")}</th><th class="text-right">${__("Progress %")}</th>
				</tr></thead>
				<tbody>${details.map((d) => `
					<tr>
						<td>${frappe.utils.escape_html(d.source || "")}</td>
						<td>${frappe.utils.escape_html(d.article || "")}</td>
						<td>${frappe.utils.escape_html(d.size || "")}</td>
						<td>${frappe.utils.escape_html(d.color || "")}</td>
						<td>${frappe.utils.escape_html(d.design_combination || "")}</td>
						<td>${frappe.utils.escape_html(d.operator_name || "—")}</td>
						<td class="text-right">${this.fmt(d.plan_qty)}</td>
						<td class="text-right">${this.fmt(d.inspected_qty)}</td>
						<td class="text-right">${this.fmt(d.defect_qty)}</td>
						<td class="text-right">${this.pct(d.progress_pct)}%</td>
					</tr>
				`).join("")}</tbody>
			</table>
		`;
	},

	render_doc_cards(docs) {
		return Object.keys(docs || {}).map((source) => {
			const list = docs[source] || [];
			const rows = list.length
				? list.map((d) => `<tr>
					<td><a href="${frappe.utils.get_form_link(source, d.name)}">${frappe.utils.escape_html(d.name)}</a></td>
					<td>${frappe.datetime.str_to_user(d.reporting_date) || ""}</td>
				</tr>`).join("")
				: `<tr><td colspan="2" class="text-muted text-center">${__("No documents")}</td></tr>`;
			return `
				<div class="col-md-4">
					<div class="card dashboard-table">
						<div class="card-header gradient-header"><h5>${frappe.utils.escape_html(source)}</h5></div>
						<div class="card-body p-0 table-responsive" style="max-height:200px;">
							<table class="table table-sm mb-0"><thead><tr><th>${__("Name")}</th><th>${__("Date")}</th></tr></thead><tbody>${rows}</tbody></table>
						</div>
					</div>
				</div>
			`;
		}).join("");
	},

	show_empty_chart(wrapId, msg) {
		const el = document.getElementById(wrapId);
		if (el) {
			el.innerHTML = `<div class="os-q-empty-chart">${frappe.utils.escape_html(msg)}</div>`;
		}
	},

	render_bar_entries(canvasId, wrapId, entries, color) {
		if (!entries.length) {
			this.show_empty_chart(wrapId, __("No data"));
			return;
		}
		osQualityCreateChart(`osQ_${canvasId}`, canvasId, {
			type: "bar",
			data: {
				labels: entries.map(([k]) => osQualityDefectLabel(k)),
				datasets: [{
					label: __("Qty"),
					data: entries.map(([, v]) => v),
					backgroundColor: color + "B3",
					borderColor: color,
					borderWidth: 1,
				}],
			},
			options: {
				indexAxis: "y",
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
			},
		});
	},

	render_charts(data, summary, weaving, finishing, sewing) {
		if (typeof Chart === "undefined") return;
		osQualityDestroyCharts();

		const bySource = data.by_source || [];
		const trend = data.trend || {};
		const colors = ["#FF6384", "#36A2EB", "#FFCE56"];
		const sourceLabels = bySource.map((d) => d.source);
		const inspectedVals = bySource.map((d) => Number(d.inspected_qty) || 0);
		const planQty = Number(summary.plan_qty) || 0;
		const inspectedQty = Number(summary.inspected_qty) || 0;

		if (inspectedVals.reduce((a, b) => a + b, 0) > 0) {
			osQualityCreateChart("osQ_sourcePie", "os_q_source_pie", {
				type: "pie",
				data: {
					labels: sourceLabels,
					datasets: [{ data: inspectedVals, backgroundColor: colors, borderColor: "#fff", borderWidth: 2 }],
				},
				options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
			});
		} else {
			this.show_empty_chart("os_q_source_pie_wrap", __("No inspection data"));
		}

		if (planQty > 0 || inspectedQty > 0) {
			osQualityCreateChart("osQ_planBar", "os_q_plan_bar", {
				type: "bar",
				data: {
					labels: [__("Plan Qty"), __("Inspected")],
					datasets: [{
						data: [planQty, inspectedQty],
						backgroundColor: ["#667eea", "#28a745"],
						borderRadius: 6,
					}],
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { display: false } },
					scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
				},
			});
		} else {
			this.show_empty_chart("os_q_plan_wrap", __("No quantities"));
		}

		const tw = osQualitySumDefects(weaving);
		const tf = osQualitySumDefects(finishing);
		const ts = osQualitySumDefects(sewing);
		if (tw + tf + ts > 0) {
			osQualityCreateChart("osQ_categoryPie", "os_q_category_pie", {
				type: "pie",
				data: {
					labels: [__("Weaving"), __("Finishing"), __("Sewing")],
					datasets: [{ data: [tw, tf, ts], backgroundColor: colors, borderColor: "#fff", borderWidth: 2 }],
				},
				options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
			});
		} else {
			this.show_empty_chart("os_q_cat_pie_wrap", __("No defects"));
		}

		const allDefects = [];
		const pushDef = (obj, cat, col) => {
			Object.entries(obj || {}).forEach(([k, v]) => {
				if (v > 0) allDefects.push({ label: `${osQualityDefectLabel(k)} (${cat})`, value: v, color: col });
			});
		};
		pushDef(weaving, "W", colors[0]);
		pushDef(finishing, "F", colors[1]);
		pushDef(sewing, "S", colors[2]);
		allDefects.sort((a, b) => b.value - a.value);
		const top = allDefects.slice(0, 12);
		if (top.length) {
			osQualityCreateChart("osQ_topBar", "os_q_top_bar", {
				type: "bar",
				data: {
					labels: top.map((d) => d.label),
					datasets: [{
						data: top.map((d) => d.value),
						backgroundColor: top.map((d) => d.color + "B3"),
						borderColor: top.map((d) => d.color),
						borderWidth: 1,
					}],
				},
				options: {
					indexAxis: "y",
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { display: false } },
					scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
				},
			});
		} else {
			this.show_empty_chart("os_q_top_wrap", __("No defects"));
		}

		this.render_bar_entries(
			"os_q_weaving_bar",
			"os_q_weaving_wrap",
			Object.entries(weaving).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 8),
			"#FF6384"
		);
		this.render_bar_entries(
			"os_q_finishing_bar",
			"os_q_finishing_wrap",
			Object.entries(finishing).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 8),
			"#36A2EB"
		);
		this.render_bar_entries(
			"os_q_sewing_bar",
			"os_q_sewing_wrap",
			Object.entries(sewing).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 8),
			"#FFCE56"
		);

		const trendLabels = trend.labels || [];
		if (trendLabels.length && (trend.datasets || []).some((ds) => (ds.values || []).some((v) => v > 0))) {
			const palette = ["#667eea", "#ffa00a", "#28a745"];
			osQualityCreateChart("osQ_trendLine", "os_q_trend_line", {
				type: "line",
				data: {
					labels: trendLabels,
					datasets: (trend.datasets || []).map((ds, i) => ({
						label: ds.name,
						data: ds.values || [],
						borderColor: palette[i % palette.length],
						backgroundColor: palette[i % palette.length] + "33",
						fill: true,
						tension: 0.35,
						pointRadius: 3,
					})),
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					interaction: { mode: "index", intersect: false },
					plugins: { legend: { position: "bottom" } },
					scales: {
						y: { beginAtZero: true, ticks: { precision: 0 } },
						x: { ticks: { maxRotation: 45, autoSkip: true, maxTicksLimit: 16 } },
					},
				},
			});
		} else {
			this.show_empty_chart("os_q_trend_wrap", __("No activity yet"));
		}

		const helper = typeof quality_addon !== "undefined" ? quality_addon.chartjs : null;
		if (helper && helper.instances) {
			Object.values(helper.instances).forEach((c) => c.resize && c.resize());
		}
	},

	fmt(n) {
		return (n == null ? 0 : Number(n)).toLocaleString("en-US", { maximumFractionDigits: 2 });
	},

	pct(n) {
		return (n == null ? 0 : Number(n)).toFixed(1);
	},
};

const dailyCheckingDashboardInForm = {
	charts: {},

	render(frm) {
		const $wrapper = frm.fields_dict.daily_checking_dashboard?.$wrapper;
		if (!$wrapper) return;

		osQualityInjectDashStyles();

		if (!frm.doc.name || frm.doc.__islocal) {
			$wrapper.html(
				`<div class="text-muted text-center p-4">${__("Save the document to load the Daily Checking dashboard.")}</div>`
			);
			return;
		}

		$wrapper.html(`
			<div class="daily-stitching-dashboard os-order-sheet-quality os-daily-checking-dash">
				<div class="text-center text-muted p-4"><i class="fa fa-spinner fa-spin"></i> ${__("Loading Daily Checking dashboard...")}</div>
			</div>
		`);

		loadOrderSheetQualityChartJS()
			.then(() => this.load(frm, $wrapper))
			.catch(() => {
				$wrapper.html(
					`<div class="alert alert-warning">${__("Could not load Daily Checking dashboard.")}</div>`
				);
			});
	},

	load(frm, $wrapper) {
		frappe.call({
			method: "quality_addon.api.order_sheet_quality_dashboard.get_order_sheet_daily_checking_dashboard",
			args: { order_sheet: frm.doc.name },
			callback: (r) => this.render_dashboard($wrapper, r.message || {}),
			error: () => {
				$wrapper.html(
					`<div class="alert alert-danger">${__("Failed to load Daily Checking dashboard.")}</div>`
				);
			},
		});
	},

	destroy_charts() {
		Object.keys(this.charts).forEach((key) => {
			try {
				this.charts[key]?.destroy?.();
			} catch (e) {
				/* ignore */
			}
		});
		this.charts = {};
	},

	make_chart(key, canvasId, config) {
		this.charts[key]?.destroy?.();
		const helper = typeof quality_addon !== "undefined" ? quality_addon.chartjs : null;
		if (helper) {
			this.charts[key] = helper.create(key, canvasId, config);
			return;
		}
		const el = document.getElementById(canvasId);
		if (el && typeof Chart !== "undefined") {
			this.charts[key] = new Chart(el.getContext("2d"), config);
		}
	},

	fmt(n) {
		return frappe.format(n || 0, { fieldtype: "Float", precision: 0 });
	},

	pct(n) {
		return (Number(n) || 0).toFixed(1);
	},

	summary_card(title, value, icon, cls, sub) {
		return `
			<div class="col-md-2 col-sm-4 col-xs-6">
				<div class="card summary-card">
					<div class="card-body">
						<div class="d-flex justify-content-between">
							<div>
								<h6 class="card-title text-muted">${title}</h6>
								<h3 class="mb-0 ${cls || ""}">${value}</h3>
								${sub ? `<small class="text-muted">${sub}</small>` : ""}
							</div>
							<div class="align-self-center"><i class="fa ${icon} fa-2x ${cls || "text-primary"}"></i></div>
						</div>
					</div>
				</div>
			</div>`;
	},

	render_person_table(perf) {
		const persons = perf.persons || [];
		if (!persons.length) {
			return `<p class="text-muted text-center p-3">${__("No Daily Checking data for this Order Sheet.")}</p>`;
		}
		const worst = perf.worst_person;
		return `
			${worst ? `<div class="alert alert-danger py-2 mb-2"><strong>${__("Worst Checker")}:</strong> ${frappe.utils.escape_html(worst)}</div>` : ""}
			<table class="table table-bordered table-sm table-hover mb-0">
				<thead><tr>
					<th>#</th><th>${__("Checker")}</th>
					<th class="text-right">${__("Pcs")}</th>
					<th class="text-right">${__("Major")}</th><th class="text-right">${__("Minor")}</th><th class="text-right">${__("Critical")}</th>
					<th class="text-right">${__("Defects")}</th><th class="text-right">${__("Defect %")}</th><th>${__("Status")}</th>
				</tr></thead>
				<tbody>${persons
					.map((p) => {
						const sk = p.status_key || "ok";
						const rowCls = sk === "worst" ? "qd-op-worst" : sk === "high" ? "qd-op-high" : "";
						let badge = "qd-badge-ok";
						if (sk === "worst") badge = "qd-badge-worst";
						else if (sk === "high") badge = "qd-badge-high";
						else if (sk === "watch") badge = "badge badge-warning";
						return `<tr class="${rowCls}">
							<td>${p.rank}</td>
							<td><strong>${frappe.utils.escape_html(p.person)}</strong></td>
							<td class="text-right">${this.fmt(p.pcs_checked)}</td>
							<td class="text-right">${this.fmt(p.major)}</td>
							<td class="text-right">${this.fmt(p.minor)}</td>
							<td class="text-right">${this.fmt(p.critical)}</td>
							<td class="text-right"><strong>${this.fmt(p.defect_qty)}</strong></td>
							<td class="text-right"><strong>${this.pct(p.defect_rate)}%</strong></td>
							<td><span class="badge ${badge}">${frappe.utils.escape_html(p.status)}</span></td>
						</tr>`;
					})
					.join("")}</tbody>
			</table>`;
	},

	render_details_table(details) {
		if (!details.length) {
			return `<p class="text-muted text-center p-3">${__("No detail rows.")}</p>`;
		}
		return `
			<table class="table table-bordered table-sm mb-0" style="font-size:12px;">
				<thead><tr>
					<th>${__("Article")}</th><th>${__("Size")}</th><th>${__("Color")}</th><th>${__("Design")}</th>
					<th class="text-right">${__("Plan Qty")}</th><th class="text-right">${__("Pcs Checked")}</th>
					<th class="text-right">${__("Major")}</th><th class="text-right">${__("Minor")}</th><th class="text-right">${__("Critical")}</th>
					<th class="text-right">${__("Defects")}</th><th class="text-right">${__("Defect %")}</th><th class="text-right">${__("Progress %")}</th>
				</tr></thead>
				<tbody>${details
					.slice(0, 100)
					.map(
						(r) => `<tr>
						<td>${frappe.utils.escape_html(r.article)}</td>
						<td>${frappe.utils.escape_html(r.size)}</td>
						<td>${frappe.utils.escape_html(r.color)}</td>
						<td>${frappe.utils.escape_html(r.design)}</td>
						<td class="text-right">${this.fmt(r.plan_qty)}</td>
						<td class="text-right">${this.fmt(r.pcs_checked)}</td>
						<td class="text-right text-danger">${this.fmt(r.major)}</td>
						<td class="text-right text-warning">${this.fmt(r.minor)}</td>
						<td class="text-right">${this.fmt(r.critical)}</td>
						<td class="text-right">${this.fmt(r.defect_qty)}</td>
						<td class="text-right">${this.pct(r.defect_rate)}%</td>
						<td class="text-right">${this.pct(r.progress_pct)}%</td>
					</tr>`
					)
					.join("")}</tbody>
			</table>`;
	},

	dim_bar(key, canvasId, dimData, datasetLabel, valueKey = "defect_qty") {
		if (!dimData?.labels?.length) return;
		const values = dimData[valueKey] || dimData.defect_qty || [];
		this.make_chart(key, canvasId, {
			type: "bar",
			data: {
				labels: dimData.labels,
				datasets: [{ label: datasetLabel, data: values, backgroundColor: "#667eea" }],
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				scales: { x: { ticks: { maxRotation: 45, minRotation: 0 } } },
			},
		});
	},

	trend_chart(key, canvasId, trend) {
		const t = trend || {};
		if (!t.labels?.length) return;
		this.make_chart(key, canvasId, {
			type: "line",
			data: {
				labels: t.labels,
				datasets: (t.datasets || []).map((ds) => ({
					label: ds.name,
					data: ds.values,
					borderColor: "#4facfe",
					backgroundColor: "transparent",
					tension: 0.3,
				})),
			},
			options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
		});
	},

	render_dashboard($wrapper, data) {
		const s = data.summary || {};
		const perf = data.checker_performance || {};
		const prefix = "os_dc_";
		const $root = $wrapper.find(".os-daily-checking-dash");

		this.destroy_charts();

		$root.html(`
			<div class="d-flex justify-content-between align-items-center mb-3">
				<div>
					<h5 class="mb-0">${__("Daily Checking")}</h5>
					<small class="text-muted">${__("All Daily Checking documents linked to this Order Sheet")}</small>
				</div>
				<button type="button" class="btn btn-default btn-sm" data-action="refresh-dc">${__("Refresh")}</button>
			</div>
			<div class="row">${this.summary_card(__("Pcs Checked"), this.fmt(s.pcs_checked), "fa-check-square", "text-primary")}
				${this.summary_card(__("Major"), this.fmt(s.major), "fa-times-circle", "text-danger")}
				${this.summary_card(__("Minor"), this.fmt(s.minor), "fa-exclamation-circle", "text-warning")}
				${this.summary_card(__("Critical"), this.fmt(s.critical), "fa-ban", "text-danger")}
				${this.summary_card(__("Total Defects"), this.fmt(s.total_defects), "fa-bug", "text-warning")}
				${this.summary_card(__("Defect Rate"), `${this.pct(s.defect_rate)}%`, "fa-percent", "text-danger", `${s.document_count || 0} ${__("docs")}`)}
			</div>
			<div class="row">
				<div class="col-md-6"><div class="card"><div class="card-header gradient-header-success"><h5 class="mb-0">${__("Major vs Minor")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}severity_pie"></canvas></div></div></div></div>
				<div class="col-md-6"><div class="card"><div class="card-header gradient-header-danger"><h5 class="mb-0">${__("Worst Checkers")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}worst_bar"></canvas></div></div></div></div>
			</div>
			<div class="row">
				<div class="col-md-6"><div class="card"><div class="card-header gradient-header"><h5 class="mb-0">${__("Defects by Article")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}article_bar"></canvas></div></div></div></div>
				<div class="col-md-6"><div class="card"><div class="card-header gradient-header"><h5 class="mb-0">${__("Pcs Checked by Size")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}size_bar"></canvas></div></div></div></div>
			</div>
			<div class="row">
				<div class="col-md-6"><div class="card"><div class="card-header gradient-header-info"><h5 class="mb-0">${__("By Color")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}color_bar"></canvas></div></div></div></div>
				<div class="col-md-6"><div class="card"><div class="card-header gradient-header-info"><h5 class="mb-0">${__("Activity Trend")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}trend"></canvas></div></div></div></div>
			</div>
			<div class="row">
				<div class="col-md-5"><div class="card"><div class="card-header gradient-header-danger"><h5 class="mb-0"><i class="fa fa-user"></i> ${__("Checker Performance")}</h5></div>
					<div class="card-body table-responsive" style="max-height:360px;overflow:auto;">${this.render_person_table(perf)}</div></div></div>
				<div class="col-md-7"><div class="card"><div class="card-header gradient-header"><h5 class="mb-0"><i class="fa fa-table"></i> ${__("By Article / Size / Color / Design")}</h5></div>
					<div class="card-body table-responsive" style="max-height:360px;overflow:auto;">${this.render_details_table(data.details || [])}</div></div></div>
			</div>
		`);

		$root.find('[data-action="refresh-dc"]').on("click", () => {
			const frm = $wrapper.closest(".form-page")?.[0]?.cur_frm;
			if (frm) this.render(frm);
		});

		setTimeout(() => {
			this.make_chart(`${prefix}severity`, `${prefix}severity_pie`, {
				type: "pie",
				data: {
					labels: [__("Major"), __("Minor"), __("Critical")],
					datasets: [
						{
							data: [s.major || 0, s.minor || 0, s.critical || 0],
							backgroundColor: ["#dc3545", "#ffc107", "#6c757d"],
						},
					],
				},
				options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
			});

			const topCheckers = (perf.persons || []).slice(0, 8).reverse();
			if (topCheckers.length) {
				this.make_chart(`${prefix}worst`, `${prefix}worst_bar`, {
					type: "bar",
					data: {
						labels: topCheckers.map((p) => p.person),
						datasets: [{ label: __("Defects"), data: topCheckers.map((p) => p.defect_qty), backgroundColor: "#dc3545" }],
					},
					options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
				});
			}

			this.dim_bar(`${prefix}article`, `${prefix}article_bar`, data.by_article, __("Defects"));
			this.dim_bar(`${prefix}size`, `${prefix}size_bar`, data.by_size, __("Pcs Checked"), "pcs_checked");
			this.dim_bar(`${prefix}color`, `${prefix}color_bar`, data.by_color, __("Defects"));
			this.trend_chart(`${prefix}trend`, `${prefix}trend`, data.trend);

			const helper = typeof quality_addon !== "undefined" ? quality_addon.chartjs : null;
			if (helper?.instances) {
				Object.values(helper.instances).forEach((c) => c.resize && c.resize());
			}
		}, 80);
	},
};

const inlineStitchingDashboardInForm = {
	charts: {},

	render(frm) {
		const $wrapper = frm.fields_dict.inline_stitching_dashboard?.$wrapper;
		if (!$wrapper) return;

		osQualityInjectDashStyles();

		if (!frm.doc.name || frm.doc.__islocal) {
			$wrapper.html(
				`<div class="text-muted text-center p-4">${__("Save the document to load the Inline Stitching dashboard.")}</div>`
			);
			return;
		}

		$wrapper.html(`
			<div class="daily-stitching-dashboard os-order-sheet-quality os-inline-stitching-dash">
				<div class="text-center text-muted p-4"><i class="fa fa-spinner fa-spin"></i> ${__("Loading Inline Stitching dashboard...")}</div>
			</div>
		`);

		loadOrderSheetQualityChartJS()
			.then(() => this.load(frm, $wrapper))
			.catch(() => {
				$wrapper.html(
					`<div class="alert alert-warning">${__("Could not load Inline Stitching dashboard.")}</div>`
				);
			});
	},

	load(frm, $wrapper) {
		frappe.call({
			method: "quality_addon.api.order_sheet_quality_dashboard.get_order_sheet_inline_stitching_dashboard",
			args: { order_sheet: frm.doc.name },
			callback: (r) => this.render_dashboard($wrapper, r.message || {}),
			error: () => {
				$wrapper.html(
					`<div class="alert alert-danger">${__("Failed to load Inline Stitching dashboard.")}</div>`
				);
			},
		});
	},

	destroy_charts() {
		Object.keys(this.charts).forEach((key) => {
			try {
				this.charts[key]?.destroy?.();
			} catch (e) {
				/* ignore */
			}
		});
		this.charts = {};
	},

	make_chart(key, canvasId, config) {
		this.charts[key]?.destroy?.();
		const helper = typeof quality_addon !== "undefined" ? quality_addon.chartjs : null;
		if (helper) {
			this.charts[key] = helper.create(key, canvasId, config);
			return;
		}
		const el = document.getElementById(canvasId);
		if (el && typeof Chart !== "undefined") {
			this.charts[key] = new Chart(el.getContext("2d"), config);
		}
	},

	fmt(n) {
		return frappe.format(n || 0, { fieldtype: "Float", precision: 0 });
	},

	pct(n) {
		return (Number(n) || 0).toFixed(1);
	},

	summary_card(title, value, icon, cls, sub) {
		return `
			<div class="col-md-2 col-sm-4 col-xs-6">
				<div class="card summary-card">
					<div class="card-body">
						<div class="d-flex justify-content-between">
							<div>
								<h6 class="card-title text-muted">${title}</h6>
								<h3 class="mb-0 ${cls || ""}">${value}</h3>
								${sub ? `<small class="text-muted">${sub}</small>` : ""}
							</div>
							<div class="align-self-center"><i class="fa ${icon} fa-2x ${cls || "text-primary"}"></i></div>
						</div>
					</div>
				</div>
			</div>`;
	},

	render_person_table(perf) {
		const persons = perf.persons || [];
		const label = perf.person_label || __("Operator");
		if (!persons.length) {
			return `<p class="text-muted text-center p-3">${__("No Inline Stitching data for this Order Sheet.")}</p>`;
		}
		const worst = perf.worst_person;
		return `
			${worst ? `<div class="alert alert-danger py-2 mb-2"><strong>${__("Worst")} ${label}:</strong> ${frappe.utils.escape_html(worst)}</div>` : ""}
			<table class="table table-bordered table-sm table-hover mb-0">
				<thead><tr>
					<th>#</th><th>${label}</th>
					<th class="text-right">${__("Pcs")}</th>
					<th class="text-right">${__("Defects")}</th><th class="text-right">${__("Defect %")}</th><th>${__("Status")}</th>
				</tr></thead>
				<tbody>${persons
					.map((p) => {
						const sk = p.status_key || "ok";
						const rowCls = sk === "worst" ? "qd-op-worst" : sk === "high" ? "qd-op-high" : "";
						let badge = "qd-badge-ok";
						if (sk === "worst") badge = "qd-badge-worst";
						else if (sk === "high") badge = "qd-badge-high";
						else if (sk === "watch") badge = "badge badge-warning";
						return `<tr class="${rowCls}">
							<td>${p.rank}</td>
							<td><strong>${frappe.utils.escape_html(p.person)}</strong></td>
							<td class="text-right">${this.fmt(p.pcs_checked)}</td>
							<td class="text-right"><strong>${this.fmt(p.defect_qty)}</strong></td>
							<td class="text-right"><strong>${this.pct(p.defect_rate)}%</strong></td>
							<td><span class="badge ${badge}">${frappe.utils.escape_html(p.status)}</span></td>
						</tr>`;
					})
					.join("")}</tbody>
			</table>`;
	},

	render_details_table(details) {
		if (!details.length) {
			return `<p class="text-muted text-center p-3">${__("No detail rows.")}</p>`;
		}
		return `
			<table class="table table-bordered table-sm mb-0" style="font-size:12px;">
				<thead><tr>
					<th>${__("Article")}</th><th>${__("Size")}</th><th>${__("Color")}</th><th>${__("Design")}</th>
					<th class="text-right">${__("Plan Qty")}</th><th class="text-right">${__("Pcs Checked")}</th>
					<th class="text-right">${__("Defects")}</th><th class="text-right">${__("Defect %")}</th><th class="text-right">${__("Progress %")}</th>
				</tr></thead>
				<tbody>${details
					.slice(0, 100)
					.map(
						(r) => `<tr>
						<td>${frappe.utils.escape_html(r.article)}</td>
						<td>${frappe.utils.escape_html(r.size)}</td>
						<td>${frappe.utils.escape_html(r.color)}</td>
						<td>${frappe.utils.escape_html(r.design)}</td>
						<td class="text-right">${this.fmt(r.plan_qty)}</td>
						<td class="text-right">${this.fmt(r.pcs_checked)}</td>
						<td class="text-right">${this.fmt(r.defect_qty)}</td>
						<td class="text-right">${this.pct(r.defect_rate)}%</td>
						<td class="text-right">${this.pct(r.progress_pct)}%</td>
					</tr>`
					)
					.join("")}</tbody>
			</table>`;
	},

	dim_bar(key, canvasId, dimData, datasetLabel, valueKey = "defect_qty") {
		if (!dimData?.labels?.length) return;
		const values = dimData[valueKey] || dimData.defect_qty || [];
		this.make_chart(key, canvasId, {
			type: "bar",
			data: {
				labels: dimData.labels,
				datasets: [{ label: datasetLabel, data: values, backgroundColor: "#667eea" }],
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				scales: { x: { ticks: { maxRotation: 45, minRotation: 0 } } },
			},
		});
	},

	trend_chart(key, canvasId, trend) {
		const t = trend || {};
		if (!t.labels?.length) return;
		this.make_chart(key, canvasId, {
			type: "line",
			data: {
				labels: t.labels,
				datasets: (t.datasets || []).map((ds) => ({
					label: ds.name,
					data: ds.values,
					borderColor: "#fa709a",
					backgroundColor: "transparent",
					tension: 0.3,
				})),
			},
			options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
		});
	},

	render_dashboard($wrapper, data) {
		const s = data.summary || {};
		const perf = data.operator_performance || {};
		const prefix = "os_is_";
		const $root = $wrapper.find(".os-inline-stitching-dash");

		this.destroy_charts();

		$root.html(`
			<div class="d-flex justify-content-between align-items-center mb-3">
				<div>
					<h5 class="mb-0">${__("Inline Stitching")}</h5>
					<small class="text-muted">${__("All Inline Stitching documents linked to this Order Sheet")}</small>
				</div>
				<button type="button" class="btn btn-default btn-sm" data-action="refresh-is">${__("Refresh")}</button>
			</div>
			<div class="row">${this.summary_card(__("Pcs Checked"), this.fmt(s.pcs_checked), "fa-check-square", "text-primary")}
				${this.summary_card(__("Total Defect Pcs"), this.fmt(s.total_defects), "fa-bug", "text-warning")}
				${this.summary_card(__("Defect Rate"), `${this.pct(s.defect_rate)}%`, "fa-percent", "text-danger")}
				${this.summary_card(__("Lines"), s.line_count || 0, "fa-list", "text-info")}
				${this.summary_card(__("Documents"), s.document_count || 0, "fa-file", "text-success")}
			</div>
			<div class="row">
				<div class="col-md-6"><div class="card"><div class="card-header gradient-header-danger"><h5 class="mb-0">${__("Worst Operators")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}worst_bar"></canvas></div></div></div></div>
				<div class="col-md-6"><div class="card"><div class="card-header gradient-header-success"><h5 class="mb-0">${__("Defects by Article")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}article_bar"></canvas></div></div></div></div>
			</div>
			<div class="row">
				<div class="col-md-4"><div class="card"><div class="card-header gradient-header"><h5 class="mb-0">${__("By Size")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}size_bar"></canvas></div></div></div></div>
				<div class="col-md-4"><div class="card"><div class="card-header gradient-header"><h5 class="mb-0">${__("By Color")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}color_bar"></canvas></div></div></div></div>
				<div class="col-md-4"><div class="card"><div class="card-header gradient-header-info"><h5 class="mb-0">${__("By Design")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}design_bar"></canvas></div></div></div></div>
			</div>
			<div class="row">
				<div class="col-md-12"><div class="card"><div class="card-header gradient-header-info"><h5 class="mb-0">${__("Activity Trend")}</h5></div>
					<div class="card-body p-0"><div class="chart-container chart-sm"><canvas id="${prefix}trend"></canvas></div></div></div></div>
			</div>
			<div class="row">
				<div class="col-md-5"><div class="card"><div class="card-header gradient-header-danger"><h5 class="mb-0"><i class="fa fa-user"></i> ${__("Operator Performance")}</h5></div>
					<div class="card-body table-responsive" style="max-height:360px;overflow:auto;">${this.render_person_table(perf)}</div></div></div>
				<div class="col-md-7"><div class="card"><div class="card-header gradient-header"><h5 class="mb-0"><i class="fa fa-table"></i> ${__("By Article / Size / Color / Design")}</h5></div>
					<div class="card-body table-responsive" style="max-height:360px;overflow:auto;">${this.render_details_table(data.details || [])}</div></div></div>
			</div>
		`);

		$root.find('[data-action="refresh-is"]').on("click", () => {
			const frm = $wrapper.closest(".form-page")?.[0]?.cur_frm;
			if (frm) this.render(frm);
		});

		setTimeout(() => {
			const topOps = (perf.persons || []).slice(0, 8).reverse();
			if (topOps.length) {
				this.make_chart(`${prefix}worst`, `${prefix}worst_bar`, {
					type: "bar",
					data: {
						labels: topOps.map((p) => p.person),
						datasets: [{ label: __("Defect Pcs"), data: topOps.map((p) => p.defect_qty), backgroundColor: "#dc3545" }],
					},
					options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
				});
			}

			this.dim_bar(`${prefix}article`, `${prefix}article_bar`, data.by_article, __("Defect Pcs"));
			this.dim_bar(`${prefix}size`, `${prefix}size_bar`, data.by_size, __("Pcs Checked"), "pcs_checked");
			this.dim_bar(`${prefix}color`, `${prefix}color_bar`, data.by_color, __("Defect Pcs"));
			this.dim_bar(`${prefix}design`, `${prefix}design_bar`, data.by_design, __("Defect Pcs"));
			this.trend_chart(`${prefix}trend`, `${prefix}trend`, data.trend);

			const helper = typeof quality_addon !== "undefined" ? quality_addon.chartjs : null;
			if (helper?.instances) {
				Object.values(helper.instances).forEach((c) => c.resize && c.resize());
			}
		}, 80);
	},
};
