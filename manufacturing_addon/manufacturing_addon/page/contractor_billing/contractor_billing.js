// Contractor Billing — detailed Chart.js dashboard

frappe.pages["contractor-billing"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Contractor Billing"),
		single_column: true,
	});

	inject_cb_styles();

	const state = {
		process: "All",
		status: "All",
		data: null,
		expanded: new Set(),
		charts: {},
	};

	const filters = {
		order_sheet: page.add_field({
			label: __("Order Sheet"),
			fieldtype: "Link",
			fieldname: "order_sheet",
			options: "Order Sheet",
		}),
		contractor: page.add_field({
			label: __("Contractor"),
			fieldtype: "Link",
			fieldname: "contractor",
			options: "Manufacturing Contractor",
		}),
		from_date: page.add_field({
			label: __("From Date"),
			fieldtype: "Date",
			fieldname: "from_date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		}),
		to_date: page.add_field({
			label: __("To Date"),
			fieldtype: "Date",
			fieldname: "to_date",
			default: frappe.datetime.get_today(),
		}),
	};

	page.add_inner_button(__("Refresh"), () => load_data());

	const $root = $(`
		<div class="cb-dashboard">
			<div class="cb-hero">
				<div class="cb-hero-main">
					<div class="cb-hero-eyebrow">${__("Manufacturing")}</div>
					<h2>${__("Contractor Billing")}</h2>
					<p class="cb-hero-sub">${__(
						"Billable work from submitted Cutting, Stitching, Packing & Quality reports, valued using each Item's Style tab rates."
					)}</p>
					<div class="cb-hero-stats" id="cb-hero-stats"></div>
				</div>
				<div class="cb-hero-side">
					<div class="cb-hero-ring" id="cb-hero-ring">
						<svg viewBox="0 0 120 120"><circle class="cb-ring-bg" cx="60" cy="60" r="52"/><circle class="cb-ring-fill" id="cb-ring-fill" cx="60" cy="60" r="52"/></svg>
						<div class="cb-hero-ring-label">
							<span id="cb-ring-pct">0%</span>
							<small>${__("cleared")}</small>
						</div>
					</div>
				</div>
			</div>
			<div class="cb-alert" id="cb-coverage-alert" hidden></div>
			<div class="cb-toolbar">
				<div class="cb-toolbar-label">${__("Process")}</div>
				<div class="cb-tabs" id="cb-process-tabs"></div>
				<div class="cb-toolbar-actions">
					<span class="cb-period" id="cb-period"></span>
				</div>
			</div>
			<div class="cb-kpi-grid" id="cb-kpis"></div>
			<div class="cb-charts-grid cb-charts-grid--trend">
				<div class="cb-card cb-card-chart">
					<div class="cb-card-head"><div><h4>${__("Monthly billing & quantity")}</h4><span class="cb-card-hint">${__("Billed amount (bars) and work qty (line)")}</span></div></div>
					<div class="cb-chart-canvas-wrap cb-chart-canvas-wrap--lg"><canvas id="cb-trend-chart"></canvas></div>
				</div>
				<div class="cb-card cb-card-chart cb-card-payment">
					<div class="cb-card-head"><div><h4>${__("Payment split")}</h4><span class="cb-card-hint">${__("Paid vs outstanding")}</span></div></div>
					<div class="cb-payment-center" id="cb-payment-center"></div>
					<div class="cb-chart-canvas-wrap"><canvas id="cb-payment-chart"></canvas></div>
				</div>
			</div>
			<div class="cb-charts-grid cb-charts-grid--3">
				<div class="cb-card cb-card-chart cb-card-span-2">
					<div class="cb-card-head"><div><h4>${__("Contractor ledger")}</h4><span class="cb-card-hint">${__("Paid vs due per contractor — click bar to filter")}</span></div></div>
					<div class="cb-chart-canvas-wrap cb-chart-canvas-wrap--md"><canvas id="cb-contractor-chart"></canvas></div>
				</div>
				<div class="cb-card cb-card-chart">
					<div class="cb-card-head"><div><h4>${__("Process mix")}</h4><span class="cb-card-hint">${__("Billed amount by process")}</span></div></div>
					<div class="cb-chart-canvas-wrap"><canvas id="cb-process-chart"></canvas></div>
				</div>
			</div>
			<div class="cb-charts-grid cb-charts-grid--3">
				<div class="cb-card cb-card-chart">
					<div class="cb-card-head"><div><h4>${__("Production volume")}</h4><span class="cb-card-hint">${__("Submitted report rows by process")}</span></div></div>
					<div class="cb-chart-canvas-wrap"><canvas id="cb-volume-chart"></canvas></div>
				</div>
				<div class="cb-card cb-card-chart">
					<div class="cb-card-head"><div><h4>${__("Style tab coverage")}</h4><span class="cb-card-hint">${__("Rated vs missing rates")}</span></div></div>
					<div class="cb-chart-canvas-wrap"><canvas id="cb-coverage-chart"></canvas></div>
				</div>
				<div class="cb-card cb-card-chart">
					<div class="cb-card-head"><div><h4>${__("Settlement status")}</h4><span class="cb-card-hint">${__("Row counts by payment status")}</span></div></div>
					<div class="cb-chart-canvas-wrap"><canvas id="cb-status-chart"></canvas></div>
				</div>
			</div>
			<div class="cb-charts-grid">
				<div class="cb-card cb-card-chart">
					<div class="cb-card-head"><div><h4>${__("Top orders")}</h4><span class="cb-card-hint">${__("Highest billed order sheets")}</span></div></div>
					<div class="cb-chart-canvas-wrap cb-chart-canvas-wrap--md"><canvas id="cb-order-chart"></canvas></div>
				</div>
				<div class="cb-card cb-card-chart">
					<div class="cb-card-head"><div><h4>${__("Quantity by process")}</h4><span class="cb-card-hint">${__("Billable work quantity")}</span></div></div>
					<div class="cb-chart-canvas-wrap cb-chart-canvas-wrap--md"><canvas id="cb-qty-chart"></canvas></div>
				</div>
			</div>
			<div class="cb-insights" id="cb-insights"></div>
			<div class="cb-card cb-card-table">
				<div class="cb-table-head">
					<div>
						<h4>${__("Billing details")}</h4>
						<span class="cb-card-hint">${__("Expand a row for report-level breakdown")}</span>
					</div>
					<div class="cb-table-toolbar">
						<input type="search" class="cb-search" id="cb-search" placeholder="${__(
							"Search contractor or order…"
						)}" />
						<select class="cb-select" id="cb-status-filter">
							<option value="All">${__("All statuses")}</option>
							<option value="Paid">${__("Paid")}</option>
							<option value="Partial">${__("Partial")}</option>
							<option value="Due">${__("Due")}</option>
						</select>
						<span class="cb-row-count" id="cb-row-count"></span>
					</div>
				</div>
				<div class="table-responsive">
					<table class="table cb-table">
						<thead>
							<tr>
								<th class="cb-col-expand"></th>
								<th>${__("Contractor")}</th>
								<th>${__("Process")}</th>
								<th>${__("Order")}</th>
								<th class="text-right">${__("Qty")}</th>
								<th>${__("Status")}</th>
								<th class="text-right">${__("Total Bill")}</th>
								<th class="text-right">${__("Paid")}</th>
								<th class="text-right">${__("Due")}</th>
								<th>${__("Progress")}</th>
							</tr>
						</thead>
						<tbody id="cb-table-body"></tbody>
					</table>
				</div>
			</div>
		</div>
	`);

	$(page.body).append($root);

	const PROCESSES = ["All", "Cutting", "Stitching", "Sub-Assembly", "Quality", "Packing"];
	const $tabs = $("#cb-process-tabs");
	PROCESSES.forEach((proc) => {
		$tabs.append(
			`<button type="button" class="cb-tab${proc === "All" ? " active" : ""}" data-process="${proc}">${__(
				proc
			)}</button>`
		);
	});

	$tabs.on("click", ".cb-tab", function () {
		$tabs.find(".cb-tab").removeClass("active");
		$(this).addClass("active");
		state.process = $(this).data("process");
		state.expanded.clear();
		load_data();
	});

	$("#cb-status-filter").on("change", function () {
		state.status = $(this).val();
		load_data();
	});

	let searchTimer;
	$("#cb-search").on("input", function () {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(load_data, 300);
	});

	Object.values(filters).forEach((field) => {
		if (field && field.$input) {
			field.$input.on("change", () => load_data());
		}
	});

	$("#cb-table-body").on("click", ".cb-expand-btn", function (e) {
		e.stopPropagation();
		const key = $(this).closest("tr").data("row-key");
		if (state.expanded.has(key)) state.expanded.delete(key);
		else state.expanded.add(key);
		render_table(state.data?.rows || []);
	});

	$("#cb-table-body").on("click", ".cb-row-main", function () {
		const key = $(this).data("row-key");
		if (state.expanded.has(key)) state.expanded.delete(key);
		else state.expanded.add(key);
		render_table(state.data?.rows || []);
	});

	function load_data() {
		load_chartjs()
			.then(() => {
				frappe.call({
					method:
						"manufacturing_addon.manufacturing_addon.page.contractor_billing.contractor_billing.get_contractor_billing_data",
					args: {
						filters: {
							order_sheet: filters.order_sheet.get_value(),
							contractor: filters.contractor.get_value(),
							from_date: filters.from_date.get_value(),
							to_date: filters.to_date.get_value(),
							process: state.process,
							status: state.status,
							search: $("#cb-search").val(),
						},
					},
					freeze: true,
					freeze_message: __("Loading billing data…"),
					callback(r) {
						state.data = r.message || {};
						render_dashboard(state.data);
					},
				});
			})
			.catch(() => {
				frappe.msgprint(__("Could not load chart libraries. Please refresh the page."));
			});
	}

	function render_dashboard(data) {
		render_hero(data.kpis || {}, data.filters || {});
		render_coverage_alert(data.kpis || {});
		render_kpis(data.kpis || {});
		render_insights(data);
		render_trend_chart(data.trend_chart || {});
		render_payment_chart(data.kpis || {});
		render_contractor_chart(data.contractor_stacked || data.process_chart || {});
		render_process_chart(data.process_totals || {});
		render_volume_chart(data.report_volume || {});
		render_coverage_chart(data.coverage_chart || {});
		render_status_chart(data.status_summary || {}, data.rows || []);
		render_order_chart(data.order_chart || {});
		render_qty_chart(data.process_qty || {});
		render_table(data.rows || []);
	}

	function render_hero(k, filters) {
		const cleared = Math.min(k.cleared_pct || 0, 100);
		$("#cb-hero-stats").html(`
			<div class="cb-hero-stat">
				<span class="cb-hero-stat-label">${__("Total billed")}</span>
				<strong>${format_currency(k.total_billed)}</strong>
			</div>
			<div class="cb-hero-stat">
				<span class="cb-hero-stat-label">${__("Amount due")}</span>
				<strong class="cb-text-danger">${format_currency(k.total_due)}</strong>
			</div>
			<div class="cb-hero-stat">
				<span class="cb-hero-stat-label">${__("Contractors")}</span>
				<strong>${k.contractor_count || 0}</strong>
			</div>
		`);
		$("#cb-ring-pct").text(`${cleared}%`);
		const circumference = 2 * Math.PI * 52;
		const offset = circumference - (cleared / 100) * circumference;
		$("#cb-ring-fill").css({
			strokeDasharray: circumference,
			strokeDashoffset: offset,
		});
		const from = filters.from_date ? frappe.datetime.str_to_user(filters.from_date) : "";
		const to = filters.to_date ? frappe.datetime.str_to_user(filters.to_date) : "";
		$("#cb-period").text(from && to ? `${from} → ${to}` : "");
	}

	function render_coverage_alert(k) {
		const total = k.report_qty_rows || 0;
		const billed = k.line_count || 0;
		const $alert = $("#cb-coverage-alert");
		if (!total || billed >= total) {
			$alert.prop("hidden", true).empty();
			return;
		}
		const pct = total ? Math.round((billed / total) * 100) : 0;
		$alert.prop("hidden", false).html(`
			<div class="cb-alert-icon">ℹ</div>
			<div class="cb-alert-body">
				<strong>${__("Style tab coverage is low")}</strong>
				<span>${billed} ${__("of")} ${total} ${__(
					"report lines have billable rates"
				)} (${pct}%). ${__(
					"Add Cutting / Stitching / Packing rates on each Item's Style tab to bill the rest."
				)}</span>
			</div>
		`);
	}

	function render_kpis(k) {
		$("#cb-kpis").html(`
			<div class="cb-kpi cb-kpi-primary">
				<div class="cb-kpi-top">
					<span class="cb-kpi-label">${__("Amount paid")}</span>
					<span class="cb-kpi-badge cb-kpi-badge-success">${k.cleared_pct || 0}%</span>
				</div>
				<div class="cb-kpi-value">${format_currency(k.total_paid)}</div>
				<div class="cb-kpi-bar"><span class="cb-kpi-bar-fill cb-kpi-bar-success" style="width:${Math.min(k.cleared_pct || 0, 100)}%"></span></div>
			</div>
			<div class="cb-kpi">
				<div class="cb-kpi-top">
					<span class="cb-kpi-label">${__("Report lines")}</span>
					<span class="cb-kpi-badge">${k.line_count || 0} ${__("rated")}</span>
				</div>
				<div class="cb-kpi-value cb-kpi-num">${format_number(k.report_qty_rows || 0)}</div>
				<div class="cb-kpi-sub">${__("submitted production rows in range")}</div>
			</div>
			<div class="cb-kpi">
				<div class="cb-kpi-top">
					<span class="cb-kpi-label">${__("Settlements")}</span>
				</div>
				<div class="cb-kpi-split">
					<div><span class="cb-kpi-mini">${__("Paid")}</span><strong>${k.bills_paid || 0}</strong></div>
					<div><span class="cb-kpi-mini">${__("Partial")}</span><strong>${k.bills_partial || 0}</strong></div>
					<div><span class="cb-kpi-mini">${__("Draft")}</span><strong>${k.bills_draft || 0}</strong></div>
				</div>
			</div>
			<div class="cb-kpi cb-kpi-danger-soft">
				<div class="cb-kpi-top">
					<span class="cb-kpi-label">${__("Outstanding bills")}</span>
					<span class="cb-kpi-badge cb-kpi-badge-danger">${k.bills_due || 0}</span>
				</div>
				<div class="cb-kpi-value cb-text-danger">${format_currency(k.total_due)}</div>
				<div class="cb-kpi-sub">${__("pending contractor settlements")}</div>
			</div>
		`);
	}

	function render_insights(data) {
		const k = data.kpis || {};
		const rows = data.rows || [];
		const proc = data.process_totals || {};
		const topProc = Object.entries(proc).sort((a, b) => b[1] - a[1])[0];
		const topRow = rows.slice().sort((a, b) => flt(b.total_bill) - flt(a.total_bill))[0];
		const avgBill = rows.length ? flt(k.total_billed) / rows.length : 0;
		$("#cb-insights").html(`
			<div class="cb-insight"><span class="cb-insight-label">${__("Avg per row")}</span><strong>${format_currency(avgBill)}</strong></div>
			<div class="cb-insight"><span class="cb-insight-label">${__("Top process")}</span><strong>${topProc ? frappe.utils.escape_html(topProc[0]) : "—"}</strong><small>${topProc ? format_currency(topProc[1]) : ""}</small></div>
			<div class="cb-insight"><span class="cb-insight-label">${__("Largest bill")}</span><strong>${topRow ? frappe.utils.escape_html(topRow.contractor || "") : "—"}</strong><small>${topRow ? format_currency(topRow.total_bill) : ""}</small></div>
			<div class="cb-insight"><span class="cb-insight-label">${__("Coverage")}</span><strong>${k.report_qty_rows ? Math.round(((k.line_count || 0) / k.report_qty_rows) * 100) : 0}%</strong><small>${k.line_count || 0} / ${k.report_qty_rows || 0} ${__("lines rated")}</small></div>
		`);
	}

	function destroy_chart(key) {
		if (state.charts[key]) {
			state.charts[key].destroy();
			delete state.charts[key];
		}
	}

	function chart_font() {
		return { family: getComputedStyle(document.body).fontFamily || "inherit", size: 11 };
	}

	function chart_options(extra = {}) {
		const base = {
			responsive: true,
			maintainAspectRatio: false,
			plugins: {
				legend: { labels: { font: chart_font(), boxWidth: 12, padding: 14 } },
				tooltip: {
					backgroundColor: "#0f172a",
					titleFont: chart_font(),
					bodyFont: chart_font(),
					padding: 10,
					cornerRadius: 8,
				},
			},
			animation: { duration: 700, easing: "easeOutQuart" },
		};
		return $.extend(true, {}, base, extra);
	}

	function currency_tooltip() {
		return {
			callbacks: {
				label: (ctx) => {
					const label = ctx.dataset.label ? `${ctx.dataset.label}: ` : "";
					return `${label}${format_currency(ctx.parsed.y ?? ctx.parsed.x ?? ctx.raw)}`;
				},
			},
		};
	}

	function show_chart_empty(canvasId, message) {
		destroy_chart(canvasId);
		const wrap = document.getElementById(canvasId)?.parentElement;
		if (!wrap) return;
		wrap.querySelector(".cb-chart-empty")?.remove();
		const el = document.createElement("div");
		el.className = "cb-chart-empty";
		el.textContent = message;
		wrap.appendChild(el);
	}

	function clear_chart_empty(canvasId) {
		document.getElementById(canvasId)?.parentElement?.querySelector(".cb-chart-empty")?.remove();
	}

	function render_trend_chart(chart) {
		const canvas = document.getElementById("cb-trend-chart");
		if (!canvas || typeof Chart === "undefined") return;
		destroy_chart("trend");
		const labels = chart.labels || [];
		if (!labels.length) {
			show_chart_empty("cb-trend-chart", __("No trend data for selected period."));
			return;
		}
		clear_chart_empty("cb-trend-chart");
		state.charts.trend = new Chart(canvas.getContext("2d"), {
			type: "bar",
			data: {
				labels,
				datasets: [
					{
						type: "bar",
						label: __("Billed"),
						data: chart.billed || [],
						backgroundColor: "rgba(79, 70, 229, 0.85)",
						borderRadius: 6,
						yAxisID: "y",
						order: 2,
					},
					{
						type: "line",
						label: __("Work Qty"),
						data: chart.qty || [],
						borderColor: "#f59e0b",
						backgroundColor: "rgba(245, 158, 11, 0.12)",
						borderWidth: 2.5,
						tension: 0.35,
						fill: true,
						pointRadius: 4,
						pointHoverRadius: 6,
						yAxisID: "y1",
						order: 1,
					},
				],
			},
			options: chart_options({
				interaction: { mode: "index", intersect: false },
				plugins: {
					legend: { position: "top", align: "end" },
					tooltip: {
						callbacks: {
							label: (ctx) => {
								if (ctx.dataset.label === __("Work Qty")) {
									return `${ctx.dataset.label}: ${format_number(ctx.parsed.y)}`;
								}
								return `${ctx.dataset.label}: ${format_currency(ctx.parsed.y)}`;
							},
						},
					},
				},
				scales: {
					x: { grid: { display: false }, ticks: { font: chart_font(), maxRotation: 45 } },
					y: {
						position: "left",
						ticks: { callback: (v) => format_compact(v), font: chart_font() },
						grid: { color: "#f1f5f9" },
					},
					y1: {
						position: "right",
						grid: { drawOnChartArea: false },
						ticks: { callback: (v) => format_number(v), font: chart_font() },
					},
				},
			}),
		});
	}

	function render_payment_chart(kpis) {
		const canvas = document.getElementById("cb-payment-chart");
		if (!canvas || typeof Chart === "undefined") return;
		destroy_chart("payment");
		const paid = flt(kpis.total_paid);
		const due = flt(kpis.total_due);
		if (paid <= 0 && due <= 0) {
			$("#cb-payment-center").empty();
			show_chart_empty("cb-payment-chart", __("No payment data yet."));
			return;
		}
		clear_chart_empty("cb-payment-chart");
		$("#cb-payment-center").html(`
			<div class="cb-payment-total">${format_currency(flt(kpis.total_billed))}</div>
			<div class="cb-payment-sub">${__("total billed")}</div>
		`);
		state.charts.payment = new Chart(canvas.getContext("2d"), {
			type: "doughnut",
			data: {
				labels: [__("Paid"), __("Due")],
				datasets: [
					{
						data: [paid, due],
						backgroundColor: ["#10b981", "#ef4444"],
						borderWidth: 3,
						borderColor: "#ffffff",
						hoverOffset: 10,
					},
				],
			},
			options: chart_options({
				cutout: "70%",
				plugins: {
					legend: { position: "bottom" },
					tooltip: currency_tooltip(),
				},
			}),
		});
	}

	function contractor_initials(name) {
		return String(name || "?")
			.split(/[\s(]+/)
			.filter(Boolean)
			.slice(0, 2)
			.map((w) => w[0])
			.join("")
			.toUpperCase();
	}

	function short_label(text, max = 24) {
		const s = String(text || "");
		return s.length > max ? `${s.slice(0, max - 1)}…` : s;
	}

	function render_contractor_chart(chart) {
		const canvas = document.getElementById("cb-contractor-chart");
		if (!canvas || typeof Chart === "undefined") return;
		destroy_chart("contractor");
		const labels = (chart.labels || []).map((l) => short_label(l, 28));
		const rawLabels = chart.labels || [];
		if (!labels.length) {
			show_chart_empty(
				"cb-contractor-chart",
				__("No billable contractors. Add Style tab rates on Items used in submitted reports.")
			);
			return;
		}
		clear_chart_empty("cb-contractor-chart");
		const hasStack = chart.paid && chart.due;
		const datasets = hasStack
			? [
					{
						label: __("Paid"),
						data: chart.paid,
						backgroundColor: "#10b981",
						borderRadius: 4,
						stack: "stack",
					},
					{
						label: __("Due"),
						data: chart.due,
						backgroundColor: "#ef4444",
						borderRadius: 4,
						stack: "stack",
					},
				]
			: [
					{
						label: __("Billed"),
						data: chart.amounts || [],
						backgroundColor: "#4f46e5",
						borderRadius: 6,
					},
				];
		state.charts.contractor = new Chart(canvas.getContext("2d"), {
			type: "bar",
			data: { labels, datasets },
			options: chart_options({
				indexAxis: "y",
				plugins: {
					legend: { position: "top", align: "end" },
					tooltip: currency_tooltip(),
				},
				scales: {
					x: {
						stacked: !!hasStack,
						ticks: { callback: (v) => format_compact(v), font: chart_font() },
						grid: { color: "#f1f5f9" },
					},
					y: { stacked: !!hasStack, grid: { display: false }, ticks: { font: { ...chart_font(), weight: "600" } } },
				},
				onClick: (_e, elements) => {
					if (!elements.length || !filters.contractor) return;
					const idx = elements[0].index;
					const name = rawLabels[idx];
					if (name) {
						filters.contractor.set_value(name);
						load_data();
					}
				},
			}),
		});
	}

	const PROCESS_COLORS = {
		Cutting: "#4f46e5",
		Stitching: "#059669",
		"Sub-Assembly": "#d97706",
		Quality: "#9333ea",
		Packing: "#0891b2",
		Other: "#94a3b8",
	};

	function process_colors(labels) {
		return (labels || []).map((l) => PROCESS_COLORS[l] || "#64748b");
	}

	function render_process_chart(processTotals) {
		const canvas = document.getElementById("cb-process-chart");
		if (!canvas || typeof Chart === "undefined") return;
		destroy_chart("process");
		const labels = Object.keys(processTotals || {});
		const data = labels.map((k) => processTotals[k]);
		if (!labels.length) {
			show_chart_empty("cb-process-chart", __("No process breakdown."));
			return;
		}
		clear_chart_empty("cb-process-chart");
		state.charts.process = new Chart(canvas.getContext("2d"), {
			type: "polarArea",
			data: {
				labels,
				datasets: [
					{
						data,
						backgroundColor: process_colors(labels).map((c) => c + "cc"),
						borderColor: "#fff",
						borderWidth: 2,
					},
				],
			},
			options: chart_options({
				plugins: {
					legend: { position: "bottom" },
					tooltip: currency_tooltip(),
				},
				scales: { r: { ticks: { display: false }, grid: { color: "#e2e8f0" } } },
				onClick: (_e, elements) => {
					if (!elements.length) return;
					const proc = labels[elements[0].index];
					if (!proc) return;
					state.process = proc;
					$tabs.find(".cb-tab").removeClass("active");
					const $match = $tabs.find(`.cb-tab[data-process="${proc}"]`);
					if ($match.length) $match.addClass("active");
					else {
						state.process = "All";
						$tabs.find('.cb-tab[data-process="All"]').addClass("active");
					}
					load_data();
				},
			}),
		});
	}

	function render_volume_chart(chart) {
		const canvas = document.getElementById("cb-volume-chart");
		if (!canvas || typeof Chart === "undefined") return;
		destroy_chart("volume");
		const labels = chart.labels || [];
		if (!labels.length) {
			show_chart_empty("cb-volume-chart", __("No production report rows in range."));
			return;
		}
		clear_chart_empty("cb-volume-chart");
		state.charts.volume = new Chart(canvas.getContext("2d"), {
			type: "bar",
			data: {
				labels,
				datasets: [
					{
						label: __("Report lines"),
						data: chart.counts || [],
						backgroundColor: process_colors(labels),
						borderRadius: 6,
						yAxisID: "y",
					},
					{
						type: "line",
						label: __("Work qty"),
						data: chart.work_qty || [],
						borderColor: "#0ea5e9",
						backgroundColor: "transparent",
						borderWidth: 2,
						tension: 0.3,
						pointRadius: 3,
						yAxisID: "y1",
					},
				],
			},
			options: chart_options({
				plugins: {
					legend: { position: "top", align: "end" },
					tooltip: {
						callbacks: {
							label: (ctx) => {
								if (ctx.dataset.label === __("Work qty")) {
									return `${ctx.dataset.label}: ${format_number(ctx.parsed.y)}`;
								}
								return `${ctx.dataset.label}: ${format_number(ctx.parsed.y)}`;
							},
						},
					},
				},
				scales: {
					x: { grid: { display: false }, ticks: { font: chart_font() } },
					y: { position: "left", ticks: { font: chart_font() }, grid: { color: "#f1f5f9" } },
					y1: { position: "right", grid: { drawOnChartArea: false }, ticks: { font: chart_font() } },
				},
			}),
		});
	}

	function render_coverage_chart(chart) {
		const canvas = document.getElementById("cb-coverage-chart");
		if (!canvas || typeof Chart === "undefined") return;
		destroy_chart("coverage");
		const labels = chart.labels || [];
		if (!labels.length) {
			show_chart_empty("cb-coverage-chart", __("No coverage data."));
			return;
		}
		clear_chart_empty("cb-coverage-chart");
		state.charts.coverage = new Chart(canvas.getContext("2d"), {
			type: "bar",
			data: {
				labels,
				datasets: [
					{
						label: __("With Style rates"),
						data: chart.rated || [],
						backgroundColor: "#10b981",
						borderRadius: 4,
						stack: "cov",
					},
					{
						label: __("Missing rates"),
						data: chart.missing || [],
						backgroundColor: "#fbbf24",
						borderRadius: 4,
						stack: "cov",
					},
				],
			},
			options: chart_options({
				plugins: {
					legend: { position: "top", align: "end" },
					tooltip: {
						callbacks: {
							label: (ctx) => `${ctx.dataset.label}: ${format_number(ctx.parsed.y)} ${__("lines")}`,
						},
					},
				},
				scales: {
					x: { stacked: true, grid: { display: false }, ticks: { font: chart_font() } },
					y: { stacked: true, ticks: { font: chart_font() }, grid: { color: "#f1f5f9" } },
				},
			}),
		});
	}

	function render_status_chart(statusSummary, rows) {
		const canvas = document.getElementById("cb-status-chart");
		if (!canvas || typeof Chart === "undefined") return;
		destroy_chart("status");
		const counts = statusSummary.counts || {};
		const labels = [__("Paid"), __("Partial"), __("Due")];
		const data = [counts.Paid || 0, counts.Partial || 0, counts.Due || 0];
		const amounts = [
			rows.filter((r) => r.status === "Paid").reduce((s, r) => s + flt(r.total_bill), 0),
			rows.filter((r) => r.status === "Partial").reduce((s, r) => s + flt(r.total_bill), 0),
			rows.filter((r) => r.status === "Due").reduce((s, r) => s + flt(r.total_bill), 0),
		];
		if (!data.some((v) => v > 0)) {
			show_chart_empty("cb-status-chart", __("No settlement rows."));
			return;
		}
		clear_chart_empty("cb-status-chart");
		state.charts.status = new Chart(canvas.getContext("2d"), {
			type: "bar",
			data: {
				labels,
				datasets: [
					{
						label: __("Rows"),
						data,
						backgroundColor: ["#10b981", "#f59e0b", "#ef4444"],
						borderRadius: 8,
						yAxisID: "y",
					},
					{
						type: "line",
						label: __("Amount"),
						data: amounts,
						borderColor: "#4f46e5",
						backgroundColor: "transparent",
						borderWidth: 2.5,
						tension: 0.3,
						pointRadius: 5,
						yAxisID: "y1",
					},
				],
			},
			options: chart_options({
				plugins: {
					legend: { position: "top", align: "end" },
					tooltip: {
						callbacks: {
							label: (ctx) => {
								if (ctx.dataset.label === __("Amount")) {
									return `${ctx.dataset.label}: ${format_currency(ctx.parsed.y)}`;
								}
								return `${ctx.dataset.label}: ${format_number(ctx.parsed.y)}`;
							},
						},
					},
				},
				scales: {
					x: { grid: { display: false }, ticks: { font: chart_font() } },
					y: { position: "left", ticks: { stepSize: 1, font: chart_font() }, grid: { color: "#f1f5f9" } },
					y1: {
						position: "right",
						grid: { drawOnChartArea: false },
						ticks: { callback: (v) => format_compact(v), font: chart_font() },
					},
				},
			}),
		});
	}

	function render_order_chart(chart) {
		const canvas = document.getElementById("cb-order-chart");
		if (!canvas || typeof Chart === "undefined") return;
		destroy_chart("order");
		const rawLabels = chart.labels || [];
		const labels = rawLabels.map((l) => short_label(l, 22));
		if (!labels.length) {
			show_chart_empty("cb-order-chart", __("No order sheet billing."));
			return;
		}
		clear_chart_empty("cb-order-chart");
		state.charts.order = new Chart(canvas.getContext("2d"), {
			type: "bar",
			data: {
				labels,
				datasets: [
					{
						label: __("Billed"),
						data: chart.amounts || [],
						backgroundColor: "rgba(99, 102, 241, 0.8)",
						borderRadius: 6,
					},
				],
			},
			options: chart_options({
				indexAxis: "y",
				plugins: { legend: { display: false }, tooltip: currency_tooltip() },
				scales: {
					x: { ticks: { callback: (v) => format_compact(v), font: chart_font() }, grid: { color: "#f1f5f9" } },
					y: { grid: { display: false }, ticks: { font: { ...chart_font(), weight: "600" } } },
				},
			}),
		});
	}

	function render_qty_chart(chart) {
		const canvas = document.getElementById("cb-qty-chart");
		if (!canvas || typeof Chart === "undefined") return;
		destroy_chart("qty");
		const labels = chart.labels || [];
		if (!labels.length) {
			show_chart_empty("cb-qty-chart", __("No billable quantity."));
			return;
		}
		clear_chart_empty("cb-qty-chart");
		state.charts.qty = new Chart(canvas.getContext("2d"), {
			type: "doughnut",
			data: {
				labels,
				datasets: [
					{
						data: chart.qty || [],
						backgroundColor: process_colors(labels),
						borderWidth: 2,
						borderColor: "#fff",
						hoverOffset: 8,
					},
				],
			},
			options: chart_options({
				cutout: "55%",
				plugins: {
					legend: { position: "right" },
					tooltip: {
						callbacks: {
							label: (ctx) => `${ctx.label}: ${format_number(ctx.parsed)}`,
						},
					},
				},
			}),
		});
	}

	function row_key(row, idx) {
		return `${row.contractor}|${row.process}|${row.order_sheet}|${idx}`;
	}

	function render_table(rows) {
		const $body = $("#cb-table-body");
		$("#cb-row-count").text(
			rows.length ? `${rows.length} ${__("rows")}` : __("0 rows")
		);
		if (!rows.length) {
			$body.html(
				`<tr><td colspan="10" class="cb-empty">${__(
					"No billing rows in this view. Work qty is read from submitted Cutting, Stitching, Packing & Quality reports; amounts need rates on the Item Style tab."
				)}</td></tr>`
			);
			return;
		}

		const html = [];
		rows.forEach((row, idx) => {
			const key = row_key(row, idx);
			const expanded = state.expanded.has(key);
			const statusClass =
				row.status === "Paid" ? "cb-status-paid" : row.status === "Partial" ? "cb-status-partial" : "cb-status-due";
			const subTag = row.is_subassembly ? `<span class="cb-sub-tag">${__("sub-assembly")}</span>` : "";
			const reports = (row.report_names || []).slice(0, 3).join(", ");
			const moreReports = (row.report_names || []).length > 3 ? ` +${row.report_names.length - 3}` : "";

			html.push(`
			<tr class="cb-row-main${expanded ? " expanded" : ""}" data-row-key="${frappe.utils.escape_html(key)}">
				<td class="cb-col-expand">
					<button type="button" class="cb-expand-btn" aria-label="${__("Toggle details")}">${expanded ? "▼" : "▶"}</button>
				</td>
				<td>
					<div class="cb-contractor-cell">
						<span class="cb-avatar">${frappe.utils.escape_html(contractor_initials(row.contractor))}</span>
						<div>
							<div class="cb-contractor-name">${frappe.utils.escape_html(row.contractor || "")}</div>
							${row.supplier ? `<div class="cb-contractor-sub">${frappe.utils.escape_html(row.supplier)}</div>` : ""}
							${subTag}
						</div>
					</div>
				</td>
				<td><span class="cb-process-pill cb-process-${(row.process || "").replace(/\s/g, "-")}">${frappe.utils.escape_html(row.process || "")}</span></td>
				<td class="cb-order">
					${row.order_sheet ? `<a href="/app/order-sheet/${encodeURIComponent(row.order_sheet)}" class="cb-link">${frappe.utils.escape_html(row.order_sheet)}</a>` : "—"}
					${reports ? `<div class="cb-report-refs">${frappe.utils.escape_html(reports)}${moreReports}</div>` : ""}
				</td>
				<td class="cb-qty">${format_number(row.qty)}</td>
				<td><span class="cb-status ${statusClass}">${frappe.utils.escape_html(row.status || "Due")}</span></td>
				<td class="text-right cb-money">${format_currency(row.total_bill)}</td>
				<td class="text-right cb-money cb-paid">${format_currency(row.paid)}</td>
				<td class="text-right cb-money cb-due">${format_currency(row.due)}</td>
				<td>
					<div class="cb-progress-wrap">
						<div class="cb-progress-bar"><div class="cb-progress-fill" style="width:${row.progress || 0}%"></div></div>
						<span class="cb-progress-pct">${row.progress || 0}%</span>
					</div>
				</td>
			</tr>`);

			if (expanded && (row.details || []).length) {
				html.push(`
				<tr class="cb-row-detail">
					<td colspan="10">
						<div class="cb-detail-panel">
							<div class="cb-detail-title">${__("Report line breakdown")}</div>
							<table class="table table-sm cb-detail-table">
								<thead><tr>
									<th>${__("Report")}</th>
									<th>${__("Date")}</th>
									<th>${__("Style")}</th>
									<th>${__("Item")}</th>
									<th class="text-right">${__("Work Qty")}</th>
									<th class="text-right">${__("Rate")}</th>
									<th class="text-right">${__("Amount")}</th>
								</tr></thead>
								<tbody>
									${row.details
										.map(
											(d) => `
										<tr>
											<td><a href="#" class="cb-report-link" data-report="${frappe.utils.escape_html(d.report_name || "")}">${frappe.utils.escape_html(d.report_name || "—")}</a></td>
											<td>${frappe.utils.escape_html(d.report_date || "—")}</td>
											<td>${frappe.utils.escape_html(d.style || "—")}</td>
											<td class="cb-detail-item">${frappe.utils.escape_html(d.so_item || "—")}</td>
											<td class="text-right">${format_number(d.work_qty)}</td>
											<td class="text-right">${format_currency(d.rate)}</td>
											<td class="text-right">${format_currency(d.amount)}</td>
										</tr>`
										)
										.join("")}
								</tbody>
							</table>
						</div>
					</td>
				</tr>`);
			}
		});
		$body.html(html.join(""));

		$body.find(".cb-report-link").on("click", function (e) {
			e.preventDefault();
			e.stopPropagation();
			const name = $(this).data("report");
			if (!name) return;
			const doctype_map = [
				["SR-", "Stitching Report"],
				["CR-", "Cutting Report"],
				["PR-", "Packing Report"],
				["QR-", "Quality Report"],
			];
			for (const [prefix, doctype] of doctype_map) {
				if (String(name).startsWith(prefix)) {
					frappe.set_route("Form", doctype, name);
					return;
				}
			}
			frappe.show_alert({ message: name, indicator: "blue" });
		});
	}

	function format_currency(value) {
		return frappe.format(value || 0, { fieldtype: "Currency" });
	}

	function format_number(value) {
		return flt(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
	}

	function format_compact(value) {
		const n = flt(value);
		if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
		if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
		return String(Math.round(n));
	}

	function flt(value) {
		return Number(value || 0) || 0;
	}

	load_data();
};

let chartjsPromise = null;

function load_chartjs() {
	if (typeof Chart !== "undefined") return Promise.resolve();
	if (chartjsPromise) return chartjsPromise;
	const urls = ["/assets/quality_addon/js/chart.min.js", "https://cdn.jsdelivr.net/npm/chart.js"];
	chartjsPromise = new Promise((resolve, reject) => {
		let idx = 0;
		const tryNext = () => {
			if (typeof Chart !== "undefined") return resolve();
			if (idx >= urls.length) return reject(new Error("Chart.js failed"));
			const script = document.createElement("script");
			script.src = urls[idx++];
			script.onload = () => (typeof Chart !== "undefined" ? resolve() : tryNext());
			script.onerror = tryNext;
			document.head.appendChild(script);
		};
		tryNext();
	});
	return chartjsPromise;
}

function inject_cb_styles() {
	const styleId = "cb-dashboard-styles-v4";
	document.getElementById("cb-dashboard-styles-v3")?.remove();
	document.getElementById("cb-dashboard-styles-v2")?.remove();
	document.getElementById("cb-dashboard-styles")?.remove();
	if (document.getElementById(styleId)) return;
	const css = `
		.cb-dashboard {
			--cb-bg: #eef2f7;
			--cb-card: #ffffff;
			--cb-border: #e5eaf1;
			--cb-text: #0f172a;
			--cb-muted: #64748b;
			--cb-success: #059669;
			--cb-danger: #dc2626;
			--cb-warning: #d97706;
			--cb-primary: #4f46e5;
			--cb-primary-soft: #eef2ff;
			background: var(--cb-bg);
			color: var(--cb-text);
			padding: 20px;
			border-radius: 16px;
			margin: -8px -8px 12px;
		}
		.cb-hero {
			display: grid;
			grid-template-columns: 1fr auto;
			gap: 24px;
			align-items: center;
			margin-bottom: 16px;
			padding: 28px 32px;
			background: linear-gradient(135deg, #312e81 0%, #4f46e5 48%, #6366f1 100%);
			border-radius: 20px;
			color: #fff;
			box-shadow: 0 20px 40px rgba(79, 70, 229, 0.22);
			position: relative;
			overflow: hidden;
		}
		.cb-hero::after {
			content: "";
			position: absolute;
			right: -40px;
			top: -60px;
			width: 220px;
			height: 220px;
			border-radius: 50%;
			background: rgba(255,255,255,.08);
		}
		.cb-hero-main { position: relative; z-index: 1; }
		.cb-hero-eyebrow {
			font-size: 11px;
			font-weight: 700;
			letter-spacing: .12em;
			text-transform: uppercase;
			opacity: .75;
			margin-bottom: 8px;
		}
		.cb-hero h2 { margin: 0 0 8px; font-size: 28px; font-weight: 800; letter-spacing: -.02em; }
		.cb-hero-sub { margin: 0 0 20px; font-size: 14px; line-height: 1.55; max-width: 620px; opacity: .9; }
		.cb-hero-stats { display: flex; flex-wrap: wrap; gap: 12px; }
		.cb-hero-stat {
			background: rgba(255,255,255,.12);
			border: 1px solid rgba(255,255,255,.18);
			border-radius: 14px;
			padding: 12px 16px;
			min-width: 140px;
			backdrop-filter: blur(8px);
		}
		.cb-hero-stat-label { display: block; font-size: 11px; opacity: .8; margin-bottom: 4px; }
		.cb-hero-stat strong { font-size: 18px; font-weight: 800; font-variant-numeric: tabular-nums; }
		.cb-hero-side { position: relative; z-index: 1; }
		.cb-hero-ring { position: relative; width: 120px; height: 120px; }
		.cb-hero-ring svg { transform: rotate(-90deg); width: 100%; height: 100%; }
		.cb-ring-bg { fill: none; stroke: rgba(255,255,255,.18); stroke-width: 10; }
		.cb-ring-fill {
			fill: none;
			stroke: #a5f3fc;
			stroke-width: 10;
			stroke-linecap: round;
			transition: stroke-dashoffset .8s ease;
		}
		.cb-hero-ring-label {
			position: absolute;
			inset: 0;
			display: flex;
			flex-direction: column;
			align-items: center;
			justify-content: center;
			font-weight: 800;
		}
		.cb-hero-ring-label span { font-size: 22px; line-height: 1; }
		.cb-hero-ring-label small { font-size: 11px; opacity: .8; margin-top: 2px; font-weight: 600; }
		.cb-alert {
			display: flex;
			gap: 12px;
			align-items: flex-start;
			padding: 14px 16px;
			margin-bottom: 16px;
			background: #fffbeb;
			border: 1px solid #fde68a;
			border-radius: 14px;
			color: #92400e;
		}
		.cb-alert-icon {
			width: 28px; height: 28px; border-radius: 8px;
			background: #fef3c7; display: flex; align-items: center; justify-content: center;
			font-weight: 700; flex-shrink: 0;
		}
		.cb-alert-body { display: flex; flex-direction: column; gap: 4px; font-size: 13px; line-height: 1.45; }
		.cb-alert-body strong { color: #78350f; }
		.cb-toolbar {
			display: flex;
			flex-wrap: wrap;
			align-items: center;
			gap: 12px;
			margin-bottom: 16px;
			padding: 12px 16px;
			background: var(--cb-card);
			border: 1px solid var(--cb-border);
			border-radius: 14px;
			box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
		}
		.cb-toolbar-label {
			font-size: 11px;
			font-weight: 700;
			text-transform: uppercase;
			letter-spacing: .06em;
			color: var(--cb-muted);
		}
		.cb-toolbar-actions { margin-left: auto; }
		.cb-period { font-size: 12px; color: var(--cb-muted); font-weight: 500; }
		.cb-kpi-grid {
			display: grid;
			grid-template-columns: repeat(4, 1fr);
			gap: 14px;
			margin-bottom: 16px;
		}
		@media (max-width: 1100px) { .cb-kpi-grid { grid-template-columns: repeat(2, 1fr); } }
		@media (max-width: 640px) {
			.cb-kpi-grid { grid-template-columns: 1fr; }
			.cb-hero { grid-template-columns: 1fr; }
			.cb-hero-side { display: none; }
		}
		.cb-kpi {
			background: var(--cb-card);
			border: 1px solid var(--cb-border);
			border-radius: 16px;
			padding: 18px;
			box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
			transition: transform .2s, box-shadow .2s;
		}
		.cb-kpi:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08); }
		.cb-kpi-primary { border-color: #c7d2fe; background: linear-gradient(180deg, #fff 0%, #f5f7ff 100%); }
		.cb-kpi-danger-soft { border-color: #fecaca; background: linear-gradient(180deg, #fff 0%, #fff5f5 100%); }
		.cb-kpi-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
		.cb-kpi-label { font-size: 11px; color: var(--cb-muted); text-transform: uppercase; letter-spacing: .05em; font-weight: 700; }
		.cb-kpi-badge {
			font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 999px;
			background: #f1f5f9; color: var(--cb-muted);
		}
		.cb-kpi-badge-success { background: #d1fae5; color: var(--cb-success); }
		.cb-kpi-badge-danger { background: #fee2e2; color: var(--cb-danger); }
		.cb-kpi-value { font-size: 24px; font-weight: 800; font-variant-numeric: tabular-nums; line-height: 1.1; }
		.cb-kpi-num { font-size: 30px; }
		.cb-kpi-sub { font-size: 12px; color: var(--cb-muted); margin-top: 8px; }
		.cb-kpi-bar { height: 5px; background: #e2e8f0; border-radius: 999px; margin-top: 12px; overflow: hidden; }
		.cb-kpi-bar-fill { display: block; height: 100%; border-radius: 999px; transition: width .6s ease; }
		.cb-kpi-bar-success { background: linear-gradient(90deg, #34d399, #059669); }
		.cb-kpi-split { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 4px; }
		.cb-kpi-split strong { display: block; font-size: 22px; margin-top: 4px; }
		.cb-kpi-mini { font-size: 10px; color: var(--cb-muted); text-transform: uppercase; font-weight: 700; }
		.cb-text-danger { color: var(--cb-danger) !important; }
		.cb-charts-grid { display: grid; grid-template-columns: 1.35fr 1fr; gap: 16px; margin-bottom: 16px; }
		.cb-charts-grid--trend { grid-template-columns: 1.5fr 1fr; }
		.cb-charts-grid--3 { grid-template-columns: repeat(3, 1fr); }
		@media (max-width: 1200px) { .cb-charts-grid--3 { grid-template-columns: 1fr 1fr; } }
		@media (max-width: 992px) {
			.cb-charts-grid, .cb-charts-grid--3, .cb-charts-grid--trend { grid-template-columns: 1fr; }
		}
		.cb-insights {
			display: grid;
			grid-template-columns: repeat(4, 1fr);
			gap: 12px;
			margin-bottom: 16px;
		}
		@media (max-width: 900px) { .cb-insights { grid-template-columns: repeat(2, 1fr); } }
		.cb-insight {
			background: var(--cb-card);
			border: 1px solid var(--cb-border);
			border-radius: 14px;
			padding: 14px 16px;
			display: flex;
			flex-direction: column;
			gap: 4px;
		}
		.cb-insight-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--cb-muted); }
		.cb-insight strong { font-size: 15px; font-weight: 800; color: var(--cb-text); }
		.cb-insight small { font-size: 11px; color: var(--cb-muted); }
		.cb-chart-canvas-wrap { position: relative; height: 280px; padding: 4px 8px 8px; }
		.cb-chart-canvas-wrap--lg { height: 320px; }
		.cb-chart-canvas-wrap--md { height: 300px; }
		.cb-chart-canvas-wrap canvas { display: block; width: 100% !important; height: 100% !important; }
		.cb-chart-empty {
			position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
			padding: 24px; text-align: center; font-size: 13px; color: var(--cb-muted); background: #fafbfc;
			border-radius: 12px;
		}
		.cb-card {
			background: var(--cb-card);
			border: 1px solid var(--cb-border);
			border-radius: 16px;
			padding: 18px;
			margin-bottom: 16px;
			box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
		}
		.cb-card-chart { margin-bottom: 0; }
		.cb-card-table { padding: 0; overflow: hidden; }
		.cb-card-head, .cb-table-head {
			display: flex;
			flex-wrap: wrap;
			align-items: flex-start;
			justify-content: space-between;
			gap: 12px;
			margin-bottom: 12px;
		}
		.cb-table-head {
			padding: 18px 18px 0;
			margin-bottom: 0;
			border-bottom: 1px solid var(--cb-border);
			padding-bottom: 14px;
		}
		.cb-card-head h4, .cb-table-head h4 { margin: 0 0 2px; font-size: 15px; font-weight: 800; }
		.cb-card-hint { font-size: 12px; color: var(--cb-muted); }
		.cb-tabs { display: flex; flex-wrap: wrap; gap: 8px; flex: 1; }
		.cb-tab {
			border: 1px solid var(--cb-border);
			background: #f8fafc;
			color: var(--cb-muted);
			border-radius: 10px;
			padding: 7px 14px;
			font-size: 12px;
			font-weight: 600;
			cursor: pointer;
			transition: all .15s;
		}
		.cb-tab:hover { border-color: #c7d2fe; color: var(--cb-primary); background: #fff; }
		.cb-tab.active {
			background: var(--cb-primary);
			border-color: var(--cb-primary);
			color: #fff;
			box-shadow: 0 4px 12px rgba(79, 70, 229, 0.28);
		}
		.cb-card-payment { position: relative; }
		.cb-payment-center {
			position: absolute;
			left: 50%;
			top: 40%;
			transform: translate(-50%, -50%);
			text-align: center;
			pointer-events: none;
			z-index: 2;
		}
		.cb-payment-total { font-size: 18px; font-weight: 800; color: var(--cb-text); }
		.cb-payment-sub { font-size: 11px; color: var(--cb-muted); text-transform: uppercase; font-weight: 600; }
		.cb-table-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
		.cb-search, .cb-select {
			background: #fff;
			border: 1px solid var(--cb-border);
			color: var(--cb-text);
			border-radius: 10px;
			padding: 9px 12px;
			font-size: 13px;
		}
		.cb-search { flex: 1; min-width: 200px; }
		.cb-search:focus, .cb-select:focus { outline: none; border-color: var(--cb-primary); box-shadow: 0 0 0 3px rgba(79,70,229,.12); }
		.cb-row-count { font-size: 12px; color: var(--cb-muted); font-weight: 600; }
		.cb-table { margin: 0; font-size: 13px; background: #fff; }
		.cb-table thead th {
			background: #f8fafc;
			border-color: var(--cb-border) !important;
			color: var(--cb-muted);
			font-size: 10px;
			text-transform: uppercase;
			letter-spacing: .06em;
			font-weight: 800;
			padding: 12px 14px;
			white-space: nowrap;
		}
		.cb-table td { border-color: var(--cb-border) !important; vertical-align: middle !important; padding: 12px 14px; }
		.cb-row-main { cursor: pointer; transition: background .15s; }
		.cb-row-main:hover { background: #fafbff; }
		.cb-row-main.expanded { background: #eef2ff; }
		.cb-col-expand { width: 40px; padding: 8px !important; }
		.cb-expand-btn {
			border: none; background: #f1f5f9; width: 28px; height: 28px; border-radius: 8px;
			cursor: pointer; font-size: 10px; color: var(--cb-muted);
		}
		.cb-expand-btn:hover { background: #e0e7ff; color: var(--cb-primary); }
		.cb-contractor-cell { display: flex; align-items: center; gap: 10px; }
		.cb-avatar {
			width: 36px; height: 36px; border-radius: 10px;
			background: linear-gradient(135deg, #4f46e5, #7c3aed);
			color: #fff; font-size: 12px; font-weight: 800;
			display: flex; align-items: center; justify-content: center; flex-shrink: 0;
		}
		.cb-contractor-name { font-weight: 700; color: var(--cb-text); }
		.cb-contractor-sub { font-size: 11px; color: var(--cb-muted); margin-top: 2px; }
		.cb-sub-tag {
			display: inline-block; margin-top: 4px; font-size: 10px; font-weight: 700;
			color: var(--cb-warning); background: #fffbeb; padding: 2px 8px; border-radius: 999px;
		}
		.cb-process-pill {
			display: inline-block; padding: 4px 10px; border-radius: 999px;
			font-size: 11px; font-weight: 700; background: #eef2ff; color: #4338ca;
		}
		.cb-process-Sub-Assembly { background: #fffbeb; color: #b45309; }
		.cb-process-Stitching { background: #ecfdf5; color: #047857; }
		.cb-process-Cutting { background: #eef2ff; color: #4338ca; }
		.cb-process-Quality { background: #faf5ff; color: #7e22ce; }
		.cb-process-Packing { background: #ecfeff; color: #0e7490; }
		.cb-status { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; }
		.cb-status-paid { background: #d1fae5; color: var(--cb-success); }
		.cb-status-partial { background: #fef3c7; color: var(--cb-warning); }
		.cb-status-due { background: #fee2e2; color: var(--cb-danger); }
		.cb-money { font-variant-numeric: tabular-nums; font-weight: 600; }
		.cb-paid { color: var(--cb-success); }
		.cb-due { color: var(--cb-danger); font-weight: 800; }
		.cb-qty { font-variant-numeric: tabular-nums; color: var(--cb-muted); font-weight: 600; }
		.cb-progress-wrap { display: flex; align-items: center; gap: 8px; min-width: 120px; }
		.cb-progress-bar { flex: 1; height: 8px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
		.cb-progress-fill { height: 100%; background: linear-gradient(90deg, #34d399, #4f46e5); border-radius: 999px; transition: width .5s ease; }
		.cb-progress-pct { font-size: 11px; color: var(--cb-muted); min-width: 34px; text-align: right; font-weight: 600; }
		.cb-empty { color: var(--cb-muted); padding: 32px 24px; text-align: center; font-size: 13px; line-height: 1.5; }
		.cb-empty-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,.92); }
		.cb-order { max-width: 220px; }
		.cb-link { color: var(--cb-primary); font-weight: 600; text-decoration: none; }
		.cb-link:hover { text-decoration: underline; }
		.cb-report-refs { font-size: 10px; color: var(--cb-muted); margin-top: 4px; }
		.cb-row-detail td { padding: 0 !important; background: #f8fafc; border-top: none !important; }
		.cb-detail-panel { padding: 14px 18px 18px 52px; }
		.cb-detail-title { font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .06em; color: var(--cb-muted); margin-bottom: 10px; }
		.cb-detail-table { margin: 0; background: #fff; border-radius: 12px; overflow: hidden; border: 1px solid var(--cb-border); }
		.cb-detail-table th { font-size: 10px; background: #f1f5f9; }
		.cb-report-link { color: var(--cb-primary); font-weight: 600; }
		.layout-main-section .page-content { background: #eef2f7; }
	`;
	const style = document.createElement("style");
	style.id = styleId;
	style.textContent = css;
	document.head.appendChild(style);
}
