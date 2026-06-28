frappe.pages["order-target"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Order Target Dashboard",
		single_column: true,
	});

	const state = { page, controls: {} };

	render_layout(wrapper, state);
	setup_filters(state);
	setup_actions(state);
	refresh_data(state);
};

/* ─── Layout ──────────────────────────────────────────────────────────── */

function render_layout(wrapper, state) {
	const $body = $(`
		<div class="ot-page" style="padding:12px 0;">

			<!-- Filters -->
			<div class="ot-filter-card card-panel">
				<div class="card-header-row">
					<h4 class="card-title">Filters</h4>
					<span class="ot-meta text-muted small"></span>
				</div>
				<div class="ot-filters filter-row"></div>
			</div>

			<!-- Summary cards -->
			<div class="ot-summary summary-grid"></div>

			<!-- Detail table -->
			<div class="ot-detail-card card-panel">
				<div class="card-header-row">
					<h4 class="card-title">Order-wise Target &amp; Progress</h4>
					<input type="search" class="ot-search form-control form-control-sm"
						placeholder="Search order / customer…"
						style="width:220px; font-size:12px;" />
				</div>
				<div class="ot-table-wrap" style="overflow-x:auto; margin-top:10px;"></div>
			</div>
		</div>

		<style>
			.ot-page .card-panel {
				border:1px solid #e5e7eb; border-radius:8px;
				padding:12px 14px; background:#fff; margin-bottom:14px;
			}
			.ot-page .card-header-row {
				display:flex; justify-content:space-between;
				align-items:center; margin-bottom:10px;
			}
			.ot-page .card-title { margin:0; font-size:14px; font-weight:600; }
			.ot-page .filter-row {
				display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;
			}
			.ot-page .summary-grid {
				display:grid;
				grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
				gap:10px; margin-bottom:14px;
			}
			.ot-page .stat-card {
				border-radius:8px; padding:12px 14px;
				border:1px solid #e5e7eb; background:#fff;
			}
			.ot-page .stat-label { font-size:11px; color:#6b7280; margin-bottom:4px; }
			.ot-page .stat-value { font-size:22px; font-weight:700; }
			.ot-page .ot-tbl { width:100%; font-size:12px; border-collapse:collapse; }
			.ot-page .ot-tbl th {
				background:#f1f5f9; padding:7px 8px;
				text-align:left; border-bottom:2px solid #e5e7eb;
				white-space:nowrap; font-weight:600; font-size:11px;
			}
			.ot-page .ot-tbl td { padding:6px 8px; border-bottom:1px solid #f3f4f6; vertical-align:middle; }
			.ot-page .ot-tbl tr:hover td { background:#f8fafc; }
			.ot-page .ot-tbl th.th-group {
				text-align:center; background:#e8f5e9; border-left:2px solid #c8e6c9;
			}
			.ot-page .ot-tbl td.td-group { border-left:2px solid #c8e6c9; }
			.progress-mini {
				height:6px; border-radius:3px; background:#e5e7eb;
				overflow:hidden; min-width:50px;
			}
			.progress-mini .bar { height:100%; border-radius:3px; transition:width .3s; }
			.pill {
				display:inline-block; padding:2px 9px; border-radius:99px;
				font-size:11px; font-weight:600; white-space:nowrap;
			}
			.pill-green  { background:#dcfce7; color:#166534; }
			.pill-blue   { background:#dbeafe; color:#1e40af; }
			.pill-orange { background:#ffedd5; color:#9a3412; }
			.pill-red    { background:#fee2e2; color:#991b1b; }
			.pill-gray   { background:#f3f4f6; color:#374151; }
		</style>
	`);

	$(wrapper).find(".layout-main-section").empty().append($body);

	state.$body     = $body;
	state.$filters  = $body.find(".ot-filters");
	state.$summary  = $body.find(".ot-summary");
	state.$table    = $body.find(".ot-table-wrap");
	state.$meta     = $body.find(".ot-meta");
	state.$search   = $body.find(".ot-search");

	// Live search on table
	state.$search.on("input", frappe.utils.debounce(function () {
		const term = $(this).val().trim().toLowerCase();
		$body.find(".ot-tbl tbody tr").each(function () {
			$(this).toggle(!term || $(this).text().toLowerCase().includes(term));
		});
	}, 200));
}

/* ─── Filters ─────────────────────────────────────────────────────────── */

function setup_filters(state) {
	const today = frappe.datetime.get_today();
	const three_months = frappe.datetime.add_months(today, 3);

	const make = (df) => {
		const ctrl = frappe.ui.form.make_control({
			parent: state.$filters,
			df,
			render_input: true,
		});
		return ctrl;
	};

	state.controls.report_date = make({
		label: __("Report Date"),
		fieldname: "report_date",
		fieldtype: "Date",
		default: today,
	});
	state.controls.from_shipment = make({
		label: __("Shipment From"),
		fieldname: "from_shipment",
		fieldtype: "Date",
		default: today,
	});
	state.controls.to_shipment = make({
		label: __("Shipment To"),
		fieldname: "to_shipment",
		fieldtype: "Date",
		default: three_months,
	});
	state.controls.customer = make({
		label: __("Customer"),
		fieldname: "customer",
		fieldtype: "Link",
		options: "Customer",
	});
	state.controls.order_sheet = make({
		label: __("Order Sheet"),
		fieldname: "order_sheet",
		fieldtype: "Link",
		options: "Order Sheet",
	});
	state.controls.status = make({
		label: __("Status"),
		fieldname: "status",
		fieldtype: "Select",
		options: "\nAll\nNot Started\nOn Track\nBehind\nOverdue\nCompleted",
		default: "All",
	});

	// Set defaults
	state.controls.report_date.set_value(today);
	state.controls.from_shipment.set_value(today);
	state.controls.to_shipment.set_value(three_months);
	state.controls.status.set_value("All");

	// Auto-refresh on change
	const debounced_refresh = frappe.utils.debounce(() => refresh_data(state), 400);
	["report_date", "from_shipment", "to_shipment", "customer", "order_sheet", "status"].forEach((k) => {
		const ctrl = state.controls[k];
		if (ctrl.$input) {
			ctrl.$input.on("change", debounced_refresh);
		}
		if (ctrl.$wrapper) {
			ctrl.$wrapper.on("awesomplete-selectcomplete change", debounced_refresh);
		}
	});
}

/* ─── Actions ─────────────────────────────────────────────────────────── */

function setup_actions(state) {
	state.page.set_primary_action(__("Refresh"), () => refresh_data(state), "refresh");
	state.page.add_inner_button(__("Open Full Report"), () => {
		frappe.set_route("query-report", "Order Target Dashboard");
	});
}

/* ─── Data Fetch ──────────────────────────────────────────────────────── */

function get_filters(state) {
	const v = (k) => state.controls[k] && state.controls[k].get_value();
	return {
		report_date:   v("report_date")   || frappe.datetime.get_today(),
		from_shipment: v("from_shipment") || "",
		to_shipment:   v("to_shipment")   || "",
		customer:      v("customer")      || "",
		order_sheet:   v("order_sheet")   || "",
		status:        v("status")        || "All",
	};
}

function refresh_data(state) {
	const filters = get_filters(state);

	frappe.call({
		method: "frappe.desk.query_report.run",
		args: {
			report_name: "Order Target Dashboard",
			filters,
		},
		freeze: true,
		freeze_message: __("Loading order targets…"),
		callback: function (r) {
			const rows = (r.message && r.message.result) || [];
			state.$meta.text(`${rows.length} order(s) | ${filters.report_date}`);
			render_summary(state, rows);
			render_table(state, rows);
		},
	});
}

/* ─── Summary Cards ───────────────────────────────────────────────────── */

function render_summary(state, rows) {
	const counts = { "Not Started": 0, "On Track": 0, "Behind": 0, "Overdue": 0, "Completed": 0 };
	let total_order_qty = 0, total_cut = 0, total_pack = 0;

	rows.forEach((r) => {
		const s = r.status || "Not Started";
		if (s in counts) counts[s]++;
		total_order_qty += num(r.order_qty);
		total_cut       += num(r.total_cut);
		total_pack      += num(r.total_pack);
	});

	const overall_cut_pct  = total_order_qty ? (total_cut  / total_order_qty * 100).toFixed(1) : "0.0";
	const overall_pack_pct = total_order_qty ? (total_pack / total_order_qty * 100).toFixed(1) : "0.0";

	const cards = [
		{ label: "Total Orders",  value: rows.length,           color: "#1e40af", bg: "#eff6ff" },
		{ label: "Not Started",   value: counts["Not Started"],  color: "#374151", bg: "#f9fafb" },
		{ label: "On Track",      value: counts["On Track"],     color: "#166534", bg: "#f0fdf4" },
		{ label: "Behind",        value: counts["Behind"],       color: "#9a3412", bg: "#fff7ed" },
		{ label: "Overdue",       value: counts["Overdue"],      color: "#991b1b", bg: "#fef2f2" },
		{ label: "Completed",     value: counts["Completed"],    color: "#065f46", bg: "#ecfdf5" },
		{ label: "Total Order Qty", value: fmtNum(total_order_qty), color: "#1e40af", bg: "#eff6ff" },
		{ label: "Overall Cut %", value: overall_cut_pct + "%",  color: "#0f766e", bg: "#f0fdfa" },
		{ label: "Overall Pack %",value: overall_pack_pct + "%", color: "#7e22ce", bg: "#faf5ff" },
	];

	state.$summary.html(
		cards.map((c) => `
			<div class="stat-card" style="border-left:4px solid ${c.color}; background:${c.bg};">
				<div class="stat-label">${c.label}</div>
				<div class="stat-value" style="color:${c.color};">${c.value}</div>
			</div>
		`).join("")
	);
}

/* ─── Detail Table ────────────────────────────────────────────────────── */

function render_table(state, rows) {
	if (!rows.length) {
		state.$table.html(`
			<div style="padding:20px; color:#6b7280; text-align:center;">
				No orders found for the selected filters.
			</div>`);
		return;
	}

	const thead = `
		<thead>
			<tr>
				<th rowspan="2">${__("Order Sheet")}</th>
				<th rowspan="2">${__("Customer")}</th>
				<th rowspan="2">${__("Ship Date")}</th>
				<th rowspan="2" style="text-align:right;">${__("Order Qty")}</th>
				<th rowspan="2" style="text-align:right;">${__("Days Left")}</th>
				<th rowspan="2" style="text-align:right;">${__("Daily Tgt")}</th>
				<th rowspan="2" style="text-align:right;">${__("Weekly Tgt")}</th>
				<th colspan="3" class="th-group">✂️ ${__("Cutting")}</th>
				<th colspan="3" class="th-group">🪡 ${__("Stitching")}</th>
				<th colspan="3" class="th-group">🔍 ${__("Checking")}</th>
				<th colspan="3" class="th-group">📦 ${__("Packing")}</th>
				<th rowspan="2">${__("Status")}</th>
			</tr>
			<tr>
				<th class="th-group" style="text-align:right;">${__("Total")}</th>
				<th class="th-group">${__("Progress")}</th>
				<th class="th-group" style="text-align:right;">${__("Today")}</th>

				<th class="th-group" style="text-align:right;">${__("Total")}</th>
				<th class="th-group">${__("Progress")}</th>
				<th class="th-group" style="text-align:right;">${__("Today")}</th>

				<th class="th-group" style="text-align:right;">${__("Total")}</th>
				<th class="th-group">${__("Progress")}</th>
				<th class="th-group" style="text-align:right;">${__("Today")}</th>

				<th class="th-group" style="text-align:right;">${__("Total")}</th>
				<th class="th-group">${__("Progress")}</th>
				<th class="th-group" style="text-align:right;">${__("Today")}</th>
			</tr>
		</thead>`;

	const tbody = rows.map((r) => {
		const days = num(r.days_remaining);
		const days_html = days < 0
			? `<b style="color:#dc2626;">${days}</b>`
			: days <= 7
				? `<b style="color:#ea580c;">${days}</b>`
				: `<span style="color:#16a34a;">${days}</span>`;

		const status_html = pill_html(r.status);

		return `
			<tr>
				<td><a href="/app/order-sheet/${encodeURIComponent(r.order_sheet)}"
					style="color:#0f766e; font-weight:500;">${esc(r.order_sheet)}</a></td>
				<td style="white-space:nowrap;">${esc(r.customer)}</td>
				<td style="white-space:nowrap;">${r.shipment_date || "—"}</td>
				<td style="text-align:right;">${fmtNum(r.order_qty)}</td>
				<td style="text-align:center;">${days_html}</td>
				<td style="text-align:right; font-weight:600;">${fmtNum(r.daily_target)}</td>
				<td style="text-align:right;">${fmtNum(r.weekly_target)}</td>

				${stage_cells(r.total_cut,    r.cut_pct,    r.today_cut)}
				${stage_cells(r.total_stitch, r.stitch_pct, r.today_stitch)}
				${stage_cells(r.total_check,  r.check_pct,  r.today_check)}
				${stage_cells(r.total_pack,   r.pack_pct,   r.today_pack)}

				<td>${status_html}</td>
			</tr>`;
	}).join("");

	state.$table.html(`
		<table class="ot-tbl">
			${thead}
			<tbody>${tbody}</tbody>
		</table>
	`);

	// Re-apply search if term already typed
	const term = (state.$search.val() || "").trim().toLowerCase();
	if (term) {
		state.$table.find("tbody tr").each(function () {
			$(this).toggle($(this).text().toLowerCase().includes(term));
		});
	}
}

/* ─── Helpers ─────────────────────────────────────────────────────────── */

function stage_cells(total, pct, today_qty) {
	const p = Math.min(num(pct), 100);
	let bar_color = "#ef4444";
	if (p >= 100) bar_color = "#22c55e";
	else if (p >= 70) bar_color = "#3b82f6";
	else if (p >= 40) bar_color = "#f97316";

	const today_style = num(today_qty) > 0
		? "color:#2563eb; font-weight:700;"
		: "color:#9ca3af;";

	return `
		<td class="td-group" style="text-align:right;">${fmtNum(total)}</td>
		<td class="td-group" style="min-width:80px;">
			<div style="font-size:10px; color:${bar_color}; font-weight:600; margin-bottom:2px;">
				${p.toFixed(1)}%
			</div>
			<div class="progress-mini">
				<div class="bar" style="width:${p}%; background:${bar_color};"></div>
			</div>
		</td>
		<td class="td-group" style="text-align:right; ${today_style}">${fmtNum(today_qty)}</td>
	`;
}

function pill_html(status) {
	const cls_map = {
		"Completed":   "pill-green",
		"On Track":    "pill-blue",
		"Behind":      "pill-orange",
		"Overdue":     "pill-red",
		"Not Started": "pill-gray",
	};
	const cls = cls_map[status] || "pill-gray";
	return `<span class="pill ${cls}">${esc(status || "—")}</span>`;
}

function num(v) { return Number(v || 0); }
function esc(v) { return frappe.utils.escape_html(String(v == null ? "" : v)); }
function fmtNum(v) {
	const n = num(v);
	return n === 0 ? "—" : n.toLocaleString("en", { maximumFractionDigits: 0 });
}
