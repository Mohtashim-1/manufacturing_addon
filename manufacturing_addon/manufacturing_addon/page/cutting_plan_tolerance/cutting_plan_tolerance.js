// Copyright (c) 2026, Manufacturing Addon contributors

frappe.pages["cutting-plan-tolerance"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Cutting Plan Tolerance"),
		single_column: true,
	});

	const state = { page, controls: {} };
	render_layout(wrapper, state);
	setup_filters(state);
	setup_actions(state);
	refresh_data(state);
};

function render_layout(wrapper, state) {
	const $body = $(wrapper).find(".layout-main-section");
	$body.empty().append(`
		<div id="cpt-root" style="padding:12px 0;">
			<div style="font-size:12px;color:#6b7280;margin-bottom:10px;" id="cpt-meta"></div>
			<div id="cpt-summary" style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px;"></div>
			<div id="cpt-table-wrap" style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:8px;background:#fff;padding:10px;"></div>
		</div>
	`);
	state.$meta = $body.find("#cpt-meta");
	state.$summary = $body.find("#cpt-summary");
	state.$table = $body.find("#cpt-table-wrap");
}

function setup_filters(state) {
	const p = state.page;
	state.controls.customer = p.add_field({
		fieldname: "customer",
		label: __("Customer"),
		fieldtype: "Link",
		options: "Customer",
	});
	state.controls.sales_order = p.add_field({
		fieldname: "sales_order",
		label: __("Sales Order"),
		fieldtype: "Link",
		options: "Sales Order",
	});
	state.controls.order_sheet = p.add_field({
		fieldname: "order_sheet",
		label: __("Order Sheet"),
		fieldtype: "Link",
		options: "Order Sheet",
	});
	state.controls.status = p.add_field({
		fieldname: "status",
		label: __("Status"),
		fieldtype: "Select",
		options: "\nAll\nWithin\nOver\nUnder\nNo Cutting",
		default: "All",
	});
	Object.values(state.controls).forEach((c) => {
		if (c?.$input) c.$input.on("change", () => refresh_data(state));
	});
}

function setup_actions(state) {
	state.page.add_inner_button(__("Refresh"), () => refresh_data(state));
}

function get_filters(state) {
	const v = (k) => (state.controls[k] && state.controls[k].get_value()) || "";
	return {
		customer: v("customer"),
		sales_order: v("sales_order"),
		order_sheet: v("order_sheet"),
		status: v("status") || "All",
	};
}

function refresh_data(state) {
	const filters = get_filters(state);
	frappe.call({
		method:
			"manufacturing_addon.manufacturing_addon.utils.cutting_plan_tolerance.get_cutting_plan_tolerance_dashboard",
		args: filters,
		freeze: true,
		freeze_message: __("Loading cutting plan tolerance…"),
		callback(r) {
			const data = r.message || {};
			render_meta(state, data);
			render_summary(state, data.summary || {}, data.tolerance_pct);
			render_table(state, data.rows || []);
		},
	});
}

function render_meta(state, data) {
	const pct = data.tolerance_pct || 10;
	state.$meta.text(
		__(
			"Planned qty vs total cutting qty (±{0}% tolerance). {1} line(s) shown.",
			[pct, (data.rows || []).length]
		)
	);
}

const SUMMARY_CARDS = [
	{ key: "total", label: __("Total Lines"), color: "#3b82f6" },
	{ key: "within", label: __("Within Tolerance"), color: "#22c55e" },
	{ key: "over", label: __("Over Plan"), color: "#ef4444" },
	{ key: "under", label: __("Under Plan"), color: "#f97316" },
	{ key: "no_cutting", label: __("No Cutting Yet"), color: "#9ca3af" },
];

function render_summary(state, summary, tolerance_pct) {
	state.$summary.empty();
	SUMMARY_CARDS.forEach((card) => {
		state.$summary.append(`
			<div style="flex:1;min-width:150px;border:1px solid #e5e7eb;border-radius:8px;padding:12px;background:#fff;border-top:3px solid ${card.color};">
				<div style="font-size:12px;color:#6b7280;">${card.label}</div>
				<div style="font-size:22px;font-weight:700;color:${card.color};">${fmtN(summary[card.key] || 0, 0)}</div>
			</div>
		`);
	});
	state.$summary.append(`
		<div style="flex:1;min-width:150px;border:1px dashed #d1d5db;border-radius:8px;padding:12px;background:#fafafa;">
			<div style="font-size:12px;color:#6b7280;">${__("Allowed Band")}</div>
			<div style="font-size:14px;font-weight:600;color:#374151;">${__("Planned ± {0}%", [tolerance_pct || 10])}</div>
		</div>
	`);
}

function render_table(state, rows) {
	if (!rows.length) {
		state.$table.html(
			`<div class="text-muted" style="padding:16px;">${__("No order lines match the selected filters.")}</div>`
		);
		return;
	}

	const thead = `
		<tr style="background:#f8fafc;">
			<th>${__("Order Sheet")}</th>
			<th>${__("Customer")}</th>
			<th>${__("Sales Order")}</th>
			<th>${__("Item")}</th>
			<th>${__("Colour")}</th>
			<th>${__("Size")}</th>
			<th class="text-right">${__("Planned Qty")}</th>
			<th class="text-right">${__("Min Allowed")}</th>
			<th class="text-right">${__("Max Allowed")}</th>
			<th class="text-right">${__("Actual Cutting")}</th>
			<th class="text-right">${__("Variance")}</th>
			<th class="text-right">${__("Variance %")}</th>
			<th>${__("Status")}</th>
		</tr>`;

	const tbody = rows
		.map((row) => {
			const badge = status_badge(row.status);
			return `
			<tr>
				<td><a href="/app/order-sheet/${encodeURIComponent(row.order_sheet)}">${frappe.utils.escape_html(row.order_sheet)}</a></td>
				<td>${frappe.utils.escape_html(row.customer || "")}</td>
				<td>${frappe.utils.escape_html(row.sales_order || "")}</td>
				<td>${frappe.utils.escape_html(row.so_item || "")}</td>
				<td>${frappe.utils.escape_html(row.colour || "")}</td>
				<td>${frappe.utils.escape_html(row.size || "")}</td>
				<td class="text-right">${fmtN(row.planned_qty)}</td>
				<td class="text-right">${fmtN(row.min_allowed)}</td>
				<td class="text-right">${fmtN(row.max_allowed)}</td>
				<td class="text-right"><b>${fmtN(row.actual_cutting_pieces)}</b></td>
				<td class="text-right">${fmtN(row.variance)}</td>
				<td class="text-right">${fmtN(row.variance_pct, 1)}%</td>
				<td>${badge}</td>
			</tr>`;
		})
		.join("");

	state.$table.html(`
		<table class="table table-bordered table-sm" style="margin:0;font-size:12px;">
			<thead>${thead}</thead>
			<tbody>${tbody}</tbody>
		</table>
	`);
}

function status_badge(status) {
	const map = {
		Within: "green",
		Over: "red",
		Under: "orange",
		"No Cutting": "gray",
	};
	const color = map[status] || "blue";
	return `<span class="indicator-pill ${color} filterable no-indicator-dot">${frappe.utils.escape_html(status || "")}</span>`;
}

function fmtN(v, d) {
	const n = parseFloat(v) || 0;
	const dp = d != null ? d : 0;
	return n.toLocaleString("en-US", { maximumFractionDigits: dp, minimumFractionDigits: dp });
}
