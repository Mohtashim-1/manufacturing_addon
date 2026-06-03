// Sales Order — Connection Dashboard tab (cutting / stitching progress + linked reports)

const salesOrderConnectionDashboard = {
	render(frm) {
		const $wrapper = frm.fields_dict.custom_connections?.$wrapper;
		if (!$wrapper || frm.is_new()) return;

		$wrapper.html(`
			<div class="so-mfg-dashboard">
				<div class="text-center text-muted p-4">
					<i class="fa fa-spinner fa-spin"></i> ${__("Loading manufacturing dashboard...")}
				</div>
			</div>
		`);

		frappe.call({
			method:
				"manufacturing_addon.manufacturing_addon.doctype.sales_order.sales_order_connection_dashboard.get_sales_order_connection_dashboard",
			args: { sales_order: frm.doc.name },
			callback: (r) => this.paint(frm, $wrapper, r.message || {}),
			error: () => {
				$wrapper.html(
					`<div class="alert alert-warning">${__("Could not load manufacturing dashboard.")}</div>`
				);
			},
		});
	},

	paint(frm, $wrapper, data) {
		const s = data.summary || {};
		const pct = (n) => (Number(n) || 0).toFixed(1);

		const progressBar = (label, progress, finished, planned, barClass) => {
			const p = Math.min(Number(progress) || 0, 100);
			return `
				<div class="so-mfg-progress-block">
					<div class="d-flex justify-content-between mb-1">
						<strong>${label}</strong>
						<span>${pct(p)}% <small class="text-muted">(${this.fmt(finished)} / ${this.fmt(planned)})</small></span>
					</div>
					<div class="progress" style="height:26px;border-radius:8px;">
						<div class="progress-bar ${barClass}" style="width:${p}%;min-width:${p > 0 ? "2em" : "0"};">
							${p >= 8 ? `${pct(p)}%` : ""}
						</div>
					</div>
				</div>`;
		};

		$wrapper.find(".so-mfg-dashboard").html(`
			<style>
				.so-mfg-dashboard { padding: 8px 4px 20px; }
				.so-mfg-dashboard .so-mfg-card {
					background:#fff;border:1px solid #e6e9ef;border-radius:10px;
					box-shadow:0 2px 8px rgba(0,0,0,.06);padding:16px;margin-bottom:16px;
				}
				.so-mfg-dashboard .so-mfg-card h5 { margin:0 0 12px; color:#334155; font-weight:600; }
				.so-mfg-dashboard .so-mfg-progress-block { margin-bottom:14px; }
				.so-mfg-dashboard .so-mfg-table { width:100%; font-size:12px; }
				.so-mfg-dashboard .so-mfg-table th { background:#f8fafc; font-weight:600; }
				.so-mfg-dashboard .so-mfg-badge {
					display:inline-block;background:#eef2ff;color:#1d4ed8;border-radius:999px;
					font-size:11px;padding:2px 8px;margin-left:6px;
				}
			</style>
			<div class="d-flex justify-content-between align-items-center mb-3">
				<div>
					<h5 class="mb-0">${__("Manufacturing Dashboard")}</h5>
					<small class="text-muted">${__("Cutting, stitching, and packing for this Sales Order")}</small>
				</div>
				<div>
					<a class="btn btn-default btn-sm" href="/app/order-tracking?sales_order=${encodeURIComponent(data.sales_order || "")}" target="_blank">
						${__("Order Tracking")}
					</a>
					<button type="button" class="btn btn-default btn-sm so-mfg-refresh">${__("Refresh")}</button>
				</div>
			</div>
			<div class="so-mfg-card">
				<h5><i class="fa fa-line-chart"></i> ${__("Production Progress")}</h5>
				${progressBar(__("Cutting"), s.cutting_progress, s.cutting_finished, s.cutting_planned, "bg-info")}
				${progressBar(__("Stitching"), s.stitching_progress, s.stitching_finished, s.stitching_planned, "bg-warning")}
				${progressBar(__("Packing"), s.packing_progress, s.packing_finished, s.packing_planned, "bg-success")}
				<div class="mt-2 text-muted small">
					${__("Order Sheets")}: <strong>${s.total_orders || 0}</strong> ·
					${__("Planned Qty")}: <strong>${this.fmt(s.total_planned_qty)}</strong> ·
					${__("Overall")}: <strong>${pct(s.overall_progress)}%</strong>
				</div>
			</div>
			${this.tableSection(__("Order Sheets"), data.order_sheets_count, data.order_sheet_rows || [], [
				{ key: "name", label: __("Name"), doctype: "Order Sheet" },
				{ key: "customer", label: __("Customer") },
				{ key: "date", label: __("Date") },
				{ key: "shipment_date", label: __("Shipment") },
			])}
			${this.tableSection(__("Cutting Reports"), data.cutting_reports_count, data.cutting_report_rows || [], [
				{ key: "name", label: __("Name"), doctype: "Cutting Report" },
				{ key: "date", label: __("Date") },
				{ key: "order_sheet", label: __("Order Sheet"), doctype: "Order Sheet" },
				{ key: "supplier", label: __("Supplier") },
			])}
			${this.tableSection(__("Stitching Reports"), data.stitching_reports_count, data.stitching_report_rows || [], [
				{ key: "name", label: __("Name"), doctype: "Stitching Report" },
				{ key: "date", label: __("Date") },
				{ key: "order_sheet", label: __("Order Sheet"), doctype: "Order Sheet" },
				{ key: "supplier", label: __("Supplier") },
			])}
			${this.tableSection(__("Packing Reports"), data.packing_reports_count, data.packing_report_rows || [], [
				{ key: "name", label: __("Name"), doctype: "Packing Report" },
				{ key: "date", label: __("Date") },
				{ key: "order_sheet", label: __("Order Sheet"), doctype: "Order Sheet" },
				{ key: "supplier", label: __("Supplier") },
			])}
		`);

		$wrapper.find(".so-mfg-refresh").on("click", () => this.render(frm));
	},

	tableSection(title, count, rows, columns) {
		const route = (doctype, name) =>
			`/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name || "")}`;

		const ths = columns.map((c) => `<th>${c.label}</th>`).join("");
		const trs = (rows || [])
			.map((row) => {
				const tds = columns
					.map((c) => {
						let val = row[c.key] ?? "";
						if (c.doctype && val) {
							val = `<a href="${route(c.doctype, val)}" target="_blank">${frappe.utils.escape_html(val)}</a>`;
						} else {
							val = frappe.utils.escape_html(String(val));
						}
						return `<td>${val}</td>`;
					})
					.join("");
				return `<tr>${tds}</tr>`;
			})
			.join("");

		return `
			<div class="so-mfg-card">
				<h5>${title}<span class="so-mfg-badge">${count || 0}</span></h5>
				<div class="table-responsive">
					<table class="table table-bordered table-sm table-hover so-mfg-table mb-0">
						<thead><tr>${ths}</tr></thead>
						<tbody>${trs || `<tr><td colspan="${columns.length}" class="text-muted text-center">${__("None")}</td></tr>`}</tbody>
					</table>
				</div>
			</div>`;
	},

	fmt(n) {
		return frappe.format(n || 0, { fieldtype: "Float", precision: 0 });
	},
};

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (!frm.is_new() && frm.fields_dict.custom_connections) {
			salesOrderConnectionDashboard.render(frm);
		}
	},
});
