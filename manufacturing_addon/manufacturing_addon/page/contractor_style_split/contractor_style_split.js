// Copyright (c) 2026, Manufacturing Addon contributors

frappe.pages["contractor-style-split"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Contractor Style Split"),
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
		<div style="padding:12px 0;">
			<div id="css-meta" style="font-size:12px;color:#6b7280;margin-bottom:10px;"></div>
			<div id="css-summary" style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px;"></div>
			<div id="css-table" style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:8px;background:#fff;padding:10px;"></div>
		</div>
	`);
	state.$meta = $body.find("#css-meta");
	state.$summary = $body.find("#css-summary");
	state.$table = $body.find("#css-table");
}

function setup_filters(state) {
	const p = state.page;
	const today = frappe.datetime.get_today();
	const month_start = frappe.datetime.month_start(today);
	state.controls.from_date = p.add_field({
		fieldname: "from_date",
		label: __("From Date"),
		fieldtype: "Date",
		default: month_start,
	});
	state.controls.to_date = p.add_field({
		fieldname: "to_date",
		label: __("To Date"),
		fieldtype: "Date",
		default: today,
	});
	state.controls.operation = p.add_field({
		fieldname: "operation",
		label: __("Process"),
		fieldtype: "Select",
		options: "\nAll\nCutting\nStitching\nPacking",
		default: "All",
	});
	state.controls.order_sheet = p.add_field({
		fieldname: "order_sheet",
		label: __("Order Sheet"),
		fieldtype: "Link",
		options: "Order Sheet",
	});
	state.controls.contractor = p.add_field({
		fieldname: "contractor",
		label: __("Contractor"),
		fieldtype: "Link",
		options: "Manufacturing Contractor",
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
		from_date: v("from_date"),
		to_date: v("to_date"),
		operation: v("operation") || "All",
		order_sheet: v("order_sheet"),
		contractor: v("contractor"),
	};
}

function refresh_data(state) {
	frappe.call({
		method:
			"manufacturing_addon.manufacturing_addon.utils.style_contractor_split.get_contractor_split_dashboard",
		args: get_filters(state),
		freeze: true,
		callback(r) {
			const data = r.message || {};
			render_meta(state, data);
			render_summary(state, data.summary || {});
			render_table(state, data.rows || []);
		},
	});
}

function render_meta(state, data) {
	const s = data.summary || {};
	state.$meta.text(
		__("{0} split line(s) | {1} contractor(s) | Total {2}", [
			s.rows || 0,
			s.contractors || 0,
			format_money(s.total_amount || 0),
		])
	);
}

function render_summary(state, summary) {
	const cards = [
		{ label: __("Split Lines"), value: summary.rows || 0, color: "#3b82f6" },
		{ label: __("Contractors"), value: summary.contractors || 0, color: "#8b5cf6" },
		{ label: __("Total Amount"), value: format_money(summary.total_amount || 0), color: "#22c55e" },
	];
	state.$summary.empty();
	cards.forEach((c) => {
		state.$summary.append(`
			<div style="flex:1;min-width:160px;border:1px solid #e5e7eb;border-radius:8px;padding:12px;border-top:3px solid ${c.color};">
				<div style="font-size:12px;color:#6b7280;">${c.label}</div>
				<div style="font-size:20px;font-weight:700;">${c.value}</div>
			</div>`);
	});
}

function render_table(state, rows) {
	if (!rows.length) {
		state.$table.html(`<div class="text-muted" style="padding:16px;">${__("No contractor splits found.")}</div>`);
		return;
	}
	const head = `
		<tr style="background:#f8fafc;">
			<th>${__("Date")}</th><th>${__("Process")}</th><th>${__("Report")}</th><th>${__("Order Sheet")}</th>
			<th>${__("Item")}</th><th>${__("Style")}</th><th>${__("Contractor")}</th>
			<th class="text-right">${__("Split Qty")}</th><th class="text-right">${__("Billable Qty")}</th>
			<th class="text-right">${__("Rate")}</th><th class="text-right">${__("Amount")}</th>
		</tr>`;
	const body = rows
		.map(
			(r) => `
		<tr>
			<td>${frappe.utils.escape_html(r.report_date || "")}</td>
			<td>${frappe.utils.escape_html(r.operation || "")}</td>
			<td>${frappe.utils.escape_html(r.report_name || "")}</td>
			<td>${frappe.utils.escape_html(r.order_sheet || "")}</td>
			<td>${frappe.utils.escape_html(r.so_item || "")}</td>
			<td>${frappe.utils.escape_html(r.style || "")}${r.is_subassembly ? " <span class='text-muted'>(sub)</span>" : ""}</td>
			<td>${frappe.utils.escape_html(r.contractor || "")}</td>
			<td class="text-right">${fmt(r.split_qty)}</td>
			<td class="text-right">${fmt(r.billable_qty)}</td>
			<td class="text-right">${fmt(r.rate, 2)}</td>
			<td class="text-right"><b>${format_money(r.amount)}</b></td>
		</tr>`
		)
		.join("");
	state.$table.html(`<table class="table table-bordered table-sm" style="margin:0;font-size:12px;"><thead>${head}</thead><tbody>${body}</tbody></table>`);
}

function fmt(v, d) {
	const n = parseFloat(v) || 0;
	return n.toLocaleString("en-US", {
		maximumFractionDigits: d != null ? d : 0,
		minimumFractionDigits: d != null ? d : 0,
	});
}

function format_money(v) {
	return fmt(v, 2);
}
