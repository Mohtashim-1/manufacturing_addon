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

		if (frm.fields_dict.dashboard) {
			orderSheetDashboard.render(frm);
		}
		if (frm.fields_dict.contractor_dashboard) {
			contractorDashboardInForm.render(frm);
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
						<div class="col-md-3"><div id="osd-customer-field"></div></div>
						<div class="col-md-3"><div id="osd-so-field"></div></div>
						<div class="col-md-3"><div id="osd-os-field"></div></div>
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
		const self = this;

		const make_link = (container, df, initial_value) => {
			// Clear container first to avoid duplicates from repeated make_control calls
			container.empty();
			const label = $(`<label style="font-weight:600;font-size:13px;color:#495057;margin-bottom:5px;">${df.label}</label>`);
			const input_wrap = $(`<div></div>`);
			container.append(label).append(input_wrap);

			const ctrl = frappe.ui.form.make_control({
				df: { ...df, label: "" },
				parent: input_wrap,
				render_input: true,
				only_input: true,
			});
			// render_input:true already calls make_input() internally — do NOT call it again
			if (initial_value) ctrl.set_value(initial_value);
			return ctrl;
		};

		this._customer_field = make_link(
			$wrapper.find("#osd-customer-field"),
			{ fieldtype: "Link", fieldname: "customer", options: "Customer", label: __("Customer"), placeholder: "Select Customer" },
			frm.doc.customer
		);

		this._so_field = make_link(
			$wrapper.find("#osd-so-field"),
			{
				fieldtype: "Link", fieldname: "sales_order", options: "Sales Order", label: __("Sales Order"), placeholder: "Select Sales Order",
				get_query: () => {
					const c = self._customer_field ? self._customer_field.get_value() : "";
					const f = { docstatus: ["!=", 2] };
					if (c) f.customer = c;
					return { filters: f };
				}
			},
			frm.doc.sales_order
		);

		this._os_field = make_link(
			$wrapper.find("#osd-os-field"),
			{
				fieldtype: "Link", fieldname: "order_sheet", options: "Order Sheet", label: __("Order Sheet"), placeholder: "Select Order Sheet",
				get_query: () => {
					const so = self._so_field ? self._so_field.get_value() : "";
					return { filters: so ? { sales_order: so } : {} };
				}
			},
			frm.doc.name
		);

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
				customer: (self._customer_field && self._customer_field.get_value()) || null,
				sales_order: (self._so_field && self._so_field.get_value()) || null,
				order_sheet: (self._os_field && self._os_field.get_value()) || frm.doc.name || null,
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
						Complete: ${this._fmt_num(s.packing_finished_finished_items || s.packing_finished || 0)} / Total: ${this._fmt_num(s.total_order_qty || 0)}
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
			} else if (hasChildren) {
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
					<td class="text-right ${ic} osd-audit" style="${ic ? auditStyle : ""}">${this._fmt_num(cFin)}</td>
					<td class="text-right ${ic}">${this._fmt_pct(cPlanPct)}%</td>
					<td class="text-right ${ic}">${this._fmt_pct(cQtyPct)}%</td>
					<td class="text-center ${ic}">${this._badge(cQtyPct)}</td>
					<td class="text-right ${wc} osd-audit" style="${wc ? auditStyle : ""}">${this._fmt_num(sFin)}</td>
					<td class="text-right ${wc}">${this._fmt_pct(sPlanPct)}%</td>
					<td class="text-right ${wc}">${this._fmt_pct(sQtyPct)}%</td>
					<td class="text-center ${wc}">${this._badge(sQtyPct)}</td>
					<td class="text-right ${gc} ${isBundle ? "" : "osd-audit"}" style="${gc && !isBundle ? auditStyle : ""}">${isBundle ? "-" : this._fmt_num(pFin)}</td>
					<td class="text-right ${gc}">${isBundle ? "-" : this._fmt_pct(pPlanPct) + "%"}</td>
					<td class="text-right ${gc}">${isBundle ? "-" : this._fmt_pct(pQtyPct) + "%"}</td>
					<td class="text-center ${gc}">${isBundle ? "-" : this._badge(pQtyPct)}</td>
				</tr>
			`);

			// Attach audit data objects
			$tr.find(".osd-audit").eq(0).data("audit", JSON.parse(auditData("Cutting")));
			$tr.find(".osd-audit").eq(1).data("audit", JSON.parse(auditData("Stitching")));
			if (!isBundle) $tr.find(".osd-audit").eq(2).data("audit", JSON.parse(auditData("Packing")));

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

const contractorDashboardInForm = {
	render(frm) {
		const $wrapper = frm.fields_dict.contractor_dashboard.$wrapper;
		if (!$wrapper) return;

		if (!frm.doc.name || frm.doc.__islocal) {
			$wrapper.html(`
				<div style="padding:20px; text-align:center; color:#6c757d;">
					${__("Save the document to load contractor dashboard.")}
				</div>
			`);
			return;
		}

		$wrapper.html(`
			<div style="padding:20px;">
				<div class="text-muted" style="margin-bottom:8px;">
					${__("Contractor dashboard for Order Sheet")} <b>${frappe.utils.escape_html(frm.doc.name)}</b>
				</div>
				<div class="text-muted">
					<i class="fa fa-spinner fa-spin"></i> ${__("Loading...")}
				</div>
			</div>
		`);

		frappe.call({
			method: "manufacturing_addon.manufacturing_addon.page.order_tracking.order_tracking.get_dashboard_data",
			args: { order_sheet: frm.doc.name },
			callback: (r) => {
				const data = r.message || {};
				const summary = data.summary || {};
				const details = data.details || [];

				const html = `
					<div style="padding:16px;">
						<div class="row" style="margin-bottom:14px;">
							<div class="col-md-3"><div class="alert alert-info"><b>${__("Order Qty")}</b><br>${this.fmt(summary.total_order_qty)}</div></div>
							<div class="col-md-3"><div class="alert alert-primary"><b>${__("Cutting %")}</b><br>${this.pct(summary.cutting_progress)}%</div></div>
							<div class="col-md-3"><div class="alert alert-warning"><b>${__("Stitching %")}</b><br>${this.pct(summary.stitching_progress)}%</div></div>
							<div class="col-md-3"><div class="alert alert-success"><b>${__("Packing %")}</b><br>${this.pct(summary.packing_progress)}%</div></div>
						</div>
						<div class="table-responsive">
							<table class="table table-bordered table-sm">
								<thead>
									<tr>
										<th>${__("Item")}</th>
										<th>${__("Bundle Item")}</th>
										<th class="text-right">${__("Order Qty")}</th>
										<th class="text-right">${__("Planned Qty")}</th>
										<th class="text-right">${__("Cutting")}</th>
										<th class="text-right">${__("Stitching")}</th>
										<th class="text-right">${__("Packing")}</th>
									</tr>
								</thead>
								<tbody>
									${details.length ? details.map((d) => `
										<tr>
											<td>${frappe.utils.escape_html(d.item || "")}</td>
											<td>${frappe.utils.escape_html(d.bundle_item || "-")}</td>
											<td class="text-right">${this.fmt(d.order_qty)}</td>
											<td class="text-right">${this.fmt(d.planned_qty)}</td>
											<td class="text-right">${this.fmt(d.cutting_finished)}</td>
											<td class="text-right">${this.fmt(d.stitching_finished)}</td>
											<td class="text-right">${this.fmt(d.packing_finished)}</td>
										</tr>
									`).join("") : `<tr><td colspan="7" class="text-center text-muted">${__("No data found")}</td></tr>`}
								</tbody>
							</table>
						</div>
					</div>
				`;
				$wrapper.html(html);
			},
			error: () => {
				$wrapper.html(`<div style="padding:20px;color:#dc3545;">${__("Failed to load contractor dashboard.")}</div>`);
			},
		});
	},

	fmt(n) {
		return (n == null ? 0 : Number(n)).toLocaleString("en-US", { maximumFractionDigits: 2 });
	},

	pct(n) {
		return (n == null ? 0 : Number(n)).toFixed(1);
	},
};
