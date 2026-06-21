// Copyright (c) 2026, Manufacturing Addon and contributors

frappe.provide("manufacturing_addon.subcontracting_order_history");

manufacturing_addon.subcontracting_order_history.SubcontractingOrderHistoryPage = class {
	constructor(page, page_wrapper) {
		this.page = page;
		this.page_wrapper = page_wrapper;
		this.wrapper = $(page.body);
		this.sco_field = null;
		this.setup();
	}

	setup() {
		if (this.page_wrapper.sco_history_initialized) {
			this.sco_field = this.page_wrapper.sco_history_field;
			return;
		}

		frappe.require("/assets/manufacturing_addon/css/subcontracting_order_history.css");

		this.wrapper.empty().html(`
			<div class="sco-history-root">
				<div class="sco-toolbar">
					<div class="sco-field-wrap">
						<label class="sco-filter-label">${__("Subcontracting Order")}</label>
						<div id="sco_history_filter"></div>
					</div>
					<div class="sco-actions">
						<button class="btn btn-primary btn-sm" id="sco_history_refresh_btn">${__("Refresh")}</button>
						<button class="btn btn-default btn-sm" id="sco_history_open_form_btn" style="display:none;">${__("Open SCO")}</button>
						<button class="btn btn-default btn-sm" id="sco_history_report_btn" style="display:none;">${__("Export Report")}</button>
					</div>
				</div>
				<div id="sco_history_content">
					<div class="sco-empty">${__("Select a Subcontracting Order to view complete history.")}</div>
				</div>
			</div>
		`);

		const $filter = this.wrapper.find("#sco_history_filter");
		$filter.empty();

		this.sco_field = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				fieldname: "subcontracting_order",
				options: "Subcontracting Order",
				label: "",
				placeholder: __("Search Subcontracting Order..."),
				change: () => this.load_history(),
			},
			parent: $filter,
			render_input: true,
			only_input: true,
		});

		if (this.sco_field.$label) this.sco_field.$label.hide();
		if (this.sco_field.label_area) this.sco_field.label_area.hide();

		this.page_wrapper.sco_history_initialized = true;
		this.page_wrapper.sco_history_field = this.sco_field;
		this.page_wrapper.sco_history_page = this;

		this.wrapper.find("#sco_history_refresh_btn").on("click", () => this.load_history());
		this.wrapper.find("#sco_history_open_form_btn").on("click", () => {
			const sco = this.sco_field.get_value();
			if (sco) frappe.set_route("Form", "Subcontracting Order", sco);
		});
		this.wrapper.find("#sco_history_report_btn").on("click", () => {
			const sco = this.sco_field.get_value();
			if (!sco) return;
			frappe.route_options = { subcontracting_order: sco };
			frappe.set_route("query-report", "Subcontracting Order History");
		});

		this.initialized = true;

		if (frappe.route_options?.subcontracting_order) {
			this.sco_field.set_value(frappe.route_options.subcontracting_order);
			frappe.route_options = null;
			setTimeout(() => this.load_history(), 150);
		}
	}

	load_history() {
		const subcontracting_order = this.sco_field?.get_value?.();
		if (!subcontracting_order) {
			this.wrapper.find("#sco_history_content").html(
				`<div class="sco-empty">${__("Please select a Subcontracting Order.")}</div>`
			);
			return;
		}

		frappe.call({
			method:
				"manufacturing_addon.manufacturing_addon.page.subcontracting_order_history.subcontracting_order_history.get_subcontracting_order_history",
			args: { subcontracting_order },
			freeze: true,
			freeze_message: __("Loading history..."),
			callback: (r) => {
				if (r.message) {
					this.render_history(r.message);
					this.wrapper.find("#sco_history_open_form_btn, #sco_history_report_btn").show();
				}
			},
		});
	}

	render_history(data) {
		const h = data.header || {};
		const s = data.summary || {};
		const invoices = data.purchase_invoices || [];
		const total_invoiced = invoices.reduce((sum, inv) => sum + flt(inv.grand_total), 0);
		const total_outstanding = invoices.reduce((sum, inv) => sum + flt(inv.outstanding_amount), 0);
		const total_paid = Math.max(total_invoiced - total_outstanding, 0);

		const $content = this.wrapper.find("#sco_history_content");

		$content.html(`
			${this.render_kpis(s)}
			${this.render_financial_kpis(h, total_invoiced, total_paid, total_outstanding)}
			${this.render_header(h, s, data.purchase_order)}
			<div class="row">
				<div class="col-lg-6">${this.render_fg_section(data.order_items || [])}</div>
				<div class="col-lg-6">${this.render_rm_section(data.supplied_by_fg || [], s)}</div>
			</div>
			${this.render_timeline(data.timeline || [])}
			${this.render_stock_entries(data.stock_entries || [])}
			${this.render_receipts(data.receipts || [])}
			${this.render_service_items(data.service_items || [])}
			${this.render_invoices(invoices, total_invoiced, total_paid, total_outstanding)}
		`);

		$content.find(".sco-timeline-item").on("click", function () {
			const doctype = $(this).data("doctype");
			const docname = $(this).data("docname");
			if (doctype && docname) frappe.set_route("Form", doctype, docname);
		});
	}

	render_kpis(s) {
		return `
			<div class="sco-kpi-row">
				${kpi(__("FG Ordered"), format_qty(s.total_ordered_qty))}
				${kpi(__("FG Received"), format_qty(s.total_received_qty), "done")}
				${kpi(__("FG Pending"), format_qty(s.pending_fg_qty), s.pending_fg_qty > 0 ? "pending" : "")}
				${kpi(__("Received %"), `${flt(s.per_received, 1)}%`)}
				${kpi(__("RM Consumed"), format_qty(s.rm_consumed_qty), "done")}
				${kpi(__("RM Pending Use"), format_qty(s.rm_pending_consumption_qty), s.rm_pending_consumption_qty > 0 ? "pending" : "")}
				${kpi(__("Transfers"), s.material_transfer_count || 0)}
				${kpi(__("Receipts"), s.receipt_count || 0)}
			</div>
		`;
	}

	render_financial_kpis(h, total_invoiced, total_paid, total_outstanding) {
		const order_value = flt(h.total);
		const billing_pct = order_value ? flt((total_invoiced / order_value) * 100, 1) : 0;
		return `
			<div class="sco-kpi-row sco-financial-row">
				${fin_kpi(__("Order Value"), format_amount(order_value), "blue")}
				${fin_kpi(__("Total Invoiced"), format_amount(total_invoiced), total_invoiced > 0 ? "blue" : "")}
				${fin_kpi(__("Total Paid"), format_amount(total_paid), total_paid > 0 ? "done" : "")}
				${fin_kpi(__("Outstanding"), format_amount(total_outstanding), total_outstanding > 0 ? "pending" : "done")}
				${fin_kpi(__("Billed %"), billing_pct + "%", billing_pct >= 100 ? "done" : billing_pct > 0 ? "partial" : "")}
			</div>
		`;
	}

	render_header(h, s, po) {
		return `
			<div class="sco-header">
				<div class="sco-header-top">
					<div>
						<h4 style="margin:0 0 4px 0;">${doc_link("Subcontracting Order", h.name, h.name)}</h4>
						<div style="color:#64748b;font-size:12px;">
							${escape_html(h.supplier_name || h.supplier || "")}
							${h.purchase_order ? " · PO: " + doc_link("Purchase Order", h.purchase_order) : ""}
							${h.transaction_date ? " · " + frappe.datetime.str_to_user(h.transaction_date) : ""}
						</div>
					</div>
					<div>${status_pill(h.status)}</div>
				</div>
				<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;">
					<span><b>${__("Overall FG Received")}</b></span>
					<span>${format_qty(s.total_received_qty)} / ${format_qty(s.total_ordered_qty)} (${flt(s.per_received, 1)}%)</span>
				</div>
				<div class="sco-overall-bar"><span style="width:${Math.min(flt(s.per_received), 100)}%"></span></div>
				<div style="display:flex;gap:16px;margin-top:10px;font-size:12px;flex-wrap:wrap;">
					<span>${__("FG Complete")}: <b style="color:#059669">${s.fg_complete_count || 0}</b></span>
					<span>${__("FG Partial")}: <b style="color:#d97706">${s.fg_partial_count || 0}</b></span>
					<span>${__("FG Pending")}: <b style="color:#dc2626">${s.fg_pending_count || 0}</b></span>
					<span>${__("RM Fully Consumed")}: <b style="color:#059669">${s.rm_fully_consumed_count || 0}</b></span>
					<span>${__("RM Pending Consumption")}: <b style="color:#dc2626">${s.rm_pending_consumption_count || 0}</b></span>
					${po ? `<span>${__("PO Status")}: ${status_pill(po.status)}</span>` : ""}
				</div>
				<div class="sco-meta-grid">
					${h.company ? meta_item(__("Company"), escape_html(h.company)) : ""}
					${h.schedule_date ? meta_item(__("Due Date"), frappe.datetime.str_to_user(h.schedule_date)) : ""}
					${h.set_warehouse ? meta_item(__("FG Warehouse"), escape_html(h.set_warehouse)) : ""}
					${h.supplier_warehouse ? meta_item(__("Supplier WH"), escape_html(h.supplier_warehouse)) : ""}
					${h.owner ? meta_item(__("Created By"), escape_html(h.owner)) : ""}
					${h.total ? meta_item(__("Order Value"), `<b style="color:var(--sco-blue)">${format_amount(h.total)}</b>`) : ""}
					${po ? meta_item(__("PO Received %"), flt(po.per_received, 1) + "%") : ""}
					${po ? meta_item(__("PO Billed %"), flt(po.per_billed, 1) + "%") : ""}
				</div>
			</div>
		`;
	}

	render_fg_section(items) {
		if (!items.length) {
			return section(__("Finished Goods — Receive Status"), `<div class="sco-empty">${__("No finished goods")}</div>`);
		}

		const cards = items
			.map((item) => {
				const border = status_border(item.status);
				const pct = Math.min(flt(item.received_pct), 100);
				return `
					<div class="sco-item-card ${border}">
						<div class="sco-item-title">${escape_html(item.item_code)}</div>
						<div style="font-size:11px;color:#64748b;margin-bottom:6px;">${escape_html(item.item_name || "")}</div>
						<div style="display:flex;justify-content:space-between;align-items:center;">
							${status_pill(item.status)}
							<span style="font-size:12px;font-weight:600;">${flt(item.received_pct, 1)}% ${__("received")}</span>
						</div>
						<div class="sco-mini-bar received"><span style="width:${pct}%"></span></div>
						<div class="sco-metrics">
							<div class="sco-metric"><b>${format_qty(item.qty)}</b><span>${__("Ordered")}</span></div>
							<div class="sco-metric highlight-done"><b>${format_qty(item.received_qty)}</b><span>${__("Received")}</span></div>
							<div class="sco-metric ${item.pending_qty > 0 ? "highlight-pending" : ""}"><b>${format_qty(item.pending_qty)}</b><span>${__("Pending")}</span></div>
							<div class="sco-metric"><b>${escape_html(item.uom || "")}</b><span>${__("UOM")}</span></div>
						</div>
						<div class="sco-item-tags">
							${item.rate ? `<span class="sco-tag">${__("Rate")}: ${format_amount(item.rate)}</span>` : ""}
							${item.amount ? `<span class="sco-tag sco-tag-blue">${__("Amount")}: ${format_amount(item.amount)}</span>` : ""}
							${item.bom ? `<span class="sco-tag">${doc_link("BOM", item.bom, __("BOM"))}</span>` : ""}
							${item.warehouse ? `<span class="sco-tag">${__("WH")}: ${escape_html(item.warehouse)}</span>` : ""}
							${item.schedule_date ? `<span class="sco-tag">${__("Due")}: ${frappe.datetime.str_to_user(item.schedule_date)}</span>` : ""}
						</div>
					</div>
				`;
			})
			.join("");

		return section(__("Finished Goods — Receive Status"), cards);
	}

	render_rm_section(groups, summary) {
		if (!groups.length) {
			return section(__("Raw Materials — Supply & Consumption"), `<div class="sco-empty">${__("No raw materials")}</div>`);
		}

		const summary_bar = `
			<div style="background:#f8fafc;border-radius:8px;padding:10px;margin-bottom:12px;font-size:12px;">
				<div style="display:flex;justify-content:space-between;margin-bottom:4px;flex-wrap:wrap;gap:6px;">
					<span>${__("Total RM Required")}: <b>${format_qty(summary.rm_required_qty)}</b></span>
					<span>${__("Supplied")}: <b>${format_qty(summary.rm_supplied_qty)}</b></span>
					<span>${__("Consumed")}: <b style="color:#059669">${format_qty(summary.rm_consumed_qty)}</b></span>
					<span>${__("Pending Use")}: <b style="color:#dc2626">${format_qty(summary.rm_pending_consumption_qty)}</b></span>
					<span>${__("Not Supplied")}: <b style="color:#d97706">${format_qty(summary.rm_not_supplied_qty || 0)}</b></span>
				</div>
			</div>
		`;

		const body = groups
			.map((group) => {
				const rm_cards = (group.items || [])
					.map((rm) => {
						const consumed_pct = Math.min(flt(rm.consumed_pct), 100);
						const supplied_pct = Math.min(flt(rm.supplied_pct), 100);
						const border = consumption_border(rm.consumption_status);
						return `
							<div class="sco-item-card ${border}" style="margin-left:8px;">
								<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;">
									<div class="sco-item-title" style="margin:0;">${escape_html(rm.rm_item_code)}</div>
									<div>${status_pill(rm.consumption_status)}</div>
								</div>
								<div style="font-size:11px;color:#64748b;margin:4px 0;">${status_pill(rm.supply_status, "supplied")}</div>
								${rm.reserve_warehouse ? `<div style="font-size:11px;color:#64748b;margin-bottom:6px;">📦 ${escape_html(rm.reserve_warehouse)}</div>` : ""}
								<div style="font-size:11px;margin-bottom:2px;">${__("Consumed")} ${flt(rm.consumed_pct, 1)}%</div>
								<div class="sco-mini-bar consumed"><span style="width:${consumed_pct}%"></span></div>
								<div style="font-size:11px;margin-bottom:2px;">${__("Supplied")} ${flt(rm.supplied_pct, 1)}%</div>
								<div class="sco-mini-bar supplied"><span style="width:${supplied_pct}%"></span></div>
								<div class="sco-metrics">
									<div class="sco-metric"><b>${format_qty(rm.required_qty)}</b><span>${__("Required")}</span></div>
									<div class="sco-metric"><b>${format_qty(rm.supplied_qty)}</b><span>${__("Supplied")}</span></div>
									<div class="sco-metric highlight-done"><b>${format_qty(rm.consumed_qty)}</b><span>${__("Consumed")}</span></div>
									<div class="sco-metric ${flt(rm.returned_qty) > 0 ? "highlight-partial" : ""}"><b>${format_qty(rm.returned_qty || 0)}</b><span>${__("Returned")}</span></div>
									<div class="sco-metric ${rm.pending_consumption_qty > 0 ? "highlight-pending" : ""}"><b>${format_qty(rm.pending_consumption_qty)}</b><span>${__("Pending")}</span></div>
									<div class="sco-metric ${rm.not_supplied_qty > 0 ? "highlight-pending" : ""}"><b>${format_qty(rm.not_supplied_qty)}</b><span>${__("Not Supplied")}</span></div>
									<div class="sco-metric"><b>${escape_html(rm.stock_uom || "")}</b><span>${__("UOM")}</span></div>
								</div>
								${rm.rate || rm.amount ? `
								<div class="sco-item-tags">
									${rm.rate ? `<span class="sco-tag">${__("Rate")}: ${format_amount(rm.rate)}</span>` : ""}
									${rm.amount ? `<span class="sco-tag sco-tag-blue">${__("Amount")}: ${format_amount(rm.amount)}</span>` : ""}
								</div>` : ""}
							</div>
						`;
					})
					.join("");

				return `
					<div class="sco-fg-group">
						<div class="sco-fg-group-title">${escape_html(group.fg_item)}</div>
						${rm_cards}
					</div>
				`;
			})
			.join("");

		return section(__("Raw Materials — Supply & Consumption"), summary_bar + body);
	}

	render_timeline(events) {
		if (!events.length) return "";

		const type_colors = {
			"Purchase Order": "#7c3aed",
			"Subcontracting Order": "#2563eb",
			"Stock Entry": "#d97706",
			"Subcontracting Receipt": "#059669",
			"Purchase Invoice": "#dc2626",
		};

		const rows = events
			.map((e) => {
				const dot_color = type_colors[e.document_type] || "#64748b";
				return `
				<div class="sco-timeline-item" data-doctype="${escape_attr(e.document_type)}" data-docname="${escape_attr(e.document)}">
					<div class="sco-timeline-dot" style="background:${dot_color};"></div>
					<div style="flex:1;">
						<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:center;">
							<div>
								<span class="sco-timeline-type" style="color:${dot_color}">${escape_html(e.document_type)}</span>
								<b style="margin-left:4px;">${doc_link(e.document_type, e.document)}</b>
							</div>
							<span style="color:#64748b;font-size:11px;">${frappe.datetime.str_to_user(e.date)}</span>
						</div>
						<div style="font-size:12px;color:#475569;margin-top:2px;">${escape_html(e.description || "")}</div>
						<div style="font-size:11px;margin-top:4px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
							${e.qty != null ? `<span>${__("Qty")}: <b>${format_qty(e.qty)}</b></span>` : ""}
							${e.amount != null ? `<span>${__("Amount")}: <b>${format_amount(e.amount)}</b></span>` : ""}
							${status_pill(e.status)}
						</div>
					</div>
				</div>
			`;
			})
			.join("");

		return section(__("Document Timeline"), rows);
	}

	render_stock_entries(entries) {
		if (!entries.length) return "";

		const blocks = entries
			.map(
				(entry) => `
				<div class="sco-doc-block">
					<div class="sco-doc-head" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
						<div>
							${doc_link("Stock Entry", entry.name)}
							· <b>${escape_html(entry.purpose || entry.stock_entry_type)}</b>
							· ${frappe.datetime.str_to_user(entry.posting_date)}
							· ${__("Qty")}: <b>${format_qty(entry.total_qty)}</b>
						</div>
						<div style="display:flex;gap:6px;align-items:center;">
							${status_pill(entry.docstatus_label)}
							${entry.owner ? `<span style="font-size:11px;color:#64748b;">${__("By")}: ${escape_html(entry.owner)}</span>` : ""}
						</div>
					</div>
					<table class="sco-table">
						<thead><tr>
							<th>${__("RM Item")}</th><th>${__("For FG Item")}</th>
							<th class="text-right">${__("Qty")}</th>
							<th class="text-right">${__("Rate")}</th>
							<th class="text-right">${__("Amount")}</th>
							<th>${__("From")}</th><th>${__("To")}</th>
						</tr></thead>
						<tbody>
							${(entry.items || [])
								.map(
									(i) => `<tr>
								<td>${escape_html(i.item_code)}</td>
								<td>${escape_html(i.subcontracted_item || "")}</td>
								<td class="text-right">${format_qty(i.qty)}</td>
								<td class="text-right">${i.basic_rate ? format_amount(i.basic_rate) : "-"}</td>
								<td class="text-right">${i.amount ? format_amount(i.amount) : "-"}</td>
								<td>${escape_html(i.s_warehouse || "")}</td>
								<td>${escape_html(i.t_warehouse || "")}</td>
							</tr>`
								)
								.join("")}
						</tbody>
					</table>
				</div>
			`
			)
			.join("");

		return section(__("Material Transfers"), blocks);
	}

	render_receipts(receipts) {
		if (!receipts.length) return "";

		const blocks = receipts
			.map(
				(r) => `
				<div class="sco-doc-block">
					<div class="sco-doc-head" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
						<div>
							${doc_link("Subcontracting Receipt", r.name)}
							· ${frappe.datetime.str_to_user(r.posting_date)}
							· ${__("Qty")}: <b>${format_qty(r.total_qty)}</b>
							· ${__("Amount")}: <b>${format_amount(r.total)}</b>
						</div>
						<div style="display:flex;gap:6px;align-items:center;">
							${status_pill(r.docstatus_label)}
							${r.set_warehouse ? `<span style="font-size:11px;color:#64748b;">📦 ${escape_html(r.set_warehouse)}</span>` : ""}
						</div>
					</div>
					<table class="sco-table">
						<thead><tr>
							<th>${__("FG Item")}</th>
							<th class="text-right">${__("Ordered")}</th>
							<th class="text-right">${__("Received")}</th>
							<th class="text-right">${__("Rejected")}</th>
							<th class="text-right">${__("Rate")}</th>
							<th class="text-right">${__("Amount")}</th>
						</tr></thead>
						<tbody>
							${(r.items || [])
								.map(
									(i) => `<tr>
								<td>${escape_html(i.item_code)}${i.item_name ? `<div style="font-size:11px;color:#64748b;">${escape_html(i.item_name)}</div>` : ""}</td>
								<td class="text-right">${format_qty(i.qty)}</td>
								<td class="text-right" style="color:#059669;font-weight:600;">${format_qty(i.received_qty)}</td>
								<td class="text-right" style="${flt(i.rejected_qty) > 0 ? "color:#dc2626;font-weight:600;" : ""}">${format_qty(i.rejected_qty || 0)}</td>
								<td class="text-right">${format_amount(i.rate)}</td>
								<td class="text-right" style="font-weight:600;">${format_amount(i.amount)}</td>
							</tr>`
								)
								.join("")}
						</tbody>
					</table>
					${
						(r.supplied_items || []).length
							? `<div style="padding:8px 12px;font-size:11px;font-weight:600;background:#f8fafc;border-top:1px solid var(--sco-border);">${__("RM Consumed in this Receipt")}</div>
						<table class="sco-table"><thead><tr>
							<th>${__("RM Item")}</th><th>${__("FG Item")}</th>
							<th class="text-right">${__("Consumed")}</th>
							<th class="text-right">${__("Rate")}</th>
							<th class="text-right">${__("Amount")}</th>
						</tr></thead><tbody>
							${r.supplied_items
								.map(
									(i) => `<tr>
								<td>${escape_html(i.rm_item_code)}</td>
								<td>${escape_html(i.main_item_code || "")}</td>
								<td class="text-right">${format_qty(i.consumed_qty)}</td>
								<td class="text-right">${i.rate ? format_amount(i.rate) : "-"}</td>
								<td class="text-right">${i.amount ? format_amount(i.amount) : "-"}</td>
							</tr>`
								)
								.join("")}
						</tbody></table>`
							: ""
					}
				</div>
			`
			)
			.join("");

		return section(__("Subcontracting Receipts"), blocks);
	}

	render_service_items(items) {
		if (!items.length) return "";

		const rows = items
			.map(
				(i) => `<tr>
				<td>${escape_html(i.item_code)}</td>
				<td>${escape_html(i.item_name || "")}</td>
				<td class="text-right">${format_qty(i.qty)}</td>
				<td class="text-right">${format_qty(i.fg_item_qty)}</td>
				<td class="text-right">${format_amount(i.rate)}</td>
				<td class="text-right">${format_amount(i.amount)}</td>
			</tr>`
			)
			.join("");

		return section(
			__("Service Items"),
			`<table class="sco-table"><thead><tr>
				<th>${__("Service Item")}</th><th>${__("Item Name")}</th>
				<th class="text-right">${__("Qty")}</th>
				<th class="text-right">${__("FG Qty")}</th>
				<th class="text-right">${__("Rate")}</th>
				<th class="text-right">${__("Amount")}</th>
			</tr></thead><tbody>${rows}</tbody></table>`
		);
	}

	render_invoices(invoices, total_invoiced, total_paid, total_outstanding) {
		if (!invoices.length) return "";

		const pay_pct = total_invoiced ? Math.min(flt((total_paid / total_invoiced) * 100), 100) : 0;

		const summary_bar = `
			<div class="sco-invoice-summary">
				<div class="sco-invoice-summary-row">
					<div class="sco-inv-kpi">
						<span>${__("Total Invoiced")}</span>
						<b style="color:var(--sco-blue)">${format_amount(total_invoiced)}</b>
					</div>
					<div class="sco-inv-kpi">
						<span>${__("Paid")}</span>
						<b style="color:var(--sco-green)">${format_amount(total_paid)}</b>
					</div>
					<div class="sco-inv-kpi">
						<span>${__("Outstanding")}</span>
						<b style="${total_outstanding > 0 ? "color:var(--sco-red)" : "color:var(--sco-green)"}">${format_amount(total_outstanding)}</b>
					</div>
					<div class="sco-inv-kpi">
						<span>${__("Paid %")}</span>
						<b style="color:${pay_pct >= 100 ? "var(--sco-green)" : pay_pct > 0 ? "var(--sco-orange)" : "var(--sco-red)"}">${flt(pay_pct, 1)}%</b>
					</div>
				</div>
				<div style="margin-top:10px;">
					<div style="font-size:11px;color:#64748b;margin-bottom:3px;">${__("Payment Progress")} — ${flt(pay_pct, 1)}%</div>
					<div class="sco-overall-bar"><span style="width:${pay_pct}%;background:linear-gradient(90deg,var(--sco-blue),var(--sco-green));"></span></div>
				</div>
			</div>
		`;

		const blocks = invoices
			.map(
				(inv) => `
				<div class="sco-doc-block">
					<div class="sco-doc-head" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
						<div>
							${doc_link("Purchase Invoice", inv.name)}
							${inv.bill_no ? `· <span style="color:#64748b;font-size:11px;">${__("Bill #")}: ${escape_html(inv.bill_no)}</span>` : ""}
							· ${frappe.datetime.str_to_user(inv.posting_date)}
							· <b>${format_amount(inv.grand_total)}</b>
						</div>
						<div style="display:flex;gap:6px;align-items:center;">
							${status_pill(inv.status || inv.docstatus_label)}
							${flt(inv.outstanding_amount) > 0
								? `<span class="sco-tag sco-tag-pending">${__("Due")}: ${format_amount(inv.outstanding_amount)}</span>`
								: `<span class="sco-tag sco-tag-paid">${__("Fully Paid")}</span>`}
						</div>
					</div>
					${
						(inv.items || []).length
							? `<table class="sco-table"><thead><tr>
							<th>${__("Item")}</th>
							<th class="text-right">${__("Qty")}</th>
							<th class="text-right">${__("Rate")}</th>
							<th class="text-right">${__("Amount")}</th>
						</tr></thead><tbody>
							${inv.items
								.map(
									(i) => `<tr>
								<td>${escape_html(i.item_code)}${i.item_name ? `<div style="font-size:11px;color:#64748b;">${escape_html(i.item_name)}</div>` : ""}</td>
								<td class="text-right">${format_qty(i.qty)} ${escape_html(i.uom || "")}</td>
								<td class="text-right">${format_amount(i.rate)}</td>
								<td class="text-right" style="font-weight:600;">${format_amount(i.amount)}</td>
							</tr>`
								)
								.join("")}
						</tbody></table>`
							: ""
					}
				</div>
			`
			)
			.join("");

		return section(__("Purchase Invoices"), summary_bar + blocks);
	}
};

frappe.pages["subcontracting-order-history"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Subcontracting Order History"),
		single_column: true,
	});

	if (wrapper.sco_history_initialized && wrapper.sco_history_page) {
		wrapper.sco_history_page.sco_field = wrapper.sco_history_field;
		return;
	}

	wrapper.sco_history_page = new manufacturing_addon.subcontracting_order_history.SubcontractingOrderHistoryPage(
		page,
		wrapper
	);
};

frappe.pages["subcontracting-order-history"].on_page_show = function (wrapper) {
	const sco_page = wrapper.sco_history_page;
	if (frappe.route_options?.subcontracting_order && sco_page?.sco_field) {
		sco_page.sco_field.set_value(frappe.route_options.subcontracting_order);
		frappe.route_options = null;
		sco_page.load_history();
	}
};

function section(title, body) {
	return `
		<div class="sco-section">
			<div class="sco-section-head">${title}</div>
			<div class="sco-section-body">${body}</div>
		</div>
	`;
}

function kpi(label, value, tone = "") {
	const cls = tone === "pending" ? 'style="color:#dc2626"' : tone === "done" ? 'style="color:#059669"' : "";
	return `
		<div class="sco-kpi">
			<div class="sco-kpi-label">${label}</div>
			<div class="sco-kpi-value" ${cls}>${value}</div>
		</div>
	`;
}

function fin_kpi(label, value, tone = "") {
	const color =
		tone === "pending" ? "#dc2626"
		: tone === "done" ? "#059669"
		: tone === "blue" ? "#2563eb"
		: tone === "partial" ? "#d97706"
		: "#1e293b";
	return `
		<div class="sco-kpi sco-fin-kpi">
			<div class="sco-kpi-label">${label}</div>
			<div class="sco-kpi-value sco-fin-value" style="color:${color}">${value}</div>
		</div>
	`;
}

function meta_item(label, value) {
	return `
		<div class="sco-meta-item">
			<span class="sco-meta-label">${label}</span>
			<span class="sco-meta-value">${value}</span>
		</div>
	`;
}

function status_pill(status, variant) {
	if (!status) return "";
	const s = String(status).toLowerCase();
	let cls = "not-started";
	if (variant === "supplied") cls = "supplied";
	else if (s.includes("complete") || s.includes("fully") || s.includes("submitted")) cls = "complete";
	else if (s.includes("partial")) cls = "partial";
	else if (
		s.includes("pending") ||
		s.includes("not supplied") ||
		s.includes("not started") ||
		s.includes("unpaid") ||
		s.includes("overdue") ||
		s.includes("cancel")
	)
		cls = "pending";
	return `<span class="sco-pill ${cls}">${escape_html(status)}</span>`;
}

function status_border(status) {
	if (status === "Complete") return "complete-border";
	if (status === "Partial") return "partial-border";
	return "pending-border";
}

function consumption_border(status) {
	if (status === "Fully Consumed") return "complete-border";
	if (status === "Partially Consumed") return "partial-border";
	return "pending-border";
}

function doc_link(doctype, name, label) {
	if (!name) return "-";
	const text = label || name;
	return `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}">${escape_html(text)}</a>`;
}

function format_qty(val) {
	return val == null || val === "" ? "0" : flt(val, 2);
}

function format_amount(val) {
	return val == null || val === "" ? "-" : format_currency(flt(val, 2));
}

function escape_html(value) {
	return frappe.utils.escape_html(String(value ?? ""));
}

function escape_attr(value) {
	return String(value ?? "").replace(/"/g, "&quot;");
}
