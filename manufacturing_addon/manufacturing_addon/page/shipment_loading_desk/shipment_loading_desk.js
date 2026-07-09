frappe.pages["shipment-loading-desk"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Shipment Loading"),
		single_column: true,
	});

	const API = "manufacturing_addon.manufacturing_addon.doctype.shipment_loading.shipment_loading";
	const LOADING_TAGS = ["Manual", "Forklift", "Pallet Jack", "Crane", "Conveyor", "Bulk"];
	const CONTAINER_SPECS = {
		"20ft FCL": { rows: 3, cols: 10, capacity_cbm: 33, height_cm: 239, label: "20ft FCL (~33 CBM)" },
		"40ft FCL": { rows: 3, cols: 20, capacity_cbm: 67, height_cm: 239, label: "40ft FCL (~67 CBM)" },
	};

	const state = {
		rows: [],
		selectedOrderSheet: null,
		cartons: [],
		selectedCartons: new Set(),
		summary: {},
		readiness: {},
		containerType: "20ft FCL",
		containerSpec: CONTAINER_SPECS["20ft FCL"],
		trayLimit: 40,
		trayGroupMode: "packing_report",
		plannerView: "2d",
		containerEstimate: null,
		threeViewer: null,
	};

	function show_detail_panel() {
		$("#sl-detail-empty").hide();
		$("#sl-detail-panel").prop("hidden", false).css("display", "block");
	}

	function hide_detail_panel() {
		$("#sl-detail-empty").show();
		$("#sl-detail-panel").prop("hidden", true).hide();
	}

	function is_loaded(row) {
		return cint(row.is_loaded) === 1;
	}

	const filters = {
		order_sheet: page.add_field({
			label: __("Order Sheet"),
			fieldtype: "Link",
			fieldname: "order_sheet",
			options: "Order Sheet",
			change() {
				load_board();
			},
		}),
		customer: page.add_field({
			label: __("Customer"),
			fieldtype: "Link",
			fieldname: "customer",
			options: "Customer",
			change() {
				load_board();
			},
		}),
		status: page.add_field({
			label: __("Status"),
			fieldtype: "Select",
			fieldname: "status",
			options: ["", "Pending", "In Progress", "Completed"].join("\n"),
			change() {
				load_board();
			},
		}),
	};

	page.add_inner_button(__("Refresh"), () => {
		load_board();
		if (state.selectedOrderSheet) {
			load_cartons(state.selectedOrderSheet);
		}
	});

	const $root = $(`
		<div class="sl-page" style="padding:16px;">
			<div class="sl-hero" style="background:linear-gradient(135deg,#0f4c81,#1b6ca8);color:#fff;padding:20px;border-radius:10px;margin-bottom:16px;">
				<h3 style="margin:0;font-weight:700;"><i class="fa fa-truck"></i> ${__("Shipment Loading")}</h3>
				<p style="margin:6px 0 0;opacity:.9;">${__(
					"Load cartons order-sheet wise from submitted Packing Reports. Tag how each carton was added."
				)}</p>
			</div>
			<div class="row" id="sl-summary-cards" style="margin-bottom:16px;"></div>
			<div class="row">
				<div class="col-md-4">
					<div class="panel panel-default" style="border-radius:8px;overflow:hidden;">
						<div class="panel-heading" style="font-weight:600;">${__("Order Sheets")}</div>
						<div class="panel-body" style="padding:0;max-height:70vh;overflow:auto;" id="sl-order-list"></div>
					</div>
				</div>
				<div class="col-md-8">
					<div class="panel panel-default" style="border-radius:8px;overflow:hidden;">
						<div class="panel-heading" style="font-weight:600;">
							<span id="sl-detail-title">${__("Select an Order Sheet")}</span>
						</div>
						<div class="panel-body">
							<div id="sl-detail-empty" class="text-muted text-center" style="padding:40px;">
								<i class="fa fa-cube fa-3x" style="opacity:.3;"></i>
								<p style="margin-top:12px;">${__(
									"Choose an order sheet to view and load cartons from packing reports."
								)}</p>
							</div>
							<div id="sl-detail-panel" style="display:none;">
								<div id="sl-readiness-banner" class="alert alert-info" style="padding:10px 14px;margin-bottom:12px;"></div>
								<div id="sl-consignment-estimate" class="alert alert-warning" style="padding:10px 14px;margin-bottom:12px;display:none;"></div>
								<div class="row" style="margin-bottom:12px;">
									<div class="col-md-3">
										<label class="small text-muted">${__("Container Type")}</label>
										<select class="form-control input-sm" id="sl-container-type">
											<option value="20ft FCL">20ft FCL (~33 CBM)</option>
											<option value="40ft FCL">40ft FCL (~67 CBM)</option>
										</select>
									</div>
									<div class="col-md-3">
										<label class="small text-muted">${__("Loading Tag")}</label>
										<select class="form-control input-sm" id="sl-loading-tag">
											${LOADING_TAGS.map((t) => `<option value="${t}">${__(t)}</option>`).join("")}
										</select>
									</div>
									<div class="col-md-3">
										<label class="small text-muted">${__("Container / Truck No")}</label>
										<input type="text" class="form-control input-sm" id="sl-container-no" placeholder="${__(
											"Optional"
										)}" />
									</div>
									<div class="col-md-3" style="display:flex;align-items:flex-end;gap:8px;flex-wrap:wrap;">
										<button class="btn btn-success btn-sm" id="sl-load-btn">
											<i class="fa fa-check"></i> ${__("Load Selected")}
										</button>
										<button class="btn btn-default btn-sm" id="sl-sync-btn">
											<i class="fa fa-refresh"></i> ${__("Sync Cartons")}
										</button>
									</div>
								</div>
								<div class="progress" style="height:18px;margin-bottom:12px;">
									<div class="progress-bar progress-bar-success" id="sl-progress-bar" style="width:0%;min-width:0;">0%</div>
								</div>
								<div class="panel panel-default" style="margin-bottom:12px;">
									<div class="panel-heading" style="font-weight:600;display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
										<span><i class="fa fa-th"></i> ${__("Container Planner")}</span>
										<div style="display:flex;gap:6px;flex-wrap:wrap;">
											<button type="button" class="btn btn-primary btn-xs" id="sl-auto-fill-btn">
												<i class="fa fa-magic"></i> ${__("Auto Fill Container")}
											</button>
											<button type="button" class="btn btn-default btn-xs" id="sl-auto-fill-selected-btn">
												${__("Auto Add Selected")}
											</button>
										</div>
									</div>
									<div class="panel-body" style="padding:12px;">
										<div class="row">
											<div class="col-md-3">
												<div class="small text-muted" style="margin-bottom:6px;">${__(
													"Cartons to place"
												)} <span id="sl-tray-count"></span></div>
												<div class="btn-group btn-group-xs" style="margin-bottom:6px;display:flex;">
													<button type="button" class="btn btn-default sl-tray-mode active" data-mode="packing_report">${__(
														"Packing Report"
													)}</button>
													<button type="button" class="btn btn-default sl-tray-mode" data-mode="item">${__(
														"Item"
													)}</button>
												</div>
												<input type="text" class="form-control input-sm" id="sl-tray-search" placeholder="${__(
													"Search item / packing report / size"
												)}" style="margin-bottom:6px;" />
												<div id="sl-carton-tray" class="sl-carton-tray"></div>
												<button class="btn btn-default btn-xs btn-block" id="sl-tray-more" style="margin-top:6px;display:none;">
													${__("Show more")}
												</button>
											</div>
											<div class="col-md-9">
												<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:6px;">
													<div class="small text-muted" id="sl-container-meta"></div>
													<div class="btn-group btn-group-xs">
														<button type="button" class="btn btn-default sl-planner-view active" data-view="2d">${__(
															"2D Grid"
														)}</button>
														<button type="button" class="btn btn-default sl-planner-view" data-view="3d">${__(
															"3D View"
														)}</button>
													</div>
												</div>
												<div class="progress" style="height:10px;margin-bottom:8px;">
													<div class="progress-bar progress-bar-info" id="sl-container-cbm-bar" style="width:0%;"></div>
												</div>
												<div id="sl-container-grid" class="sl-container-grid"></div>
												<div id="sl-container-3d" class="sl-3d-scene" style="display:none;"></div>
												<div class="small text-muted" id="sl-3d-legend" style="display:none;margin-top:6px;">
													${__(
														"Hover carton for quick info · Click to select · Scroll on 3D view to zoom · Walk Inside to enter container"
													)}
												</div>
											</div>
										</div>
									</div>
								</div>
								<div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;">
									<button class="btn btn-default btn-sm" id="sl-unload-btn">
										<i class="fa fa-undo"></i> ${__("Unload Selected")}
									</button>
									<button class="btn btn-default btn-sm" id="sl-select-pending">${__("Select Pending")}</button>
									<button class="btn btn-default btn-sm" id="sl-clear-selection">${__("Clear")}</button>
								</div>
								<div class="table-responsive" style="max-height:55vh;overflow:auto;">
									<table class="table table-bordered table-hover table-condensed" style="font-size:12px;">
										<thead style="background:#f8f9fa;position:sticky;top:0;z-index:1;">
											<tr>
												<th style="width:32px;"><input type="checkbox" id="sl-select-all" /></th>
												<th>${__("Carton")}</th>
												<th>${__("Packing Report")}</th>
												<th>${__("Item")}</th>
												<th>${__("Size")}</th>
												<th>${__("Qty")}</th>
												<th>${__("Dimension")}</th>
												<th>${__("CBM")}</th>
												<th>${__("Tag")}</th>
												<th>${__("Status")}</th>
											</tr>
										</thead>
										<tbody id="sl-carton-body"></tbody>
									</table>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	`);

	page.main.append($root);

	if (!$("#sl-container-styles").length) {
		$("head").append(`
			<style id="sl-container-styles">
				.sl-carton-tray { min-height:220px; max-height:320px; overflow:auto; border:1px dashed #ced4da; border-radius:6px; padding:8px; background:#f8f9fa; }
				.sl-carton-chip { display:block; margin-bottom:6px; padding:6px 8px; background:#fff; border:1px solid #dee2e6; border-radius:4px; font-size:11px; cursor:grab; }
				.sl-carton-chip .sl-chip-actions { margin-top:6px; display:flex; gap:4px; }
				.sl-carton-chip .sl-chip-actions .btn { cursor:pointer; flex:1; }
				.sl-carton-chip.dragging { opacity:.5; }
				.sl-container-grid { display:grid; gap:4px; border:2px solid #495057; border-radius:6px; padding:8px; background:linear-gradient(180deg,#e9ecef,#f8f9fa); min-height:180px; }
				.sl-container-slot { min-height:52px; border:1px dashed #adb5bd; border-radius:4px; background:rgba(255,255,255,.7); position:relative; font-size:10px; padding:2px; }
				.sl-container-slot.drop-hover { background:#d4edda; border-color:#28a745; }
				.sl-container-slot.occupied { background:#cce5ff; border-style:solid; border-color:#0f4c81; }
				.sl-stack-pill { display:flex; gap:2px; justify-content:center; margin-top:16px; min-height:28px; align-items:flex-end; }
				.sl-stack-block { width:10px; border-radius:2px 2px 0 0; background:linear-gradient(180deg,#4dabf7,#0f4c81); border:1px solid #0f4c81; }
				.sl-stack-count { position:absolute; bottom:2px; right:4px; font-size:9px; font-weight:700; color:#0f4c81; }
				.sl-slot-label { position:absolute; top:2px; left:4px; color:#868e96; font-size:9px; }
				.sl-slot-carton { margin-top:14px; font-weight:600; color:#0f4c81; word-break:break-all; }
				.sl-3d-scene { position:relative; min-height:420px; height:420px; border-radius:8px; overflow:hidden; border:2px solid #343a40; background:#0f1724; touch-action:none; }
				.sl-3d-scene canvas { display:block; width:100% !important; height:100% !important; cursor:grab; }
				.sl-3d-hud { position:absolute; left:10px; top:10px; z-index:3; padding:8px 10px; border-radius:6px; background:rgba(15,23,36,.82); color:#e9ecef; font-size:11px; pointer-events:auto; max-width:calc(100% - 20px); }
				.sl-3d-hud-actions { margin-top:6px; display:flex; gap:6px; flex-wrap:wrap; }
				.sl-3d-tooltip { position:absolute; z-index:5; pointer-events:none; padding:8px 10px; border-radius:6px; background:rgba(255,255,255,.96); color:#212529; font-size:11px; max-width:260px; box-shadow:0 4px 16px rgba(0,0,0,.35); line-height:1.45; }
				.sl-3d-info { position:absolute; right:10px; top:10px; z-index:4; width:260px; padding:10px 12px; border-radius:6px; background:rgba(15,76,129,.92); color:#fff; font-size:11px; line-height:1.5; box-shadow:0 4px 16px rgba(0,0,0,.35); }
				.sl-3d-info-title { font-weight:700; margin-bottom:6px; font-size:12px; }
			</style>
		`);
	}

	function get_filters() {
		return {
			order_sheet: filters.order_sheet.get_value() || "",
			customer: filters.customer.get_value() || "",
			status: filters.status.get_value() || "",
		};
	}

	function status_badge(status) {
		const map = {
			Pending: "default",
			"In Progress": "warning",
			Completed: "success",
		};
		return `<span class="label label-${map[status] || "default"}">${frappe.utils.escape_html(
			status || "Pending"
		)}</span>`;
	}

	function load_board() {
		$("#sl-order-list").html(
			`<div class="text-center text-muted" style="padding:24px;"><i class="fa fa-spinner fa-spin"></i> ${__(
				"Loading order sheets..."
			)}</div>`
		);
		frappe.call({
			method: `${API}.get_shipment_loading_board`,
			args: { filters: get_filters() },
			callback(r) {
				state.rows = (r.message && r.message.rows) || [];
				render_summary();
				render_order_list();
			},
		});
	}

	function render_summary() {
		const total = state.rows.length;
		const pieces = state.rows.reduce((s, row) => s + flt(row.total_pieces_ready), 0);
		const expected = state.rows.reduce((s, row) => s + (row.expected_cartons || 0), 0);
		const cartons = state.rows.reduce((s, row) => s + (row.total_cartons || 0), 0);
		const loaded = state.rows.reduce((s, row) => s + (row.loaded_cartons || 0), 0);
		const pending = state.rows.reduce((s, row) => s + (row.pending_cartons || 0), 0);
		const pct = cartons ? Math.round((loaded / cartons) * 100) : 0;

		$("#sl-summary-cards").html(`
			<div class="col-md-2"><div class="panel panel-default text-center" style="padding:14px;border-radius:8px;"><div class="text-muted small">${__(
				"Order Sheets"
			)}</div><h3 style="margin:6px 0 0;">${total}</h3></div></div>
			<div class="col-md-2"><div class="panel panel-default text-center" style="padding:14px;border-radius:8px;"><div class="text-muted small">${__(
				"Pieces Ready"
			)}</div><h3 style="margin:6px 0 0;">${format_qty(pieces)}</h3></div></div>
			<div class="col-md-2"><div class="panel panel-default text-center" style="padding:14px;border-radius:8px;"><div class="text-muted small">${__(
				"Expected Cartons"
			)}</div><h3 style="margin:6px 0 0;">${expected}</h3></div></div>
			<div class="col-md-2"><div class="panel panel-default text-center" style="padding:14px;border-radius:8px;"><div class="text-muted small">${__(
				"Synced Cartons"
			)}</div><h3 style="margin:6px 0 0;">${cartons}</h3></div></div>
			<div class="col-md-2"><div class="panel panel-default text-center" style="padding:14px;border-radius:8px;"><div class="text-muted small">${__(
				"Loaded"
			)}</div><h3 style="margin:6px 0 0;color:#28a745;">${loaded}</h3></div></div>
			<div class="col-md-2"><div class="panel panel-default text-center" style="padding:14px;border-radius:8px;"><div class="text-muted small">${__(
				"Pending"
			)}</div><h3 style="margin:6px 0 0;color:#f0ad4e;">${pending} <small>(${pct}%)</small></h3></div></div>
		`);
	}

	function format_qty(value, decimals = 0) {
		return format_number(flt(value), null, decimals);
	}

	function short_item_label(so_item) {
		const text = so_item || "";
		if (!text) return __("Item");
		const parts = text.split("-");
		return parts.length > 3 ? parts.slice(0, 3).join("-") : text.length > 32 ? `${text.slice(0, 32)}…` : text;
	}

	function row_per_carton_cbm(row) {
		if (flt(row.per_carton_cbm)) return flt(row.per_carton_cbm);
		const count = Math.max(1, cint(row.carton_count));
		return flt(row.cbm) / count;
	}

	function slot_label(row) {
		return `${frappe.utils.escape_html(short_item_label(row.so_item))}<br><small>${frappe.utils.escape_html(
			row.finished_size || ""
		)}</small>`;
	}

	function get_tray_entries() {
		const unplaced = get_unplaced_cartons();
		if (state.trayGroupMode !== "item") {
			return unplaced.map((row) => ({
				...row,
				is_group: false,
				place_name: row.name,
				chip_title: row.carton_label || "",
				chip_subtitle: `${cint(row.carton_count) || 1} ${__("ctns")} · ${format_qty(
					row.total_pieces || row.qty_in_carton || 0
				)} ${__("pcs")} · ${row.finished_size || ""}`,
				auto_fill_args: { carton_rows: [row.name] },
			}));
		}

		const groups = {};
		unplaced.forEach((row) => {
			const key = `${row.so_item || ""}||${row.finished_size || ""}||${row.carton_dimension || ""}`;
			if (!groups[key]) {
				groups[key] = {
					key,
					so_item: row.so_item,
					finished_size: row.finished_size,
					carton_dimension: row.carton_dimension,
					carton_count: 0,
					total_pieces: 0,
					per_carton_cbm: row_per_carton_cbm(row),
					row_names: [],
					packing_lines: 0,
				};
			}
			const group = groups[key];
			group.carton_count += cint(row.carton_count) || 1;
			group.total_pieces += flt(row.total_pieces || row.qty_in_carton);
			group.row_names.push(row.name);
			group.packing_lines += 1;
		});

		return Object.values(groups).map((group) => ({
			...group,
			is_group: true,
			place_name: group.row_names[0],
			chip_title: short_item_label(group.so_item),
			chip_subtitle: `${group.carton_count} ${__("ctns")} · ${format_qty(group.total_pieces)} ${__(
				"pcs"
			)} · ${group.finished_size || ""}`,
			chip_meta: `${group.packing_lines} ${__("packing lines")}`,
			auto_fill_args: {
				so_item: group.so_item,
				finished_size: group.finished_size || "",
			},
		}));
	}

	function render_order_list() {
		const $list = $("#sl-order-list").empty();
		if (!state.rows.length) {
			$list.html(
				`<div class="text-muted text-center" style="padding:24px;">${__(
					"No submitted packing reports found."
				)}</div>`
			);
			return;
		}

		state.rows.forEach((row) => {
			const active = state.selectedOrderSheet === row.order_sheet ? "active" : "";
			const pct = row.total_cartons
				? Math.round((row.loaded_cartons / row.total_cartons) * 100)
				: 0;
			$list.append(`
				<a href="#" class="list-group-item sl-order-item ${active}" data-order-sheet="${frappe.utils.escape_html(
					row.order_sheet
				)}" style="border-left:0;border-right:0;">
					<div style="display:flex;justify-content:space-between;align-items:center;">
						<strong>${frappe.utils.escape_html(row.order_sheet)}</strong>
						${status_badge(row.status)}
					</div>
					<div class="small text-muted" style="margin-top:4px;">
						${frappe.utils.escape_html(row.customer || "")} · ${row.packing_report_count} ${__(
							"Packing Reports"
						)}
					</div>
					<div class="small" style="margin-top:6px;">
						<strong>${format_qty(row.total_pieces_ready || 0)}</strong> ${__("pcs")} →
						<strong>${row.expected_cartons || 0}</strong> ${__("cartons expected")}
					</div>
					<div class="small text-muted">
						${row.loaded_cartons || 0}/${row.total_cartons || 0} ${__("synced")} · ${row.loaded_cartons || 0} ${__(
							"loaded"
						)}
					</div>
				</a>
			`);
		});
	}

	function load_cartons(order_sheet, options = {}) {
		state.selectedOrderSheet = order_sheet;
		state.selectedCartons.clear();
		state.trayLimit = 40;
		render_order_list();

		show_detail_panel();
		$("#sl-carton-body").html(
			`<tr><td colspan="10" class="text-center text-muted"><i class="fa fa-spinner fa-spin"></i> ${__(
				"Loading cartons..."
			)}</td></tr>`
		);

		frappe.call({
			method: `${API}.get_order_sheet_cartons`,
			args: { order_sheet, sync: options.sync ? 1 : 0 },
			callback(r) {
				const msg = r.message || {};
				state.cartons = msg.cartons || [];
				state.summary = msg.summary || {};
				state.readiness = msg.readiness || {};
				state.containerType = msg.container_type || "20ft FCL";
				state.containerSpec = msg.container_spec || CONTAINER_SPECS[state.containerType];
				state.containerEstimate = msg.container_estimate || null;
				$("#sl-container-type").val(state.containerType);
				$("#sl-tray-search").val("");
				if (state.summary.container_no) {
					$("#sl-container-no").val(state.summary.container_no);
				}
				render_cartons(state.summary);
				if (options.sync) {
					load_board();
				}
			},
		});
	}

	function render_cartons(summary) {
		summary = summary || state.summary || {};
		const readiness = state.readiness || {};
		const pieces = flt(readiness.pieces_ready || summary.total_pieces_ready);
		const expected = cint(readiness.expected_cartons || summary.expected_cartons);
		const synced = cint(summary.total_cartons);
		const loaded = cint(summary.loaded_cartons);

		$("#sl-detail-empty").hide();
		show_detail_panel();
		$("#sl-readiness-banner").html(
			`<strong>${format_qty(pieces)} ${__("pieces ready")}</strong> ${__(
				"from submitted Packing Reports"
			)} → <strong>${expected} ${__("cartons expected")}</strong> (${__(
				"based on qty/ctn"
			)}) · <strong>${synced} ${__("cartons synced")}</strong> · <strong>${loaded} ${__(
				"loaded in container"
			)}</strong>`
		);
		$("#sl-detail-title").text(`${state.selectedOrderSheet} — ${loaded}/${synced || expected} ${__("loaded")}`);

		render_consignment_estimate();

		const pct = synced ? Math.round((loaded / synced) * 100) : 0;
		$("#sl-progress-bar").css("width", `${pct}%`).text(`${pct}%`);

		render_container_planner();
		render_carton_table();
		$("#sl-select-all").prop("checked", false);
	}

	function cint(v) {
		const n = parseInt(v, 10);
		return Number.isFinite(n) ? n : 0;
	}

	function get_container_estimate_for_type(container_type) {
		const total_cbm =
			flt(state.containerEstimate?.total_cbm) ||
			flt(state.readiness?.ready_cbm) ||
			flt(state.summary?.total_cbm);
		const t20 = CONTAINER_SPECS["20ft FCL"].capacity_cbm;
		const t40 = CONTAINER_SPECS["40ft FCL"].capacity_cbm;
		const needed = total_cbm > 0 ? Math.ceil(total_cbm / (CONTAINER_SPECS[container_type]?.capacity_cbm || t20)) : 0;
		return {
			total_cbm,
			selected_type: container_type,
			containers_needed: needed,
			consignment_fits_one: needed <= 1,
			by_type: {
				"20ft FCL": { containers_needed: total_cbm > 0 ? Math.ceil(total_cbm / t20) : 0, capacity_cbm: t20 },
				"40ft FCL": { containers_needed: total_cbm > 0 ? Math.ceil(total_cbm / t40) : 0, capacity_cbm: t40 },
			},
		};
	}

	function render_consignment_estimate() {
		const est = state.containerEstimate || get_container_estimate_for_type(state.containerType);
		const totalCbm = flt(est.total_cbm);
		if (!totalCbm) {
			$("#sl-consignment-estimate").hide();
			return;
		}
		const t20 = est.by_type?.["20ft FCL"]?.containers_needed || 0;
		const t40 = est.by_type?.["40ft FCL"]?.containers_needed || 0;
		const selected = est.containers_needed || 0;
		const type = state.containerType || "20ft FCL";
		const cap = CONTAINER_SPECS[type]?.capacity_cbm || 33;
		const fitsOne = est.consignment_fits_one;
		const expected = cint(state.readiness?.expected_cartons || state.summary?.expected_cartons);
		const avgPerCarton = expected ? totalCbm / expected : 0;
		const cartonsPerContainer = avgPerCarton > 0 ? Math.floor(cap / avgPerCarton) : 0;

		let fitMsg = "";
		if (fitsOne) {
			fitMsg = `<strong class="text-success">${__(
				"Fits in 1 container"
			)}</strong> (${type})`;
		} else {
			fitMsg = `<strong>${__(
				"Needs multiple containers"
			)}</strong> — ${__("planning container 1 of")} <strong>${selected}</strong>`;
		}

		$("#sl-consignment-estimate")
			.show()
			.html(
				`<i class="fa fa-ship"></i> <strong>${__("Consignment volume")}:</strong> ${totalCbm.toFixed(
					2
				)} CBM ${__(
					"from carton dimensions"
				)} → <strong>${t20} × 20ft FCL</strong> ${__("or")} <strong>${t40} × 40ft FCL</strong> ${__(
					"for full shipment"
				)}. ${fitMsg}. ${__("Approx cartons per container by volume")}: <strong>${
					cartonsPerContainer || "—"
				}</strong> (${type})`
			);
	}

	function render_container_3d(stacks, spec) {
		const placedCount = Object.values(stacks).reduce((s, arr) => s + arr.length, 0);
		const $scene = $("#sl-container-3d");
		if (!$scene.is(":visible") && state.plannerView !== "3d") {
			return;
		}

		if (typeof manufacturing_addon === "undefined" || !manufacturing_addon.container_3d) {
			$scene.html(
				`<div class="text-center text-muted" style="padding:80px 20px;color:#adb5bd !important;">
					<i class="fa fa-spinner fa-spin"></i> ${__("Loading 3D viewer...")}
				</div>`
			);
			frappe.require("/assets/manufacturing_addon/js/shipment_container_3d.js", () => {
				render_container_3d(stacks, spec);
			});
			return;
		}

		manufacturing_addon.container_3d.destroy(state.threeViewer);
		manufacturing_addon.container_3d
			.render($scene, stacks, spec, {
				containerLabel: state.containerType || "20ft FCL",
				placedCount,
				onSelect(carton) {
					if (!carton || !carton.name) return;
					state.selectedCartons.clear();
					state.selectedCartons.add(carton.name);
					render_carton_table();
					const $row = $(`.sl-carton-check[data-name="${carton.name}"]`).closest("tr");
					if ($row.length) {
						$row[0].scrollIntoView({ behavior: "smooth", block: "center" });
					}
				},
			})
			.then((viewer) => {
				state.threeViewer = viewer;
			});
	}

	function set_planner_view(view) {
		state.plannerView = view;
		$(".sl-planner-view").removeClass("active");
		$(`.sl-planner-view[data-view="${view}"]`).addClass("active");
		if (view === "3d") {
			$("#sl-container-grid").hide();
			$("#sl-container-3d, #sl-3d-legend").show();
			render_container_3d(build_position_stacks(), state.containerSpec || CONTAINER_SPECS["20ft FCL"]);
		} else {
			if (manufacturing_addon?.container_3d) {
				manufacturing_addon.container_3d.destroy(state.threeViewer);
			}
			state.threeViewer = null;
			$("#sl-container-grid").show();
			$("#sl-container-3d, #sl-3d-legend").hide();
		}
	}

	function parse_carton_height_cm(text) {
		const m = String(text || "").match(/(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)/);
		return m ? parseFloat(m[3]) : 35;
	}

	function build_position_stacks() {
		const stacks = {};
		state.cartons.forEach((row) => {
			const r = cint(row.position_row);
			const c = cint(row.position_col);
			if (!(r > 0 && c > 0)) return;
			const key = `${r}-${c}`;
			if (!stacks[key]) stacks[key] = [];
			stacks[key].push(row);
		});
		Object.values(stacks).forEach((arr) => arr.sort((a, b) => cint(a.position_layer) - cint(b.position_layer)));
		return stacks;
	}

	function stack_height_cm(stack) {
		return (stack || []).reduce((s, row) => s + parse_carton_height_cm(row.carton_dimension), 0);
	}

	function max_stack_layers(carton_dimension) {
		const spec = state.containerSpec || CONTAINER_SPECS["20ft FCL"];
		const containerH = flt(spec.height_cm) || 239;
		const cartonH = parse_carton_height_cm(carton_dimension);
		return Math.max(1, Math.floor(containerH / cartonH));
	}

	function get_unplaced_cartons() {
		return state.cartons.filter((row) => {
			const r = cint(row.position_row);
			const c = cint(row.position_col);
			return !(r > 0 && c > 0) && !is_loaded(row);
		});
	}

	function render_container_planner() {
		const spec = state.containerSpec || CONTAINER_SPECS["20ft FCL"];
		const stacks = build_position_stacks();
		const unplaced = get_unplaced_cartons();
		const search = ($("#sl-tray-search").val() || "").toLowerCase().trim();

		const placedCartons = Object.values(stacks).reduce((s, arr) => s + arr.length, 0);
		const usedCells = Object.keys(stacks).length;
		const totalCells = spec.rows * spec.cols;
		const cellPct = totalCells ? Math.round((usedCells / totalCells) * 100) : 0;
		const usedCbm = state.cartons
			.filter((row) => cint(row.position_row) > 0)
			.reduce((s, row) => s + row_per_carton_cbm(row), 0);
		const usedHeight = Object.values(stacks).reduce((s, stack) => s + stack_height_cm(stack), 0);
		const containerH = flt(spec.height_cm) || 239;
		const heightPct = containerH ? Math.round((usedHeight / containerH) * 100) : 0;
		const pctCbm = spec.capacity_cbm ? Math.round((usedCbm / spec.capacity_cbm) * 100) : 0;
		const barPct = Math.min(100, Math.max(pctCbm, heightPct));
		const cbmClass = pctCbm > 100 || heightPct > 100 ? "progress-bar-danger" : "progress-bar-info";
		$("#sl-container-meta").html(
			`${spec.label || state.containerType} · ${placedCartons} ${__(
				"cartons"
			)} · ${usedCells}/${totalCells} ${__("floor cells")} (${cellPct}%) · ${__(
				"height"
			)} ${usedHeight.toFixed(0)}/${containerH} cm (${heightPct}%) · ${usedCbm.toFixed(2)} / ${
				spec.capacity_cbm
			} CBM (${pctCbm}%)`
		);
		$("#sl-container-cbm-bar")
			.css("width", `${barPct}%`)
			.removeClass("progress-bar-info progress-bar-danger")
			.addClass(cbmClass);

		const trayEntries = get_tray_entries();
		const filtered = search
			? trayEntries.filter(
					(entry) =>
						(entry.chip_title || "").toLowerCase().includes(search) ||
						(entry.chip_subtitle || "").toLowerCase().includes(search) ||
						(entry.so_item || "").toLowerCase().includes(search) ||
						(entry.packing_report || "").toLowerCase().includes(search) ||
						(entry.finished_size || "").toLowerCase().includes(search)
			  )
			: trayEntries;
		const visible = filtered.slice(0, state.trayLimit);

		$("#sl-tray-count").text(`(${trayEntries.length})`);
		const $tray = $("#sl-carton-tray").empty();
		if (!trayEntries.length) {
			$tray.html(`<div class="text-muted small">${__("All cartons are placed or loaded.")}</div>`);
			$("#sl-tray-more").hide();
		} else if (!filtered.length) {
			$tray.html(`<div class="text-muted small">${__("No cartons match your search.")}</div>`);
			$("#sl-tray-more").hide();
		} else {
			visible.forEach((entry) => {
				const autoArgs = entry.auto_fill_args || { carton_rows: [entry.place_name] };
				const $chip = $(`
					<div class="sl-carton-chip" draggable="true" data-name="${frappe.utils.escape_html(
						entry.place_name
					)}" title="${__(
						"Drop to stack on this floor cell (uses vertical layers by carton height)"
					)}">
						<strong>${frappe.utils.escape_html(entry.chip_title || "")}</strong><br>
						${frappe.utils.escape_html(entry.chip_subtitle || "")}
						${entry.chip_meta ? `<br><small class="text-muted">${frappe.utils.escape_html(entry.chip_meta)}</small>` : ""}
						<div class="sl-chip-actions">
							<button type="button" class="btn btn-default btn-xs sl-chip-add-one">${__("+1 Slot")}</button>
							<button type="button" class="btn btn-primary btn-xs sl-chip-auto-add">${__("Auto Add")}</button>
						</div>
					</div>
				`);
				$chip.data("auto-fill-args", autoArgs);
				$chip.on("dragstart", (e) => {
					e.originalEvent.dataTransfer.setData("carton", entry.place_name);
					$chip.addClass("dragging");
				});
				$chip.on("dragend", () => $chip.removeClass("dragging"));
				$chip.find(".sl-chip-add-one").on("click", (e) => {
					e.stopPropagation();
					place_carton_in_next_slot(entry.place_name);
				});
				$chip.find(".sl-chip-auto-add").on("click", (e) => {
					e.stopPropagation();
					auto_fill_container($chip.data("auto-fill-args") || {});
				});
				$tray.append($chip);
			});
			if (filtered.length > visible.length) {
				$("#sl-tray-more")
					.show()
					.text(`${__("Show more")} (${filtered.length - visible.length} ${__("remaining")})`);
			} else {
				$("#sl-tray-more").hide();
			}
		}

		const $grid = $("#sl-container-grid").empty();
		$grid.css("grid-template-columns", `repeat(${spec.cols}, minmax(48px, 1fr))`);

		for (let r = 1; r <= spec.rows; r++) {
			for (let c = 1; c <= spec.cols; c++) {
				const key = `${r}-${c}`;
				const stack = stacks[key] || [];
				const top = stack[stack.length - 1];
				const maxLayers = top ? max_stack_layers(top.carton_dimension) : 7;
				const fillPct = Math.min(100, Math.round((stack_height_cm(stack) / containerH) * 100));
				const stackBlocks = stack
					.map(
						(row, idx) =>
							`<span class="sl-stack-block" style="height:${12 + idx * 4}px;" title="L${
								cint(row.position_layer) || idx + 1
							}"></span>`
					)
					.join("");
				const $slot = $(`
					<div class="sl-container-slot ${stack.length ? "occupied" : ""}" data-row="${r}" data-col="${c}" style="background:linear-gradient(0deg, rgba(15,76,129,${fillPct /
						200}) 0%, rgba(255,255,255,.7) ${100 - fillPct}%, rgba(255,255,255,.7) 100%);">
						<div class="sl-slot-label">R${r} C${c}</div>
						<div class="sl-stack-pill">${stackBlocks}</div>
						${
							stack.length
								? `<span class="sl-stack-count">${stack.length}/${maxLayers}↑</span>`
								: ""
						}
						${top ? `<div class="sl-slot-carton" style="font-size:9px;">${slot_label(top)}</div>` : ""}
					</div>
				`);
				$slot.on("dragover", (e) => {
					e.preventDefault();
					$slot.addClass("drop-hover");
				});
				$slot.on("dragleave", () => $slot.removeClass("drop-hover"));
				$slot.on("drop", (e) => {
					e.preventDefault();
					$slot.removeClass("drop-hover");
					const cartonName = e.originalEvent.dataTransfer.getData("carton");
					if (!cartonName) return;
					place_carton(cartonName, r, c);
				});
				if (top) {
					$slot.on("dblclick", () => clear_carton_position(top.name));
					$slot.attr(
						"title",
						`${__("Double-click to remove top carton")} · ${stack.length} ${__("in stack")}`
					);
				}
				$grid.append($slot);
			}
		}

		render_container_3d(stacks, spec);
		if (state.plannerView === "3d") {
			$("#sl-container-grid").hide();
			$("#sl-container-3d, #sl-3d-legend").show();
		} else if (manufacturing_addon?.container_3d && state.threeViewer) {
			manufacturing_addon.container_3d.destroy(state.threeViewer);
			state.threeViewer = null;
		}
	}

	function place_carton_in_next_slot(carton_name) {
		frappe.call({
			method: `${API}.place_carton_in_next_slot`,
			args: {
				order_sheet: state.selectedOrderSheet,
				carton_name,
				loading_tag: $("#sl-loading-tag").val(),
				mark_loaded: 1,
			},
			callback() {
				load_cartons(state.selectedOrderSheet, { sync: false });
				load_board();
			},
		});
	}

	function auto_fill_container(options = {}) {
		if (!state.selectedOrderSheet) return;
		const args = {
			order_sheet: state.selectedOrderSheet,
			loading_tag: $("#sl-loading-tag").val(),
			stop_at_capacity: 1,
		};
		if (options.carton_rows && options.carton_rows.length) {
			args.carton_rows = options.carton_rows;
		}
		if (options.so_item) {
			args.so_item = options.so_item;
		}
		if (options.finished_size !== undefined && options.finished_size !== null) {
			args.finished_size = options.finished_size;
		}
		frappe.call({
			method: `${API}.auto_fill_container`,
			args,
			freeze: true,
			callback(r) {
				const msg = r.message || {};
				const placed = cint(msg.placed);
				frappe.show_alert({
					message: `${placed} ${__("batch(es) placed")} · ${flt(msg.used_cbm).toFixed(2)} / ${flt(
						msg.capacity_cbm
					).toFixed(0)} CBM (${msg.cbm_percent || 0}%)`,
					indicator: placed ? "green" : "orange",
				});
				load_cartons(state.selectedOrderSheet, { sync: false });
				load_board();
			},
		});
	}

	function place_carton(carton_name, position_row, position_col) {
		frappe.call({
			method: `${API}.place_carton_in_container`,
			args: {
				order_sheet: state.selectedOrderSheet,
				carton_name,
				position_row,
				position_col,
				loading_tag: $("#sl-loading-tag").val(),
				mark_loaded: 1,
			},
			callback() {
				load_cartons(state.selectedOrderSheet, { sync: false });
				load_board();
			},
		});
	}

	function clear_carton_position(carton_name) {
		frappe.call({
			method: `${API}.clear_carton_position`,
			args: { order_sheet: state.selectedOrderSheet, carton_name },
			callback() {
				load_cartons(state.selectedOrderSheet, { sync: false });
			},
		});
	}

	function render_carton_table() {
		const $body = $("#sl-carton-body").empty();
		if (!state.cartons.length) {
			$body.html(
				`<tr><td colspan="10" class="text-center text-muted">${__(
					"No cartons synced yet. Click Sync Cartons to build cartons from packed pieces."
				)}</td></tr>`
			);
			return;
		}

		state.cartons.forEach((row) => {
			const checked = state.selectedCartons.has(row.name) ? "checked" : "";
			const count = cint(row.carton_count) || 1;
			const pos =
				cint(row.position_row) && cint(row.position_col)
					? `R${row.position_row} C${row.position_col} L${cint(row.position_layer) || 1}`
					: "-";
			const loaded = is_loaded(row)
				? `<span class="label label-success">${__("Loaded")}</span>`
				: `<span class="label label-warning">${__("Pending")}</span>`;
			$body.append(`
				<tr class="${is_loaded(row) ? "success" : ""}">
					<td><input type="checkbox" class="sl-carton-check" data-name="${frappe.utils.escape_html(
						row.name
					)}" ${checked} /></td>
					<td><strong>${frappe.utils.escape_html(row.carton_label || "")}</strong><br><small>${count} ${__(
						"ctns"
					)} · ${pos}</small></td>
					<td><a href="/app/packing-report/${encodeURIComponent(row.packing_report)}">${frappe.utils.escape_html(
						row.packing_report
					)}</a></td>
					<td title="${frappe.utils.escape_html(row.so_item || "")}">${frappe.utils.escape_html(
						(row.so_item || "").slice(0, 28)
					)}${(row.so_item || "").length > 28 ? "…" : ""}</td>
					<td>${frappe.utils.escape_html(row.finished_size || "")}</td>
					<td>${format_qty(row.total_pieces || row.qty_in_carton || 0)}<br><small>${count}×${format_qty(
						row.qty_in_carton || 0
					)}</small></td>
					<td>${frappe.utils.escape_html(row.carton_dimension || "")}</td>
					<td>${format_qty(row_per_carton_cbm(row), 4)}<br><small>${format_qty(row.cbm || 0, 2)} ${__(
						"total"
					)}</small></td>
					<td>${frappe.utils.escape_html(row.loading_tag || "-")}</td>
					<td>${loaded}</td>
				</tr>
			`);
		});
	}

	$root.on("click", ".sl-order-item", function (e) {
		e.preventDefault();
		load_cartons($(this).data("order-sheet"));
	});

	$root.on("change", ".sl-carton-check", function () {
		const name = $(this).data("name");
		if (this.checked) state.selectedCartons.add(name);
		else state.selectedCartons.delete(name);
	});

	$root.on("change", "#sl-select-all", function () {
		const checked = this.checked;
		state.selectedCartons.clear();
		$(".sl-carton-check").each(function () {
			this.checked = checked;
			if (checked) state.selectedCartons.add($(this).data("name"));
		});
	});

	$("#sl-select-pending").on("click", () => {
		state.selectedCartons.clear();
		state.cartons.forEach((row) => {
			if (!is_loaded(row)) state.selectedCartons.add(row.name);
		});
		render_carton_table();
	});

	$root.on("click", ".sl-planner-view", function () {
		set_planner_view($(this).data("view"));
	});

	$root.on("click", ".sl-tray-mode", function () {
		state.trayGroupMode = $(this).data("mode");
		state.trayLimit = 40;
		$(".sl-tray-mode").removeClass("active");
		$(this).addClass("active");
		render_container_planner();
	});

	$("#sl-tray-search").on("input", () => {
		state.trayLimit = 40;
		render_container_planner();
	});

	$("#sl-tray-more").on("click", () => {
		state.trayLimit += 40;
		render_container_planner();
	});

	$("#sl-auto-fill-btn").on("click", () => auto_fill_container());

	$("#sl-auto-fill-selected-btn").on("click", () => {
		if (!state.selectedCartons.size) {
			frappe.msgprint(__("Select cartons in the table, or use Auto Add on an item in the tray."));
			return;
		}
		auto_fill_container({ carton_rows: Array.from(state.selectedCartons) });
	});

	$("#sl-sync-btn").on("click", () => {
		if (!state.selectedOrderSheet) return;
		load_cartons(state.selectedOrderSheet, { sync: true });
	});

	$("#sl-container-type").on("change", function () {
		if (!state.selectedOrderSheet) return;
		frappe.call({
			method: `${API}.save_container_settings`,
			args: {
				order_sheet: state.selectedOrderSheet,
				container_type: $(this).val(),
				container_no: $("#sl-container-no").val() || "",
			},
			callback() {
				state.containerType = $("#sl-container-type").val();
				state.containerSpec = CONTAINER_SPECS[state.containerType];
				state.containerEstimate = get_container_estimate_for_type(state.containerType);
				render_consignment_estimate();
				load_cartons(state.selectedOrderSheet, { sync: false });
			},
		});
	});

	$("#sl-clear-selection").on("click", () => {
		state.selectedCartons.clear();
		render_carton_table();
	});

	$("#sl-load-btn").on("click", () => {
		if (!state.selectedOrderSheet || !state.selectedCartons.size) {
			frappe.msgprint(__("Select at least one carton."));
			return;
		}
		const loading_tag = $("#sl-loading-tag").val();
		frappe.call({
			method: `${API}.load_cartons`,
			args: {
				order_sheet: state.selectedOrderSheet,
				carton_rows: Array.from(state.selectedCartons),
				loading_tag,
				container_no: $("#sl-container-no").val() || null,
			},
			freeze: true,
			callback() {
				frappe.show_alert({ message: __("Cartons loaded"), indicator: "green" });
				load_board();
				load_cartons(state.selectedOrderSheet, { sync: false });
			},
		});
	});

	$("#sl-unload-btn").on("click", () => {
		if (!state.selectedOrderSheet || !state.selectedCartons.size) {
			frappe.msgprint(__("Select at least one carton."));
			return;
		}
		frappe.call({
			method: `${API}.unload_cartons`,
			args: {
				order_sheet: state.selectedOrderSheet,
				carton_rows: Array.from(state.selectedCartons),
			},
			freeze: true,
			callback() {
				frappe.show_alert({ message: __("Cartons unloaded"), indicator: "orange" });
				load_board();
				load_cartons(state.selectedOrderSheet, { sync: false });
			},
		});
	});

	load_board();
	frappe.require("/assets/manufacturing_addon/js/shipment_container_3d.js");
};
