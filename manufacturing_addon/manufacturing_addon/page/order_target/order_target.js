// Copyright (c) 2026, mohtashim and contributors
frappe.pages["order-target"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Order Target"),
		single_column: true,
	});
	const state = {
		page,
		controls: {},
		expanded: {},
		mode: "planner",
		planner: {
			order_sheet: "",
			items: [],
			meta: {},
			dirty: false,
		},
	};
	render_layout(wrapper, state);
	setup_filters(state);
	setup_actions(state);

	const opts = frappe.route_options || {};
	frappe.route_options = null;
	if (opts.order_sheet) {
		state.mode = "planner";
		state.planner.order_sheet = opts.order_sheet;
		if (state.controls.order_sheet) {
			state.controls.order_sheet.set_value(opts.order_sheet);
		}
		setTimeout(() => load_assumption_board(state), 200);
	} else {
		set_mode(state, "planner");
	}
};

function render_layout(wrapper, state) {
	const $body = $(wrapper).find(".page-content");
	$body.empty().append(`
		<div id="otd-root" style="padding:12px 4px;">
			<style>
				#otd-root .ot-tabs { display:flex; gap:8px; margin-bottom:12px; }
				#otd-root .ot-tab {
					border:1px solid #cbd5e1; background:#fff; border-radius:8px;
					padding:8px 14px; font-size:13px; font-weight:600; cursor:pointer;
				}
				#otd-root .ot-tab.active { background:#0f4c81; color:#fff; border-color:#0f4c81; }
				#otd-root .ot-banner {
					background:#fff7ed; border:1px solid #fdba74; border-radius:8px;
					padding:10px 12px; margin-bottom:12px; font-size:12px; color:#9a3412;
				}
				#otd-root .ot-cards { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }
				#otd-root .ot-card {
					background:#fff; border:1px solid #e5e7eb; border-radius:10px;
					padding:10px 14px; min-width:120px; flex:1;
					box-shadow:0 1px 3px rgba(0,0,0,.06);
				}
				#otd-root .ot-card .lbl { font-size:10px; color:#6b7280; font-weight:500; }
				#otd-root .ot-card .val { font-size:20px; font-weight:700; margin-top:2px; }
				#otd-root table.ot-table { width:100%; border-collapse:collapse; font-size:12px; background:#fff; }
				#otd-root table.ot-table th {
					padding:7px 8px; background:#f8fafc; border-bottom:2px solid #e5e7eb;
					text-align:left; white-space:nowrap; font-size:11px;
				}
				#otd-root table.ot-table td {
					padding:6px 8px; border-bottom:1px solid #f1f5f9; vertical-align:middle;
				}
				#otd-root .ot-toolbar {
					display:flex; flex-wrap:wrap; gap:8px; align-items:end;
					margin-bottom:10px; background:#fff; border:1px solid #e5e7eb;
					border-radius:8px; padding:10px;
				}
				#otd-root .badge-ok { background:#dcfce7; color:#166534; }
				#otd-root .badge-bad { background:#fee2e2; color:#991b1b; }
				#otd-root .badge-warn { background:#ffedd5; color:#9a3412; }
				#otd-root .badge-muted { background:#f3f4f6; color:#374151; }
			</style>
			<div class="ot-tabs">
				<button type="button" class="ot-tab" data-mode="planner">${__("Assumption Planner")}</button>
				<button type="button" class="ot-tab" data-mode="dashboard">${__("Live Dashboard")}</button>
			</div>
			<div id="otd-planner"></div>
			<div id="otd-dashboard" style="display:none;">
				<div id="otd-meta" style="font-size:12px;color:#6b7280;margin-bottom:10px;"></div>
				<div id="otd-summary" style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px;"></div>
				<div id="otd-table-wrap" style="overflow-x:auto;"></div>
			</div>
		</div>
	`);
	state.$planner = $body.find("#otd-planner");
	state.$dash = $body.find("#otd-dashboard");
	state.$meta = $body.find("#otd-meta");
	state.$sum = $body.find("#otd-summary");
	state.$table = $body.find("#otd-table-wrap");

	$body.on("click", ".ot-tab", function () {
		set_mode(state, $(this).data("mode"));
	});
}

function set_mode(state, mode) {
	state.mode = mode;
	$("#otd-root .ot-tab").removeClass("active");
	$(`#otd-root .ot-tab[data-mode="${mode}"]`).addClass("active");
	if (mode === "planner") {
		state.$planner.show();
		state.$dash.hide();
		render_planner(state);
		if (state.planner.order_sheet && !state.planner.items.length) {
			load_assumption_board(state);
		}
	} else {
		state.$planner.hide();
		state.$dash.show();
		refresh_dashboard(state);
	}
}

function setup_filters(state) {
	const p = state.page;
	state.controls.order_sheet = p.add_field({
		fieldname: "order_sheet",
		label: __("Order Sheet"),
		fieldtype: "Link",
		options: "Order Sheet",
		change() {
			const val = state.controls.order_sheet.get_value();
			state.planner.order_sheet = val || "";
			if (state.mode === "planner") {
				if (val) load_assumption_board(state);
				else {
					state.planner.items = [];
					render_planner(state);
				}
			} else {
				refresh_dashboard(state);
			}
		},
	});
	state.controls.report_date = p.add_field({
		fieldname: "report_date",
		label: __("As Of / Report Date"),
		fieldtype: "Date",
		default: frappe.datetime.get_today(),
		change() {
			if (state.mode === "planner") recalculate_planner(state);
			else refresh_dashboard(state);
		},
	});
	state.controls.customer = p.add_field({
		fieldname: "customer",
		label: __("Customer"),
		fieldtype: "Link",
		options: "Customer",
		change() {
			if (state.mode === "dashboard") refresh_dashboard(state);
		},
	});
	state.controls.status = p.add_field({
		fieldname: "status",
		label: __("Status"),
		fieldtype: "Select",
		options: "\nAll\nNot Started\nOn Track\nBehind\nOverdue\nCompleted",
		default: "All",
		change() {
			if (state.mode === "dashboard") refresh_dashboard(state);
		},
	});
}

function setup_actions(state) {
	state.page.set_primary_action(__("Recalculate"), () => {
		if (state.mode === "planner") recalculate_planner(state);
		else refresh_dashboard(state);
	});
	state.page.add_inner_button(__("Refresh"), () => {
		if (state.mode === "planner") load_assumption_board(state);
		else refresh_dashboard(state);
	});
}

function storage_key(order_sheet) {
	return `order_target_assumptions::${order_sheet}`;
}

function load_saved_assumptions(order_sheet) {
	try {
		return JSON.parse(localStorage.getItem(storage_key(order_sheet)) || "{}");
	} catch (e) {
		return {};
	}
}

function save_assumptions(state) {
	const os = state.planner.order_sheet;
	if (!os) return;
	const payload = {};
	state.planner.items.forEach((row) => {
		payload[row.row_name] = {
			selected: cint(row.selected),
			assumption_delivery_date: row.assumption_delivery_date || "",
			assumed_daily_rate: row.assumed_daily_rate || "",
		};
	});
	localStorage.setItem(storage_key(os), JSON.stringify(payload));
	frappe.show_alert({
		message: __("Assumptions saved on this browser only (not on Order Sheet / Sales Order)"),
		indicator: "blue",
	});
}

function load_assumption_board(state) {
	const order_sheet =
		(state.controls.order_sheet && state.controls.order_sheet.get_value()) ||
		state.planner.order_sheet;
	if (!order_sheet) {
		frappe.show_alert({ message: __("Select Order Sheet first"), indicator: "orange" });
		return;
	}
	state.planner.order_sheet = order_sheet;
	state.$planner.html(
		`<div style="padding:40px;text-align:center;color:#64748b;"><i class="fa fa-spinner fa-spin fa-2x"></i></div>`
	);

	frappe.call({
		method: "manufacturing_addon.manufacturing_addon.page.order_target.order_target.get_assumption_board",
		args: { order_sheet },
		callback(r) {
			const msg = r.message || {};
			const saved = load_saved_assumptions(order_sheet);
			state.planner.meta = msg;
			state.planner.items = (msg.items || []).map((row) => {
				const s = saved[row.row_name] || {};
				return {
					...row,
					selected: s.selected != null ? cint(s.selected) : 1,
					assumption_delivery_date: s.assumption_delivery_date || "",
					assumed_daily_rate:
						s.assumed_daily_rate !== undefined && s.assumed_daily_rate !== ""
							? s.assumed_daily_rate
							: row.suggested_daily || "",
					days_needed: null,
					days_available: null,
					buffer_days: null,
					status: "Set date & rate",
				};
			});
			recalculate_planner(state);
		},
		error() {
			state.$planner.html(
				`<div class="text-danger" style="padding:24px;">${__("Failed to load Order Sheet items")}</div>`
			);
		},
	});
}

function recalculate_planner(state) {
	const as_of =
		(state.controls.report_date && state.controls.report_date.get_value()) ||
		frappe.datetime.get_today();
	const rows = state.planner.items.map((row) => ({
		row_name: row.row_name,
		pending_qty: row.pending_qty,
		assumed_daily_rate: row.assumed_daily_rate,
		assumption_delivery_date: row.assumption_delivery_date,
		selected: row.selected,
	}));

	frappe.call({
		method:
			"manufacturing_addon.manufacturing_addon.page.order_target.order_target.calculate_assumption_days",
		args: { rows, as_of },
		callback(r) {
			const msg = r.message || {};
			const by = {};
			(msg.rows || []).forEach((x) => {
				by[x.row_name] = x;
			});
			state.planner.items.forEach((row) => {
				const calc = by[row.row_name] || {};
				row.days_needed = calc.days_needed;
				row.days_available = calc.days_available;
				row.buffer_days = calc.buffer_days;
				row.status = calc.status || row.status;
			});
			state.planner.summary = msg.summary || {};
			render_planner(state);
		},
	});
}

function num(v) {
	return parseFloat(v) || 0;
}
function fmtN(v, d) {
	const n = num(v);
	const dp = d != null ? d : 0;
	const s = n.toFixed(dp);
	const parts = s.split(".");
	parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
	return parts.join(".");
}
function fmtNum(v) {
	return fmtN(v, 0);
}
function esc(v) {
	return frappe.utils.escape_html(cstr(v || ""));
}
function short(v, n) {
	const t = cstr(v || "");
	return t.length > n ? t.slice(0, n) + "…" : t;
}

function status_badge(status) {
	let cls = "badge-muted";
	if (status === "OK") cls = "badge-ok";
	else if (status === "Not enough days" || status === "Past date") cls = "badge-bad";
	else if (status === "Tight") cls = "badge-warn";
	else if (status === "Done") cls = "badge-ok";
	return `<span class="badge ${cls}" style="border-radius:10px;padding:2px 8px;">${esc(status)}</span>`;
}

function render_planner(state) {
	const os = state.planner.order_sheet;
	if (!os) {
		state.$planner.html(`
			<div class="ot-banner">
				<b>${__("Assumption Planner")}</b> —
				${__("Select an Order Sheet above. Delivery dates here are manual assumptions only and are never written to Sales Order or Order Sheet.")}
			</div>
			<div style="padding:48px;text-align:center;color:#94a3b8;">
				<i class="fa fa-calendar fa-3x" style="opacity:.4;"></i>
				<p style="margin-top:12px;">${__("Choose Order Sheet to start planning.")}</p>
			</div>
		`);
		return;
	}

	const meta = state.planner.meta || {};
	const sum = state.planner.summary || {};
	const items = state.planner.items || [];

	const cards = `
		<div class="ot-cards">
			<div class="ot-card"><div class="lbl">${__("Order Sheet")}</div><div class="val" style="font-size:14px;">
				<a href="/app/order-sheet/${encodeURIComponent(os)}">${esc(os)}</a>
			</div></div>
			<div class="ot-card"><div class="lbl">${__("Customer")}</div><div class="val" style="font-size:14px;">${esc(
				meta.customer || "—"
			)}</div></div>
			<div class="ot-card"><div class="lbl">${__("Selected")}</div><div class="val">${cint(
				sum.selected_count
			)}</div></div>
			<div class="ot-card"><div class="lbl">${__("Days Needed (max)")}</div><div class="val" style="color:#2563eb;">${
				sum.max_days_needed != null ? fmtNum(sum.max_days_needed) : "—"
			}</div></div>
			<div class="ot-card"><div class="lbl">${__("Days Available (min)")}</div><div class="val">${
				sum.min_days_available != null ? fmtNum(sum.min_days_available) : "—"
			}</div></div>
			<div class="ot-card"><div class="lbl">${__("Buffer")}</div><div class="val" style="color:${
				sum.buffer_days == null ? "#64748b" : sum.buffer_days >= 0 ? "#16a34a" : "#dc2626"
			};">${sum.buffer_days != null ? fmtNum(sum.buffer_days) : "—"}</div></div>
		</div>
	`;

	const rows_html = items
		.map((row, idx) => {
			return `
			<tr data-idx="${idx}">
				<td style="text-align:center;"><input type="checkbox" class="ot-sel" data-idx="${idx}" ${
				cint(row.selected) ? "checked" : ""
			}></td>
				<td style="text-align:center;font-weight:600;">${idx + 1}</td>
				<td title="${esc(row.so_item)}">${esc(short(row.so_item, 36))}</td>
				<td>${esc(row.article)}</td>
				<td>${esc(row.colour)}</td>
				<td>${esc(row.size)}</td>
				<td style="text-align:right;">${fmtNum(row.order_qty)}</td>
				<td style="text-align:right;">${fmtNum(row.pack_done)}</td>
				<td style="text-align:right;font-weight:700;color:#c2410c;">${fmtNum(row.pending_qty)}</td>
				<td>
					<input type="date" class="form-control input-xs ot-del" data-idx="${idx}"
						value="${esc(row.assumption_delivery_date)}" style="min-width:130px;">
				</td>
				<td>
					<input type="number" min="0" step="1" class="form-control input-xs ot-rate" data-idx="${idx}"
						value="${esc(row.assumed_daily_rate)}" placeholder="${esc(row.suggested_daily || "")}"
						style="width:90px;text-align:right;">
				</td>
				<td style="text-align:right;font-weight:700;">${
					row.days_needed != null ? fmtNum(row.days_needed) : "—"
				}</td>
				<td style="text-align:right;">${row.days_available != null ? fmtNum(row.days_available) : "—"}</td>
				<td style="text-align:right;font-weight:700;color:${
					row.buffer_days == null ? "#64748b" : row.buffer_days >= 0 ? "#16a34a" : "#dc2626"
				};">${row.buffer_days != null ? fmtNum(row.buffer_days) : "—"}</td>
				<td>${status_badge(row.status)}</td>
			</tr>`;
		})
		.join("");

	state.$planner.html(`
		<div class="ot-banner">
			<i class="fa fa-info-circle"></i>
			${esc(
				meta.note ||
					__(
						"Manual working only. Dates you enter here are assumptions and do not change Sales Order or Order Sheet."
					)
			)}
			${
				meta.order_sheet_shipment_date
					? " · " +
					  __("OS shipment (reference only)") +
					  ": <b>" +
					  esc(meta.order_sheet_shipment_date) +
					  "</b>"
					: ""
			}
		</div>
		${cards}
		<div class="ot-toolbar">
			<div>
				<label style="font-size:11px;color:#64748b;display:block;">${__("Apply delivery date to selected")}</label>
				<input type="date" class="form-control input-sm" id="ot-bulk-date" style="width:160px;">
			</div>
			<div>
				<label style="font-size:11px;color:#64748b;display:block;">${__("Apply daily rate to selected")}</label>
				<input type="number" min="0" class="form-control input-sm" id="ot-bulk-rate" style="width:120px;" placeholder="${__(
					"pcs / day"
				)}">
			</div>
			<button type="button" class="btn btn-default btn-sm" id="ot-apply-bulk">${__("Apply")}</button>
			<button type="button" class="btn btn-primary btn-sm" id="ot-recalc">${__("Calculate Days")}</button>
			<button type="button" class="btn btn-success btn-sm" id="ot-save-local">${__(
				"Save Assumptions (Browser)"
			)}</button>
			<button type="button" class="btn btn-default btn-sm" id="ot-select-all">${__("Select All")}</button>
			<button type="button" class="btn btn-default btn-sm" id="ot-select-none">${__("Clear Selection")}</button>
		</div>
		<div style="overflow:auto;border:1px solid #e5e7eb;border-radius:8px;">
			<table class="ot-table">
				<thead>
					<tr>
						<th></th>
						<th>${__("S.No")}</th>
						<th>${__("Item")}</th>
						<th>${__("Article")}</th>
						<th>${__("Colour")}</th>
						<th>${__("Size")}</th>
						<th>${__("Order Qty")}</th>
						<th>${__("Packed")}</th>
						<th>${__("Pending")}</th>
						<th>${__("Assumption Delivery")}</th>
						<th>${__("Assumed Pcs/Day")}</th>
						<th>${__("Days Needed")}</th>
						<th>${__("Days Available")}</th>
						<th>${__("Buffer")}</th>
						<th>${__("Result")}</th>
					</tr>
				</thead>
				<tbody>${
					rows_html ||
					`<tr><td colspan="15" style="padding:24px;text-align:center;color:#94a3b8;">${__(
						"No items on this Order Sheet"
					)}</td></tr>`
				}</tbody>
			</table>
		</div>
	`);

	state.$planner.find("#ot-apply-bulk").on("click", () => {
		const d = state.$planner.find("#ot-bulk-date").val();
		const rate = state.$planner.find("#ot-bulk-rate").val();
		state.planner.items.forEach((row) => {
			if (!cint(row.selected)) return;
			if (d) row.assumption_delivery_date = d;
			if (rate !== "") row.assumed_daily_rate = rate;
		});
		recalculate_planner(state);
	});
	state.$planner.find("#ot-recalc").on("click", () => recalculate_planner(state));
	state.$planner.find("#ot-save-local").on("click", () => save_assumptions(state));
	state.$planner.find("#ot-select-all").on("click", () => {
		state.planner.items.forEach((r) => (r.selected = 1));
		recalculate_planner(state);
	});
	state.$planner.find("#ot-select-none").on("click", () => {
		state.planner.items.forEach((r) => (r.selected = 0));
		recalculate_planner(state);
	});
	state.$planner.on("change", ".ot-sel", function () {
		const idx = cint($(this).data("idx"));
		if (state.planner.items[idx]) state.planner.items[idx].selected = $(this).is(":checked") ? 1 : 0;
		recalculate_planner(state);
	});
	state.$planner.on("change", ".ot-del", function () {
		const idx = cint($(this).data("idx"));
		if (state.planner.items[idx]) {
			state.planner.items[idx].assumption_delivery_date = $(this).val() || "";
			state.planner.dirty = true;
		}
		recalculate_planner(state);
	});
	state.$planner.on("change", ".ot-rate", function () {
		const idx = cint($(this).data("idx"));
		if (state.planner.items[idx]) {
			state.planner.items[idx].assumed_daily_rate = $(this).val() || "";
			state.planner.dirty = true;
		}
		recalculate_planner(state);
	});
}

// ─── Live Dashboard (existing) ───────────────────────────────────────────────
function get_dash_filters(state) {
	const v = (k) => (state.controls[k] && state.controls[k].get_value()) || "";
	return {
		report_date: v("report_date") || frappe.datetime.get_today(),
		customer: v("customer"),
		order_sheet: v("order_sheet"),
		status: v("status") || "All",
	};
}

function refresh_dashboard(state) {
	state.expanded = {};
	const filters = get_dash_filters(state);
	frappe.call({
		method: "frappe.desk.query_report.run",
		args: { report_name: "Order Target Dashboard", filters },
		freeze: true,
		freeze_message: __("Loading order targets…"),
		callback(r) {
			const rows = (r.message && r.message.result) || [];
			state.$meta.text(`${rows.length} order(s) | as of ${filters.report_date}`);
			render_summary(state, rows);
			render_table(state, rows);
		},
	});
}

const CARD_DEFS = [
	{ key: "total", label: "Total Orders", color: "#3b82f6" },
	{ key: "not_started", label: "Not Started", color: "#9ca3af" },
	{ key: "on_track", label: "On Track", color: "#22c55e" },
	{ key: "behind", label: "Behind", color: "#f97316" },
	{ key: "overdue", label: "Overdue", color: "#ef4444" },
	{ key: "completed", label: "Completed", color: "#10b981" },
	{ key: "order_qty", label: "Total Order Qty", color: "#6366f1" },
	{ key: "delayed_total", label: "Total Delayed Days", color: "#dc2626" },
];

function render_summary(state, rows) {
	const agg = {
		total: 0,
		not_started: 0,
		on_track: 0,
		behind: 0,
		overdue: 0,
		completed: 0,
		order_qty: 0,
		delayed_total: 0,
	};
	rows.forEach((r) => {
		agg.total++;
		const s = r.status || "";
		if (s === "Not Started") agg.not_started++;
		if (s === "On Track") agg.on_track++;
		if (s === "Behind") agg.behind++;
		if (s === "Overdue") agg.overdue++;
		if (s === "Completed") agg.completed++;
		agg.order_qty += num(r.order_qty);
		agg.delayed_total += num(r.delayed_days);
	});
	const vals = {
		total: agg.total,
		not_started: agg.not_started,
		on_track: agg.on_track,
		behind: agg.behind,
		overdue: agg.overdue,
		completed: agg.completed,
		order_qty: fmtNum(agg.order_qty),
		delayed_total: agg.delayed_total > 0 ? fmtNum(agg.delayed_total) + "d" : "None",
	};
	state.$sum.empty();
	CARD_DEFS.forEach((def) => {
		state.$sum.append(`
			<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;
				padding:10px 16px;min-width:115px;flex:1;box-shadow:0 1px 3px rgba(0,0,0,.06);">
				<div style="font-size:10px;color:#6b7280;font-weight:500;">${def.label}</div>
				<div style="font-size:22px;font-weight:700;color:${def.color};line-height:1.2;margin-top:2px;">${
			vals[def.key]
		}</div>
			</div>`);
	});
}

function pill_html(status) {
	const cfg = {
		Completed: ["#dcfce7", "#166534"],
		"On Track": ["#dbeafe", "#1e40af"],
		Behind: ["#ffedd5", "#9a3412"],
		Overdue: ["#fee2e2", "#991b1b"],
		"Not Started": ["#f3f4f6", "#374151"],
	}[status] || ["#f3f4f6", "#374151"];
	return `<span style="background:${cfg[0]};color:${cfg[1]};border-radius:12px;
		padding:2px 8px;font-size:11px;font-weight:600;white-space:nowrap;">${status}</span>`;
}

function days_status_html(days_remaining, delayed_days) {
	const dr = num(days_remaining);
	const dd = num(delayed_days);
	if (dd > 0) {
		return `<div style="text-align:center;">
			<div style="background:#fee2e2;border:2px solid #dc2626;border-radius:8px;padding:4px 6px;display:inline-block;min-width:92px;">
				<div style="font-size:14px;font-weight:800;color:#dc2626;">⚠ ${fmtNum(dd)}</div>
				<div style="font-size:9px;color:#991b1b;font-weight:700;">DAYS DELAYED</div>
			</div></div>`;
	}
	return `<div style="text-align:center;"><b>${fmtNum(dr)}</b><div style="font-size:9px;color:#64748b;">DAYS LEFT</div></div>`;
}

function stage_cells(done, pending, pct, avg_d, need_d, today_qty) {
	const p = Math.min(num(pct), 100);
	let bar_color = "#ef4444";
	if (p >= 100) bar_color = "#22c55e";
	else if (p >= 70) bar_color = "#3b82f6";
	else if (p >= 40) bar_color = "#f97316";
	return `
		<td style="text-align:right;">${fmtNum(done)}</td>
		<td style="text-align:right;">${fmtNum(pending)}</td>
		<td style="min-width:70px;">
			<div style="font-size:10px;color:${bar_color};font-weight:700;text-align:right;">${p.toFixed(1)}%</div>
			<div style="background:#e5e7eb;border-radius:3px;height:5px;overflow:hidden;">
				<div style="height:100%;background:${bar_color};width:${p}%;"></div>
			</div>
		</td>
		<td style="text-align:center;font-size:10px;">avg ${fmtNum(avg_d)} / need ${fmtNum(need_d)}</td>
		<td style="text-align:right;">${fmtNum(today_qty)}</td>`;
}

function render_table(state, rows) {
	const th = (label) =>
		`<th style="padding:7px 8px;font-size:11px;font-weight:600;background:#f8fafc;border-bottom:2px solid #e5e7eb;">${label}</th>`;
	const body = rows
		.map((r, i) => {
			return `<tr>
				<td style="padding:7px 8px;"><a href="/app/order-sheet/${encodeURIComponent(r.order_sheet)}">${esc(
				r.order_sheet
			)}</a></td>
				<td style="padding:7px 8px;">${esc(r.customer)}</td>
				<td style="padding:7px 8px;">${esc(r.shipment_date || "")}</td>
				<td style="padding:7px 8px;text-align:right;">${fmtNum(r.order_qty)}</td>
				<td style="padding:7px 8px;">${days_status_html(r.days_remaining, r.delayed_days)}</td>
				<td style="padding:7px 8px;text-align:right;">${fmtNum(r.daily_target)}</td>
				${stage_cells(r.total_cut, r.pending_cut, r.cut_pct, r.avg_daily_cut, r.needed_daily_cut, r.today_cut)}
				${stage_cells(
					r.total_stitch,
					r.pending_stitch,
					r.stitch_pct,
					r.avg_daily_stitch,
					r.needed_daily_stitch,
					r.today_stitch
				)}
				${stage_cells(
					r.total_pack,
					r.pending_pack,
					r.pack_pct,
					r.avg_daily_pack,
					r.needed_daily_pack,
					r.today_pack
				)}
				<td style="padding:7px 8px;">${pill_html(r.status)}</td>
			</tr>`;
		})
		.join("");

	state.$table.html(`
		<table style="width:100%;border-collapse:collapse;background:#fff;font-size:12px;">
			<thead><tr>
				${th("Order Sheet")}${th("Customer")}${th("Shipment")}${th("Order Qty")}${th("Days")}${th("Daily Target")}
				${th("Cut Done")}${th("Cut Pend")}${th("Cut %")}${th("Cut Avg/Need")}${th("Today Cut")}
				${th("Stitch Done")}${th("Stitch Pend")}${th("Stitch %")}${th("Stitch Avg/Need")}${th("Today Stitch")}
				${th("Pack Done")}${th("Pack Pend")}${th("Pack %")}${th("Pack Avg/Need")}${th("Today Pack")}
				${th("Status")}
			</tr></thead>
			<tbody>${body || `<tr><td colspan="22" style="padding:24px;text-align:center;color:#94a3b8;">No rows</td></tr>`}</tbody>
		</table>
	`);
}
