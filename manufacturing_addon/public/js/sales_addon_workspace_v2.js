(function () {
	const TARGET_ROUTE = "sales-addon";
	const TARGET_WORKSPACE_TITLE = "Sales Addon";
	const BLOCK_ID = "sales-addon-dashboard-block";
	const STYLE_ID = "sales-addon-dashboard-style";
	const FONT_ID = "sales-addon-dashboard-fonts";
	const state = {
		filters: get_default_filters(),
		statusFilter: "All",
		activeTab: "overview",
		selectedOrder: null,
		data: null,
		charts: {},
	};
	let apexPromise = null;

	const STATUS_CONFIG = {
		Draft: { color: "#64748b", bg: "#f1f5f9", border: "#cbd5e1" },
		"To Deliver and Bill": { color: "#b45309", bg: "#fef3c7", border: "#fbbf24" },
		"To Deliver": { color: "#1d4ed8", bg: "#dbeafe", border: "#60a5fa" },
		"To Bill": { color: "#7c3aed", bg: "#ede9fe", border: "#a78bfa" },
		Completed: { color: "#047857", bg: "#d1fae5", border: "#34d399" },
		Closed: { color: "#475569", bg: "#e2e8f0", border: "#94a3b8" },
		Overdue: { color: "#dc2626", bg: "#fee2e2", border: "#f87171" },
		Cancelled: { color: "#9ca3af", bg: "#f3f4f6", border: "#d1d5db" },
	};

	const BAR_COLORS = ["#2563eb", "#7c3aed", "#0891b2", "#d97706", "#059669", "#dc2626"];
	const STATUS_FILTERS = ["All", "Draft", "To Deliver and Bill", "To Deliver", "To Bill", "Completed", "Closed", "Overdue"];
	const TAB_LIST = ["overview", "orders", "analytics"];

	function boot() {
		if (!frappe.router) return;
		frappe.router.on("change", queue_mount);
		queue_mount();
	}

	function queue_mount() {
		window.setTimeout(mount_if_needed, 200);
		window.setTimeout(mount_if_needed, 800);
		window.setTimeout(mount_if_needed, 1500);
	}

	function mount_if_needed() {
		if (!is_target_route()) {
			teardown();
			return;
		}

		const editorContainer = document.querySelector(".layout-main-section .editor-js-container");
		const fallbackContainer = document.querySelector(".layout-main-section");
		const container = editorContainer || fallbackContainer;
		if (!container) return;

		inject_fonts();
		inject_style();
		hide_empty_workspace_state(editorContainer, fallbackContainer);

		let block = document.getElementById(BLOCK_ID);
		if (!block) {
			block = document.createElement("section");
			block.id = BLOCK_ID;
			block.className = "sad-shell";
			container.prepend(block);
		}

		render_shell(block);
		bind_static_events(block);
		load_data(block);
	}

	function teardown() {
		destroy_charts();
		document.body.classList.remove("sales-addon-workspace-active");
		const block = document.getElementById(BLOCK_ID);
		if (block) block.remove();
	}

	function is_target_route() {
		const currentSubPath = frappe.router && frappe.router.current_sub_path;
		if (currentSubPath) {
			if (currentSubPath === TARGET_ROUTE) return true;
			if (decode_route_part(currentSubPath) === `workspace/${TARGET_WORKSPACE_TITLE}`) return true;
		}

		const route = frappe.get_route ? frappe.get_route() : [];
		if (Array.isArray(route) && route.length >= 2) {
			if (route[0] === "Workspaces" && route[1] === TARGET_WORKSPACE_TITLE) return true;
			if (route[0] === "workspace" && decode_route_part(route[1] || "") === TARGET_WORKSPACE_TITLE)
				return true;
		}

		const path = decode_route_part(window.location.pathname || "");
		if (path.includes("/app/workspace/Sales Addon")) return true;
		return path.replace(/^\/app\//, "").split("?")[0] === TARGET_ROUTE;
	}

	function inject_fonts() {
		if (document.getElementById(FONT_ID)) return;
		const link = document.createElement("link");
		link.id = FONT_ID;
		link.rel = "stylesheet";
		link.href =
			"https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap";
		document.head.appendChild(link);
	}

	function inject_style() {
		if (document.getElementById(STYLE_ID)) return;
		const style = document.createElement("style");
		style.id = STYLE_ID;
		style.textContent = `
			body.sales-addon-workspace-active .layout-main-section .editor-js-container {
				padding-top: 0 !important;
			}
			.sad-shell {
				font-family: "DM Sans", system-ui, sans-serif;
				background: #f8fafc;
				color: #1e293b;
				padding: 28px;
				border-radius: 20px;
				margin-bottom: 24px;
			}
			.sad-header {
				display: flex;
				align-items: center;
				justify-content: space-between;
				gap: 18px;
				margin-bottom: 28px;
				flex-wrap: wrap;
			}
			.sad-brand {
				display: flex;
				align-items: center;
				gap: 14px;
			}
			.sad-logo {
				width: 44px;
				height: 44px;
				border-radius: 12px;
				background: linear-gradient(135deg, #2563eb, #7c3aed);
				display: flex;
				align-items: center;
				justify-content: center;
				font-size: 20px;
				font-weight: 700;
				color: #fff;
				box-shadow: 0 4px 14px rgba(37,99,235,0.3);
				font-family: "Instrument Sans", sans-serif;
			}
			.sad-title {
				margin: 0;
				font-size: 24px;
				font-weight: 700;
				font-family: "Instrument Sans", sans-serif;
				letter-spacing: -0.5px;
				color: #0f172a;
			}
			.sad-subtitle {
				margin: 0;
				font-size: 12px;
				color: #94a3b8;
				font-family: "JetBrains Mono", monospace;
			}
			.sad-status-filters {
				display: flex;
				gap: 6px;
				flex-wrap: wrap;
			}
			.sad-chip {
				padding: 7px 16px;
				border-radius: 20px;
				cursor: pointer;
				font-size: 11px;
				font-weight: 600;
				font-family: "DM Sans", sans-serif;
				transition: all 0.2s;
				border: 1px solid #e2e8f0;
				background: #fff;
				color: #64748b;
			}
			.sad-chip.is-active {
				border: none;
				box-shadow: 0 2px 8px rgba(0,0,0,0.08);
			}
			.sad-filters {
				display: grid;
				grid-template-columns: repeat(4, minmax(150px, 1fr)) auto;
				gap: 12px;
				margin-bottom: 24px;
				padding: 16px;
				background: #fff;
				border-radius: 14px;
				border: 1px solid #e2e8f0;
				box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
			}
			.sad-filter {
				display: flex;
				flex-direction: column;
				gap: 6px;
			}
			.sad-filter label {
				font-size: 11px;
				font-weight: 700;
				color: #64748b;
				text-transform: uppercase;
				letter-spacing: 0.5px;
				font-family: "JetBrains Mono", monospace;
			}
			.sad-filter input,
			.sad-filter select {
				height: 40px;
				padding: 0 12px;
				border-radius: 10px;
				border: 1px solid #e2e8f0;
				background: #fff;
				font-family: "DM Sans", sans-serif;
				font-size: 13px;
				color: #1e293b;
			}
			.sad-filter-action {
				display: flex;
				align-items: end;
			}
			.sad-btn-primary {
				padding: 10px 16px;
				border-radius: 10px;
				border: none;
				background: #2563eb;
				color: #fff;
				font-size: 13px;
				font-weight: 600;
				cursor: pointer;
				box-shadow: 0 2px 8px rgba(37,99,235,0.25);
			}
			.sad-kpis {
				display: grid;
				grid-template-columns: repeat(4, 1fr);
				gap: 16px;
				margin-bottom: 24px;
			}
			.sad-kpi {
				border-radius: 14px;
				padding: 20px 22px;
				border: 1px solid #e2e8f0;
				position: relative;
				overflow: hidden;
				box-shadow: 0 1px 3px rgba(0,0,0,0.04);
			}
			.sad-kpi-orb {
				position: absolute;
				top: -30px;
				right: -30px;
				width: 90px;
				height: 90px;
				border-radius: 50%;
				opacity: 0.07;
			}
			.sad-kpi-label {
				font-size: 11px;
				color: #64748b;
				font-weight: 600;
				text-transform: uppercase;
				letter-spacing: 0.8px;
				margin-bottom: 8px;
			}
			.sad-kpi-value {
				font-size: 30px;
				font-weight: 700;
				font-family: "Instrument Sans", sans-serif;
				letter-spacing: -1px;
			}
			.sad-kpi-sub {
				font-size: 11px;
				color: #94a3b8;
				font-family: "JetBrains Mono", monospace;
				margin-top: 4px;
			}
			.sad-tabs {
				display: flex;
				gap: 2px;
				margin-bottom: 22px;
				background: #fff;
				border-radius: 12px;
				padding: 4px;
				border: 1px solid #e2e8f0;
			}
			.sad-tab {
				flex: 1;
				padding: 10px 16px;
				border-radius: 9px;
				border: none;
				cursor: pointer;
				font-size: 13px;
				font-weight: 600;
				font-family: "DM Sans", sans-serif;
				text-transform: capitalize;
				background: transparent;
				color: #94a3b8;
				transition: all 0.2s;
			}
			.sad-tab.is-active {
				background: #2563eb;
				color: #fff;
				box-shadow: 0 2px 8px rgba(37,99,235,0.25);
			}
			.sad-grid-2-1 {
				display: grid;
				grid-template-columns: 2fr 1fr;
				gap: 16px;
				margin-bottom: 20px;
			}
			.sad-grid-2 {
				display: grid;
				grid-template-columns: repeat(2, minmax(0, 1fr));
				gap: 16px;
				margin-bottom: 16px;
			}
			.sad-grid-1-1,
			.sad-grid-analytics {
				display: grid;
				grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
				gap: 16px;
			}
			.sad-card-full {
				grid-column: 1 / -1;
			}
			.sad-card {
				background: #fff;
				border-radius: 14px;
				padding: 22px;
				border: 1px solid #e2e8f0;
				box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
			}
			.sad-card h3 {
				margin: 0 0 16px;
				font-size: 14px;
				font-weight: 600;
				color: #475569;
			}
			.sad-chart {
				min-height: 220px;
			}
			.sad-legend {
				display: flex;
				flex-wrap: wrap;
				gap: 6px 14px;
				justify-content: center;
			}
			.sad-legend-item {
				display: flex;
				align-items: center;
				gap: 5px;
				font-size: 10px;
				font-family: "JetBrains Mono", monospace;
			}
			.sad-legend-swatch {
				width: 8px;
				height: 8px;
				border-radius: 2px;
			}
			.sad-progress-list {
				display: flex;
				flex-direction: column;
				gap: 14px;
			}
			.sad-progress-head {
				display: flex;
				justify-content: space-between;
				margin-bottom: 6px;
			}
			.sad-progress-label {
				font-size: 12px;
				font-weight: 500;
				color: #334155;
			}
			.sad-progress-meta {
				font-size: 11px;
				font-family: "JetBrains Mono", monospace;
				color: #64748b;
			}
			.sad-progress-track {
				height: 7px;
				background: #f1f5f9;
				border-radius: 4px;
				overflow: hidden;
			}
			.sad-progress-fill {
				height: 100%;
				border-radius: 4px;
				transition: width 0.6s ease;
			}
			.sad-table-card {
				background: #fff;
				border-radius: 14px;
				border: 1px solid #e2e8f0;
				box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
				overflow: hidden;
			}
			.sad-table-wrap {
				overflow-x: auto;
			}
			.sad-table {
				width: 100%;
				border-collapse: collapse;
				font-family: "DM Sans", sans-serif;
			}
			.sad-table thead tr {
				border-bottom: 2px solid #e2e8f0;
				background: #f8fafc;
			}
			.sad-table th {
				padding: 14px 16px;
				text-align: left;
				font-size: 11px;
				font-weight: 700;
				color: #64748b;
				text-transform: uppercase;
				letter-spacing: 0.5px;
				font-family: "JetBrains Mono", monospace;
				white-space: nowrap;
			}
			.sad-table td {
				padding: 12px 16px;
				font-size: 12px;
				border-bottom: 1px solid #f1f5f9;
				vertical-align: middle;
			}
			.sad-order-row {
				cursor: pointer;
				transition: background 0.15s;
			}
			.sad-order-row:nth-child(even) {
				background: #fafbfc;
			}
			.sad-order-row.is-selected {
				background: #eff6ff !important;
			}
			.sad-mono {
				font-family: "JetBrains Mono", monospace;
			}
			.sad-order-link {
				color: #2563eb;
				font-weight: 600;
			}
			.sad-status-pill {
				padding: 5px 12px;
				border-radius: 20px;
				font-size: 11px;
				font-weight: 600;
				white-space: nowrap;
				display: inline-flex;
			}
			.sad-progress-mini {
				display: flex;
				align-items: center;
				gap: 6px;
			}
			.sad-progress-mini-track {
				width: 44px;
				height: 5px;
				background: #e2e8f0;
				border-radius: 3px;
				overflow: hidden;
			}
			.sad-progress-mini-fill {
				height: 100%;
				border-radius: 3px;
			}
			.sad-order-detail {
				padding: 20px 24px;
				border-top: 2px solid #e2e8f0;
				background: #f8fafc;
			}
			.sad-order-detail-head {
				display: flex;
				justify-content: space-between;
				align-items: center;
				margin-bottom: 14px;
				gap: 10px;
				flex-wrap: wrap;
			}
			.sad-order-detail-grid {
				display: grid;
				grid-template-columns: repeat(4, 1fr);
				gap: 16px;
			}
			.sad-detail-label {
				font-size: 10px;
				color: #94a3b8;
				font-family: "JetBrains Mono", monospace;
				text-transform: uppercase;
				margin-bottom: 4px;
			}
			.sad-detail-value {
				font-size: 13px;
				color: #1e293b;
				font-weight: 600;
			}
			.sad-progress-cards {
				display: grid;
				grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
				gap: 12px;
			}
			.sad-progress-card {
				background: #f8fafc;
				border-radius: 12px;
				padding: 16px;
				border: 1px solid #e2e8f0;
			}
			.sad-progress-card-head {
				display: flex;
				justify-content: space-between;
				margin-bottom: 8px;
				gap: 8px;
			}
			.sad-mini-pill {
				font-size: 9px;
				padding: 2px 6px;
				border-radius: 8px;
				font-weight: 600;
				border: 1px solid transparent;
			}
			.sad-footer {
				margin-top: 24px;
				text-align: center;
				font-size: 10px;
				color: #94a3b8;
				font-family: "JetBrains Mono", monospace;
			}
			.sad-empty,
			.sad-loading,
			.sad-error {
				display: flex;
				align-items: center;
				justify-content: center;
				min-height: 180px;
				border-radius: 14px;
				background: #fff;
				border: 1px solid #e2e8f0;
				color: #64748b;
				font-size: 14px;
			}
			.sad-error {
				color: #b91c1c;
				background: #fff7f7;
			}
			@media (max-width: 1200px) {
				.sad-kpis {
					grid-template-columns: 1fr 1fr;
				}
				.sad-grid-2-1,
				.sad-grid-2,
				.sad-grid-1-1,
				.sad-grid-analytics {
					grid-template-columns: 1fr;
				}
				.sad-order-detail-grid {
					grid-template-columns: 1fr 1fr;
				}
			}
			@media (max-width: 900px) {
				.sad-filters {
					grid-template-columns: 1fr 1fr;
				}
			}
			@media (max-width: 700px) {
				.sad-shell {
					padding: 18px;
				}
				.sad-kpis,
				.sad-filters,
				.sad-order-detail-grid {
					grid-template-columns: 1fr;
				}
			}
		`;
		document.head.appendChild(style);
	}

	function hide_empty_workspace_state(editorContainer, fallbackContainer) {
		document.body.classList.add("sales-addon-workspace-active");
		const blocks = (editorContainer || fallbackContainer)?.querySelectorAll(".ce-block") || [];
		blocks.forEach((block, index) => {
			const text = (block.textContent || "").trim();
			if (index === 0 && text === "Sales Addon") block.style.display = "none";
			if (!text && block.offsetHeight > 160) block.style.display = "none";
		});
	}

	function render_shell(block) {
		block.innerHTML = `
			<div class="sad-header">
				<div class="sad-brand">
					<div class="sad-logo">S</div>
					<div>
						<h1 class="sad-title">Sales Order Dashboard</h1>
						<p class="sad-subtitle">ERPNext · Sales Module · Live Workspace Data</p>
					</div>
				</div>
				<div class="sad-status-filters" data-role="status-filters"></div>
			</div>
			<div class="sad-filters">
				<div class="sad-filter">
					<label>From Date</label>
					<input type="date" data-filter="from_date" value="${escape_html(state.filters.from_date)}">
				</div>
				<div class="sad-filter">
					<label>To Date</label>
					<input type="date" data-filter="to_date" value="${escape_html(state.filters.to_date)}">
				</div>
				<div class="sad-filter">
					<label>Company</label>
					<input type="text" data-filter="company" value="${escape_html(state.filters.company || "")}" placeholder="Default company">
				</div>
				<div class="sad-filter">
					<label>Top Customers</label>
					<select data-filter="top_n">
						${[5, 8, 10, 15, 20].map((value) => `<option value="${value}" ${value === state.filters.top_n ? "selected" : ""}>${value}</option>`).join("")}
					</select>
				</div>
				<div class="sad-filter-action">
					<button class="sad-btn-primary" type="button" data-action="apply">Apply Filters</button>
				</div>
			</div>
			<div class="sad-kpis" data-role="kpis"></div>
			<div class="sad-tabs" data-role="tabs"></div>
			<div data-role="content"><div class="sad-loading">Loading dashboard...</div></div>
			<div class="sad-footer">Dashboard populated with ERPNext sales orders · Filters apply to live workspace data</div>
		`;
	}

	function bind_static_events(block) {
		block.querySelector('[data-action="apply"]').addEventListener("click", () => {
			sync_filters_from_dom(block);
			load_data(block);
		});
		block.querySelectorAll("[data-filter]").forEach((field) => {
			field.addEventListener("change", () => sync_filters_from_dom(block));
		});
	}

	function load_data(block) {
		set_loading_state(block);
		Promise.all([load_apexcharts()])
			.then(() => {
				frappe.call({
					method: "manufacturing_addon.sales_addon_api.get_sales_addon_customer_sales_data",
					args: { filters: state.filters },
					callback: (response) => {
						if (!is_target_route()) return;
						state.data = normalize_data(response.message || {});
						state.selectedOrder = null;
						render_dashboard(block);
					},
					error: () => show_error(block, "Unable to load sales dashboard data."),
				});
			})
			.catch(() => show_error(block, "ApexCharts could not be loaded."));
	}

	function normalize_data(data) {
		const orders = (data.orders || []).map((row) => ({
			...row,
			transaction_date: row.transaction_date || "",
			delivery_date: row.delivery_date || "",
			customer_name: row.customer_name || row.customer || "",
			territory: row.territory || "Unassigned",
			status: row.status || infer_status(row),
			total_qty: flt(row.total_qty),
			grand_total: flt(row.grand_total),
			base_grand_total: flt(row.base_grand_total),
			per_delivered: flt(row.per_delivered),
			per_billed: flt(row.per_billed),
		}));
		const normalize_breakdown = (rows) => (rows || []).map((row) => ({
			name: row.name || "Unassigned",
			value: flt(row.value),
			order_count: cint(row.order_count || 0, 0),
		}));
		return {
			...data,
			orders,
			territory_breakdown: normalize_breakdown(data.territory_breakdown),
			status_pipeline: normalize_breakdown(data.status_pipeline),
			item_group_breakdown: normalize_breakdown(data.item_group_breakdown),
			filters: data.filters || state.filters,
		};
	}

	function infer_status(row) {
		if (cint(row.docstatus, 0) === 0) return "Draft";
		return row.status || "To Deliver and Bill";
	}

	function render_dashboard(block) {
		render_status_filters(block);
		render_kpis(block);
		render_tabs(block);
		render_content(block);
	}

	function render_status_filters(block) {
		const host = block.querySelector('[data-role="status-filters"]');
		host.innerHTML = STATUS_FILTERS.map((status) => {
			const active = state.statusFilter === status;
			const cfg = STATUS_CONFIG[status] || {};
			const background = active
				? status === "All"
					? "linear-gradient(135deg, #2563eb, #7c3aed)"
					: cfg.bg || "#e0e7ff"
				: "#ffffff";
			const color = active ? (status === "All" ? "#fff" : cfg.color || "#2563eb") : "#64748b";
			return `<button class="sad-chip ${active ? "is-active" : ""}" data-status="${escape_html(status)}" style="background:${background};color:${color};">${status === "All" ? "All Orders" : escape_html(status)}</button>`;
		}).join("");
		host.querySelectorAll("[data-status]").forEach((button) => {
			button.addEventListener("click", () => {
				state.statusFilter = button.getAttribute("data-status");
				state.selectedOrder = null;
				render_dashboard(block);
			});
		});
	}

	function render_tabs(block) {
		const host = block.querySelector('[data-role="tabs"]');
		host.innerHTML = TAB_LIST.map((tab) => `<button class="sad-tab ${state.activeTab === tab ? "is-active" : ""}" data-tab="${tab}">${tab}</button>`).join("");
		host.querySelectorAll("[data-tab]").forEach((button) => {
			button.addEventListener("click", () => {
				state.activeTab = button.getAttribute("data-tab");
				render_content(block);
			});
		});
	}

	function render_kpis(block) {
		const orders = get_filtered_orders();
		const totalRevenue = sum(orders, "grand_total");
		const totalOrders = orders.length;
		const avgOrderValue = totalOrders ? totalRevenue / totalOrders : 0;
		const completedOrders = orders.filter((row) => row.status === "Completed").length;
		const completionRate = totalOrders ? Math.round((completedOrders / totalOrders) * 100) : 0;
		const kpis = [
			{
				label: "Total Revenue",
				value: format_currency_short(totalRevenue),
				sub: format_currency_full(totalRevenue, base_currency()),
				accent: "#2563eb",
				from: "#eff6ff",
				to: "#dbeafe",
			},
			{
				label: "Total Orders",
				value: totalOrders,
				sub: `${state.data.orders.length} in range`,
				accent: "#7c3aed",
				from: "#f5f3ff",
				to: "#ede9fe",
			},
			{
				label: "Avg Order Value",
				value: format_currency_short(avgOrderValue),
				sub: format_currency_full(Math.round(avgOrderValue), base_currency()),
				accent: "#d97706",
				from: "#fffbeb",
				to: "#fef3c7",
			},
			{
				label: "Completion Rate",
				value: `${completionRate}%`,
				sub: `${completedOrders} of ${totalOrders} completed`,
				accent: "#059669",
				from: "#ecfdf5",
				to: "#d1fae5",
			},
		];
		block.querySelector('[data-role="kpis"]').innerHTML = kpis.map((kpi) => `
			<div class="sad-kpi" style="background:linear-gradient(135deg, ${kpi.from}, ${kpi.to});">
				<div class="sad-kpi-orb" style="background:${kpi.accent};"></div>
				<div class="sad-kpi-label">${kpi.label}</div>
				<div class="sad-kpi-value" style="color:${kpi.accent};">${kpi.value}</div>
				<div class="sad-kpi-sub">${kpi.sub}</div>
			</div>
		`).join("");
	}

	function render_content(block) {
		destroy_charts();
		const host = block.querySelector('[data-role="content"]');
		if (!state.data) {
			host.innerHTML = '<div class="sad-empty">No data available.</div>';
			return;
		}
		if (state.activeTab === "overview") {
			host.innerHTML = overview_markup();
			render_overview_charts(host);
			return;
		}
		if (state.activeTab === "orders") {
			host.innerHTML = orders_markup();
			bind_order_events(host);
			return;
		}
		host.innerHTML = analytics_markup();
		render_analytics_charts(host);
	}

	function overview_markup() {
		return `
			<div class="sad-grid-2-1">
				<div class="sad-card">
					<h3>Monthly Revenue Trend</h3>
					<div class="sad-chart" data-chart="monthly-revenue"></div>
				</div>
				<div class="sad-card">
					<h3>Status Breakdown</h3>
					<div class="sad-chart" data-chart="status-breakdown" style="min-height:160px;"></div>
					<div class="sad-legend" data-role="status-legend"></div>
				</div>
			</div>
			<div class="sad-grid-2">
				<div class="sad-card">
					<h3>Sales Pipeline by Status</h3>
					<div class="sad-chart" data-chart="status-pipeline"></div>
				</div>
				<div class="sad-card">
					<h3>Revenue by Item Group</h3>
					<div class="sad-chart" data-chart="item-group-revenue"></div>
				</div>
			</div>
			<div class="sad-grid-2">
				<div class="sad-card">
					<h3>Revenue by Territory</h3>
					<div class="sad-chart" data-chart="territory-revenue"></div>
				</div>
				<div class="sad-card">
					<h3>Revenue by Currency</h3>
					<div class="sad-chart" data-chart="currency-revenue"></div>
				</div>
			</div>
			<div class="sad-grid-1-1">
				<div class="sad-card sad-card-full">
					<h3>Top 5 Customers</h3>
					<div class="sad-progress-list" data-role="top-customers-list"></div>
				</div>
			</div>
		`;
	}

	function orders_markup() {
		const orders = get_filtered_orders();
		const selected = orders.find((row) => row.name === state.selectedOrder);
		return `
			<div class="sad-table-card">
				<div class="sad-table-wrap">
					<table class="sad-table">
						<thead>
							<tr>
								${["Order #", "Customer", "Date", "Territory", "Qty", "Grand Total", "Delivered", "Billed", "Status"].map((head) => `<th>${head}</th>`).join("")}
							</tr>
						</thead>
						<tbody>
							${orders.map((order) => order_row_markup(order)).join("")}
						</tbody>
					</table>
				</div>
				${selected ? order_detail_markup(selected) : ""}
			</div>
		`;
	}

	function analytics_markup() {
		return `
			<div class="sad-grid-analytics">
				<div class="sad-card">
					<h3>Orders per Month</h3>
					<div class="sad-chart" data-chart="orders-per-month"></div>
				</div>
				<div class="sad-card">
					<h3>Quantity Ordered Trend</h3>
					<div class="sad-chart" data-chart="qty-trend"></div>
				</div>
				<div class="sad-card" style="grid-column:1 / -1;">
					<h3>Delivery & Billing Progress</h3>
					<div class="sad-progress-cards" data-role="progress-cards"></div>
				</div>
			</div>
		`;
	}

	function render_overview_charts(host) {
		const monthly = get_monthly_data(get_non_cancelled_orders());
		const status = get_status_data(state.data.orders);
		const pipeline = get_status_pipeline_data();
		const territory = get_territory_data();
		const itemGroups = get_item_group_data();
		const currency = get_currency_data(get_filtered_orders());
		const customers = get_top_customers(get_filtered_orders(), 5);

		render_area_chart(host.querySelector('[data-chart="monthly-revenue"]'), monthly, "revenue", "#2563eb", "Monthly Revenue", base_currency());
		render_donut_chart(host.querySelector('[data-chart="status-breakdown"]'), status, "value");
		render_horizontal_bar_chart(host.querySelector('[data-chart="status-pipeline"]'), pipeline, "Sales Value");
		render_vertical_value_chart(host.querySelector('[data-chart="item-group-revenue"]'), itemGroups, "Revenue by Item Group");
		render_horizontal_bar_chart(host.querySelector('[data-chart="territory-revenue"]'), territory, "Revenue");
		render_currency_chart(host.querySelector('[data-chart="currency-revenue"]'), currency);
		render_status_legend(host.querySelector('[data-role="status-legend"]'), status);
		render_top_customers_list(host.querySelector('[data-role="top-customers-list"]'), customers);
	}

	function render_analytics_charts(host) {
		const monthly = get_monthly_data(get_non_cancelled_orders());
		const filtered = get_filtered_orders();
		render_simple_bar_chart(host.querySelector('[data-chart="orders-per-month"]'), monthly, "orders", "Orders");
		render_area_chart(host.querySelector('[data-chart="qty-trend"]'), monthly, "qty", "#7c3aed", "Quantity");
		render_progress_cards(host.querySelector('[data-role="progress-cards"]'), filtered.slice(0, 8));
	}

	function render_area_chart(container, rows, key, color, label, currency) {
		if (!container) return;
		const chart = new ApexCharts(container, {
			chart: {
				...base_chart(220),
				type: "area",
				dropShadow: { enabled: true, top: 8, left: 0, blur: 10, opacity: 0.2, color },
			},
			series: [{ name: label, data: rows.map((row) => flt(row[key])) }],
			colors: [color],
			stroke: { curve: "smooth", width: 4.5, lineCap: "round" },
			grid: { borderColor: "#e2e8f0", strokeDashArray: 3 },
			xaxis: base_xaxis(rows.map((row) => row.month)),
			yaxis: {
				labels: {
					style: axis_style("#94a3b8", 10),
					formatter: currency ? (value) => format_currency_short(value) : undefined,
				},
			},
			dataLabels: { enabled: false },
			fill: {
				type: "gradient",
				gradient: {
					shadeIntensity: 1,
					opacityFrom: 0.18,
					opacityTo: 0.02,
					stops: [0, 100],
				},
			},
			markers: { size: 6.5, strokeWidth: 3, strokeColors: "#fff", hover: { size: 9 } },
			forecastDataPoints: { count: 0, strokeWidth: 0 },
			tooltip: {
				theme: "light",
				style: { fontFamily: "DM Sans" },
				y: {
					formatter: currency ? (value) => format_currency_full(value, currency) : (value) => value,
				},
			},
		});
		chart.render();
		state.charts[chart.w.config.chart.id || `chart-${Object.keys(state.charts).length}`] = chart;
	}

	function render_donut_chart(container, rows) {
		if (!container) return;
		const chart = new ApexCharts(container, {
			chart: { ...base_chart(160), type: "donut" },
			series: rows.map((row) => cint(row.value, 0)),
			labels: rows.map((row) => row.name),
			colors: rows.map((row) => row.color),
			dataLabels: { enabled: false },
			legend: { show: false },
			stroke: { width: 0 },
			tooltip: { theme: "light", style: { fontFamily: "DM Sans" } },
			plotOptions: { pie: { donut: { size: "56%" } } },
		});
		chart.render();
		state.charts[`chart-${Object.keys(state.charts).length}`] = chart;
	}

	function render_horizontal_bar_chart(container, rows, seriesName) {
		if (!container) return;
		if (!rows.length) {
			container.innerHTML = '<div class="sad-empty">No territory data available.</div>';
			return;
		}
		const chart = new ApexCharts(container, {
			chart: {
				...base_chart(200),
				type: "bar",
				animations: {
					enabled: true,
					easing: "easeout",
					speed: 1200,
					animateGradually: { enabled: true, delay: 180 },
					dynamicAnimation: { enabled: true, speed: 500 },
				},
			},
			series: [{
				name: seriesName || "Revenue",
				data: rows.map((row, index) => ({
					x: row.name,
					y: flt(row.value),
					fillColor: BAR_COLORS[index % BAR_COLORS.length],
				})),
			}],
			plotOptions: {
				bar: {
					horizontal: true,
					borderRadius: 6,
					barHeight: "48%",
					distributed: true,
					dataLabels: { position: "top" },
				},
			},
			dataLabels: { enabled: false },
			grid: { borderColor: "#e2e8f0", strokeDashArray: 3, xaxis: { lines: { show: true } }, yaxis: { lines: { show: false } } },
			states: {
				normal: { filter: { type: "none" } },
				hover: { filter: { type: "lighten", value: 0.08 } },
				active: { filter: { type: "darken", value: 0.04 } },
			},
			xaxis: {
				type: "numeric",
				labels: {
					style: axis_style("#94a3b8", 10),
					formatter: (value) => format_currency_short(value),
				},
			},
			yaxis: {
				labels: {
					style: axis_style("#475569", 11, "500", "DM Sans"),
					formatter: (_, index) => escape_html(rows[index]?.name || ""),
				},
			},
			tooltip: {
				theme: "light",
				style: { fontFamily: "DM Sans" },
				y: { formatter: (value) => format_currency_full(value, base_currency()) },
			},
		});
		chart.render();
		state.charts[`chart-${Object.keys(state.charts).length}`] = chart;
	}

	function render_vertical_value_chart(container, rows, seriesName) {
		if (!container) return;
		if (!rows.length) {
			container.innerHTML = '<div class="sad-empty">No item group data available.</div>';
			return;
		}
		const chart = new ApexCharts(container, {
			chart: { ...base_chart(220), type: "bar" },
			series: [{ name: seriesName || "Revenue", data: rows.map((row) => flt(row.value)) }],
			colors: rows.map((_, index) => BAR_COLORS[index % BAR_COLORS.length]),
			plotOptions: { bar: { borderRadius: 6, columnWidth: "44%", distributed: true } },
			dataLabels: { enabled: false },
			grid: { borderColor: "#e2e8f0", strokeDashArray: 3 },
			xaxis: base_xaxis(rows.map((row) => row.name)),
			yaxis: {
				labels: {
					style: axis_style("#94a3b8", 10),
					formatter: (value) => format_currency_short(value),
				},
			},
			tooltip: {
				theme: "light",
				style: { fontFamily: "DM Sans" },
				y: { formatter: (value) => format_currency_full(value, base_currency()) },
			},
		});
		chart.render();
		state.charts[`chart-${Object.keys(state.charts).length}`] = chart;
	}

	function render_currency_chart(container, rows) {
		if (!container) return;
		if (!rows.length) {
			container.innerHTML = '<div class="sad-empty">No currency data available.</div>';
			return;
		}
		const chart = new ApexCharts(container, {
			chart: { ...base_chart(200), type: "donut" },
			series: rows.map((row) => flt(row.value)),
			labels: rows.map((row) => row.name),
			colors: ["#2563eb", "#7c3aed", "#0891b2", "#d97706", "#059669", "#dc2626"],
			dataLabels: { enabled: false },
			legend: { position: "bottom", fontFamily: "DM Sans", fontSize: "12px" },
			stroke: { width: 0 },
			plotOptions: { pie: { donut: { size: "58%" } } },
			tooltip: {
				theme: "light",
				style: { fontFamily: "DM Sans" },
				y: { formatter: (value) => format_currency_full(value, base_currency()) },
			},
		});
		chart.render();
		state.charts[`chart-${Object.keys(state.charts).length}`] = chart;
	}

	function render_simple_bar_chart(container, rows, key, label) {
		if (!container) return;
		const chart = new ApexCharts(container, {
			chart: { ...base_chart(220), type: "bar" },
			series: [{ name: label, data: rows.map((row) => flt(row[key])) }],
			colors: rows.map((_, index) => BAR_COLORS[index % BAR_COLORS.length]),
			plotOptions: { bar: { borderRadius: 6, columnWidth: "38%" } },
			dataLabels: { enabled: false },
			grid: { borderColor: "#e2e8f0", strokeDashArray: 3 },
			xaxis: base_xaxis(rows.map((row) => row.month)),
			yaxis: { labels: { style: axis_style("#94a3b8", 10) } },
			tooltip: { theme: "light", style: { fontFamily: "DM Sans" } },
		});
		chart.render();
		state.charts[`chart-${Object.keys(state.charts).length}`] = chart;
	}

	function render_status_legend(container, rows) {
		container.innerHTML = rows.map((row) => `
			<div class="sad-legend-item">
				<div class="sad-legend-swatch" style="background:${row.color}"></div>
				<span style="color:#64748b">${escape_html(row.name)}</span>
				<span style="color:#94a3b8">(${row.value})</span>
			</div>
		`).join("");
	}

	function render_top_customers_list(container, rows) {
		const max = rows[0]?.value || 1;
		container.innerHTML = rows.map((row, index) => `
			<div>
				<div class="sad-progress-head">
					<span class="sad-progress-label">${escape_html(row.name)}</span>
					<span class="sad-progress-meta">${format_currency_short(row.value)}</span>
				</div>
				<div class="sad-progress-track">
					<div class="sad-progress-fill" style="width:${(row.value / max) * 100}%;background:linear-gradient(90deg, ${BAR_COLORS[index % BAR_COLORS.length]}, ${BAR_COLORS[index % BAR_COLORS.length]}cc);"></div>
				</div>
			</div>
		`).join("");
	}

	function render_progress_cards(container, rows) {
		container.innerHTML = rows.map((order) => {
			const cfg = get_status_config(order.status);
			return `
				<div class="sad-progress-card">
					<div class="sad-progress-card-head">
						<span class="sad-mono" style="font-size:10px;color:#2563eb;font-weight:600;">${escape_html(order.name)}</span>
						<span class="sad-mini-pill" style="background:${cfg.bg};color:${cfg.color};border-color:${cfg.border};">${escape_html(order.status.split(" ")[0])}</span>
					</div>
					<div style="font-size:12px;color:#334155;font-weight:500;margin-bottom:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escape_html(order.customer_name)}</div>
					${progress_block_markup("Delivered", order.per_delivered, "#059669")}
					${progress_block_markup("Billed", order.per_billed, "#7c3aed")}
				</div>
			`;
		}).join("");
	}

	function progress_block_markup(label, value, color) {
		return `
			<div style="margin-bottom:8px;">
				<div style="display:flex;justify-content:space-between;margin-bottom:4px;">
					<span style="font-size:10px;color:#64748b;">${label}</span>
					<span class="sad-mono" style="font-size:10px;color:${color};font-weight:600;">${Math.round(value)}%</span>
				</div>
				<div style="height:5px;background:#e2e8f0;border-radius:3px;">
					<div style="height:100%;width:${value}%;background:${color};border-radius:3px;transition:width 0.5s;"></div>
				</div>
			</div>
		`;
	}

	function order_row_markup(order) {
		const cfg = get_status_config(order.status);
		const selected = state.selectedOrder === order.name;
		return `
			<tr class="sad-order-row ${selected ? "is-selected" : ""}" data-order="${escape_html(order.name)}">
				<td class="sad-mono sad-order-link">${escape_html(order.name)}</td>
				<td style="font-size:13px;color:#1e293b;font-weight:500;">${escape_html(order.customer_name)}</td>
				<td class="sad-mono" style="color:#64748b;">${escape_html(order.transaction_date)}</td>
				<td style="color:#64748b;">${escape_html(order.territory)}</td>
				<td class="sad-mono" style="color:#334155;">${format_number(order.total_qty)}</td>
				<td class="sad-mono" style="color:#0f172a;font-weight:700;">${format_currency_short(order.grand_total)}</td>
				<td>${mini_progress_markup(order.per_delivered, "#059669")}</td>
				<td>${mini_progress_markup(order.per_billed, "#7c3aed")}</td>
				<td><span class="sad-status-pill" style="background:${cfg.bg};color:${cfg.color};border:1px solid ${cfg.border};">${escape_html(order.status)}</span></td>
			</tr>
		`;
	}

	function mini_progress_markup(value, color) {
		return `
			<div class="sad-progress-mini">
				<div class="sad-progress-mini-track">
					<div class="sad-progress-mini-fill" style="width:${value}%;background:${color};"></div>
				</div>
				<span class="sad-mono" style="font-size:10px;color:#64748b;">${Math.round(value)}%</span>
			</div>
		`;
	}

	function order_detail_markup(order) {
		const cfg = get_status_config(order.status);
		return `
			<div class="sad-order-detail">
				<div class="sad-order-detail-head">
					<span class="sad-mono" style="font-size:15px;font-weight:700;color:#2563eb;">${escape_html(order.name)}</span>
					<span class="sad-status-pill" style="background:${cfg.bg};color:${cfg.color};border:1px solid ${cfg.border};">${escape_html(order.status)}</span>
				</div>
				<div class="sad-order-detail-grid">
					${detail_item("Customer", order.customer_name)}
					${detail_item("Transaction Date", order.transaction_date)}
					${detail_item("Delivery Date", order.delivery_date || "--")}
					${detail_item("Territory", order.territory)}
					${detail_item("Grand Total", format_currency_full(order.grand_total, order.currency || base_currency()))}
					${detail_item("Total Qty", format_number(order.total_qty))}
					${detail_item("Delivered", `${Math.round(order.per_delivered)}%`)}
					${detail_item("Billed", `${Math.round(order.per_billed)}%`)}
				</div>
			</div>
		`;
	}

	function detail_item(label, value) {
		return `<div><div class="sad-detail-label">${label}</div><div class="sad-detail-value">${escape_html(String(value || ""))}</div></div>`;
	}

	function bind_order_events(host) {
		host.querySelectorAll("[data-order]").forEach((row) => {
			row.addEventListener("click", () => {
				const orderName = row.getAttribute("data-order");
				state.selectedOrder = state.selectedOrder === orderName ? null : orderName;
				render_content(document.getElementById(BLOCK_ID));
			});
		});
	}

	function get_filtered_orders() {
		const orders = state.data?.orders || [];
		if (state.statusFilter === "All") return orders.filter((order) => order.status !== "Cancelled");
		return orders.filter((order) => order.status === state.statusFilter);
	}

	function get_non_cancelled_orders() {
		return (state.data?.orders || []).filter((order) => order.status !== "Cancelled");
	}

	function get_monthly_data(orders) {
		const map = {};
		orders.forEach((order) => {
			const month = month_label(order.transaction_date);
			if (!month) return;
			if (!map[month.key]) {
				map[month.key] = { month: month.label, sort_key: month.key, revenue: 0, orders: 0, qty: 0 };
			}
			map[month.key].revenue += flt(order.grand_total);
			map[month.key].orders += 1;
			map[month.key].qty += flt(order.total_qty);
		});
		return Object.values(map).sort((a, b) => a.sort_key.localeCompare(b.sort_key));
	}

	function get_status_data(orders) {
		const counts = {};
		orders.forEach((order) => {
			counts[order.status] = (counts[order.status] || 0) + 1;
		});
		return Object.entries(counts).map(([name, value]) => ({
			name,
			value,
			color: get_status_config(name).border,
		}));
	}

	function get_status_pipeline_data() {
		return (state.data?.status_pipeline || []).filter((row) => flt(row.value) > 0);
	}

	function get_territory_data() {
		return (state.data?.territory_breakdown || [])
			.filter((row) => row.name && flt(row.value) > 0)
			.sort((a, b) => b.value - a.value);
	}

	function get_item_group_data() {
		return (state.data?.item_group_breakdown || [])
			.filter((row) => row.name && flt(row.value) > 0)
			.sort((a, b) => b.value - a.value);
	}

	function get_currency_data(orders) {
		const totals = {};
		orders.forEach((order) => {
			const key = order.currency || base_currency();
			totals[key] = (totals[key] || 0) + flt(order.grand_total);
		});
		return Object.entries(totals)
			.map(([name, value]) => ({ name, value }))
			.sort((a, b) => b.value - a.value);
	}

	function get_top_customers(orders, limit) {
		const totals = {};
		orders.forEach((order) => {
			totals[order.customer_name] = (totals[order.customer_name] || 0) + flt(order.grand_total);
		});
		return Object.entries(totals)
			.map(([name, value]) => ({ name, value }))
			.sort((a, b) => b.value - a.value)
			.slice(0, limit);
	}

	function get_status_config(status) {
		return STATUS_CONFIG[status] || STATUS_CONFIG.Draft;
	}

	function set_loading_state(block) {
		destroy_charts();
		block.querySelector('[data-role="content"]').innerHTML = '<div class="sad-loading">Loading dashboard...</div>';
	}

	function show_error(block, message) {
		destroy_charts();
		block.querySelector('[data-role="content"]').innerHTML = `<div class="sad-error">${escape_html(message)}</div>`;
	}

	function destroy_charts() {
		Object.values(state.charts).forEach((chart) => {
			try {
				chart.destroy();
			} catch (e) {}
		});
		state.charts = {};
	}

	function load_apexcharts() {
		if (window.ApexCharts) return Promise.resolve();
		if (apexPromise) return apexPromise;
		apexPromise = new Promise((resolve, reject) => {
			const script = document.createElement("script");
			script.src = "/assets/management_dashboard/js/apexcharts.min.js";
			script.onload = resolve;
			script.onerror = reject;
			document.head.appendChild(script);
		});
		return apexPromise;
	}

	function base_chart(height) {
		return {
			type: "line",
			height,
			toolbar: { show: false },
			fontFamily: "DM Sans, sans-serif",
			animations: {
				enabled: true,
				easing: "easeinout",
				speed: 700,
				animateGradually: { enabled: true, delay: 120 },
				dynamicAnimation: { enabled: true, speed: 350 },
			},
		};
	}

	function base_xaxis(categories) {
		return {
			categories,
			labels: {
				style: axis_style("#64748b", 11, "400", "JetBrains Mono"),
			},
			axisBorder: { show: false },
			axisTicks: { show: false },
		};
	}

	function axis_style(color, size, weight, family) {
		return {
			colors: color,
			fontSize: `${size}px`,
			fontWeight: weight || "400",
			fontFamily: family || "JetBrains Mono",
		};
	}

	function get_default_filters() {
		const today = frappe.datetime.get_today();
		return {
			from_date: frappe.datetime.month_start(today),
			to_date: today,
			company: frappe.defaults.get_default("company") || "",
			top_n: 8,
		};
	}

	function sync_filters_from_dom(block) {
		state.filters = {
			from_date: block.querySelector('[data-filter="from_date"]').value,
			to_date: block.querySelector('[data-filter="to_date"]').value,
			company: block.querySelector('[data-filter="company"]').value,
			top_n: cint(block.querySelector('[data-filter="top_n"]').value, 8),
		};
	}

	function month_label(dateString) {
		if (!dateString) return null;
		const parts = dateString.split("-");
		if (parts.length < 2) return null;
		const year = parts[0];
		const month = parts[1];
		const date = new Date(`${year}-${month}-01`);
		if (Number.isNaN(date.getTime())) return null;
		return {
			key: `${year}-${month}`,
			label: date.toLocaleString("en-US", { month: "short" }),
		};
	}

	function base_currency() {
		return state.data?.currency || state.data?.orders?.[0]?.currency || "PKR";
	}

	function format_currency_short(value) {
		const amount = flt(value);
		if (amount >= 10000000) return `₨ ${(amount / 10000000).toFixed(1)}Cr`;
		if (amount >= 100000) return `₨ ${(amount / 100000).toFixed(1)}L`;
		if (amount >= 1000) return `₨ ${(amount / 1000).toFixed(0)}K`;
		return `₨ ${Math.round(amount)}`;
	}

	function format_currency_full(value, currency) {
		const amount = flt(value);
		return `${currency || "PKR"} ${amount.toLocaleString("en-PK", { maximumFractionDigits: 2 })}`;
	}

	function format_number(value) {
		return flt(value).toLocaleString("en-PK", { maximumFractionDigits: 0 });
	}

	function sum(rows, key) {
		return rows.reduce((total, row) => total + flt(row[key]), 0);
	}

	function cint(value, fallback) {
		const parsed = Number.parseInt(value, 10);
		return Number.isNaN(parsed) ? fallback : parsed;
	}

	function flt(value) {
		return Number.parseFloat(value || 0) || 0;
	}

	function escape_html(value) {
		return frappe.utils.escape_html(String(value == null ? "" : value));
	}

	function decode_route_part(value) {
		try {
			return decodeURIComponent(value);
		} catch (e) {
			return value;
		}
	}

	if (frappe.ready) {
		frappe.ready(boot);
	} else {
		$(boot);
	}
})();
