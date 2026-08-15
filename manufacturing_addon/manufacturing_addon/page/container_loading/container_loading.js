frappe.pages["container-loading"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Container Loading"),
		single_column: true,
	});

	const API = "manufacturing_addon.manufacturing_addon.page.container_loading.container_loading";
	const state = {
		rows: [],
		filtered: [],
		summary: {},
		dirty: false,
		order_sheet: "",
		packing_report: "",
		only_pending: 0,
		search: "",
		container_filter: "",
		container_nos: [],
	};

	page.set_primary_action(__("Save Loading"), () => save_rows());
	page.add_inner_button(__("Refresh"), () => load_table());
	page.add_inner_button(__("Select Pending"), () => {
		state.rows.forEach((row) => {
			if (!cint(row.is_loaded)) row._checked = 1;
		});
		render_table();
	});
	page.add_inner_button(__("Clear Selection"), () => {
		state.rows.forEach((row) => {
			row._checked = 0;
		});
		render_table();
	});

	$(page.body).html(`
		<div class="cl-portal" style="padding:12px 16px 24px;">
			<style>
				.cl-portal .cl-hero {
					background: linear-gradient(135deg, #0f4c81, #1b6ca8);
					color: #fff; border-radius: 10px; padding: 16px 18px; margin-bottom: 14px;
				}
				.cl-portal .cl-hero h3 { margin: 0; font-weight: 700; }
				.cl-portal .cl-hero p { margin: 6px 0 0; opacity: .92; }
				.cl-portal .cl-filters {
					display:flex; flex-wrap:wrap; gap:12px; align-items:end;
					background:#fff3cd; border:2px solid #ffc107; border-radius:8px;
					padding:14px; margin-bottom:14px;
				}
				.cl-portal .cl-filters .cl-filter-field { min-width:220px; flex:1; }
				.cl-portal .cl-filters label {
					font-size:12px; font-weight:700; color:#856404; margin-bottom:4px; display:block;
				}
				.cl-portal .cl-cards { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:14px; }
				.cl-portal .cl-card {
					background:#fff; border:1px solid #dee2e6; border-radius:8px;
					padding:12px 14px; min-width:120px; flex:1;
				}
				.cl-portal .cl-card .lbl { font-size:11px; color:#6c757d; text-transform:uppercase; }
				.cl-portal .cl-card .val { font-size:20px; font-weight:700; margin-top:4px; }
				.cl-portal .cl-toolbar {
					display:flex; flex-wrap:wrap; gap:10px; align-items:end;
					background:#fff; border:1px solid #dee2e6; border-radius:8px;
					padding:12px; margin-bottom:12px;
				}
				.cl-portal .cl-toolbar .form-group { margin:0; min-width:150px; }
				.cl-portal .cl-toolbar label { font-size:11px; color:#6c757d; margin-bottom:2px; }
				.cl-portal .cl-table-wrap {
					background:#fff; border:1px solid #adb5bd; border-radius:8px; overflow:auto;
					max-height: calc(100vh - 360px);
				}
				.cl-portal table.cl-table {
					width:100%; border-collapse:collapse; font-size:12px; margin:0;
				}
				.cl-portal table.cl-table th {
					position:sticky; top:0; z-index:2; background:#e9ecef; border:1px solid #ced4da;
					padding:8px 6px; text-align:left; white-space:nowrap;
				}
				.cl-portal table.cl-table td {
					border:1px solid #e9ecef; padding:6px; vertical-align:middle;
				}
				.cl-portal table.cl-table tr.loaded { background:#e8f5e9; }
				.cl-portal table.cl-table tr.pending { background:#fff; }
				.cl-portal .cl-empty {
					text-align:center; padding:48px 16px; color:#868e96; background:#fff;
					border:1px dashed #ced4da; border-radius:8px;
				}
				.cl-portal .badge-loaded { background:#28a745; }
				.cl-portal .badge-pending { background:#6c757d; }
				.cl-portal a.cl-container-link { font-weight:600; }
				.cl-portal .cl-search-row { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
			</style>
			<div class="cl-hero">
				<h3><i class="fa fa-cubes"></i> ${__("Container Loading Portal")}</h3>
				<p>${__(
					"1) Select Order Sheet → 2) enter Loading Carton Qty + Container No → 3) tick Loaded Entry → 4) Save."
				)}</p>
			</div>
			<div class="cl-filters">
				<div class="cl-filter-field" id="cl-order-sheet-wrap">
					<label><i class="fa fa-search"></i> ${__("Select Order Sheet")} *</label>
				</div>
				<div class="cl-filter-field" id="cl-packing-report-wrap">
					<label>${__("Packing Report")} (${__("optional")})</label>
				</div>
				<div class="cl-filter-field" style="flex:0;min-width:140px;" id="cl-only-pending-wrap">
					<label>${__("Only Pending")}</label>
				</div>
				<button type="button" class="btn btn-primary btn-sm" id="cl-load-btn" style="height:30px;">
					<i class="fa fa-download"></i> ${__("Load Cartons")}
				</button>
			</div>
			<div class="cl-cards" id="cl-summary"></div>
			<div class="cl-toolbar">
				<div class="form-group">
					<label>${__("Container Type")}</label>
					<select class="form-control input-sm" id="cl-container-type">
						<option value="20ft FCL">20ft FCL</option>
						<option value="40ft FCL">40ft FCL</option>
						<option value="Truck">Truck</option>
						<option value="LCL">LCL</option>
					</select>
				</div>
				<div class="form-group" style="min-width:200px;">
					<label>${__("Container No")}</label>
					<input type="text" class="form-control input-sm" id="cl-container-no"
						list="cl-container-nos" placeholder="${__("e.g. MSKU1234567")}">
					<datalist id="cl-container-nos"></datalist>
				</div>
				<div class="form-group" style="min-width:140px;">
					<label>${__("Loading Tag")}</label>
					<select class="form-control input-sm" id="cl-loading-tag">
						<option value="Manual">Manual</option>
						<option value="Forklift">Forklift</option>
						<option value="Pallet Jack">Pallet Jack</option>
						<option value="Crane">Crane</option>
						<option value="Conveyor">Conveyor</option>
						<option value="Bulk">Bulk</option>
					</select>
				</div>
				<button type="button" class="btn btn-default btn-sm" id="cl-save-header">${__(
					"Save Header"
				)}</button>
				<button type="button" class="btn btn-success btn-sm" id="cl-mark-selected">${__(
					"Mark Selected Loaded Entry"
				)}</button>
				<button type="button" class="btn btn-warning btn-sm" id="cl-unmark-selected">${__(
					"Unmark Selected"
				)}</button>
			</div>
			<div class="cl-search-row">
				<input type="text" class="form-control input-sm" id="cl-search"
					placeholder="${__("Search item / article / colour / packing report / container…")}"
					style="flex:2; min-width:240px;">
				<input type="text" class="form-control input-sm" id="cl-container-filter"
					list="cl-container-nos" placeholder="${__("Filter by Container No")}"
					style="flex:1; min-width:180px;">
				<button type="button" class="btn btn-default btn-sm" id="cl-clear-search">${__("Clear Search")}</button>
			</div>
			<div id="cl-body">
				<div class="cl-empty">
					<i class="fa fa-table fa-3x" style="opacity:.35;"></i>
					<p style="margin-top:12px;">${__("Select an Order Sheet above, then click Load Cartons.")}</p>
				</div>
			</div>
		</div>
	`);

	function make_link(parent, fieldname, options, label, on_change) {
		const control = frappe.ui.form.make_control({
			parent: $(parent),
			df: {
				fieldtype: "Link",
				fieldname,
				options,
				label: "",
				placeholder: label,
			},
			render_input: true,
		});
		control.refresh();
		control.$input.on("change awesomplete-selectcomplete", () => {
			on_change(control.get_value());
		});
		return control;
	}

	const order_sheet_control = make_link(
		"#cl-order-sheet-wrap",
		"order_sheet",
		"Order Sheet",
		__("Search Order Sheet"),
		(val) => {
			state.order_sheet = val || "";
			if (state.order_sheet) load_table();
		}
	);

	const packing_report_control = make_link(
		"#cl-packing-report-wrap",
		"packing_report",
		"Packing Report",
		__("Optional Packing Report"),
		(val) => {
			state.packing_report = val || "";
			if (state.order_sheet) load_table();
		}
	);
	packing_report_control.get_query = () => ({
		filters: state.order_sheet
			? { order_sheet: state.order_sheet, docstatus: 1 }
			: { docstatus: 1 },
	});

	const only_pending_control = frappe.ui.form.make_control({
		parent: $("#cl-only-pending-wrap"),
		df: {
			fieldtype: "Check",
			fieldname: "only_pending",
			label: "",
		},
		render_input: true,
	});
	only_pending_control.refresh();
	only_pending_control.$input.on("change", () => {
		state.only_pending = only_pending_control.get_value() ? 1 : 0;
		if (state.order_sheet) load_table();
	});

	$("#cl-load-btn").on("click", () => load_table());

	function esc(v) {
		return frappe.utils.escape_html(cstr(v || ""));
	}

	function short_item(item) {
		const text = cstr(item || "");
		if (!text) return "";
		return text.length > 42 ? `${text.slice(0, 42)}…` : text;
	}

	function refresh_container_datalist(list) {
		state.container_nos = list || [];
		const html = state.container_nos.map((c) => `<option value="${esc(c)}"></option>`).join("");
		$("#cl-container-nos").html(html);
	}

	function apply_filters() {
		const q = (state.search || "").trim().toLowerCase();
		const cn = (state.container_filter || "").trim().toLowerCase();
		state.filtered = state.rows.filter((row) => {
			if (cn && !(cstr(row.container_no).toLowerCase().includes(cn))) return false;
			if (!q) return true;
			const blob = [
				row.packing_report,
				row.so_item,
				row.article,
				row.colour,
				row.finished_size,
				row.container_no,
				row.remarks,
			]
				.map((x) => cstr(x).toLowerCase())
				.join(" ");
			return blob.includes(q);
		});
	}

	function render_summary() {
		const s = state.summary || {};
		const sl = s.shipment_loading
			? `<a href="/app/shipment-loading/${encodeURIComponent(s.shipment_loading)}">${esc(
					s.shipment_loading
			  )}</a>`
			: "-";
		$("#cl-summary").html(`
			<div class="cl-card"><div class="lbl">${__("Status")}</div><div class="val" style="font-size:16px;">${esc(
				s.status || "-"
			)}</div></div>
			<div class="cl-card"><div class="lbl">${__("Shipment Loading")}</div><div class="val" style="font-size:13px;">${sl}</div></div>
			<div class="cl-card"><div class="lbl">${__("Ready Ctn")}</div><div class="val">${cint(
				s.total_cartons
			)}</div></div>
			<div class="cl-card"><div class="lbl">${__("Loaded Entry")}</div><div class="val" style="color:#28a745;">${cint(
				s.loaded_cartons
			)}</div></div>
			<div class="cl-card"><div class="lbl">${__("Pending")}</div><div class="val" style="color:#f0ad4e;">${cint(
				s.pending_cartons
			)}</div></div>
			<div class="cl-card"><div class="lbl">${__("Pieces Ready")}</div><div class="val">${format_number(
				flt(s.total_pieces_ready),
				null,
				0
			)}</div></div>
			<div class="cl-card"><div class="lbl">${__("CBM")}</div><div class="val">${format_number(
				flt(s.total_cbm),
				null,
				2
			)}</div></div>
		`);
		if (s.container_type) $("#cl-container-type").val(s.container_type);
		if (s.container_no != null) $("#cl-container-no").val(s.container_no || "");
	}

	function render_table() {
		apply_filters();
		if (!state.filtered.length) {
			$("#cl-body").html(`
				<div class="cl-empty">
					<i class="fa fa-inbox fa-3x" style="opacity:.35;"></i>
					<p style="margin-top:12px;">${
						state.rows.length
							? __("No rows match your search / container filter.")
							: __("No packing cartons found for this Order Sheet.")
					}</p>
				</div>
			`);
			return;
		}

		const body = state.filtered
			.map((row) => {
				const idx = state.rows.indexOf(row);
				const loaded = cint(row.is_loaded);
				const checked = cint(row._checked);
				const loadQty = cint(row.load_cartons) || (loaded ? cint(row.carton_count) : 0);
				const cbmShow = flt(row.per_carton_cbm) * (cint(row.carton_count) || 1) || flt(row.cbm);
				const containerCell = row.container_no
					? `<a href="#" class="cl-container-link" data-container="${esc(
							row.container_no
					  )}">${esc(row.container_no)}</a>`
					: `<span class="text-muted">—</span>`;
				return `
				<tr class="${loaded ? "loaded" : "pending"}" data-idx="${idx}">
					<td style="text-align:center;">
						<input type="checkbox" class="cl-check" data-idx="${idx}" ${checked ? "checked" : ""}>
					</td>
					<td style="text-align:center;font-weight:600;">${idx + 1}</td>
					<td>${esc(row.packing_report)}</td>
					<td title="${esc(row.so_item)}">${esc(short_item(row.so_item))}</td>
					<td>${esc(row.article)}</td>
					<td>${esc(row.colour)}</td>
					<td>${esc(row.finished_size)}</td>
					<td style="text-align:right;">${flt(row.qty_in_carton)}</td>
					<td style="text-align:right;font-weight:600;">${cint(row.carton_count)}</td>
					<td style="text-align:right;">
						<input type="number" min="0" max="${cint(row.carton_count)}"
							class="form-control input-xs cl-load-qty" data-idx="${idx}"
							value="${loadQty}" style="width:80px;text-align:right;">
					</td>
					<td style="text-align:right;">${format_number(flt(row.total_pieces), null, 0)}</td>
					<td style="text-align:right;" title="${esc(row.carton_dimension || "")}">${format_number(
					cbmShow,
					null,
					3
				)}</td>
					<td>
						<input type="text" class="form-control input-xs cl-row-container" data-idx="${idx}"
							list="cl-container-nos" value="${esc(row.container_no)}" style="min-width:120px;"
							placeholder="${__("Container No")}">
						<div style="margin-top:2px;">${containerCell}</div>
					</td>
					<td style="text-align:center;">
						<input type="checkbox" class="cl-loaded" data-idx="${idx}" ${loaded ? "checked" : ""}>
					</td>
					<td>
						<span class="badge ${loaded ? "badge-loaded" : "badge-pending"}">
							${loaded ? __("Loaded Entry") : __("Pending")}
						</span>
					</td>
					<td>
						<input type="text" class="form-control input-xs cl-remarks" data-idx="${idx}"
							value="${esc(row.remarks)}" style="min-width:120px;">
					</td>
				</tr>`;
			})
			.join("");

		$("#cl-body").html(`
			<div class="cl-table-wrap">
				<table class="cl-table">
					<thead>
						<tr>
							<th style="width:36px;"><input type="checkbox" id="cl-check-all" title="${__(
								"Select all"
							)}"></th>
							<th>${__("S.No")}</th>
							<th>${__("Packing Report")}</th>
							<th>${__("Item")}</th>
							<th>${__("Article")}</th>
							<th>${__("Colour")}</th>
							<th>${__("Size")}</th>
							<th>${__("Qty/Ctn")}</th>
							<th>${__("Ready Ctn")}</th>
							<th>${__("Loading Carton Qty")}</th>
							<th>${__("Pcs")}</th>
							<th>${__("CBM")}</th>
							<th>${__("Container No")}</th>
							<th>${__("Loaded Entry")}</th>
							<th>${__("Status")}</th>
							<th>${__("Remarks")}</th>
						</tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
			</div>
			<div class="text-muted small" style="margin-top:8px;">
				${__("Showing")} ${state.filtered.length} / ${state.rows.length} ${__("rows")}
				${state.dirty ? " · <b style='color:#c0392b'>" + __("Unsaved changes") + "</b>" : ""}
			</div>
		`);
	}

	function load_table() {
		state.order_sheet = order_sheet_control.get_value() || state.order_sheet || "";
		state.packing_report = packing_report_control.get_value() || "";
		state.only_pending = only_pending_control.get_value() ? 1 : 0;

		const order_sheet = state.order_sheet;
		if (!order_sheet) {
			state.rows = [];
			state.summary = {};
			render_summary();
			$("#cl-body").html(`
				<div class="cl-empty">
					<i class="fa fa-table fa-3x" style="opacity:.35;"></i>
					<p style="margin-top:12px;">${__("Select an Order Sheet above, then click Load Cartons.")}</p>
				</div>
			`);
			frappe.show_alert({ message: __("Please select Order Sheet first"), indicator: "orange" });
			return;
		}

		$("#cl-body").html(
			`<div class="cl-empty"><i class="fa fa-spinner fa-spin fa-2x"></i><p style="margin-top:10px;">${__(
				"Loading packing cartons..."
			)}</p></div>`
		);

		frappe.call({
			method: `${API}.get_portal_board`,
			args: {
				order_sheet,
				packing_report: state.packing_report || "",
				only_pending: state.only_pending || 0,
			},
			callback(r) {
				const msg = r.message || {};
				state.rows = (msg.rows || []).map((row) => ({
					...row,
					_checked: 0,
					_orig_loaded: cint(row.is_loaded),
					_orig_load_cartons: cint(row.load_cartons),
					_orig_container: row.container_no || "",
				}));
				state.summary = msg.summary || {};
				refresh_container_datalist(msg.container_nos || []);
				state.dirty = false;
				render_summary();
				render_table();
			},
			error() {
				$("#cl-body").html(
					`<div class="cl-empty text-danger">${__("Failed to load cartons.")}</div>`
				);
			},
		});
	}

	function collect_changed_rows() {
		return state.rows
			.filter(
				(row) =>
					cint(row.is_loaded) !== cint(row._orig_loaded) ||
					cint(row.load_cartons) !== cint(row._orig_load_cartons) ||
					cstr(row.container_no) !== cstr(row._orig_container) ||
					row._remarks_changed
			)
			.map((row) => ({
				name: row.name,
				is_loaded: cint(row.is_loaded),
				load_cartons: cint(row.load_cartons),
				container_no: row.container_no || "",
				remarks: row.remarks || "",
			}));
	}

	function save_rows(force_selected = false) {
		const order_sheet = order_sheet_control.get_value() || state.order_sheet;
		if (!order_sheet) {
			frappe.msgprint(__("Select Order Sheet first (yellow box at top)."));
			return;
		}

		const headerContainer = $("#cl-container-no").val() || "";
		let payload = collect_changed_rows();
		if (force_selected === "load" || force_selected === "unload") {
			payload = state.rows
				.filter((row) => cint(row._checked))
				.map((row) => {
					const ready = cint(row.carton_count) || 1;
					let loadQty = cint(row.load_cartons);
					if (force_selected === "load" && loadQty <= 0) loadQty = ready;
					if (force_selected === "unload") loadQty = 0;
					return {
						name: row.name,
						is_loaded: force_selected === "load" ? 1 : 0,
						load_cartons: loadQty,
						container_no: row.container_no || headerContainer,
						remarks: row.remarks || "",
					};
				});
		}

		if (!payload.length) {
			frappe.msgprint(
				__("No changes to save. Set Loading Carton Qty / Container No, tick Loaded Entry, then Save.")
			);
			return;
		}

		frappe.call({
			method: `${API}.save_portal_rows`,
			args: {
				order_sheet,
				rows: payload,
				container_no: headerContainer,
				loading_tag: $("#cl-loading-tag").val() || "Manual",
			},
			freeze: true,
			freeze_message: __("Saving..."),
			callback(r) {
				const msg = r.message || {};
				frappe.show_alert({
					message: __("Updated {0} row(s)", [msg.updated || 0]),
					indicator: "green",
				});
				load_table();
			},
		});
	}

	$(page.body).on("change", ".cl-check", function () {
		const idx = cint($(this).data("idx"));
		if (state.rows[idx]) state.rows[idx]._checked = $(this).is(":checked") ? 1 : 0;
	});

	$(page.body).on("change", "#cl-check-all", function () {
		const on = $(this).is(":checked") ? 1 : 0;
		state.filtered.forEach((row) => {
			row._checked = on;
		});
		render_table();
		$("#cl-check-all").prop("checked", !!on);
	});

	$(page.body).on("change", ".cl-loaded", function () {
		const idx = cint($(this).data("idx"));
		if (!state.rows[idx]) return;
		const on = $(this).is(":checked") ? 1 : 0;
		state.rows[idx].is_loaded = on;
		if (on && !cint(state.rows[idx].load_cartons)) {
			state.rows[idx].load_cartons = cint(state.rows[idx].carton_count) || 1;
		}
		if (on && !state.rows[idx].container_no) {
			state.rows[idx].container_no = $("#cl-container-no").val() || "";
		}
		if (!on) {
			state.rows[idx].load_cartons = 0;
		}
		state.dirty = true;
		render_table();
	});

	$(page.body).on("change", ".cl-load-qty", function () {
		const idx = cint($(this).data("idx"));
		if (!state.rows[idx]) return;
		let qty = cint($(this).val());
		const max = cint(state.rows[idx].carton_count) || 0;
		if (qty < 0) qty = 0;
		if (max && qty > max) qty = max;
		state.rows[idx].load_cartons = qty;
		if (qty > 0) state.rows[idx].is_loaded = 1;
		state.dirty = true;
		render_table();
	});

	$(page.body).on("change", ".cl-row-container", function () {
		const idx = cint($(this).data("idx"));
		if (!state.rows[idx]) return;
		state.rows[idx].container_no = $(this).val() || "";
		state.dirty = true;
	});

	$(page.body).on("click", ".cl-container-link", function (e) {
		e.preventDefault();
		const cn = $(this).data("container") || "";
		$("#cl-container-filter").val(cn);
		state.container_filter = cn;
		render_table();
	});

	$(page.body).on("change", ".cl-remarks", function () {
		const idx = cint($(this).data("idx"));
		if (!state.rows[idx]) return;
		state.rows[idx].remarks = $(this).val();
		state.rows[idx]._remarks_changed = 1;
		state.dirty = true;
	});

	$("#cl-search").on("input", function () {
		state.search = $(this).val() || "";
		render_table();
	});
	$("#cl-container-filter").on("input change", function () {
		state.container_filter = $(this).val() || "";
		render_table();
	});
	$("#cl-clear-search").on("click", () => {
		state.search = "";
		state.container_filter = "";
		$("#cl-search").val("");
		$("#cl-container-filter").val("");
		render_table();
	});

	$("#cl-save-header").on("click", () => {
		const order_sheet = order_sheet_control.get_value() || state.order_sheet;
		if (!order_sheet) {
			frappe.msgprint(__("Select Order Sheet first (yellow box at top)."));
			return;
		}
		frappe.call({
			method: `${API}.save_portal_header`,
			args: {
				order_sheet,
				container_type: $("#cl-container-type").val(),
				container_no: $("#cl-container-no").val() || "",
			},
			freeze: true,
			callback() {
				frappe.show_alert({ message: __("Header saved"), indicator: "green" });
				load_table();
			},
		});
	});

	$("#cl-mark-selected").on("click", () => save_rows("load"));
	$("#cl-unmark-selected").on("click", () => save_rows("unload"));

	// Open from Packing Report / route options
	const opts = frappe.route_options || {};
	frappe.route_options = null;
	if (opts.order_sheet) {
		order_sheet_control.set_value(opts.order_sheet);
		state.order_sheet = opts.order_sheet;
	}
	if (opts.packing_report) {
		packing_report_control.set_value(opts.packing_report);
		state.packing_report = opts.packing_report;
	}
	if (opts.order_sheet) {
		setTimeout(load_table, 250);
	}
};
