frappe.pages["production-progress"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Production Progress",
		single_column: true,
	});

	const state = {
		page,
		controls: {},
		charts: {},
	};

	render_layout(wrapper, state);
	setup_filters(state);
	setup_actions(state);
	refresh_data(state);
};

function render_layout(wrapper, state) {
	const $body = $(`
		<div class="production-progress-page" style="padding: 12px 0;">
			<div class="pp-filter-card" style="border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fff; margin-bottom: 12px;">
				<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
					<h4 style="margin:0; font-size:14px;">Filters</h4>
					<div class="pp-meta" style="font-size:12px; color:#6b7280;"></div>
				</div>
				<div class="pp-filters" style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;"></div>
			</div>
			<div class="pp-summary" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap:10px; margin-bottom: 12px;"></div>
			<div class="pp-chart-card" style="border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fff; margin-bottom: 12px;">
				<h4 style="margin:0 0 8px 0; font-size:14px;">Stage Comparison</h4>
				<div class="pp-chart" style="min-height: 300px;"></div>
			</div>
			<div class="pp-detail-card" style="border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fff;">
				<h4 style="margin:0 0 8px 0; font-size:14px;">Sales Order-wise Progress</h4>
				<div class="pp-table-wrap" style="overflow:auto;"></div>
			</div>
		</div>
	`);

	$(wrapper).find(".layout-main-section").empty().append($body);
	state.$body = $body;
	state.$filters = $body.find(".pp-filters");
	state.$summary = $body.find(".pp-summary");
	state.$meta = $body.find(".pp-meta");
	state.$chart = $body.find(".pp-chart")[0];
	state.$table = $body.find(".pp-table-wrap");
}

function setup_filters(state) {
	const today = frappe.datetime.get_today();

	state.controls.from_date = frappe.ui.form.make_control({
		parent: state.$filters,
		df: {
			label: __("From Date"),
			fieldname: "from_date",
			fieldtype: "Date",
			reqd: 1,
			default: today,
		},
		render_input: true,
	});
	state.controls.to_date = frappe.ui.form.make_control({
		parent: state.$filters,
		df: {
			label: __("To Date"),
			fieldname: "to_date",
			fieldtype: "Date",
			reqd: 1,
			default: today,
		},
		render_input: true,
	});

	state.controls.from_date.set_value(today);
	state.controls.to_date.set_value(today);

	$(state.controls.from_date.$input).on("change", () => refresh_data(state));
	$(state.controls.to_date.$input).on("change", () => refresh_data(state));
}

function setup_actions(state) {
	state.page.set_primary_action(__("Refresh"), () => refresh_data(state), "refresh");

	state.page.add_inner_button(__("Email System Managers"), () => {
		const from_date = state.controls.from_date.get_value();
		const to_date = state.controls.to_date.get_value();
		if (!from_date || !to_date) {
			frappe.msgprint(__("Please select both From Date and To Date."));
			return;
		}

		frappe.confirm(
			__("Send production progress email to all System Managers for {0} to {1}?", [from_date, to_date]),
			() => {
				frappe.call({
					method: "manufacturing_addon.manufacturing_addon.page.production_progress.production_progress.send_production_progress_email",
					args: { from_date, to_date },
					freeze: true,
					freeze_message: __("Sending email..."),
					callback: (r) => {
						frappe.show_alert({
							indicator: "green",
							message: __(r.message || "Production progress email has been queued."),
						});
					},
				});
			}
		);
	});
}

function refresh_data(state) {
	const from_date = state.controls.from_date.get_value();
	const to_date = state.controls.to_date.get_value();
	if (!from_date || !to_date) return;

	frappe.call({
		method: "manufacturing_addon.manufacturing_addon.page.production_progress.production_progress.get_production_progress_data",
		args: { from_date, to_date },
		freeze: true,
		freeze_message: __("Loading production progress..."),
		callback: async (r) => {
			const data = r.message || {};
			const summary = data.summary || {};
			render_summary(state, summary);
			render_table(state, data.sales_order_rows || []);
			state.$meta.text(`${data.from_date || from_date} to ${data.to_date || to_date}`);
			await render_chart(state, summary);
		},
	});
}

async function render_chart(state, summary) {
	const categories = [__("Cutting"), __("Stitching"), __("Packing")];
	const values = [
		num(summary.total_cutting_qty),
		num(summary.total_stitching_qty),
		num(summary.total_packing_qty),
	];

	if (!state.$chart) return;

	try {
		await load_apexcharts();
		if (state.charts.stage) {
			try {
				state.charts.stage.destroy();
			} catch (e) {}
		}

		state.charts.stage = new ApexCharts(state.$chart, {
			chart: { type: "bar", height: 300, toolbar: { show: false } },
			series: [{ name: __("Qty"), data: values }],
			xaxis: { categories },
			colors: ["#0f766e"],
			plotOptions: { bar: { borderRadius: 6, columnWidth: "45%" } },
			dataLabels: { enabled: true },
			grid: { borderColor: "#e5e7eb" },
		});
		state.charts.stage.render();
	} catch (e) {
		$(state.$chart).html(
			`<div style="padding:8px;color:#6b7280;">${__("Chart library failed to load. Summary cards are still available.")}</div>`
		);
	}
}

function load_apexcharts() {
	if (window.ApexCharts) return Promise.resolve();
	if (window.__productionApexPromise) return window.__productionApexPromise;

	const urls = [
		"/assets/management_dashboard/js/apexcharts.min.js",
		"https://cdn.jsdelivr.net/npm/apexcharts",
	];
	let idx = 0;

	window.__productionApexPromise = new Promise((resolve, reject) => {
		const load_next = () => {
			if (window.ApexCharts) {
				resolve();
				return;
			}
			if (idx >= urls.length) {
				reject(new Error("ApexCharts failed to load"));
				return;
			}

			const script = document.createElement("script");
			script.src = urls[idx++];
			script.async = true;
			script.onload = () => {
				if (window.ApexCharts) resolve();
				else load_next();
			};
			script.onerror = () => load_next();
			document.head.appendChild(script);
		};

		load_next();
	});

	return window.__productionApexPromise;
}

function render_summary(state, summary) {
	const cards = [
		{ label: __("Rows"), value: fmt(summary.rows_count) },
		{ label: __("Order Qty"), value: fmt(summary.total_order_qty, 2) },
		{ label: __("Planned Qty"), value: fmt(summary.total_planned_qty, 2) },
		{ label: __("Cutting"), value: fmt(summary.total_cutting_qty, 2) },
		{ label: __("Stitching"), value: fmt(summary.total_stitching_qty, 2) },
		{ label: __("Packing"), value: fmt(summary.total_packing_qty, 2) },
	];

	const html = cards
		.map(
			(card) => `
			<div style="border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fff;">
				<div style="font-size:11px; color:#6b7280; margin-bottom:4px;">${frappe.utils.escape_html(card.label)}</div>
				<div style="font-size:20px; font-weight:600;">${card.value}</div>
			</div>
		`
		)
		.join("");
	state.$summary.html(html);
}

function render_table(state, rows) {
	if (!rows.length) {
		state.$table.html(`<div style="padding:10px; color:#6b7280;">${__("No production rows found for selected dates.")}</div>`);
		return;
	}

	let body = "";
	rows.forEach((r) => {
		const cut_pct = num(r.order_qty) ? (num(r.cutting_qty) / num(r.order_qty)) * 100 : 0;
		const stitch_pct = num(r.order_qty) ? (num(r.stitching_qty) / num(r.order_qty)) * 100 : 0;
		const pack_pct = num(r.order_qty) ? (num(r.packing_qty) / num(r.order_qty)) * 100 : 0;
		body += `
			<tr>
				<td>${esc(r.sales_order)}</td>
				<td>${esc(r.customer)}</td>
				<td style="text-align:right;">${fmt(r.order_qty, 2)}</td>
				<td style="text-align:right;">${fmt(r.planned_qty, 2)}</td>
				<td style="text-align:right;">${fmt(r.cutting_qty, 2)} (${fmt(cut_pct, 2)}%)</td>
				<td style="text-align:right;">${fmt(r.stitching_qty, 2)} (${fmt(stitch_pct, 2)}%)</td>
				<td style="text-align:right;">${fmt(r.packing_qty, 2)} (${fmt(pack_pct, 2)}%)</td>
			</tr>
		`;
	});

	state.$table.html(`
		<table class="table table-bordered" style="font-size:12px; margin:0;">
			<thead>
				<tr>
					<th>${__("Sales Order")}</th>
					<th>${__("Customer")}</th>
					<th style="text-align:right;">${__("Order Qty")}</th>
					<th style="text-align:right;">${__("Planned Qty")}</th>
					<th style="text-align:right;">${__("Cutting Progress")}</th>
					<th style="text-align:right;">${__("Stitching Progress")}</th>
					<th style="text-align:right;">${__("Packing Progress")}</th>
				</tr>
			</thead>
			<tbody>${body}</tbody>
		</table>
	`);
}

function num(value) {
	return Number(value || 0);
}

function fmt(value, precision = 0) {
	return frappe.format(value || 0, { fieldtype: precision ? "Float" : "Int", precision: precision || undefined });
}

function esc(v) {
	return frappe.utils.escape_html(v || "");
}
