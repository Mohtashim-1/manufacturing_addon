frappe.provide("manufacturing_addon.sales_dashboard");

frappe.pages["sales-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Sales Dashboard"),
		single_column: true,
	});

	const dashboard = new SalesDashboard(page, wrapper);
	dashboard.init();
};

class SalesDashboard {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = wrapper;
		this.charts = {};
		this.data = null;
		this.fields = {};
		this.filter_defs = [];
	}

	init() {
		this.inject_style();
		this.build_filters();
		this.build_layout();
		this.bind_events();
		this.load();
	}

	inject_style() {
		if (document.getElementById("sales-dashboard-style")) return;
		const style = document.createElement("style");
		style.id = "sales-dashboard-style";
		style.textContent = `
			.sales-dashboard-shell {
				padding: 18px;
				background:
					radial-gradient(circle at top right, rgba(249, 115, 22, 0.10), transparent 26%),
					linear-gradient(180deg, #fffaf5 0%, #f5f7fb 100%);
				min-height: calc(100vh - 120px);
			}
			.sales-dashboard-filter-wrap {
				position: sticky;
				top: 8px;
				z-index: 8;
				margin-bottom: 18px;
			}
			.sales-dashboard-filtertitle {
				font-size: 12px;
				font-weight: 800;
				letter-spacing: 0.08em;
				text-transform: uppercase;
				color: #9a3412;
				margin-bottom: 8px;
			}
			.sales-dashboard-meta {
				display: flex;
				justify-content: space-between;
				align-items: center;
				margin-bottom: 16px;
				color: #5f6b7a;
				font-size: 12px;
			}
			.sales-dashboard-filterbar {
				display: grid;
				grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
				gap: 12px;
				padding: 14px;
				background: rgba(255, 247, 237, 0.96);
				border: 1px solid #fed7aa;
				border-radius: 16px;
				box-shadow: 0 14px 34px rgba(234, 88, 12, 0.10);
				backdrop-filter: blur(10px);
			}
			.sales-dashboard-filtercell {
				padding: 10px 10px 4px;
				background: #ffffff;
				border: 1px solid #ffedd5;
				border-radius: 14px;
			}
			.sales-dashboard-filtercell label {
				display: block;
				font-size: 11px;
				font-weight: 700;
				color: #9a3412;
				text-transform: uppercase;
				letter-spacing: 0.05em;
				margin-bottom: 6px;
			}
			.sales-dashboard-filtercell .control-input-wrapper,
			.sales-dashboard-filtercell input,
			.sales-dashboard-filtercell .form-control,
			.sales-dashboard-filtercell .link-field .awesomplete {
				width: 100%;
			}
			.sales-dashboard-filtercell .form-group {
				margin-bottom: 0;
			}
			.sales-dashboard-filtercell .control-label {
				display: none !important;
			}
			.sales-dashboard-kpis {
				display: grid;
				grid-template-columns: repeat(auto-fit, minmax(205px, 1fr));
				gap: 14px;
				margin-bottom: 18px;
			}
			.sales-dashboard-kpi {
				background: #fff;
				border: 1px solid #fed7aa;
				border-radius: 16px;
				padding: 16px 18px;
				box-shadow: 0 12px 28px rgba(234, 88, 12, 0.08);
				position: relative;
				overflow: hidden;
			}
			.sales-dashboard-kpi:before {
				content: "";
				position: absolute;
				inset: 0 auto auto 0;
				width: 100%;
				height: 4px;
				background: linear-gradient(90deg, #fb923c, #f97316);
			}
			.sales-dashboard-kpi-label {
				font-size: 12px;
				font-weight: 600;
				color: #637083;
				text-transform: uppercase;
				letter-spacing: 0.04em;
				margin-bottom: 10px;
			}
			.sales-dashboard-kpi-value {
				font-size: 26px;
				font-weight: 700;
				color: #122033;
				line-height: 1.1;
			}
			.sales-dashboard-kpi-meta {
				margin-top: 10px;
				font-size: 12px;
				color: #7a8796;
			}
			.sales-dashboard-section {
				display: grid;
				grid-template-columns: repeat(12, 1fr);
				gap: 16px;
				margin-bottom: 16px;
			}
			.sales-dashboard-panel {
				grid-column: span 6;
				background: #fff;
				border: 1px solid #e7edf5;
				border-radius: 18px;
				box-shadow: 0 12px 28px rgba(18, 32, 51, 0.05);
				overflow: hidden;
			}
			.sales-dashboard-panel.wide { grid-column: span 12; }
			.sales-dashboard-panel.third { grid-column: span 4; }
			.sales-dashboard-panel.two-third { grid-column: span 8; }
			.sales-dashboard-panel.quarter { grid-column: span 3; }
			.sales-dashboard-panel-header {
				display: flex;
				justify-content: space-between;
				align-items: center;
				padding: 16px 18px 8px;
			}
			.sales-dashboard-panel-title {
				font-size: 16px;
				font-weight: 700;
				color: #122033;
			}
			.sales-dashboard-panel-subtitle {
				font-size: 12px;
				color: #7a8796;
			}
			.sales-dashboard-chart {
				min-height: 320px;
				padding: 4px 10px 14px;
			}
			.sales-dashboard-empty {
				display: flex;
				align-items: center;
				justify-content: center;
				min-height: 320px;
				color: #8793a2;
				font-size: 14px;
			}
			.sales-dashboard-loading {
				display: flex;
				align-items: center;
				justify-content: center;
				min-height: 220px;
				color: #637083;
				font-size: 14px;
			}
			@media (max-width: 1200px) {
				.sales-dashboard-panel,
				.sales-dashboard-panel.third,
				.sales-dashboard-panel.two-third,
				.sales-dashboard-panel.wide,
				.sales-dashboard-panel.quarter {
					grid-column: span 12;
				}
				.sales-dashboard-filter-wrap {
					position: static;
				}
			}
		`;
		document.head.appendChild(style);
	}

	build_filters() {
		const today = frappe.datetime.get_today();
		const monthStart = frappe.datetime.month_start(today);
		this.filter_defs = [
			{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: monthStart },
			{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: today },
			{
				fieldname: "company",
				label: __("Company"),
				fieldtype: "Link",
				options: "Company",
				default: frappe.defaults.get_default("company"),
			},
			{ fieldname: "sales_person", label: __("Sales Person"), fieldtype: "Link", options: "Sales Person" },
			{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
			{ fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
			{ fieldname: "territory", label: __("Territory"), fieldtype: "Link", options: "Territory" },
			{ fieldname: "customer_group", label: __("Customer Group"), fieldtype: "Link", options: "Customer Group" },
			{
				fieldname: "payment_status",
				label: __("Payment Status"),
				fieldtype: "Select",
				options: "\nPaid\nUnpaid\nOverdue\nPartially Paid",
			},
		];

		this.page.set_primary_action(__("Refresh"), () => this.load());
	}

	build_layout() {
		this.$body = $(`
			<div class="sales-dashboard-shell">
				<div class="sales-dashboard-meta">
					<div data-role="summary">${__("Loading sales analytics...")}</div>
					<div data-role="timestamp"></div>
				</div>
				<div class="sales-dashboard-filter-wrap">
					<div class="sales-dashboard-filtertitle">${__("Filters")}</div>
					<div class="sales-dashboard-filterbar" data-role="filterbar"></div>
				</div>
				<div class="sales-dashboard-kpis" data-role="kpis"></div>

				<div class="sales-dashboard-section">
					<div class="sales-dashboard-panel two-third">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Sales Trend")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Daily or monthly sales movement")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="sales_trend"></div>
					</div>
					<div class="sales-dashboard-panel third">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Payment Status")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Paid, unpaid, overdue, partially paid")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="payment_status"></div>
					</div>
				</div>

				<div class="sales-dashboard-section">
					<div class="sales-dashboard-panel wide">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Monthly Target vs Achievement")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Actual sales against monthly target allocation")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="target_vs_actual"></div>
					</div>
				</div>

				<div class="sales-dashboard-section">
					<div class="sales-dashboard-panel">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Currency-wise Sales")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Document totals grouped by invoice/order currency")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="currency_wise_sales"></div>
					</div>
					<div class="sales-dashboard-panel">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Financial Snapshot")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Sales, profit, receivables, returns, target and pipeline")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="financial_snapshot"></div>
					</div>
				</div>

				<div class="sales-dashboard-section">
					<div class="sales-dashboard-panel">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Top Customers")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Top 10 customers by revenue")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="top_customers"></div>
					</div>
					<div class="sales-dashboard-panel">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Top Items")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Best selling items by amount")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="top_items"></div>
					</div>
				</div>

				<div class="sales-dashboard-section">
					<div class="sales-dashboard-panel">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Sales by Sales Person")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Revenue allocation by sales person")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="sales_people"></div>
					</div>
					<div class="sales-dashboard-panel">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Sales Order Status")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Current order pipeline mix")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="sales_order_status"></div>
					</div>
				</div>

				<div class="sales-dashboard-section">
					<div class="sales-dashboard-panel wide">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Territory-wise Sales")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Revenue by territory / region")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="territory_sales"></div>
					</div>
				</div>

				<div class="sales-dashboard-section">
					<div class="sales-dashboard-panel wide">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Customer Group Sales")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Revenue by customer group")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="customer_group_sales"></div>
					</div>
				</div>

				<div class="sales-dashboard-section">
					<div class="sales-dashboard-panel">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Commission Agent-wise")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Commission overhead amount grouped by agent/supplier")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="commission_agents"></div>
					</div>
					<div class="sales-dashboard-panel">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Commission Agent Share")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Commission distribution across agents")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="commission_agents_pie"></div>
					</div>
				</div>

				<div class="sales-dashboard-section">
					<div class="sales-dashboard-panel third">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Customer Share")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Top customer revenue distribution")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="top_customers_pie"></div>
					</div>
					<div class="sales-dashboard-panel third">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Item Share")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Top item revenue distribution")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="top_items_pie"></div>
					</div>
					<div class="sales-dashboard-panel third">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Sales Person Share")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Revenue share by sales person")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="sales_people_pie"></div>
					</div>
				</div>

				<div class="sales-dashboard-section">
					<div class="sales-dashboard-panel">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Customer Group Share")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Revenue share by customer group")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="customer_group_sales_pie"></div>
					</div>
					<div class="sales-dashboard-panel">
						<div class="sales-dashboard-panel-header">
							<div>
								<div class="sales-dashboard-panel-title">${__("Territory Share")}</div>
								<div class="sales-dashboard-panel-subtitle">${__("Revenue share by territory")}</div>
							</div>
						</div>
						<div class="sales-dashboard-chart" data-chart="territory_sales_pie"></div>
					</div>
				</div>
			</div>
		`);

		$(this.page.body).empty().append(this.$body);
		this.$summary = this.$body.find('[data-role="summary"]');
		this.$timestamp = this.$body.find('[data-role="timestamp"]');
		this.$filterbar = this.$body.find('[data-role="filterbar"]');
		this.$kpis = this.$body.find('[data-role="kpis"]');
		this.render_filterbar();
	}

	render_filterbar() {
		this.$filterbar.html(
			this.filter_defs
				.map(
					(df) => `
						<div class="sales-dashboard-filtercell">
							<label>${df.label}</label>
							<div data-filter="${df.fieldname}"></div>
						</div>
					`
				)
				.join("")
		);

		this.filter_defs.forEach((df) => {
			const parent = this.$filterbar.find(`[data-filter="${df.fieldname}"]`);
			const field = frappe.ui.form.make_control({
				parent,
				df: {
					...df,
					label: "",
				},
				render_input: true,
			});
			field.refresh();
			if (df.default !== undefined && !field.get_value()) {
				field.set_value(df.default);
			}
			this.fields[df.fieldname] = field;
		});
	}

	bind_events() {
		Object.values(this.fields).forEach((field) => {
			if (!field) return;
			field.df.change = () => this.load();
			if (field.$input) {
				field.$input.on("change", () => this.load());
			}
		});
	}

	get_filters() {
		return {
			from_date: this.fields.from_date.get_value(),
			to_date: this.fields.to_date.get_value(),
			company: this.fields.company.get_value(),
			sales_person: this.fields.sales_person.get_value(),
			customer: this.fields.customer.get_value(),
			item_group: this.fields.item_group.get_value(),
			territory: this.fields.territory.get_value(),
			customer_group: this.fields.customer_group.get_value(),
			payment_status: this.fields.payment_status.get_value(),
		};
	}

	async load() {
		this.show_loading();
		await this.load_apexcharts();

		frappe.call({
			method: "manufacturing_addon.manufacturing_addon.page.sales_dashboard.sales_dashboard.get_dashboard_data",
			args: {
				filters: this.get_filters(),
			},
			callback: (r) => {
				this.data = r.message || null;
				this.render();
			},
			error: () => {
				this.show_error();
			},
		});
	}

	show_loading() {
		this.$kpis.html("");
		this.$summary.text(__("Loading sales analytics..."));
		this.$timestamp.text("");
		this.destroy_charts();
		this.$body.find("[data-chart]").html(`<div class="sales-dashboard-loading">${__("Loading charts...")}</div>`);
	}

	show_error() {
		this.destroy_charts();
		this.$summary.text(__("Sales dashboard could not be loaded."));
		this.$body.find("[data-chart]").html(`<div class="sales-dashboard-empty">${__("No data available for the selected filters.")}</div>`);
	}

	render() {
		if (!this.data) {
			this.show_error();
			return;
		}

		this.render_kpis();
		this.render_meta();
		this.render_charts();
	}

	render_meta() {
		const filters = this.data.filters || {};
		this.$summary.text(
			__("Showing {0}-based sales analytics from {1} to {2}", [
				this.data.data_source || __("Sales Invoice"),
				frappe.datetime.str_to_user(filters.from_date),
				frappe.datetime.str_to_user(filters.to_date),
			])
		);
		this.$timestamp.text(__("Updated {0}", [frappe.datetime.now_datetime()]));
	}

	render_kpis() {
		const k = this.data.kpis || {};
		const currency = this.data.currency;
		const cards = [
			["Total Sales", this.format_currency(k.total_sales, currency), `${this.data.data_source || __("Sales Invoice")} ${__("basis")}`],
			["Net Sales", this.format_currency(k.net_sales, currency), __("After returns and adjustments")],
			["Gross Profit", this.format_currency(k.gross_profit, currency), `${this.format_percent(k.gross_profit_pct)} ${__("margin")}`],
			["Outstanding", this.format_currency(k.outstanding_amount, currency), `${this.format_currency(k.overdue_amount, currency)} ${__("overdue")}`],
			["Total Orders", this.format_number(k.total_orders), `${this.format_currency(k.average_order_value, currency)} ${__("avg order value")}`],
			["Customers", this.format_number(k.total_customers), `${this.format_number(k.new_customers)} ${__("new in period")}`],
			["Sales Returns", this.format_currency(k.sales_return_amount, currency), __("Returned sales value")],
			["Quotation Value", this.format_currency(k.quotation_value, currency), `${this.format_percent(k.conversion_rate)} ${__("conversion")}`],
			["Pending Quotations", this.format_currency(k.pending_quotation_amount, currency), `${this.format_currency(k.sales_pipeline_value, currency)} ${__("pipeline")}`],
			["Sales Target", this.format_currency(k.sales_target, currency), `${this.format_percent(k.target_achievement_pct)} ${__("achievement")}`],
		];

		this.$kpis.html(
			cards
				.map(
					([label, value, meta]) => `
						<div class="sales-dashboard-kpi">
							<div class="sales-dashboard-kpi-label">${__(label)}</div>
							<div class="sales-dashboard-kpi-value">${value}</div>
							<div class="sales-dashboard-kpi-meta">${meta}</div>
						</div>
					`
				)
				.join("")
		);
	}

	render_charts() {
		this.destroy_charts();
		const charts = this.data.charts || {};

		this.render_series_chart("sales_trend", {
			chart: { type: "line", height: 340, toolbar: { show: false } },
			series: [{ name: __("Sales"), data: charts.sales_trend?.values || [] }],
			xaxis: { categories: charts.sales_trend?.labels || [] },
			stroke: { curve: "smooth", width: 3 },
			colors: ["#f97316"],
			yaxis: { labels: { formatter: (v) => this.short_currency(v) } },
			tooltip: { y: { formatter: (v) => this.format_currency(v, this.data.currency) } },
		});

		this.render_series_chart("target_vs_actual", {
			chart: { type: "bar", height: 340, toolbar: { show: false } },
			series: [
				{ name: __("Target"), data: charts.target_vs_actual?.target || [] },
				{ name: __("Actual"), data: charts.target_vs_actual?.actual || [] },
			],
			xaxis: { categories: charts.target_vs_actual?.labels || [] },
			colors: ["#fb923c", "#f97316"],
			plotOptions: { bar: { columnWidth: "42%", borderRadius: 6 } },
			yaxis: { labels: { formatter: (v) => this.short_currency(v) } },
			tooltip: { y: { formatter: (v) => this.format_currency(v, this.data.currency) } },
		});

		this.render_horizontal_bar("top_customers", charts.top_customers, "#f97316");
		this.render_horizontal_bar("top_items", charts.top_items, "#fb923c", charts.top_items?.quantities);
		this.render_horizontal_bar("sales_people", charts.sales_people, "#ea580c");
		this.render_horizontal_bar("customer_group_sales", charts.customer_group_sales, "#c2410c");
		this.render_horizontal_bar("commission_agents", charts.commission_agents, "#9a3412");
		this.render_distribution_donut("top_customers_pie", charts.top_customers);
		this.render_distribution_donut("top_items_pie", charts.top_items);
		this.render_distribution_donut("sales_people_pie", charts.sales_people);
		this.render_distribution_donut("customer_group_sales_pie", charts.customer_group_sales);
		this.render_distribution_donut("territory_sales_pie", charts.territory_sales);
		this.render_distribution_donut("commission_agents_pie", charts.commission_agents);

		this.render_series_chart("payment_status", {
			chart: { type: "donut", height: 340, toolbar: { show: false } },
			series: charts.payment_status?.values || [],
			labels: charts.payment_status?.labels || [],
			colors: ["#fdba74", "#fb923c", "#f97316", "#ea580c"],
			legend: { position: "bottom" },
		});

		this.render_series_chart("currency_wise_sales", {
			chart: { type: "donut", height: 320, toolbar: { show: false } },
			series: charts.currency_wise_sales?.values || [],
			labels: charts.currency_wise_sales?.labels || [],
			colors: ["#fed7aa", "#fdba74", "#fb923c", "#f97316", "#ea580c", "#9a3412"],
			legend: { position: "bottom" },
			tooltip: {
				y: {
					formatter: (v, ctx) => {
						const curr = charts.currency_wise_sales?.labels?.[ctx.seriesIndex] || "";
						return `${this.format_plain_number(v)} ${curr}`.trim();
					},
				},
			},
		});

		this.render_series_chart("sales_order_status", {
			chart: { type: "donut", height: 340, toolbar: { show: false } },
			series: charts.sales_order_status?.values || [],
			labels: charts.sales_order_status?.labels || [],
			colors: ["#fed7aa", "#fdba74", "#fb923c", "#f97316", "#ea580c", "#9a3412"],
			legend: { position: "bottom" },
		});

		this.render_series_chart("territory_sales", {
			chart: { type: "bar", height: 340, toolbar: { show: false } },
			series: [{ name: __("Sales"), data: charts.territory_sales?.values || [] }],
			xaxis: { categories: charts.territory_sales?.labels || [], labels: { rotate: -30 } },
			colors: ["#f97316"],
			plotOptions: { bar: { borderRadius: 6, columnWidth: "46%" } },
			yaxis: { labels: { formatter: (v) => this.short_currency(v) } },
			tooltip: { y: { formatter: (v) => this.format_currency(v, this.data.currency) } },
		});

		this.render_series_chart("financial_snapshot", {
			chart: { type: "bar", height: 320, toolbar: { show: false } },
			series: [{ name: __("Amount"), data: charts.financial_snapshot?.values || [] }],
			xaxis: { categories: charts.financial_snapshot?.labels || [], labels: { rotate: -25 } },
			colors: ["#f97316"],
			plotOptions: { bar: { borderRadius: 6, columnWidth: "52%", distributed: true } },
			yaxis: { labels: { formatter: (v) => this.short_currency(v) } },
			tooltip: { y: { formatter: (v) => this.format_currency(v, this.data.currency) } },
		});
	}

	render_horizontal_bar(name, payload, color, quantities) {
		const labels = payload?.labels || [];
		const displayLabels = labels.map((label) => this.truncate_label(label, 44));
		this.render_series_chart(name, {
			chart: { type: "bar", height: 340, toolbar: { show: false } },
			series: [{ name: __("Sales"), data: payload?.values || [] }],
			xaxis: { categories: displayLabels },
			colors: [color],
			plotOptions: { bar: { horizontal: true, borderRadius: 6, barHeight: "58%" } },
			dataLabels: { enabled: false },
			tooltip: {
				x: {
					formatter: (_, ctx) => labels?.[ctx.dataPointIndex] || "",
				},
				y: {
					formatter: (v, ctx) => {
						const qty = quantities?.[ctx.dataPointIndex];
						const base = this.format_currency(v, this.data.currency);
						return qty !== undefined ? `${base} | ${__("Qty")}: ${this.format_number(qty)}` : base;
					},
				},
			},
		});
	}

	render_distribution_donut(name, payload) {
		const labels = payload?.labels || [];
		this.render_series_chart(name, {
			chart: { type: "donut", height: 320, toolbar: { show: false } },
			series: payload?.values || [],
			labels: labels.map((label) => this.truncate_label(label, 24)),
			colors: ["#fed7aa", "#fdba74", "#fb923c", "#f97316", "#ea580c", "#c2410c", "#9a3412", "#7c2d12", "#ffedd5", "#fb7185"],
			legend: { position: "bottom" },
			tooltip: {
				x: {
					formatter: (_, ctx) => labels?.[ctx.seriesIndex] || "",
				},
				y: {
					formatter: (v) => this.format_currency(v, this.data.currency),
				},
			},
		});
	}

	render_series_chart(name, options) {
		const target = this.$body.find(`[data-chart="${name}"]`)[0];
		if (!target) return;
		if (!window.ApexCharts) {
			target.innerHTML = `<div class="sales-dashboard-empty">${__("ApexCharts failed to load.")}</div>`;
			return;
		}
		if (!options.series || !options.series.length || !((options.series[0] && options.series[0].data?.length) || options.labels?.length || options.series.length > 1)) {
			target.innerHTML = `<div class="sales-dashboard-empty">${__("No data for this chart.")}</div>`;
			return;
		}

		const baseOptions = {
			chart: { fontFamily: "Inter, sans-serif" },
			grid: { borderColor: "rgba(148, 163, 184, 0.18)" },
			dataLabels: { enabled: false },
			stroke: { width: 2 },
			legend: { position: "top" },
			noData: { text: __("No data") },
		};

		const chart = new ApexCharts(target, Object.assign({}, baseOptions, options));
		this.charts[name] = chart;
		chart.render();
	}

	destroy_charts() {
		Object.values(this.charts).forEach((chart) => {
			try {
				chart.destroy();
			} catch (e) {
				// no-op
			}
		});
		this.charts = {};
	}

	load_apexcharts() {
		if (window.ApexCharts) return Promise.resolve();
		if (window.__salesDashboardApexPromise) return window.__salesDashboardApexPromise;

		const urls = [
			"/assets/management_dashboard/js/apexcharts.min.js",
			"https://cdn.jsdelivr.net/npm/apexcharts",
		];

		window.__salesDashboardApexPromise = new Promise((resolve, reject) => {
			const tryLoad = (idx) => {
				if (window.ApexCharts) return resolve();
				if (idx >= urls.length) return reject(new Error("ApexCharts failed to load"));

				frappe.require(urls[idx])
					.then(() => {
						if (window.ApexCharts) resolve();
						else tryLoad(idx + 1);
					})
					.catch(() => tryLoad(idx + 1));
			};
			tryLoad(0);
		});

		return window.__salesDashboardApexPromise;
	}

	format_currency(value, currency) {
		return format_currency(value || 0, currency);
	}

	short_currency(value) {
		if (Math.abs(value) >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
		if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1)}K`;
		return `${Math.round(value || 0)}`;
	}

	format_number(value) {
		return frappe.format(value || 0, { fieldtype: "Float", precision: 0 });
	}

	format_plain_number(value) {
		return frappe.format(value || 0, { fieldtype: "Currency", precision: 2 }).replace(/[^\d,.\-]/g, "").trim();
	}

	format_percent(value) {
		return `${Number(value || 0).toFixed(2)}%`;
	}

	truncate_label(value, max = 24) {
		const text = String(value || "");
		return text.length > max ? `${text.slice(0, max - 1)}…` : text;
	}
}
