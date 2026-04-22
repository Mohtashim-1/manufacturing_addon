frappe.pages["production-progress"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Total Daily Production",
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
	state.controls.item = frappe.ui.form.make_control({
		parent: state.$filters,
		df: {
			label: __("Combo Item"),
			fieldname: "item",
			fieldtype: "Link",
			options: "Item",
		},
		render_input: true,
	});

	state.controls.from_date.set_value(today);
	state.controls.to_date.set_value(today);

	$(state.controls.from_date.$input).on("change", () => refresh_data(state));
	$(state.controls.to_date.$input).on("change", () => refresh_data(state));
	$(state.controls.item.$input).on("change", () => refresh_data(state));
}

function setup_actions(state) {
	state.page.set_primary_action(__("Refresh"), () => refresh_data(state), "refresh");

	state.page.add_inner_button(__("Email System Managers"), () => {
		const previous_day = frappe.datetime.add_days(frappe.datetime.get_today(), -1);
		const from_date = previous_day;
		const to_date = previous_day;
		if (!from_date || !to_date) {
			frappe.msgprint(__("Please select both From Date and To Date."));
			return;
		}

		frappe.confirm(
			__("Send production progress email to all System Managers for previous day report: {0} to {1}?", [from_date, to_date]),
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
	const item = state.controls.item.get_value();
	if (!from_date || !to_date) return;

	frappe.call({
		method: "manufacturing_addon.manufacturing_addon.page.production_progress.production_progress.get_production_progress_data",
		args: { from_date, to_date, item },
		freeze: true,
		freeze_message: __("Loading production progress..."),
		callback: async (r) => {
			const data = r.message || {};
			const summary = data.summary || {};
			render_summary(state, summary);
			render_table(state, data.sales_order_rows || [], data.rows || [], data.stage_rows || [], data.item || "");
			const meta_parts = [`${data.from_date || from_date} to ${data.to_date || to_date}`];
			if (data.item) meta_parts.push(`${__("Combo Item")}: ${data.item}`);
			state.$meta.text(meta_parts.join(" | "));
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

function render_table(state, rows, detail_rows, stage_rows, selected_combo_item = "") {
	if (!rows.length) {
		state.$table.html(`<div style="padding:10px; color:#6b7280;">${__("No production rows found for selected dates.")}</div>`);
		return;
	}

	// Build SO -> detail items map
	const so_detail_map = {};
	(detail_rows || []).forEach((r) => {
		if (selected_combo_item && cstr(r.combo_item) !== cstr(selected_combo_item)) return;
		const so = r.sales_order || "Not Linked";
		if (!so_detail_map[so]) so_detail_map[so] = [];
		so_detail_map[so].push(r);
	});

	// Build SO -> stage -> item -> combo rows map
	const so_combo_map = {};
	(stage_rows || []).forEach((r) => {
		const so = r.sales_order || "Not Linked";
		const stage = (r.stage || "").toLowerCase();
		const combo_item = r.combo_item || "";
		if (selected_combo_item && cstr(combo_item) !== cstr(selected_combo_item)) return;
		if (!combo_item || !stage || !["cutting", "stitching"].includes(stage) || num(r.qty) <= 0) return;

		const item_key = get_item_key(r);
		const so_bucket = (so_combo_map[so] = so_combo_map[so] || {});
		const stage_bucket = (so_bucket[stage] = so_bucket[stage] || {});
		const combo_bucket = (stage_bucket[item_key] = stage_bucket[item_key] || {});
		const combo_key = combo_item;

		if (!combo_bucket[combo_key]) {
			combo_bucket[combo_key] = {
				combo_item,
				qty: 0,
			};
		}

		combo_bucket[combo_key].qty += num(r.qty);
	});

	let body = "";
	rows.forEach((r, idx) => {
		const row_id = `pp-so-detail-${idx}`;
		const items = so_detail_map[r.sales_order] || [];
		if (!items.length && selected_combo_item) return;
		const combo_map = so_combo_map[r.sales_order] || {};

		body += `
			<tr>
				<td>
					<span class="pp-so-toggle" data-target="${row_id}" style="cursor:pointer; margin-right:6px; color:#0f766e; font-size:11px; user-select:none;">&#9654;</span>${esc(r.sales_order)}
				</td>
				
				<td>${esc(r.customer)}</td>
				<td style="text-align:right;"><span style="white-space:nowrap;">${fmtNum(r.cutting_qty)} </span></td>
				<td style="text-align:right;"><span style="white-space:nowrap;">${fmtNum(r.stitching_qty)} </span></td>
				<td style="text-align:right;"><span style="white-space:nowrap;">${fmtNum(r.packing_qty)} </span></td>
			</tr>
			<tr id="${row_id}" class="pp-so-detail-row" style="display:none; background:#f9fafb;">
				<td colspan="5" style="padding:0;">${build_so_detail_html(items, combo_map, idx, selected_combo_item)}</td>
			</tr>
		`;
	});

	state.$table.html(`
		<table class="table table-bordered" style="font-size:12px; margin:0;">
			<thead>
				<tr>
					<th>${__("Sales Order")}</th>
					<th>${__("Customer")}</th>
					<th style="text-align:right; white-space:nowrap;">${__("Cutting ")}</th>
					<th style="text-align:right; white-space:nowrap;">${__("Stitching ")}</th>
					<th style="text-align:right; white-space:nowrap;">${__("Packing")}</th>
				</tr>
			</thead>
			<tbody>${body}</tbody>
		</table>
	`);

	// Toggle expand/collapse
	state.$table.find(".pp-so-toggle").on("click", function () {
		const $detail = state.$table.find(`#${$(this).data("target")}`);
		const opening = !$detail.is(":visible");
		$detail.toggle();
		$(this).html(opening ? "&#9660;" : "&#9654;");
	});

	// Stage tab switching
	state.$table.on("click", ".pp-stage-tab", function () {
		const $this = $(this);
		const $content = $this.closest(".pp-so-detail-content");
		$content.find(".pp-stage-tab").removeClass("pp-tab-active").css({ background: "#fff", fontWeight: "normal", borderBottom: "2px solid transparent" });
		$this.addClass("pp-tab-active").css({ background: "#f0fdf4", fontWeight: "600", borderBottom: "2px solid #0f766e" });
		const stage = $this.data("stage");
		$content.find(".pp-stage-panel").hide();
		$content.find(`.pp-stage-panel[data-stage="${stage}"]`).show();
	});

}

function build_so_detail_html(items, combo_map, row_index, selected_combo_item = "") {
	const stages = [
		{ key: "cutting", label: "Cutting", field: "cutting_qty" },
		{ key: "stitching", label: "Stitching", field: "stitching_qty" },
		{ key: "packing", label: "Packing", field: "packing_qty" },
	];

	let tabs_html = "";
	let panels_html = "";

	stages.forEach((stage, i) => {
		const stage_items = items.filter((r) => num(r[stage.field]) > 0);
		const is_first = i === 0;

		tabs_html += `
			<button class="pp-stage-tab${is_first ? " pp-tab-active" : ""}" data-stage="${stage.key}"
				style="padding:5px 16px; border:1px solid #e5e7eb; border-radius:4px 4px 0 0; cursor:pointer;
					background:${is_first ? "#f0fdf4" : "#fff"}; font-weight:${is_first ? "600" : "normal"};
					border-bottom:${is_first ? "2px solid #0f766e" : "2px solid transparent"}; font-size:12px; margin-right:2px;">
				${__(stage.label)} (${stage_items.length})
			</button>`;

		let rows_html = "";
		if (stage_items.length) {
			stage_items.forEach((r, item_index) => {
				const item_key = get_item_key(r);
				const combo_items = Object.values((combo_map[stage.key] || {})[item_key] || {}).sort((a, b) =>
					cstr(a.combo_item).localeCompare(cstr(b.combo_item))
				);
				if (combo_items.length) {
					const non_pillow = combo_items.filter((ci) => (ci.combo_item || "").toUpperCase() !== "PILLOW");
					const primary_combos = non_pillow.length ? non_pillow : combo_items;
					const summary_qty = selected_combo_item && combo_items.length === 1
						? fmtNum(combo_items[0].qty)
						: fmtNum(primary_combos.reduce((s, ci) => s + num(ci.qty), 0));
					rows_html += `
						<tr>
							<td style="padding:4px 8px;">${build_inline_combo_html(combo_items, r)}</td>
							<td style="padding:4px 8px; text-align:right;">${summary_qty}</td>
						</tr>`;
					return;
				}

				rows_html += `
					<tr>
						<td style="padding:4px 8px;">${build_item_label(r)}</td>
						<td style="padding:4px 8px; text-align:right;">${fmtNum(r[stage.field])}</td>
					</tr>`;
			});
		} else {
			rows_html = `<tr><td colspan="2" style="padding:8px; color:#6b7280;">No ${stage.label.toLowerCase()} records found.</td></tr>`;
		}

		panels_html += `
			<div class="pp-stage-panel" data-stage="${stage.key}" style="display:${is_first ? "block" : "none"};">
				<table style="width:100%; font-size:11px; border-collapse:collapse;">
					<thead>
						<tr style="background:#f1f5f9;">
							<th style="padding:4px 8px; text-align:left; border-bottom:1px solid #e5e7eb;">${__("Item")}</th>
							<th style="padding:4px 8px; text-align:right; border-bottom:1px solid #e5e7eb;">${__("Qty")}</th>
						</tr>
					</thead>
					<tbody>${rows_html}</tbody>
				</table>
			</div>`;
	});

	return `
		<div class="pp-so-detail-content" style="padding:10px 14px;">
			<div style="display:flex; gap:2px; margin-bottom:0;">${tabs_html}</div>
			<div style="border:1px solid #e5e7eb; border-top:none; background:#fff;">${panels_html}</div>
		</div>`;
}

function build_inline_combo_html(combo_items, row) {
	const rows_html = combo_items
		.map(
			(combo_row) => `
				<tr>
					<td style="padding:4px 8px;">${esc(combo_row.combo_item)}</td>
					<td style="padding:4px 8px; text-align:right;">${fmtNum(combo_row.qty)}</td>
				</tr>`
		)
		.join("");

	return `
		<details style="margin:0;">
			<summary style="cursor:pointer; list-style:none; display:flex; align-items:flex-start; gap:6px;">
				<span style="color:#0f766e; font-size:11px; line-height:18px;">&#9654;</span>
				<span>${build_item_label(row)}</span>
			</summary>
			<div style="margin-top:6px; margin-left:18px; border-left:2px solid #d1fae5; padding-left:8px;">
				<table style="width:100%; font-size:11px; border-collapse:collapse; background:#fff;">
					<thead>
						<tr style="background:#ecfeff;">
							<th style="padding:4px 8px; text-align:left; border-bottom:1px solid #e5e7eb;">${__("Combo Item")}</th>
							<th style="padding:4px 8px; text-align:right; border-bottom:1px solid #e5e7eb;">${__("Qty")}</th>
						</tr>
					</thead>
					<tbody>${rows_html}</tbody>
				</table>
			</div>
		</details>`;
}

function build_item_label(row) {
	const parts = [];
	if (row.combo_item) parts.push(row.combo_item);
	if (row.colour) parts.push(row.colour);
	if (row.size) parts.push(row.size);

	return `${esc(row.so_item)}${parts.length ? `<div style="font-size:10px; color:#6b7280; margin-top:2px;">${esc(parts.join(" / "))}</div>` : ""}`;
}

function get_item_key(row) {
	return [row.order_sheet || "", row.so_item || "", row.colour || "", row.size || ""].join("||");
}

function num(value) {
	return Number(value || 0);
}

function cstr(value) {
	return value == null ? "" : String(value);
}

function fmt(value, precision = 0) {
	return frappe.format(value || 0, { fieldtype: precision ? "Float" : "Int", precision: precision || undefined });
}

function esc(v) {
	return frappe.utils.escape_html(v || "");
}

function fmtNum(value) {
	return Number(value || 0).toLocaleString("en");
}

function fmtPct(value) {
	return Number(value || 0).toFixed(2);
}
