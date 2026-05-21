frappe.listview_settings["Sales Order"] = {
	add_fields: [
		"base_grand_total",
		"customer_name",
		"currency",
		"delivery_date",
		"per_delivered",
		"per_billed",
		"status",
		"order_type",
		"name",
		"skip_delivery_note",
	],

	get_indicator(doc) {
		if (doc.status === "Closed") {
			return [__("Closed"), "green", "status,=,Closed"];
		} else if (doc.status === "On Hold") {
			return [__("On Hold"), "orange", "status,=,On Hold"];
		} else if (doc.status === "Completed") {
			return [__("Completed"), "green", "status,=,Completed"];
		} else if (!doc.skip_delivery_note && flt(doc.per_delivered) < 100) {
			if (frappe.datetime.get_diff(doc.delivery_date) < 0) {
				return [
					__("Overdue"),
					"red",
					"per_delivered,<,100|delivery_date,<,Today|status,!=,Closed|docstatus,=,1",
				];
			} else if (flt(doc.grand_total) === 0) {
				return [
					__("To Deliver"),
					"orange",
					"per_delivered,<,100|grand_total,=,0|status,!=,Closed|docstatus,=,1",
				];
			} else if (flt(doc.per_billed) < 100) {
				return [
					__("To Deliver and Bill"),
					"orange",
					"per_delivered,<,100|per_billed,<,100|status,!=,Closed",
				];
			}

			return [__("To Deliver"), "orange", "per_delivered,<,100|per_billed,=,100|status,!=,Closed"];
		} else if (
			flt(doc.per_delivered) === 100 &&
			flt(doc.grand_total) !== 0 &&
			flt(doc.per_billed) < 100
		) {
			return [__("To Bill"), "orange", "per_delivered,=,100|per_billed,<,100|status,!=,Closed"];
		} else if (doc.skip_delivery_note && flt(doc.per_billed) < 100) {
			return [__("To Bill"), "orange", "per_billed,<,100|status,!=,Closed"];
		}
	},

	onload(listview) {
		const method = "erpnext.selling.doctype.sales_order.sales_order.close_or_unclose_sales_orders";

		sales_order_list_dashboard.boot(listview);

		listview.page.add_menu_item(__("Close"), function () {
			listview.call_for_selected_items(method, { status: "Closed" });
		});

		listview.page.add_menu_item(__("Re-open"), function () {
			listview.call_for_selected_items(method, { status: "Submitted" });
		});

		if (frappe.model.can_create("Sales Invoice")) {
			listview.page.add_action_item(__("Sales Invoice"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Sales Invoice");
			});
		}

		if (frappe.model.can_create("Delivery Note")) {
			listview.page.add_action_item(__("Delivery Note"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Delivery Note");
			});
		}

		if (frappe.model.can_create("Payment Entry")) {
			listview.page.add_action_item(__("Advance Payment"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Payment Entry");
			});
		}
	},

	refresh(listview) {
		sales_order_list_dashboard.render(listview);
	},
};

const sales_order_list_dashboard = (() => {
	const BLOCK_ID = "sales-order-list-dashboard";
	const STYLE_ID = "sales-order-list-dashboard-style";
	const FONT_ID = "sales-order-list-dashboard-fonts";
	const BAR_COLORS = ["#2563eb", "#7c3aed", "#0891b2", "#d97706", "#059669", "#dc2626"];
	let apexPromise = null;

	function boot(listview) {
		inject_fonts();
		inject_style();
		render(listview);
	}

	function render(listview) {
		if (!listview?.page) return;
		const host = ensure_host(listview);
		if (!host) return;
		host.innerHTML = dashboard_shell();

		host.querySelector('[data-action="refresh"]').addEventListener("click", () => render(listview));

		load_apexcharts()
			.then(() => load_data(listview, host))
			.catch(() => {
				host.querySelector('[data-role="body"]').innerHTML = '<div class="sold-empty">Unable to load chart library.</div>';
			});
	}

	function ensure_host(listview) {
		const container =
			listview.page.main?.parent()?.get?.(0) ||
			listview.page.main?.get?.(0) ||
			document.querySelector(".layout-main-section");
		if (!container) return null;

		let host = container.querySelector(`#${BLOCK_ID}`);
		if (!host) {
			host = document.createElement("section");
			host.id = BLOCK_ID;
			host.className = "sold-shell";
			container.prepend(host);
		}
		return host;
	}

	function dashboard_shell() {
		return `
			<div class="sold-head">
				<div>
					<h2 class="sold-title">KPIs & Charts</h2>
					<div class="sold-meta" data-role="meta">Loading current list summary...</div>
				</div>
				<button class="sold-btn" type="button" data-action="refresh">Refresh</button>
			</div>
			<div data-role="body"><div class="sold-empty">Loading dashboard...</div></div>
		`;
	}

	function load_data(listview, host) {
		const context = get_context_from_listview(listview);
		frappe.call({
			method: "manufacturing_addon.sales_addon_api.get_sales_order_listview_dashboard",
			args: context,
			callback: (response) => {
				const data = response.message || {};
				render_dashboard(host, data);
			},
			error: () => {
				host.querySelector('[data-role="body"]').innerHTML = '<div class="sold-empty">Unable to load Sales Order summary.</div>';
			},
		});
	}

	function get_context_from_listview(listview) {
		const filters = listview.get_filters_for_args ? listview.get_filters_for_args() : [];
		const context = {
			company: "",
			from_date: null,
			to_date: null,
		};

		(filters || []).forEach((filter) => {
			const [, fieldname, operator, value] = filter;
			if (fieldname === "company" && value) context.company = value;
			if (fieldname !== "transaction_date") return;

			const op = String(operator || "").toLowerCase();
			if (op === "between" && Array.isArray(value) && value.length >= 2) {
				context.from_date = value[0];
				context.to_date = value[1];
			} else if ((op === ">=" || op === ">") && value) {
				context.from_date = value;
			} else if ((op === "<=" || op === "<") && value) {
				context.to_date = value;
			}
		});

		return context;
	}

	function render_dashboard(host, data) {
		const currency = data.currency || "PKR";
		const kpis = data.kpis || {};
		const yearly = data.yearly_trend || [];
		const territory = data.territory_breakdown || [];
		const currencyBreakdown = data.currency_breakdown || [];
		const filters = data.filters || {};
		host.querySelector('[data-role="meta"]').textContent =
			`${filters.company || "All companies"} · ${filters.from_date || "--"} to ${filters.to_date || "--"}`;

		host.querySelector('[data-role="body"]').innerHTML = `
			<div class="sold-kpis">
				${kpi_card("Total Sales Value", format_currency_short(kpis.total_value, currency), format_currency_full(kpis.total_value, currency), "#2563eb")}
				${kpi_card("Total Orders", String(kpis.total_orders || 0), `${kpis.total_orders || 0} matching orders`, "#7c3aed")}
				${kpi_card("Pending Value", format_currency_short(kpis.pending_value, currency), "To Deliver / Bill", "#d97706")}
				${kpi_card("Completed + Closed", format_currency_short((flt(kpis.completed_value) + flt(kpis.closed_value)), currency), "Delivered lifecycle", "#059669")}
			</div>
			<div class="sold-grid">
				<div class="sold-card">
					<h3>Year Sales Trend</h3>
					<div class="sold-chart" data-chart="yearly"></div>
				</div>
				<div class="sold-card">
					<h3>Currency Wise Revenue</h3>
					<div class="sold-currency-grid" data-role="currencies"></div>
				</div>
				<div class="sold-card sold-card-wide">
					<h3>Top Territories by Sales Value</h3>
					<div class="sold-territories" data-role="territories"></div>
				</div>
			</div>
		`;

		render_area_chart(host.querySelector('[data-chart="yearly"]'), yearly, currency);
		render_currency_cards(host.querySelector('[data-role="currencies"]'), currencyBreakdown, currency);
		render_territory_cards(host.querySelector('[data-role="territories"]'), territory, currency);
	}

	function kpi_card(label, value, sub, accent) {
		return `
			<div class="sold-kpi">
				<div class="sold-kpi-icon" style="color:${accent};border-color:${accent}22;background:${accent}12;">↗</div>
				<div class="sold-kpi-label">${label}</div>
				<div class="sold-kpi-value">${frappe.utils.escape_html(value)}</div>
				<div class="sold-kpi-sub">${frappe.utils.escape_html(sub)}</div>
			</div>
		`;
	}

	function render_area_chart(container, rows, currency) {
		if (!container) return;
		if (!rows.length) {
			container.innerHTML = '<div class="sold-empty">No yearly data available.</div>';
			return;
		}

		new ApexCharts(container, {
			chart: {
				...base_chart(230, "area"),
				animations: {
					enabled: true,
					easing: "easeinout",
					speed: 1200,
					animateGradually: { enabled: true, delay: 180 },
					dynamicAnimation: { enabled: true, speed: 550 },
				},
			},
			series: [{ name: "Sales", data: rows.map((row) => flt(row.value)) }],
			colors: ["#2563eb"],
			stroke: { curve: "smooth", width: 4, lineCap: "round" },
			fill: {
				type: "gradient",
				gradient: { opacityFrom: 0.22, opacityTo: 0.03, stops: [0, 100] },
			},
			grid: { borderColor: "#e2e8f0", strokeDashArray: 3 },
			xaxis: {
				categories: rows.map((row) => row.label),
				labels: { style: axis_style("#64748b", 11) },
				axisBorder: { show: false },
				axisTicks: { show: false },
			},
			yaxis: {
				labels: {
					style: axis_style("#94a3b8", 10),
					formatter: (value) => format_currency_short(value, currency),
				},
			},
			markers: { size: 6, strokeWidth: 3, strokeColors: "#fff", hover: { size: 8 } },
			dataLabels: { enabled: false },
			tooltip: {
				theme: "light",
				y: { formatter: (value) => format_currency_full(value, currency) },
			},
		}).render();
	}

	function render_currency_cards(container, rows, currency) {
		if (!container) return;
		if (!rows.length) {
			container.innerHTML = '<div class="sold-empty">No currency data available.</div>';
			return;
		}
		container.innerHTML = rows.map((row, index) => `
			<div class="sold-currency-card">
				<div class="sold-currency-swatch" style="background:${BAR_COLORS[index % BAR_COLORS.length]}"></div>
				<div class="sold-currency-name">${frappe.utils.escape_html(row.name)}</div>
				<div class="sold-currency-value">${frappe.utils.escape_html(format_currency_short(row.currency_value, row.name))}</div>
				<div class="sold-currency-sub">${frappe.utils.escape_html(format_currency_full(row.currency_value, row.name))}</div>
				<div class="sold-currency-base">${frappe.utils.escape_html(`${currency}: ${format_currency_full(row.base_value, currency)}`)}</div>
				<div class="sold-currency-count">${row.order_count || 0} orders</div>
			</div>
		`).join("");
	}

	function render_territory_cards(container, rows, currency) {
		if (!container) return;
		if (!rows.length) {
			container.innerHTML = '<div class="sold-empty">No territory data available.</div>';
			return;
		}
		container.innerHTML = rows.map((row, index) => `
			<div class="sold-territory-card">
				<div class="sold-territory-top">
					<div class="sold-territory-name">${frappe.utils.escape_html(row.name)}</div>
					<div class="sold-territory-count">${row.order_count || 0} orders</div>
				</div>
				<div class="sold-territory-value" style="color:${BAR_COLORS[index % BAR_COLORS.length]}">${frappe.utils.escape_html(format_currency_short(row.value, currency))}</div>
				<div class="sold-territory-sub">${frappe.utils.escape_html(format_currency_full(row.value, currency))}</div>
			</div>
		`).join("");
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

	function base_chart(height, type) {
		return {
			type,
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

	function axis_style(color, size, weight, family) {
		return {
			colors: color,
			fontSize: `${size}px`,
			fontWeight: weight || "400",
			fontFamily: family || "JetBrains Mono",
		};
	}

	function format_currency_short(value, currency) {
		const amount = flt(value);
		const prefix = currency === "PKR" ? "Rs " : `${currency} `;
		if (amount >= 10000000) return `${prefix}${(amount / 10000000).toFixed(1)}Cr`;
		if (amount >= 100000) return `${prefix}${(amount / 100000).toFixed(1)}L`;
		if (amount >= 1000) return `${prefix}${(amount / 1000).toFixed(0)}K`;
		return `${prefix}${amount.toFixed(0)}`;
	}

	function format_currency_full(value, currency) {
		return `${currency} ${flt(value).toLocaleString("en-PK", { maximumFractionDigits: 2 })}`;
	}

	function flt(value) {
		return Number.parseFloat(value || 0) || 0;
	}

	function inject_fonts() {
		if (document.getElementById(FONT_ID)) return;
		const link = document.createElement("link");
		link.id = FONT_ID;
		link.rel = "stylesheet";
		link.href = "https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap";
		document.head.appendChild(link);
	}

	function inject_style() {
		if (document.getElementById(STYLE_ID)) return;
		const style = document.createElement("style");
		style.id = STYLE_ID;
		style.textContent = `
			#${BLOCK_ID} {
				margin: 0 0 18px;
				padding: 22px;
				border-radius: 18px;
				background: #f8fafc;
				border: 1px solid #e2e8f0;
			}
			#${BLOCK_ID} .sold-head {
				display: flex;
				align-items: center;
				justify-content: space-between;
				gap: 16px;
				margin-bottom: 18px;
			}
			#${BLOCK_ID} .sold-eyebrow {
				font-size: 11px;
				font-weight: 700;
				letter-spacing: 0.12em;
				text-transform: uppercase;
				color: #2563eb;
				font-family: "JetBrains Mono", monospace;
			}
			#${BLOCK_ID} .sold-title {
				margin: 4px 0;
				font-size: 24px;
				font-family: "Instrument Sans", sans-serif;
				color: #0f172a;
			}
			#${BLOCK_ID} .sold-meta {
				font-size: 12px;
				color: #64748b;
				font-family: "JetBrains Mono", monospace;
			}
			#${BLOCK_ID} .sold-btn {
				padding: 10px 16px;
				border: none;
				border-radius: 10px;
				background: #2563eb;
				color: #fff;
				font-weight: 600;
				cursor: pointer;
				box-shadow: 0 2px 8px rgba(37,99,235,0.25);
			}
			#${BLOCK_ID} .sold-kpis {
				display: grid;
				grid-template-columns: repeat(4, minmax(0, 1fr));
				gap: 14px;
				margin-bottom: 16px;
			}
			#${BLOCK_ID} .sold-kpi {
				padding: 18px 20px;
				border-radius: 20px;
				border: 1px solid #dbe5f1;
				background: #ffffff;
				box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
				animation: sold-fade-up 0.55s ease both;
			}
			#${BLOCK_ID} .sold-kpi-icon {
				width: 38px;
				height: 38px;
				display: flex;
				align-items: center;
				justify-content: center;
				border-radius: 12px;
				border: 1px solid;
				font-size: 18px;
				margin-bottom: 14px;
			}
			#${BLOCK_ID} .sold-kpi-label {
				font-size: 12px;
				font-weight: 700;
				color: #475569;
				margin-bottom: 6px;
			}
			#${BLOCK_ID} .sold-kpi-value {
				font-size: 26px;
				font-weight: 700;
				font-family: "Instrument Sans", sans-serif;
				color: #0f172a;
			}
			#${BLOCK_ID} .sold-kpi-sub {
				margin-top: 6px;
				font-size: 13px;
				color: #64748b;
			}
			#${BLOCK_ID} .sold-grid {
				display: grid;
				grid-template-columns: repeat(2, minmax(0, 1fr));
				gap: 16px;
			}
			#${BLOCK_ID} .sold-card {
				background: #fff;
				border-radius: 14px;
				padding: 18px;
				border: 1px solid #e2e8f0;
				box-shadow: 0 1px 3px rgba(0,0,0,0.04);
				animation: sold-fade-up 0.6s ease both;
			}
			#${BLOCK_ID} .sold-card-wide {
				grid-column: 1 / -1;
			}
			#${BLOCK_ID} .sold-card h3 {
				margin: 0 0 14px;
				font-size: 14px;
				color: #475569;
			}
			#${BLOCK_ID} .sold-territories {
				display: grid;
				grid-template-columns: repeat(3, minmax(0, 1fr));
				gap: 14px;
			}
			#${BLOCK_ID} .sold-currency-grid {
				display: grid;
				grid-template-columns: repeat(2, minmax(0, 1fr));
				gap: 14px;
			}
			#${BLOCK_ID} .sold-currency-card {
				padding: 18px;
				border-radius: 18px;
				background: #fff;
				border: 1px solid #e2e8f0;
				box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
				animation: sold-fade-up 0.55s ease both;
			}
			#${BLOCK_ID} .sold-currency-swatch {
				width: 14px;
				height: 14px;
				border-radius: 4px;
				margin-bottom: 14px;
			}
			#${BLOCK_ID} .sold-currency-name {
				font-size: 13px;
				font-weight: 700;
				color: #334155;
				margin-bottom: 8px;
			}
			#${BLOCK_ID} .sold-currency-value {
				font-size: 24px;
				font-weight: 700;
				font-family: "Instrument Sans", sans-serif;
				color: #0f172a;
				margin-bottom: 4px;
			}
			#${BLOCK_ID} .sold-currency-sub {
				font-size: 12px;
				color: #64748b;
				margin-bottom: 6px;
			}
			#${BLOCK_ID} .sold-currency-base {
				font-size: 11px;
				color: #94a3b8;
				font-family: "JetBrains Mono", monospace;
				margin-bottom: 8px;
			}
			#${BLOCK_ID} .sold-currency-count {
				font-size: 11px;
				color: #94a3b8;
				font-family: "JetBrains Mono", monospace;
			}
			#${BLOCK_ID} .sold-territory-card {
				padding: 18px;
				border-radius: 18px;
				background: #fff;
				border: 1px solid #e2e8f0;
				box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
				animation: sold-fade-up 0.55s ease both;
			}
			#${BLOCK_ID} .sold-kpi:nth-child(1),
			#${BLOCK_ID} .sold-card:nth-child(1),
			#${BLOCK_ID} .sold-territory-card:nth-child(1) { animation-delay: 0.03s; }
			#${BLOCK_ID} .sold-kpi:nth-child(2),
			#${BLOCK_ID} .sold-card:nth-child(2),
			#${BLOCK_ID} .sold-territory-card:nth-child(2) { animation-delay: 0.08s; }
			#${BLOCK_ID} .sold-kpi:nth-child(3),
			#${BLOCK_ID} .sold-currency-card:nth-child(3),
			#${BLOCK_ID} .sold-territory-card:nth-child(3) { animation-delay: 0.13s; }
			#${BLOCK_ID} .sold-kpi:nth-child(4),
			#${BLOCK_ID} .sold-currency-card:nth-child(4),
			#${BLOCK_ID} .sold-territory-card:nth-child(4) { animation-delay: 0.18s; }
			#${BLOCK_ID} .sold-currency-card:nth-child(1) { animation-delay: 0.03s; }
			#${BLOCK_ID} .sold-currency-card:nth-child(2) { animation-delay: 0.08s; }
			#${BLOCK_ID} .sold-territory-card:nth-child(5) { animation-delay: 0.23s; }
			#${BLOCK_ID} .sold-territory-card:nth-child(6) { animation-delay: 0.28s; }
			#${BLOCK_ID} .sold-territory-top {
				display: flex;
				align-items: center;
				justify-content: space-between;
				gap: 10px;
				margin-bottom: 12px;
			}
			#${BLOCK_ID} .sold-territory-name {
				font-size: 13px;
				font-weight: 700;
				color: #334155;
			}
			#${BLOCK_ID} .sold-territory-count {
				font-size: 11px;
				color: #94a3b8;
				font-family: "JetBrains Mono", monospace;
			}
			#${BLOCK_ID} .sold-territory-value {
				font-size: 24px;
				font-weight: 700;
				font-family: "Instrument Sans", sans-serif;
				margin-bottom: 4px;
			}
			#${BLOCK_ID} .sold-territory-sub {
				font-size: 12px;
				color: #64748b;
			}
			#${BLOCK_ID} .sold-chart {
				min-height: 230px;
			}
			#${BLOCK_ID} .sold-empty {
				display: flex;
				align-items: center;
				justify-content: center;
				min-height: 180px;
				color: #64748b;
				background: #fff;
				border-radius: 14px;
				border: 1px solid #e2e8f0;
			}
			@keyframes sold-fade-up {
				from {
					opacity: 0;
					transform: translateY(10px);
				}
				to {
					opacity: 1;
					transform: translateY(0);
				}
			}
			@media (max-width: 1100px) {
				#${BLOCK_ID} .sold-kpis,
				#${BLOCK_ID} .sold-grid {
					grid-template-columns: 1fr 1fr;
				}
				#${BLOCK_ID} .sold-currency-grid,
				#${BLOCK_ID} .sold-territories {
					grid-template-columns: 1fr 1fr;
				}
			}
			@media (max-width: 760px) {
				#${BLOCK_ID} .sold-head {
					flex-direction: column;
					align-items: flex-start;
				}
				#${BLOCK_ID} .sold-kpis,
				#${BLOCK_ID} .sold-grid {
					grid-template-columns: 1fr;
				}
				#${BLOCK_ID} .sold-currency-grid,
				#${BLOCK_ID} .sold-territories {
					grid-template-columns: 1fr;
				}
			}
		`;
		document.head.appendChild(style);
	}

	return { boot, render };
})();
