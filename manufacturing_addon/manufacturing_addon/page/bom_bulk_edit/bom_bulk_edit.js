// Copyright (c) 2026, Manufacturing Addon and contributors
frappe.pages["bom-bulk-edit"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Bulk Edit BOM"),
		single_column: true,
	});

	const API = "manufacturing_addon.manufacturing_addon.page.bom_bulk_edit.bom_bulk_edit";
	const state = {
		page,
		sales_order: "",
		item_template: "",
		variants_only: 1,
		meta: {},
		rows: [],
		rm_columns: [],
		cells: {}, // "item::rm" -> {qty, uom}
		dirty: false,
		selected: { row: null, col: null },
		fill: null, // { startRow, col, value } while dragging
	};

	page.set_primary_action(__("Save New BOM Versions"), () => save_matrix(state));
	page.add_inner_button(__("Refresh"), () => load_matrix(state));
	page.add_inner_button(__("Add Material"), () => add_material_dialog(state));
	page.add_inner_button(__("Replace RM"), () => replace_rm_dialog(state));

	render_shell(page, state);
};

function render_shell(page, state) {
	$(page.body).html(`
		<div class="bbe-portal" style="padding:12px 16px 28px;">
			<style>
				.bbe-portal .bbe-hero {
					background: linear-gradient(135deg, #1e3a5f, #2f6fed);
					color:#fff !important; border-radius:10px; padding:16px 18px; margin-bottom:14px;
				}
				.bbe-portal .bbe-hero h3,
				.bbe-portal .bbe-hero h3 *,
				.bbe-portal .bbe-hero .fa {
					margin:0; font-weight:700; color:#ffffff !important;
				}
				.bbe-portal .bbe-hero p {
					margin:6px 0 0; opacity:.92; font-size:13px; color:#ffffff !important;
				}
				.bbe-portal .bbe-filters {
					display:flex; flex-wrap:wrap; gap:12px; align-items:end;
					background:#fff3cd; border:2px solid #ffc107; border-radius:8px;
					padding:14px; margin-bottom:14px;
				}
				.bbe-portal .bbe-filters label {
					font-size:12px; font-weight:700; color:#856404; display:block; margin-bottom:4px;
				}
				.bbe-portal .bbe-cards { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }
				.bbe-portal .bbe-card {
					background:#fff; border:1px solid #dee2e6; border-radius:8px;
					padding:10px 14px; min-width:110px;
				}
				.bbe-portal .bbe-card .lbl { font-size:11px; color:#6c757d; text-transform:uppercase; }
				.bbe-portal .bbe-card .val { font-size:16px; font-weight:700; margin-top:2px; }
				.bbe-portal .bbe-toolbar {
					display:flex; flex-wrap:wrap; gap:8px; align-items:center;
					background:#fff; border:1px solid #dee2e6; border-radius:8px;
					padding:10px 12px; margin-bottom:10px;
				}
				.bbe-portal .bbe-banner {
					background:#e7f1ff; border:1px solid #b6d4fe; color:#084298;
					border-radius:8px; padding:10px 12px; margin-bottom:10px; font-size:12px;
				}
				.bbe-portal .bbe-table-wrap {
					background:#fff; border:1px solid #adb5bd; border-radius:8px;
					overflow:auto; max-height: calc(100vh - 340px);
				}
				.bbe-portal table.bbe-table {
					border-collapse:collapse; font-size:12px; margin:0; min-width:100%;
				}
				.bbe-portal table.bbe-table th {
					position:sticky; top:0; z-index:3; background:#e9ecef;
					border:1px solid #ced4da; padding:8px 6px; white-space:nowrap;
					text-align:left; font-weight:700;
				}
				.bbe-portal table.bbe-table th.rm-col {
					min-width:110px; max-width:160px; text-align:center;
					background:#dbeafe; vertical-align:bottom;
				}
				.bbe-portal table.bbe-table th.sticky-l {
					position:sticky; left:0; z-index:4; background:#e9ecef;
				}
				.bbe-portal table.bbe-table td {
					border:1px solid #e9ecef; padding:4px 6px; vertical-align:middle;
					position:relative;
				}
				.bbe-portal table.bbe-table td.sticky-l {
					position:sticky; left:0; z-index:2; background:#fff;
					font-weight:600; max-width:220px;
				}
				.bbe-portal table.bbe-table tr.dirty td.sticky-l { background:#fff8e1; }
				.bbe-portal table.bbe-table tr.selected-row td { background:#f0f7ff; }
				.bbe-portal table.bbe-table tr.selected-row td.sticky-l { background:#dbeafe; }
				.bbe-portal .bbe-cell {
					width:100%; min-width:72px; text-align:right; border:1px solid transparent;
					padding:4px 6px; border-radius:4px; background:transparent;
				}
				.bbe-portal .bbe-cell:focus {
					outline:none; border-color:#2f6fed; background:#fff; box-shadow:0 0 0 2px rgba(47,111,237,.2);
				}
				.bbe-portal .bbe-cell.empty { color:#adb5bd; }
				.bbe-portal .bbe-cell.has-val { font-weight:600; }
				.bbe-portal td.cell-active { outline:2px solid #2f6fed; outline-offset:-2px; background:#eff6ff !important; }
				.bbe-portal .fill-handle {
					position:absolute; right:1px; bottom:1px; width:8px; height:8px;
					background:#2f6fed; cursor:crosshair; border-radius:1px; display:none; z-index:5;
				}
				.bbe-portal td.cell-active .fill-handle { display:block; }
				.bbe-portal td.fill-target { background:#bfdbfe !important; }
				.bbe-portal .rm-code { font-size:11px; font-weight:700; color:#1e40af; display:block; }
				.bbe-portal .rm-name { font-size:10px; color:#64748b; display:block; max-width:140px;
					overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
				.bbe-portal .bbe-empty {
					text-align:center; padding:48px 16px; color:#868e96; background:#fff;
					border:1px dashed #ced4da; border-radius:8px;
				}
				.bbe-portal .badge-dirty { background:#f59e0b; }
				.bbe-portal .badge-ok { background:#16a34a; }
			</style>
			<div class="bbe-hero">
				<h3><i class="fa fa-th"></i> ${__("Bulk Edit BOM Versions")}</h3>
				<p>${__(
					"Loads Item Template → Variant items from the Sales Order. Same RM = same column. Edit / fill-down / replace / add material, then Save new default BOM versions."
				)}</p>
			</div>
			<div class="bbe-filters">
				<div style="flex:2;min-width:260px;">
					<label>${__("Sales Order")}</label>
					<div id="bbe-so-wrap"></div>
				</div>
				<div style="flex:1;min-width:200px;">
					<label>${__("Item Template (optional)")}</label>
					<div id="bbe-template-wrap"></div>
				</div>
				<div style="min-width:140px;">
					<label>&nbsp;</label>
					<label style="font-weight:500;color:#856404;display:flex;gap:6px;align-items:center;">
						<input type="checkbox" id="bbe-variants-only" checked>
						${__("Variants only")}
					</label>
				</div>
				<button type="button" class="btn btn-primary btn-sm" id="bbe-load" style="height:30px;">
					<i class="fa fa-download"></i> ${__("Load Variant BOMs")}
				</button>
			</div>
			<div id="bbe-body">
				<div class="bbe-empty">${__(
					"Select a Sales Order — loads its Item Template variant items and default BOMs"
				)}</div>
			</div>
		</div>
	`);

	const so_control = frappe.ui.form.make_control({
		parent: $(page.body).find("#bbe-so-wrap"),
		df: {
			fieldtype: "Link",
			fieldname: "sales_order",
			options: "Sales Order",
			placeholder: __("Search Sales Order"),
			only_select: 1,
			get_query() {
				return { filters: { docstatus: 1 } };
			},
		},
		render_input: true,
	});
	so_control.refresh();

	const template_control = frappe.ui.form.make_control({
		parent: $(page.body).find("#bbe-template-wrap"),
		df: {
			fieldtype: "Link",
			fieldname: "item_template",
			options: "Item",
			placeholder: __("Filter by Item Template"),
			only_select: 1,
			get_query() {
				return { filters: { has_variants: 1 } };
			},
		},
		render_input: true,
	});
	template_control.refresh();

	state.controls = { sales_order: so_control, item_template: template_control };
	so_control.$input.on("change awesomplete-selectcomplete", () => {
		state.sales_order = so_control.get_value() || "";
		if (state.sales_order) load_matrix(state);
	});
	template_control.$input.on("change awesomplete-selectcomplete", () => {
		state.item_template = template_control.get_value() || "";
	});
	$(page.body).find("#bbe-variants-only").on("change", function () {
		state.variants_only = $(this).is(":checked") ? 1 : 0;
	});

	$(page.body).find("#bbe-load").on("click", () => {
		state.sales_order = so_control.get_value() || state.sales_order;
		state.item_template = template_control.get_value() || "";
		state.variants_only = $(page.body).find("#bbe-variants-only").is(":checked") ? 1 : 0;
		if (!state.sales_order) {
			frappe.show_alert({ message: __("Select Sales Order first"), indicator: "orange" });
			return;
		}
		load_matrix(state);
	});
}

function cell_key(item, rm) {
	return `${item}::${rm}`;
}

function get_cell(state, item, rm) {
	const k = cell_key(item, rm);
	if (!state.cells[k]) state.cells[k] = { qty: "", uom: "" };
	return state.cells[k];
}

function mark_dirty(state, item_code) {
	const row = state.rows.find((r) => r.item_code === item_code);
	if (row) row.dirty = 1;
	state.dirty = true;
}

function load_matrix(state) {
	const so =
		(state.controls.sales_order && state.controls.sales_order.get_value()) || state.sales_order;
	if (!so) {
		frappe.show_alert({ message: __("Select Sales Order first"), indicator: "orange" });
		return;
	}
	state.sales_order = so;
	state.item_template =
		(state.controls.item_template && state.controls.item_template.get_value()) ||
		state.item_template ||
		"";
	state.variants_only = $("#bbe-variants-only").is(":checked") ? 1 : 0;

	$("#bbe-body").html(
		`<div class="bbe-empty"><i class="fa fa-spinner fa-spin fa-2x"></i><div style="margin-top:12px;">${__(
			"Loading variant items & BOMs…"
		)}</div></div>`
	);

	frappe.call({
		method: `${API}.get_bom_matrix`,
		args: {
			sales_order: so,
			item_template: state.item_template || null,
			variants_only: state.variants_only,
		},
		callback(r) {
			const msg = r.message || {};
			state.meta = msg;
			state.rows = (msg.rows || []).map((row) => ({ ...row, dirty: 0, _checked: 1 }));
			state.rm_columns = (msg.rm_columns || []).map((c) => ({ ...c }));
			state.cells = { ...(msg.cells || {}) };
			Object.keys(state.cells).forEach((k) => {
				const c = state.cells[k];
				if (c && c.qty !== undefined && c.qty !== null && c.qty !== "") {
					c.qty = flt(c.qty);
				}
			});
			state.dirty = false;
			// If templates returned and filter empty, keep link options aware
			render_matrix(state);
		},
		error() {
			$("#bbe-body").html(
				`<div class="bbe-empty text-danger">${__("Failed to load BOM matrix")}</div>`
			);
		},
	});
}

function render_matrix(state) {
	const meta = state.meta || {};
	const rows = state.rows || [];
	const cols = state.rm_columns || [];

	if (!rows.length) {
		$("#bbe-body").html(
			`<div class="bbe-empty">${__(
				"No Item Template variant items found on this Sales Order. Uncheck “Variants only” to include all items, or pick another SO."
			)}</div>`
		);
		return;
	}

	const dirty_n = rows.filter((r) => cint(r.dirty)).length;
	const templates = meta.templates || [];
	const cards = `
		<div class="bbe-cards">
			<div class="bbe-card"><div class="lbl">${__("Sales Order")}</div><div class="val" style="font-size:13px;">
				<a href="/app/sales-order/${encodeURIComponent(meta.sales_order || "")}">${frappe.utils.escape_html(
		meta.sales_order || ""
	)}</a>
			</div></div>
			<div class="bbe-card"><div class="lbl">${__("Customer")}</div><div class="val" style="font-size:13px;">${frappe.utils.escape_html(
				meta.customer || "—"
			)}</div></div>
			<div class="bbe-card"><div class="lbl">${__("Item Templates")}</div><div class="val" style="font-size:13px;">${
				templates.length
					? frappe.utils.escape_html(templates.join(", "))
					: "—"
			}</div></div>
			<div class="bbe-card"><div class="lbl">${__("Variant Items")}</div><div class="val">${rows.length}</div></div>
			<div class="bbe-card"><div class="lbl">${__("Raw Materials")}</div><div class="val">${cols.length}</div></div>
			<div class="bbe-card"><div class="lbl">${__("Changed")}</div><div class="val" style="color:#d97706;">${dirty_n}</div></div>
		</div>
	`;

	const head_rm = cols
		.map(
			(c, ci) => `
			<th class="rm-col" data-col="${ci}" title="${frappe.utils.escape_html(c.item_code)}">
				<span class="rm-code">${frappe.utils.escape_html(c.item_code)}</span>
				<span class="rm-name">${frappe.utils.escape_html(c.item_name || "")}</span>
				<span style="font-size:10px;color:#64748b;">${frappe.utils.escape_html(c.uom || "")}</span>
			</th>`
		)
		.join("");

	const body = rows
		.map((row, ri) => {
			const cells = cols
				.map((c, ci) => {
					const cell = get_cell(state, row.item_code, c.item_code);
					const qty = cell.qty === 0 || cell.qty ? cell.qty : "";
					const has = qty !== "" && flt(qty) !== 0;
					return `
					<td data-row="${ri}" data-col="${ci}" data-item="${frappe.utils.escape_html(
						row.item_code
					)}" data-rm="${frappe.utils.escape_html(c.item_code)}" class="bbe-td">
						<input type="number" step="any" min="0" class="bbe-cell ${
							has ? "has-val" : "empty"
						}"
							value="${has ? qty : ""}" placeholder="—" data-row="${ri}" data-col="${ci}">
						<div class="fill-handle" title="${__("Drag to fill down")}"></div>
					</td>`;
				})
				.join("");
			return `
			<tr data-row="${ri}" class="${cint(row.dirty) ? "dirty" : ""}">
				<td style="text-align:center;width:36px;">
					<input type="checkbox" class="bbe-sel" data-row="${ri}" ${cint(row._checked) ? "checked" : ""}>
				</td>
				<td style="white-space:nowrap;font-weight:700;color:#1e40af;">
					${
						row.item_template
							? `<a href="/app/item/${encodeURIComponent(row.item_template)}">${frappe.utils.escape_html(
									row.item_template
							  )}</a>`
							: `<span class="text-muted">—</span>`
					}
				</td>
				<td class="sticky-l" title="${frappe.utils.escape_html(row.item_code)}">
					<div>${frappe.utils.escape_html(row.item_code)}</div>
					<div style="font-size:10px;color:#64748b;font-weight:400;">${frappe.utils.escape_html(
						row.item_name || ""
					)}</div>
					${
						row.attributes_label
							? `<div style="font-size:10px;color:#0f766e;">${frappe.utils.escape_html(
									row.attributes_label
							  )}</div>`
							: ""
					}
					${
						cint(row.dirty)
							? `<span class="badge badge-dirty">${__("edited")}</span>`
							: cint(row.is_variant)
							? `<span class="badge" style="background:#6366f1;">${__("variant")}</span>`
							: ""
					}
				</td>
				<td style="white-space:nowrap;">
					${
						row.bom_no
							? `<a href="/app/bom/${encodeURIComponent(row.bom_no)}">${frappe.utils.escape_html(
									row.bom_no
							  )}</a>`
							: `<span class="text-danger">${__("No BOM")}</span>`
					}
					${cint(row.is_default) ? ` <span class="badge badge-ok">default</span>` : ""}
				</td>
				<td style="text-align:right;">${format_number(row.so_qty, null, 0)}</td>
				${cells}
			</tr>`;
		})
		.join("");

	$("#bbe-body").html(`
		<div class="bbe-banner"><i class="fa fa-info-circle"></i> ${frappe.utils.escape_html(
			meta.note || ""
		)}</div>
		${cards}
		<div class="bbe-toolbar">
			<button type="button" class="btn btn-default btn-xs" id="bbe-select-all">${__("Select All")}</button>
			<button type="button" class="btn btn-default btn-xs" id="bbe-select-none">${__("Clear Selection")}</button>
			<button type="button" class="btn btn-info btn-xs" id="bbe-apply-rest">${__(
				"Apply Active Cell Qty to Selected"
			)}</button>
			<button type="button" class="btn btn-warning btn-xs" id="bbe-replace">${__("Replace RM…")}</button>
			<button type="button" class="btn btn-success btn-xs" id="bbe-add-rm">${__("Add Material…")}</button>
			<span class="text-muted" style="font-size:11px;margin-left:8px;">
				${__("Tip: click a cell, then drag the blue square down to fill like Excel")}
			</span>
		</div>
		<div class="bbe-table-wrap">
			<table class="bbe-table">
				<thead>
					<tr>
						<th style="width:36px;"></th>
						<th>${__("Item Template")}</th>
						<th class="sticky-l">${__("Variant Item")}</th>
						<th>${__("Current BOM")}</th>
						<th>${__("SO Qty")}</th>
						${head_rm}
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		</div>
	`);

	bind_matrix_events(state);
}

function bind_matrix_events(state) {
	const $body = $("#bbe-body");

	$body.find("#bbe-select-all").on("click", () => {
		state.rows.forEach((r) => (r._checked = 1));
		render_matrix(state);
	});
	$body.find("#bbe-select-none").on("click", () => {
		state.rows.forEach((r) => (r._checked = 0));
		render_matrix(state);
	});
	$body.find("#bbe-apply-rest").on("click", () => apply_active_to_selected(state));
	$body.find("#bbe-replace").on("click", () => replace_rm_dialog(state));
	$body.find("#bbe-add-rm").on("click", () => add_material_dialog(state));

	$body.on("change", ".bbe-sel", function () {
		const ri = cint($(this).data("row"));
		if (state.rows[ri]) state.rows[ri]._checked = $(this).is(":checked") ? 1 : 0;
	});

	$body.on("focus", ".bbe-cell", function () {
		$body.find("td.cell-active").removeClass("cell-active");
		const $td = $(this).closest("td");
		$td.addClass("cell-active");
		state.selected = {
			row: cint($(this).data("row")),
			col: cint($(this).data("col")),
		};
	});

	$body.on("change input", ".bbe-cell", function () {
		const ri = cint($(this).data("row"));
		const ci = cint($(this).data("col"));
		const row = state.rows[ri];
		const col = state.rm_columns[ci];
		if (!row || !col) return;
		const val = $(this).val();
		const cell = get_cell(state, row.item_code, col.item_code);
		cell.qty = val === "" ? "" : flt(val);
		if (!cell.uom && col.uom) cell.uom = col.uom;
		mark_dirty(state, row.item_code);
		$(this).toggleClass("has-val", cell.qty !== "" && flt(cell.qty) !== 0);
		$(this).toggleClass("empty", !(cell.qty !== "" && flt(cell.qty) !== 0));
		$(this).closest("tr").addClass("dirty");
	});

	// Excel-like fill handle
	$body.on("mousedown", ".fill-handle", function (e) {
		e.preventDefault();
		e.stopPropagation();
		const $td = $(this).closest("td");
		const ri = cint($td.data("row"));
		const ci = cint($td.data("col"));
		const row = state.rows[ri];
		const col = state.rm_columns[ci];
		if (!row || !col) return;
		const cell = get_cell(state, row.item_code, col.item_code);
		state.fill = {
			startRow: ri,
			col: ci,
			value: cell.qty,
			uom: cell.uom || col.uom || "",
		};
		$(document)
			.off(".bbeFill")
			.on("mousemove.bbeFill", (ev) => on_fill_move(state, ev))
			.on("mouseup.bbeFill", () => on_fill_end(state));
	});
}

function on_fill_move(state, ev) {
	if (!state.fill) return;
	const el = document.elementFromPoint(ev.clientX, ev.clientY);
	const $td = $(el).closest("td.bbe-td");
	$("#bbe-body").find("td.fill-target").removeClass("fill-target");
	if (!$td.length) return;
	const ri = cint($td.data("row"));
	const ci = cint($td.data("col"));
	if (ci !== state.fill.col) return;
	const from = Math.min(state.fill.startRow, ri);
	const to = Math.max(state.fill.startRow, ri);
	for (let i = from; i <= to; i++) {
		$(`#bbe-body td.bbe-td[data-row="${i}"][data-col="${ci}"]`).addClass("fill-target");
	}
	state.fill.endRow = ri;
}

function on_fill_end(state) {
	$(document).off(".bbeFill");
	if (!state.fill || state.fill.endRow == null) {
		state.fill = null;
		$("#bbe-body").find("td.fill-target").removeClass("fill-target");
		return;
	}
	const ci = state.fill.col;
	const col = state.rm_columns[ci];
	const from = Math.min(state.fill.startRow, state.fill.endRow);
	const to = Math.max(state.fill.startRow, state.fill.endRow);
	for (let i = from; i <= to; i++) {
		const row = state.rows[i];
		if (!row || !col) continue;
		const cell = get_cell(state, row.item_code, col.item_code);
		cell.qty = state.fill.value;
		if (state.fill.uom) cell.uom = state.fill.uom;
		mark_dirty(state, row.item_code);
	}
	state.fill = null;
	render_matrix(state);
	frappe.show_alert({ message: __("Filled down"), indicator: "green" });
}

function apply_active_to_selected(state) {
	const sel = state.selected;
	if (sel.row == null || sel.col == null) {
		frappe.show_alert({
			message: __("Click a cell first, then Apply to Selected"),
			indicator: "orange",
		});
		return;
	}
	const src = state.rows[sel.row];
	const col = state.rm_columns[sel.col];
	if (!src || !col) return;
	const src_cell = get_cell(state, src.item_code, col.item_code);
	let n = 0;
	state.rows.forEach((row) => {
		if (!cint(row._checked)) return;
		const cell = get_cell(state, row.item_code, col.item_code);
		cell.qty = src_cell.qty;
		cell.uom = src_cell.uom || col.uom || cell.uom;
		mark_dirty(state, row.item_code);
		n++;
	});
	render_matrix(state);
	frappe.show_alert({
		message: __("Applied qty to {0} selected row(s)", [n]),
		indicator: "green",
	});
}

function replace_rm_dialog(state) {
	if (!state.rm_columns.length) {
		frappe.show_alert({ message: __("Load BOMs first"), indicator: "orange" });
		return;
	}
	const old_options = state.rm_columns.map((c) => c.item_code);
	const d = new frappe.ui.Dialog({
		title: __("Replace Raw Material"),
		fields: [
			{
				fieldtype: "Select",
				fieldname: "old_rm",
				label: __("Current Raw Material (column)"),
				options: old_options.join("\n"),
				reqd: 1,
				default:
					state.selected.col != null
						? state.rm_columns[state.selected.col].item_code
						: old_options[0],
			},
			{
				fieldtype: "Link",
				fieldname: "new_rm",
				label: __("New Raw Material"),
				options: "Item",
				reqd: 1,
				get_query() {
					return { filters: { is_stock_item: 1, disabled: 0 } };
				},
			},
			{
				fieldtype: "Select",
				fieldname: "scope",
				label: __("Apply to"),
				options: ["Selected rows", "All rows"],
				default: "Selected rows",
			},
			{
				fieldtype: "Check",
				fieldname: "keep_qty",
				label: __("Keep existing qty"),
				default: 1,
			},
		],
		primary_action_label: __("Replace"),
		primary_action(values) {
			d.hide();
			do_replace_rm(state, values);
		},
	});
	d.show();
}

function do_replace_rm(state, values) {
	const old_rm = values.old_rm;
	const new_rm = values.new_rm;
	if (!old_rm || !new_rm || old_rm === new_rm) return;

	frappe.call({
		method: `${API}.get_item_uom`,
		args: { item_code: new_rm },
		callback(r) {
			const new_uom = r.message || "";
			frappe.db.get_value("Item", new_rm, "item_name", (v) => {
				const new_name = (v && v.item_name) || new_rm;
				// Ensure new column exists
				let col = state.rm_columns.find((c) => c.item_code === new_rm);
				if (!col) {
					col = { item_code: new_rm, item_name: new_name, uom: new_uom };
					state.rm_columns.push(col);
				}
				const only_selected = values.scope === "Selected rows";
				let n = 0;
				state.rows.forEach((row) => {
					if (only_selected && !cint(row._checked)) return;
					const old_cell = get_cell(state, row.item_code, old_rm);
					const had = old_cell.qty !== "" && flt(old_cell.qty) !== 0;
					if (!had && only_selected) {
						// still allow applying blank→new with 0 skip
					}
					if (!had) return;
					const new_cell = get_cell(state, row.item_code, new_rm);
					if (cint(values.keep_qty)) {
						new_cell.qty = old_cell.qty;
					} else if (new_cell.qty === "" || new_cell.qty == null) {
						new_cell.qty = old_cell.qty;
					}
					new_cell.uom = new_uom || col.uom || new_cell.uom;
					old_cell.qty = "";
					mark_dirty(state, row.item_code);
					n++;
				});
				// Drop old column if unused
				const still_used = state.rows.some((row) => {
					const c = get_cell(state, row.item_code, old_rm);
					return c.qty !== "" && flt(c.qty) !== 0;
				});
				if (!still_used) {
					state.rm_columns = state.rm_columns.filter((c) => c.item_code !== old_rm);
				}
				render_matrix(state);
				frappe.show_alert({
					message: __("Replaced {0} → {1} on {2} row(s)", [old_rm, new_rm, n]),
					indicator: "green",
				});
			});
		},
	});
}

function add_material_dialog(state) {
	if (!state.rows.length) {
		frappe.show_alert({ message: __("Load BOMs first"), indicator: "orange" });
		return;
	}
	const d = new frappe.ui.Dialog({
		title: __("Add Raw Material Column"),
		fields: [
			{
				fieldtype: "Link",
				fieldname: "item_code",
				label: __("Raw Material"),
				options: "Item",
				reqd: 1,
				get_query() {
					return { filters: { is_stock_item: 1, disabled: 0 } };
				},
			},
			{
				fieldtype: "Float",
				fieldname: "default_qty",
				label: __("Default Qty (optional)"),
				default: 0,
			},
			{
				fieldtype: "Select",
				fieldname: "scope",
				label: __("Set default qty on"),
				options: ["Selected rows", "All rows", "None (empty column)"],
				default: "Selected rows",
			},
		],
		primary_action_label: __("Add"),
		primary_action(values) {
			d.hide();
			do_add_material(state, values);
		},
	});
	d.show();
}

function do_add_material(state, values) {
	const rm = values.item_code;
	if (!rm) return;
	if (state.rm_columns.find((c) => c.item_code === rm)) {
		frappe.show_alert({
			message: __("Column already exists — use fill-down to set qty"),
			indicator: "orange",
		});
		return;
	}
	frappe.call({
		method: `${API}.get_item_uom`,
		args: { item_code: rm },
		callback(r) {
			const uom = r.message || "";
			frappe.db.get_value("Item", rm, "item_name", (v) => {
				state.rm_columns.push({
					item_code: rm,
					item_name: (v && v.item_name) || rm,
					uom,
				});
				const qty = flt(values.default_qty);
				const scope = values.scope;
				if (scope !== "None (empty column)" && qty > 0) {
					state.rows.forEach((row) => {
						if (scope === "Selected rows" && !cint(row._checked)) return;
						const cell = get_cell(state, row.item_code, rm);
						cell.qty = qty;
						cell.uom = uom;
						mark_dirty(state, row.item_code);
					});
				}
				render_matrix(state);
				frappe.show_alert({
					message: __("Added material column {0}", [rm]),
					indicator: "green",
				});
			});
		},
	});
}

function save_matrix(state) {
	if (!state.sales_order) {
		frappe.show_alert({ message: __("Select Sales Order first"), indicator: "orange" });
		return;
	}
	const dirty_rows = state.rows.filter((r) => cint(r.dirty));
	if (!dirty_rows.length) {
		frappe.confirm(__("No cells marked edited. Save all FG BOMs from current matrix?"), () =>
			_do_save(state, 1)
		);
		return;
	}
	frappe.confirm(
		__("Create new default BOM versions for {0} changed FG item(s)?", [dirty_rows.length]),
		() => _do_save(state, 0)
	);
}

function _do_save(state, save_all) {
	const rows_payload = state.rows.map((r) => ({
		item_code: r.item_code,
		bom_no: r.bom_no,
		bom_qty: r.bom_qty,
		dirty: save_all ? 1 : cint(r.dirty),
	}));
	const cells_payload = {};
	Object.keys(state.cells).forEach((k) => {
		const c = state.cells[k];
		cells_payload[k] = { qty: c.qty, uom: c.uom || "" };
	});

	frappe.call({
		method: `${API}.save_bom_matrix`,
		args: {
			sales_order: state.sales_order,
			rows: rows_payload,
			rm_columns: state.rm_columns,
			cells: cells_payload,
			options: {
				update_so_bom_no: 1,
				deactivate_old: 0,
				save_all: save_all ? 1 : 0,
			},
		},
		freeze: true,
		freeze_message: __("Creating BOM versions…"),
		callback(r) {
			const msg = r.message || {};
			const created = msg.created || [];
			const errors = msg.errors || [];
			let html = `<p>${frappe.utils.escape_html(msg.message || "")}</p>`;
			if (created.length) {
				html += `<ul>${created
					.map(
						(c) =>
							`<li>${frappe.utils.escape_html(c.item_code)}: 
							<a href="/app/bom/${encodeURIComponent(c.old_bom)}">${frappe.utils.escape_html(
								c.old_bom
							)}</a>
							→ <a href="/app/bom/${encodeURIComponent(c.new_bom)}">${frappe.utils.escape_html(
								c.new_bom
							)}</a></li>`
					)
					.join("")}</ul>`;
			}
			if (errors.length) {
				html += `<p class="text-danger">${__("Errors")}:</p><ul>${errors
					.map(
						(e) =>
							`<li>${frappe.utils.escape_html(e.item_code)}: ${frappe.utils.escape_html(
								e.error
							)}</li>`
					)
					.join("")}</ul>`;
			}
			frappe.msgprint({
				title: __("BOM Bulk Edit"),
				indicator: errors.length && !created.length ? "red" : "green",
				message: html,
			});
			if (created.length) load_matrix(state);
		},
	});
}
