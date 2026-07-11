// Copyright (c) 2026, Manufacturing Addon and contributors

frappe.ui.form.on("Subcontracting Order", {
	refresh(frm) {
		if (frm.doc.name && !frm.doc.__islocal && !frm.is_dirty()) {
			setTimeout(() => frm.trigger("load_sco_status_dashboard"), 200);
		}

		if (frm.doc.name && !frm.doc.__islocal) {
			frm.add_custom_button(__("Refresh Dashboard"), () => frm.trigger("load_sco_status_dashboard"), __("Custom"));
			frm.add_custom_button(
				__("Complete History"),
				() => {
					frappe.route_options = { subcontracting_order: frm.doc.name };
					frappe.set_route("subcontracting-order-history");
				},
				__("View")
			);
		}
	},

	onload(frm) {
		if (frm.doc.name && !frm.doc.__islocal) {
			setTimeout(() => frm.trigger("load_sco_status_dashboard"), 100);
		}
	},

	load_sco_status_dashboard(frm) {
		if (!frm.fields_dict.custom_html_dashboard) return;
		if (frm.is_dirty() || frm.dashboard_loading || frm.saving || frm.submitting || frm.validating) return;

		frm.dashboard_loading = true;
		show_sco_dashboard_loading(frm);

		if (!frm.sco_dashboard_fg_page) frm.sco_dashboard_fg_page = 1;
		if (!frm.sco_dashboard_fg_page_size) frm.sco_dashboard_fg_page_size = 50;
		if (!frm.sco_dashboard_rm_page) frm.sco_dashboard_rm_page = 1;
		if (!frm.sco_dashboard_rm_page_size) frm.sco_dashboard_rm_page_size = 50;

		frappe.call({
			method:
				"manufacturing_addon.manufacturing_addon.page.subcontracting_order_history.subcontracting_order_history.get_subcontracting_order_status_dashboard",
			args: {
				subcontracting_order: frm.doc.name,
				fg_page: frm.sco_dashboard_fg_page,
				fg_page_size: frm.sco_dashboard_fg_page_size,
				rm_page: frm.sco_dashboard_rm_page,
				rm_page_size: frm.sco_dashboard_rm_page_size,
			},
			callback(r) {
				frm.dashboard_loading = false;
				if (r.message) {
					render_sco_status_dashboard(frm, r.message);
				} else {
					set_sco_dashboard_message(frm, __("No dashboard data available"), "#666");
				}
			},
			error() {
				frm.dashboard_loading = false;
				set_sco_dashboard_message(frm, __("Error loading dashboard data"), "#d32f2f");
			},
		});
	},

	change_sco_fg_dashboard_page(frm, new_page) {
		if (!new_page || new_page < 1) return;
		frm.sco_dashboard_fg_page = new_page;
		frm.trigger("load_sco_status_dashboard");
	},

	change_sco_fg_dashboard_page_size(frm, new_size) {
		frm.sco_dashboard_fg_page_size = parseInt(new_size, 10) || 50;
		frm.sco_dashboard_fg_page = 1;
		frm.trigger("load_sco_status_dashboard");
	},

	change_sco_rm_dashboard_page(frm, new_page) {
		if (!new_page || new_page < 1) return;
		frm.sco_dashboard_rm_page = new_page;
		frm.trigger("load_sco_status_dashboard");
	},

	change_sco_rm_dashboard_page_size(frm, new_size) {
		frm.sco_dashboard_rm_page_size = parseInt(new_size, 10) || 50;
		frm.sco_dashboard_rm_page = 1;
		frm.trigger("load_sco_status_dashboard");
	},

	before_save(frm) {
		frm.saving = true;
		frm.dashboard_disabled = true;
	},

	after_save(frm) {
		frm.saving = false;
		setTimeout(() => {
			frm.dashboard_disabled = false;
			frm.trigger("load_sco_status_dashboard");
		}, 800);
	},

	validate(frm) {
		frm.validating = true;
		setTimeout(() => {
			frm.validating = false;
		}, 100);
	},
});

function get_sco_dashboard_wrapper(frm) {
	return frm.fields_dict.custom_html_dashboard?.$wrapper;
}

function show_sco_dashboard_loading(frm) {
	const wrapper = get_sco_dashboard_wrapper(frm);
	if (!wrapper) return;
	wrapper.empty().append(`
		<div style="padding:40px;text-align:center;color:#666;">
			<div style="display:inline-block;width:40px;height:40px;border:4px solid #f3f3f3;border-top:4px solid #1976d2;border-radius:50%;animation:sco-spin 1s linear infinite;"></div>
			<div style="margin-top:15px;font-size:14px;">${__("Loading dashboard data...")}</div>
		</div>
		<style>@keyframes sco-spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}</style>
	`);
}

function set_sco_dashboard_message(frm, message, color) {
	const wrapper = get_sco_dashboard_wrapper(frm);
	if (!wrapper) return;
	wrapper.empty().append(`<div style="padding:20px;text-align:center;color:${color};">${message}</div>`);
}

function render_sco_status_dashboard(frm, data) {
	const wrapper = get_sco_dashboard_wrapper(frm);
	if (!wrapper) return;
	wrapper.empty().append(create_sco_status_dashboard_html(data));
}

function create_sco_status_dashboard_html(data) {
	const status_color = color_map(data.status_info?.status_color);
	const receipt_color = color_map(data.receipt_status?.status_color);

	let html = `
		<div style="padding:20px;background:#f8f9fa;border-radius:8px;margin:10px 0;">
			<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;padding:15px;background:white;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
				<div>
					<h3 style="margin:0;color:#333;font-size:18px;">SCO: ${esc(data.sco_name)}</h3>
					<p style="margin:5px 0;color:#666;font-size:12px;">${__("Supplier")}: ${esc(data.supplier_name || "")}</p>
					<p style="margin:5px 0;color:#666;font-size:12px;">${__("PO")}: ${esc(data.purchase_order || "-")} · ${__("Date")}: ${frappe.datetime.str_to_user(data.transaction_date)}</p>
				</div>
				<div style="text-align:right;">
					<div style="font-size:20px;font-weight:bold;color:${status_color};">${esc(data.status_info?.status || "")}</div>
					<div style="color:#666;font-size:12px;">${esc(data.status_info?.message || "")}</div>
					<button onclick="cur_frm.trigger('load_sco_status_dashboard')" style="margin-top:10px;padding:5px 10px;background:#1976d2;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;">🔄 ${__("Refresh")}</button>
				</div>
			</div>

			<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;margin-bottom:20px;">
				${kpi_card(data.total_fg_ordered, __("FG Ordered"), "#1976d2")}
				${kpi_card(data.total_fg_received, __("FG Received"), "#2e7d32")}
				${kpi_card(data.total_fg_pending, __("FG Pending"), "#d32f2f")}
				${kpi_card(data.total_rm_consumed, __("RM Consumed"), "#f57c00")}
				${kpi_card(data.total_rm_pending, __("RM Pending Use"), "#d32f2f")}
			</div>

			<div style="background:white;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-bottom:20px;">
				<h4 style="margin:0 0 15px 0;color:#333;font-size:16px;">${__("Subcontracting Activity")}</h4>
				<div style="display:flex;justify-content:space-between;align-items:center;">
					<div>
						<div style="font-size:18px;font-weight:bold;color:${receipt_color};">${esc(data.receipt_status?.status || "")}</div>
						<div style="color:#666;font-size:12px;">${esc(data.receipt_status?.message || "")}</div>
					</div>
					<div style="text-align:right;font-size:12px;color:#666;">
						<div>${__("Receipts")}: <b>${data.receipt_status?.receipt_count || 0}</b></div>
						<div>${__("Transfers")}: <b>${data.receipt_status?.transfer_count || 0}</b></div>
						<div>${__("Receipt Qty")}: <b>${fmt(data.receipt_status?.receipt_qty)}</b></div>
					</div>
				</div>
			</div>

			<div style="background:white;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-bottom:20px;">
				<h4 style="margin:0 0 15px 0;color:#333;font-size:16px;">${__("Progress Overview")}</h4>
				${progress_block(__("FG Received Progress"), data.overall_received_percentage, "#f57c00", data.total_fg_received, data.total_fg_pending, __("Received"), __("Pending"))}
				${progress_block(__("RM Supplied Progress"), data.overall_supplied_percentage, "#1976d2", data.total_rm_supplied, Math.max(data.total_rm_required - data.total_rm_supplied, 0), __("Supplied"), __("Pending"))}
				${progress_block(__("RM Consumed Progress"), data.overall_consumed_percentage, "#2e7d32", data.total_rm_consumed, data.total_rm_pending, __("Consumed"), __("Pending"))}
			</div>

			${fg_table(data)}
			${rm_table(data)}
		</div>
	`;
	return html;
}

function fg_table(data) {
	const p = data.fg_pagination || {};
	let rows = (data.fg_items_data || [])
		.map((item) => {
			const c = pct_color(item.received_percentage);
			return `<tr>
				<td style="padding:10px;border-bottom:1px solid #e0e0e0;">
					<div style="font-weight:bold;font-size:11px;">${esc(item.item_code)}</div>
					<div style="font-size:10px;color:#666;">${esc(item.item_name || "")}</div>
				</td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;">${fmt(item.ordered_qty)}</td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;"><span style="color:#2e7d32;font-weight:bold;">${fmt(item.received_qty)}</span></td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;"><span style="color:#d32f2f;font-weight:bold;">${fmt(item.pending_qty)}</span></td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;">${mini_bar(item.received_percentage, c)}</td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;">${status_tag(item.status)}</td>
			</tr>`;
		})
		.join("");

	if (!rows) rows = `<tr><td colspan="6" style="padding:16px;text-align:center;color:#888;">${__("No finished goods")}</td></tr>`;

	return `
		<div style="background:white;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-bottom:20px;">
			<h4 style="margin:0 0 15px 0;color:#333;font-size:16px;">${__("Finished Goods — Receive Status")}</h4>
			${pagination_controls("fg", p)}
			<div style="overflow-x:auto;">
				<table style="width:100%;border-collapse:collapse;font-size:12px;">
					<thead><tr style="background:#f5f5f5;">
						<th style="padding:10px;text-align:left;border-bottom:2px solid #e0e0e0;">${__("Item")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Ordered")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Received")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Pending")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Received %")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Status")}</th>
					</tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		</div>`;
}

function rm_table(data) {
	const p = data.rm_pagination || {};
	let rows = (data.rm_items_data || [])
		.map((item) => {
			const cc = pct_color(item.consumed_percentage);
			const sc = pct_color(item.supplied_percentage);
			return `<tr>
				<td style="padding:10px;border-bottom:1px solid #e0e0e0;font-size:10px;">${esc(item.main_item_code || "")}</td>
				<td style="padding:10px;border-bottom:1px solid #e0e0e0;">
					<div style="font-weight:bold;font-size:11px;">${esc(item.rm_item_code)}</div>
				</td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;">${fmt(item.required_qty)}</td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;">${fmt(item.supplied_qty)}</td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;"><span style="color:#2e7d32;font-weight:bold;">${fmt(item.consumed_qty)}</span></td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;"><span style="color:#d32f2f;font-weight:bold;">${fmt(item.pending_qty)}</span></td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;">${mini_bar(item.supplied_percentage, sc)}</td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;">${mini_bar(item.consumed_percentage, cc)}</td>
				<td style="padding:10px;text-align:center;border-bottom:1px solid #e0e0e0;font-size:10px;">${esc(item.consumption_status || "")}</td>
			</tr>`;
		})
		.join("");

	if (!rows) rows = `<tr><td colspan="9" style="padding:16px;text-align:center;color:#888;">${__("No raw materials")}</td></tr>`;

	return `
		<div style="background:white;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
			<h4 style="margin:0 0 15px 0;color:#333;font-size:16px;">${__("Raw Materials — Supply & Consumption")}</h4>
			${pagination_controls("rm", p)}
			<div style="overflow-x:auto;">
				<table style="width:100%;border-collapse:collapse;font-size:12px;">
					<thead><tr style="background:#f5f5f5;">
						<th style="padding:10px;text-align:left;border-bottom:2px solid #e0e0e0;">${__("FG Item")}</th>
						<th style="padding:10px;text-align:left;border-bottom:2px solid #e0e0e0;">${__("RM Item")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Required")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Supplied")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Consumed")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Pending")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Supplied %")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Consumed %")}</th>
						<th style="padding:10px;text-align:center;border-bottom:2px solid #e0e0e0;">${__("Status")}</th>
					</tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		</div>`;
}

function pagination_controls(prefix, p) {
	if (!p.total_items) return "";
	const page_fn = prefix === "fg" ? "change_sco_fg_dashboard_page" : "change_sco_rm_dashboard_page";
	const size_fn = prefix === "fg" ? "change_sco_fg_dashboard_page_size" : "change_sco_rm_dashboard_page_size";
	const cur_page = prefix === "fg" ? cur_frm.sco_dashboard_fg_page || 1 : cur_frm.sco_dashboard_rm_page || 1;
	return `
		<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
			<div style="font-size:12px;color:#666;">
				${p.total_items > 0 ? `${__("Showing")} <b>${p.start_index + 1}</b> - <b>${p.end_index}</b> ${__("of")} <b>${p.total_items}</b>` : __("No items")}
			</div>
			<div style="display:flex;gap:6px;align-items:center;">
				<button type="button" onclick="cur_frm.events.${page_fn}(cur_frm, 1)" style="padding:4px 8px;">⏮</button>
				<button type="button" onclick="cur_frm.events.${page_fn}(cur_frm, Math.max(1, ${cur_page}-1))" style="padding:4px 8px;">◀</button>
				<span style="font-size:12px;">${__("Page")} <b>${p.page}</b> / ${p.total_pages}</span>
				<button type="button" onclick="cur_frm.events.${page_fn}(cur_frm, Math.min(${p.total_pages}, ${cur_page}+1))" style="padding:4px 8px;">▶</button>
				<button type="button" onclick="cur_frm.events.${page_fn}(cur_frm, ${p.total_pages})" style="padding:4px 8px;">⏭</button>
				<select onchange="cur_frm.events.${size_fn}(cur_frm, this.value)" style="margin-left:8px;">
					<option value="25" ${p.page_size == 25 ? "selected" : ""}>25</option>
					<option value="50" ${p.page_size == 50 ? "selected" : ""}>50</option>
					<option value="100" ${p.page_size == 100 ? "selected" : ""}>100</option>
				</select>
			</div>
		</div>`;
}

function kpi_card(value, label, color) {
	return `
		<div style="background:white;padding:15px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);text-align:center;">
			<div style="font-size:24px;font-weight:bold;color:${color};">${fmt(value)}</div>
			<div style="color:#666;font-size:12px;">${label}</div>
		</div>`;
}

function progress_block(title, pct, color, done_val, pending_val, done_label, pending_label) {
	const width = Math.min(flt(pct), 100);
	return `
		<div style="margin-bottom:15px;">
			<div style="display:flex;justify-content:space-between;margin-bottom:5px;">
				<span style="font-size:14px;color:#333;">${title}</span>
				<span style="font-size:14px;font-weight:bold;color:${color};">${flt(pct, 1)}%</span>
			</div>
			<div style="background:#e0e0e0;height:12px;border-radius:6px;overflow:hidden;">
				<div style="background:${color};height:100%;width:${width}%;"></div>
			</div>
			<div style="display:flex;justify-content:space-between;margin-top:5px;font-size:11px;color:#666;">
				<span>${done_label}: ${fmt(done_val)}</span>
				<span>${pending_label}: ${fmt(pending_val)}</span>
			</div>
		</div>`;
}

function mini_bar(pct, color) {
	const width = Math.min(flt(pct), 100);
	return `<div style="display:flex;align-items:center;justify-content:center;">
		<div style="width:50px;background:#e0e0e0;height:6px;border-radius:3px;margin-right:5px;">
			<div style="background:${color};height:100%;width:${width}%;border-radius:3px;"></div>
		</div>
		<span style="font-size:10px;color:${color};font-weight:bold;">${flt(pct, 1)}%</span>
	</div>`;
}

function status_tag(status) {
	const s = (status || "").toLowerCase();
	let bg = "#fee2e2", color = "#991b1b";
	if (s === "complete") { bg = "#dcfce7"; color = "#166534"; }
	else if (s === "partial") { bg = "#fef3c7"; color = "#92400e"; }
	return `<span style="background:${bg};color:${color};padding:2px 8px;border-radius:999px;font-size:10px;font-weight:600;">${esc(status || "")}</span>`;
}

function pct_color(pct) {
	if (flt(pct) >= 100) return "#2e7d32";
	if (flt(pct) > 0) return "#f57c00";
	return "#d32f2f";
}

function color_map(name) {
	return { green: "#2e7d32", orange: "#f57c00", red: "#d32f2f", blue: "#1976d2", gray: "#666666" }[name] || "#666666";
}

function fmt(val) {
	return val == null || val === "" ? "0" : flt(val, 2);
}

function esc(val) {
	return frappe.utils.escape_html(String(val ?? ""));
}
