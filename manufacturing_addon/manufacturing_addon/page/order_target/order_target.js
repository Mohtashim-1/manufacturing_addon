// Copyright (c) 2026, mohtashim and contributors
frappe.pages["order-target"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Order Target Dashboard",
		single_column: true,
	});
	const state = { page, controls: {}, expanded: {} };
	render_layout(wrapper, state);
	setup_filters(state);
	setup_actions(state);
	refresh_data(state);
};

// ─── Layout skeleton ─────────────────────────────────────────────────────────
function render_layout(wrapper, state) {
	const $body = $(wrapper).find(".page-content");
	$body.empty().append(`
		<div id="otd-root" style="padding:12px 4px;">
			<div id="otd-meta" style="font-size:12px;color:#6b7280;margin-bottom:10px;"></div>
			<div id="otd-summary" style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px;"></div>
			<div id="otd-table-wrap" style="overflow-x:auto;"></div>
		</div>
	`);
	state.$meta  = $body.find("#otd-meta");
	state.$sum   = $body.find("#otd-summary");
	state.$table = $body.find("#otd-table-wrap");
}

// ─── Filter controls ─────────────────────────────────────────────────────────
function setup_filters(state) {
	const p = state.page;
	state.controls.report_date   = p.add_field({ fieldname:"report_date",   label:"Report Date",    fieldtype:"Date",   default: frappe.datetime.get_today() });
	state.controls.from_shipment = p.add_field({ fieldname:"from_shipment", label:"Ship Date From", fieldtype:"Date" });
	state.controls.to_shipment   = p.add_field({ fieldname:"to_shipment",   label:"Ship Date To",   fieldtype:"Date" });
	state.controls.customer      = p.add_field({ fieldname:"customer",      label:"Customer",       fieldtype:"Link",   options:"Customer" });
	state.controls.order_sheet   = p.add_field({ fieldname:"order_sheet",   label:"Order Sheet",    fieldtype:"Link",   options:"Order Sheet" });
	state.controls.status        = p.add_field({ fieldname:"status",        label:"Status",         fieldtype:"Select", options:"\nAll\nNot Started\nOn Track\nBehind\nOverdue\nCompleted", default:"All" });
	Object.values(state.controls).forEach(c => {
		if (c && c.$input) c.$input.on("change", () => refresh_data(state));
	});
}

function get_filters(state) {
	const v = k => (state.controls[k] && state.controls[k].get_value()) || "";
	return {
		report_date:   v("report_date")   || frappe.datetime.get_today(),
		from_shipment: v("from_shipment"),
		to_shipment:   v("to_shipment"),
		customer:      v("customer"),
		order_sheet:   v("order_sheet"),
		status:        v("status") || "All",
	};
}

// ─── Refresh button ───────────────────────────────────────────────────────────
function setup_actions(state) {
	state.page.add_inner_button(__("Refresh"), () => refresh_data(state));
}

// ─── Main data fetch ─────────────────────────────────────────────────────────
function refresh_data(state) {
	state.expanded = {};
	const filters = get_filters(state);
	frappe.call({
		method: "frappe.desk.query_report.run",
		args:   { report_name: "Order Target Dashboard", filters },
		freeze: true,
		freeze_message: __("Loading order targets…"),
		callback: function (r) {
			const rows = (r.message && r.message.result) || [];
			state.$meta.text(`${rows.length} order(s) | as of ${filters.report_date}`);
			render_summary(state, rows);
			render_table(state, rows);
		},
	});
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function num(v) { return parseFloat(v) || 0; }
function fmtN(v, d) {
	const n = num(v);
	const dp = d != null ? d : 0;
	const s = n.toFixed(dp);
	const parts = s.split(".");
	parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
	return parts.join(".");
}
function fmtNum(v) { return fmtN(v, 0); }

// ─── Summary cards ───────────────────────────────────────────────────────────
const CARD_DEFS = [
	{ key:"total",         label:"Total Orders",       color:"#3b82f6" },
	{ key:"not_started",   label:"Not Started",        color:"#9ca3af" },
	{ key:"on_track",      label:"On Track",           color:"#22c55e" },
	{ key:"behind",        label:"Behind",             color:"#f97316" },
	{ key:"overdue",       label:"Overdue",            color:"#ef4444" },
	{ key:"completed",     label:"Completed",          color:"#10b981" },
	{ key:"order_qty",     label:"Total Order Qty",    color:"#6366f1" },
	{ key:"cut_pct",       label:"Avg Cut %",          color:"#f59e0b" },
	{ key:"pack_pct",      label:"Avg Pack %",         color:"#8b5cf6" },
	{ key:"delayed_total", label:"Total Delayed Days", color:"#dc2626" },
];

function render_summary(state, rows) {
	const agg = { total:0, not_started:0, on_track:0, behind:0, overdue:0, completed:0,
		order_qty:0, cut_pct_sum:0, pack_pct_sum:0, n_pct:0, delayed_total:0 };
	rows.forEach(r => {
		agg.total++;
		const s = r.status || "";
		if (s === "Not Started") agg.not_started++;
		if (s === "On Track")    agg.on_track++;
		if (s === "Behind")      agg.behind++;
		if (s === "Overdue")     agg.overdue++;
		if (s === "Completed")   agg.completed++;
		agg.order_qty     += num(r.order_qty);
		agg.delayed_total += num(r.delayed_days);
		if (num(r.order_qty) > 0) {
			agg.cut_pct_sum  += num(r.cut_pct);
			agg.pack_pct_sum += num(r.pack_pct);
			agg.n_pct++;
		}
	});
	const vals = {
		total:         agg.total,
		not_started:   agg.not_started,
		on_track:      agg.on_track,
		behind:        agg.behind,
		overdue:       agg.overdue,
		completed:     agg.completed,
		order_qty:     fmtNum(agg.order_qty),
		cut_pct:       agg.n_pct ? fmtN(agg.cut_pct_sum / agg.n_pct, 1) + "%" : "—",
		pack_pct:      agg.n_pct ? fmtN(agg.pack_pct_sum / agg.n_pct, 1) + "%" : "—",
		delayed_total: agg.delayed_total > 0 ? fmtNum(agg.delayed_total) + "d" : "None",
	};
	state.$sum.empty();
	CARD_DEFS.forEach(def => {
		state.$sum.append(`
			<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;
				padding:10px 16px;min-width:115px;flex:1;box-shadow:0 1px 3px rgba(0,0,0,.06);">
				<div style="font-size:10px;color:#6b7280;font-weight:500;">${def.label}</div>
				<div style="font-size:22px;font-weight:700;color:${def.color};line-height:1.2;margin-top:2px;">${vals[def.key]}</div>
			</div>`);
	});
}

// ─── Status pill ─────────────────────────────────────────────────────────────
function pill_html(status) {
	const cfg = {
		"Completed":   ["#dcfce7","#166534"],
		"On Track":    ["#dbeafe","#1e40af"],
		"Behind":      ["#ffedd5","#9a3412"],
		"Overdue":     ["#fee2e2","#991b1b"],
		"Not Started": ["#f3f4f6","#374151"],
	}[status] || ["#f3f4f6","#374151"];
	return `<span style="background:${cfg[0]};color:${cfg[1]};border-radius:12px;
		padding:2px 8px;font-size:11px;font-weight:600;white-space:nowrap;">${status}</span>`;
}

// ─── Days status cell ─────────────────────────────────────────────────────────
function days_status_html(days_remaining, delayed_days) {
	const dr = num(days_remaining);
	const dd = num(delayed_days);
	if (dd > 0) {
		return `<div style="text-align:center;">
			<div style="background:#fee2e2;border:2px solid #dc2626;border-radius:8px;
				padding:4px 6px;display:inline-block;min-width:92px;">
				<div style="font-size:14px;font-weight:800;color:#dc2626;line-height:1.1;">⚠ ${fmtNum(dd)}</div>
				<div style="font-size:9px;color:#991b1b;font-weight:700;letter-spacing:.5px;">DAYS DELAYED</div>
			</div>
		</div>`;
	} else if (dr === 0) {
		return `<div style="text-align:center;">
			<div style="background:#fee2e2;border-radius:8px;padding:4px 6px;display:inline-block;">
				<div style="font-size:11px;font-weight:700;color:#dc2626;">DUE TODAY!</div>
			</div>
		</div>`;
	} else if (dr <= 7) {
		return `<div style="text-align:center;">
			<div style="background:#fff7ed;border:1px solid #fb923c;border-radius:8px;
				padding:4px 6px;display:inline-block;">
				<div style="font-size:14px;font-weight:700;color:#ea580c;">⚡ ${fmtNum(dr)}</div>
				<div style="font-size:9px;color:#9a3412;font-weight:600;">DAYS LEFT</div>
			</div>
		</div>`;
	} else {
		return `<div style="text-align:center;">
			<div style="background:#f0fdf4;border-radius:8px;padding:4px 6px;display:inline-block;">
				<div style="font-size:14px;font-weight:700;color:#16a34a;">✓ ${fmtNum(dr)}</div>
				<div style="font-size:9px;color:#15803d;font-weight:600;">DAYS LEFT</div>
			</div>
		</div>`;
	}
}

// ─── Stage cells block (5 cells per stage) ───────────────────────────────────
function stage_cells(done, pending, pct, avg_d, need_d, today_qty) {
	const p  = Math.min(num(pct), 100);
	const nd = num(need_d);
	const ad = num(avg_d);
	let bar_color = "#ef4444";
	if (p >= 100)     bar_color = "#22c55e";
	else if (p >= 70) bar_color = "#3b82f6";
	else if (p >= 40) bar_color = "#f97316";

	const done_html  = num(done) > 0
		? `<b style="color:#111827;">${fmtNum(done)}</b>`
		: `<span style="color:#d1d5db;">0</span>`;
	const pend_html  = num(pending) > 0
		? `<span style="color:#dc2626;font-weight:600;">${fmtNum(pending)}</span>`
		: `<span style="color:#16a34a;font-weight:700;">✓</span>`;
	const need_color = (nd > 0 && ad > 0 && nd > ad * 1.2) ? "#dc2626" : "#2563eb";
	const avg_need   = `<div style="font-size:10px;line-height:1.7;text-align:center;">
		<span style="color:#6b7280;">avg </span><b style="color:#374151;">${ad > 0 ? fmtNum(ad) : "—"}</b><br>
		<span style="color:#6b7280;">need </span><b style="color:${need_color};">${nd > 0 ? fmtNum(nd) : (num(pending) === 0 ? "✓" : "—")}</b>
	</div>`;
	const today_html = num(today_qty) > 0
		? `<b style="color:#2563eb;">${fmtNum(today_qty)}</b>`
		: `<span style="color:#d1d5db;">—</span>`;

	return `
		<td class="td-st" style="text-align:right;">${done_html}</td>
		<td class="td-st" style="text-align:right;">${pend_html}</td>
		<td class="td-st" style="min-width:70px;">
			<div style="font-size:10px;color:${bar_color};font-weight:700;text-align:right;margin-bottom:2px;">${p.toFixed(1)}%</div>
			<div style="background:#e5e7eb;border-radius:3px;height:5px;overflow:hidden;">
				<div style="height:100%;background:${bar_color};width:${p}%;border-radius:3px;"></div>
			</div>
		</td>
		<td class="td-st" style="min-width:80px;">${avg_need}</td>
		<td class="td-st" style="text-align:right;">${today_html}</td>`;
}

// ─── Main table ───────────────────────────────────────────────────────────────
function render_table(state, rows) {
	const cs = `padding:7px 8px;font-size:12px;vertical-align:middle;`;
	const th  = label => `<th style="padding:7px 8px;font-size:11px;font-weight:600;background:#f8fafc;
		color:#374151;white-space:nowrap;border-bottom:2px solid #e5e7eb;">${label}</th>`;
	const th_stage = label => `<th colspan="5" style="padding:6px 8px;font-size:11px;font-weight:700;
		background:#eff6ff;color:#1d4ed8;text-align:center;border-bottom:1px solid #bfdbfe;
		border-left:3px solid #3b82f6;">${label}</th>`;
	const th_sub = label => `<th style="padding:4px 8px;font-size:10px;font-weight:600;color:#6b7280;
		background:#fafbfc;text-align:center;white-space:nowrap;border-bottom:1px solid #e5e7eb;">${label}</th>`;
	const th_empty = () => `<th style="background:#f8fafc;border-bottom:2px solid #e5e7eb;"></th>`;
	const th_empty2 = () => `<th style="background:#fafbfc;border-bottom:1px solid #e5e7eb;"></th>`;

	const sub_ths = ["Done","Pending","%","Avg→Need/d","Today"];
	const stage_sub = sub_ths.map(s => th_sub(s)).join("");

	const hdr1 = `<tr>
		${th_empty()}${th("Order Sheet")}${th("Customer")}${th("Ship Date")}${th("Qty")}${th("Days Status")}
		${th_stage("✂ CUTTING")}${th_stage("🪡 STITCHING")}${th_stage("✔ CHECKING")}${th_stage("📦 PACKING")}
		${th("Status")}
	</tr>`;
	const hdr2 = `<tr>
		${Array(6).fill(th_empty2()).join("")}
		${stage_sub}${stage_sub}${stage_sub}${stage_sub}
		${th_empty2()}
	</tr>`;

	let body_html = "";
	rows.forEach((r, idx) => {
		const oq = num(r.order_qty);
		body_html += `
		<tr class="otd-row" data-idx="${idx}" data-os="${(r.order_sheet||"").replace(/"/g,"&quot;")}"
			style="border-bottom:1px solid #f0f0f0;"
			onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background=''">
			<td style="${cs}padding-left:10px;">
				<button class="expand-btn" data-idx="${idx}"
					style="background:none;border:1px solid #d1d5db;border-radius:4px;
					width:22px;height:22px;cursor:pointer;font-size:11px;color:#6b7280;padding:0;line-height:1;">
					▶
				</button>
			</td>
			<td style="${cs}">
				<a href="/app/order-sheet/${encodeURIComponent(r.order_sheet||"")}" target="_blank"
					style="color:#2563eb;font-weight:600;font-size:12px;">${r.order_sheet||""}</a>
			</td>
			<td style="${cs}color:#374151;">${r.customer||""}</td>
			<td style="${cs}white-space:nowrap;color:#6b7280;">${r.shipment_date||""}</td>
			<td style="${cs}text-align:right;font-weight:700;font-size:13px;">${oq > 0 ? fmtNum(oq) : "—"}</td>
			<td style="${cs}min-width:112px;">${days_status_html(r.days_remaining, r.delayed_days)}</td>
			${stage_cells(r.total_cut,    r.pending_cut,    r.cut_pct,    r.avg_daily_cut,    r.needed_daily_cut,    r.today_cut)}
			${stage_cells(r.total_stitch, r.pending_stitch, r.stitch_pct, r.avg_daily_stitch, r.needed_daily_stitch, r.today_stitch)}
			${stage_cells(r.total_check,  r.pending_check,  r.check_pct,  r.avg_daily_check,  r.needed_daily_check,  r.today_check)}
			${stage_cells(r.total_pack,   r.pending_pack,   r.pack_pct,   r.avg_daily_pack,   r.needed_daily_pack,   r.today_pack)}
			<td style="${cs}">${pill_html(r.status||"")}</td>
		</tr>
		<tr id="drill-${idx}" style="display:none;background:#f0f6ff;">
			<td colspan="27" style="padding:0 0 0 42px;border-bottom:2px solid #bfdbfe;">
				<div class="drill-content" data-idx="${idx}" style="padding:10px 12px 16px;"></div>
			</td>
		</tr>`;
	});

	state.$table.html(`
		<style>
			.td-st { padding:6px 8px;font-size:12px;vertical-align:middle;border-left:1px solid #f3f4f6;white-space:nowrap; }
			.otd-tbl { border-collapse:collapse;min-width:1500px;width:100%; }
			.otd-tbl td,.otd-tbl th { border-bottom:1px solid #f0f0f0; }
		</style>
		<table class="otd-tbl">
			<thead>${hdr1}${hdr2}</thead>
			<tbody>${body_html}</tbody>
		</table>`);

	// Expand / collapse handler
	state.$table.find(".expand-btn").on("click", function () {
		const idx    = $(this).data("idx");
		const $btn   = $(this);
		const $row   = state.$table.find(`#drill-${idx}`);
		const $div   = $row.find(".drill-content");
		const osName = state.$table.find(`.otd-row[data-idx="${idx}"]`).data("os");

		if (state.expanded[idx]) {
			$row.hide();
			$btn.text("▶");
			state.expanded[idx] = false;
		} else {
			$row.show();
			$btn.text("▼");
			state.expanded[idx] = true;
			if (!$div.data("loaded")) {
				$div.html(`<span style="color:#6b7280;font-size:12px;">⏳ Loading item breakdown…</span>`);
				frappe.call({
					method: "manufacturing_addon.manufacturing_addon.page.order_target.order_target.get_order_drill_down",
					args:   { order_sheet: osName },
					callback: function (r) {
						const d = r.message || {};
						const items = d.items || [];
						$div.html(items.length ? render_drill_table(items)
							: `<div style="color:#9ca3af;font-size:12px;">${d.message || "No item data."}</div>`);
						$div.data("loaded", true);
					},
				});
			}
		}
	});
}

// ─── Drill-down item table ───────────────────────────────────────────────────
function render_drill_table(items) {
	const th  = label => `<th style="padding:5px 8px;font-size:10px;font-weight:600;color:#374151;
		background:#e0e7ff;white-space:nowrap;border-bottom:1px solid #c7d2fe;">${label}</th>`;
	const th_s = label => `<th style="padding:5px 8px;font-size:10px;font-weight:600;color:#1d4ed8;
		background:#dbeafe;white-space:nowrap;border-bottom:1px solid #bfdbfe;">${label}</th>`;

	function td_done(v, oq) {
		const n = num(v);
		if (n <= 0) return `<td style="text-align:right;padding:4px 8px;color:#d1d5db;">—</td>`;
		const p = oq > 0 ? Math.min(n / oq * 100, 100) : 0;
		let color = "#ef4444";
		if (p >= 100) color = "#16a34a";
		else if (p >= 70) color = "#2563eb";
		else if (p >= 40) color = "#f97316";
		return `<td style="text-align:right;padding:4px 8px;color:${color};font-weight:600;">${fmtNum(n)}</td>`;
	}
	function td_pend(v) {
		const n = num(v);
		return n <= 0
			? `<td style="text-align:right;padding:4px 8px;color:#16a34a;font-weight:700;">✓</td>`
			: `<td style="text-align:right;padding:4px 8px;color:#dc2626;">${fmtNum(n)}</td>`;
	}
	function td_pct(v) {
		const p = num(v);
		let color = "#ef4444";
		if (p >= 100) color = "#16a34a";
		else if (p >= 70) color = "#2563eb";
		else if (p >= 40) color = "#f97316";
		const w = Math.min(p, 100);
		return `<td style="padding:4px 8px;min-width:70px;">
			<div style="font-size:10px;color:${color};font-weight:700;margin-bottom:1px;">${p.toFixed(1)}%</div>
			<div style="background:#e5e7eb;border-radius:2px;height:4px;">
				<div style="height:100%;background:${color};width:${w}%;border-radius:2px;"></div>
			</div>
		</td>`;
	}

	const rows_html = items.map(item => {
		const oq = num(item.order_qty);
		const ref = oq || Math.max(num(item.cut_done), num(item.stitch_done), num(item.check_done), num(item.pack_done));
		return `<tr style="border-bottom:1px solid #e0e7ff;"
				onmouseover="this.style.background='#eef2ff'" onmouseout="this.style.background=''">
			<td style="padding:4px 8px;font-weight:700;color:#1e40af;">${item.combo_item||"—"}</td>
			<td style="padding:4px 8px;">${item.colour||"—"}</td>
			<td style="padding:4px 8px;color:#6b7280;">${item.article||"—"}</td>
			<td style="text-align:right;padding:4px 8px;font-weight:700;">${oq > 0 ? fmtNum(oq) : "—"}</td>
			${td_done(item.cut_done, ref)}${td_pend(item.cut_pending)}${td_pct(item.cut_pct)}
			<td style="text-align:right;padding:4px 8px;color:#6b7280;font-size:10px;">${item.cut_avg_d > 0 ? fmtN(item.cut_avg_d,0)+"/d" : "—"}</td>
			${td_done(item.stitch_done, ref)}${td_pend(item.stitch_pending)}${td_pct(item.stitch_pct)}
			<td style="text-align:right;padding:4px 8px;color:#6b7280;font-size:10px;">${item.stitch_avg_d > 0 ? fmtN(item.stitch_avg_d,0)+"/d" : "—"}</td>
			${td_done(item.check_done, ref)}${td_pend(item.check_pending)}${td_pct(item.check_pct)}
			<td style="text-align:right;padding:4px 8px;color:#6b7280;font-size:10px;">${item.check_avg_d > 0 ? fmtN(item.check_avg_d,0)+"/d" : "—"}</td>
			${td_done(item.pack_done, ref)}${td_pend(item.pack_pending)}${td_pct(item.pack_pct)}
			<td style="text-align:right;padding:4px 8px;color:#6b7280;font-size:10px;">${item.pack_avg_d > 0 ? fmtN(item.pack_avg_d,0)+"/d" : "—"}</td>
		</tr>`;
	}).join("");

	return `
		<div style="font-weight:600;color:#3730a3;margin-bottom:6px;font-size:12px;">
			📋 Item/Combo Breakdown — ${items.length} combination${items.length !== 1 ? "s" : ""}
			<span style="font-weight:400;color:#6b7280;font-size:11px;">(grouped by Combo Item + Colour)</span>
		</div>
		<div style="overflow-x:auto;">
		<table style="border-collapse:collapse;min-width:1000px;width:100%;font-size:11px;">
			<thead>
				<tr>
					${th("Combo Item")}${th("Colour")}${th("Article")}${th("Order Qty")}
					${th_s("✂ Cut Done")}${th_s("Cut Left")}${th_s("Cut %")}${th_s("Avg/d")}
					${th_s("🪡 Stitch Done")}${th_s("Stitch Left")}${th_s("Stitch %")}${th_s("Avg/d")}
					${th_s("✔ Check Done")}${th_s("Check Left")}${th_s("Check %")}${th_s("Avg/d")}
					${th_s("📦 Pack Done")}${th_s("Pack Left")}${th_s("Pack %")}${th_s("Avg/d")}
				</tr>
			</thead>
			<tbody>${rows_html}</tbody>
		</table>
		</div>`;
}
