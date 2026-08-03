// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

(function () {
	const config = {
		parent_doctype: "Sub Assembly Report",
		ct_doctype: "Sub Assembly Report CT",
		ct_fieldname: "sub_assembly_report_ct",
		contractor_filter: { sub_assembly: 1 },
		operation: "Sub Assembly",
		work_qty_field: "sub_assembly_qty",
		api_method:
			"manufacturing_addon.manufacturing_addon.doctype.sub_assembly_report.sub_assembly_report.get_style_contractors_for_line",
	};

	function boot_style_contractors() {
		if (typeof init_report_style_contractors === "function") {
			init_report_style_contractors(config);
			return;
		}
		// Shared hook script may still be appending; retry briefly.
		setTimeout(boot_style_contractors, 50);
	}

	boot_style_contractors();
})();

frappe.ui.form.on("Sub Assembly Report", {
	setup(frm) {
		frm.set_query("supplier", () => ({
			filters: { sub_assembly: 1 },
		}));
	},

	refresh(frm) {
		frm.page.set_title(__("Sub Assembly Report"));
		render_article_wise_summary(frm);
		if (!frm.is_new() && frm.doc.order_sheet) {
			frm.add_custom_button(__("Repair Missing Rows"), () => frm.events.repair_missing_rows(frm));
		}
	},

	sub_assembly_report_ct(frm) {
		render_article_wise_summary(frm);
	},

	get_data(frm) {
		if (!frm.doc.order_sheet) {
			frappe.msgprint(__("Please select an Order Sheet first."));
			return;
		}
		if (!frm.doc.supplier) {
			frappe.msgprint(__("Please select a Supplier first."));
			return;
		}

		frm.call({
			method: "get_data1",
			doc: frm.doc,
			args: {},
			freeze: true,
			freeze_message: __("Fetching sub assembly lines from Order Sheet..."),
			callback: function () {
				frm.reload_doc();
			},
			error: function (r) {
				frappe.msgprint(__("Error fetching data: {0}", [r.message || r.exc]));
			},
		});
	},

	repair_missing_rows(frm) {
		if (frm.doc.docstatus === 1) {
			frappe.msgprint(
				__("Cancel and amend this Sub Assembly Report first, then use Repair Missing Rows.")
			);
			return;
		}
		frm.call({
			method:
				"manufacturing_addon.manufacturing_addon.doctype.sub_assembly_report.sub_assembly_report.repair_missing_combo_rows",
			args: { docname: frm.doc.name },
			freeze: true,
			freeze_message: __("Adding missing combo rows..."),
			callback(r) {
				const count = (r.message && r.message.added_count) || 0;
				frappe.show_alert({
					message: count
						? __("Added {0} missing row(s).", [count])
						: __("No missing rows found."),
					indicator: count ? "green" : "blue",
				});
				frm.reload_doc();
			},
		});
	},
});

frappe.ui.form.on("Sub Assembly Report CT", {
	sub_assembly_qty(frm) {
		render_article_wise_summary(frm);
	},
});

function render_article_wise_summary(frm) {
	const wrapper = frm.fields_dict.article_wise_report && frm.fields_dict.article_wise_report.$wrapper;
	if (!wrapper) return;

	const rows = frm.doc.sub_assembly_report_ct || [];
	if (!rows.length) {
		wrapper.html(
			`<div class="text-muted" style="padding:12px;">${__("No rows available for article-wise summary. Select Order Sheet + Supplier, then click Get Data.")}</div>`
		);
		return;
	}

	const grouped = {};
	for (const row of rows) {
		const article = (row.article || row.combo_item || row.so_item || __("Unspecified")).trim();
		if (!grouped[article]) {
			grouped[article] = {
				article,
				order_qty: 0,
				planned_qty: 0,
				finished_sub_assembly_qty: 0,
				sub_assembly_qty: 0,
				total_till_now: 0,
			};
		}
		grouped[article].order_qty += flt_local(row.order_qty);
		grouped[article].planned_qty += flt_local(row.planned_qty);
		grouped[article].finished_sub_assembly_qty += flt_local(row.finished_sub_assembly_qty);
		grouped[article].sub_assembly_qty += flt_local(row.sub_assembly_qty);
		grouped[article].total_till_now += flt_local(row.total_copy1);
	}

	const list = Object.values(grouped).sort((a, b) => a.article.localeCompare(b.article));
	const grand = list.reduce(
		(acc, r) => {
			acc.order_qty += r.order_qty;
			acc.planned_qty += r.planned_qty;
			acc.finished_sub_assembly_qty += r.finished_sub_assembly_qty;
			acc.sub_assembly_qty += r.sub_assembly_qty;
			acc.total_till_now += r.total_till_now;
			return acc;
		},
		{ order_qty: 0, planned_qty: 0, finished_sub_assembly_qty: 0, sub_assembly_qty: 0, total_till_now: 0 }
	);

	const html = `
		<div style="margin-top:8px;">
			<div class="text-muted small" style="margin-bottom:8px;">
				${__("Article-wise summary totals from current Sub Assembly Report rows")}
			</div>
			<div class="table-responsive">
				<table class="table table-bordered table-sm" style="margin-bottom:0;">
					<thead>
						<tr>
							<th>${__("Article")}</th>
							<th class="text-right">${__("Order Qty")}</th>
							<th class="text-right">${__("Planned Qty")}</th>
							<th class="text-right">${__("Total Sub Assembly Till Now")}</th>
						</tr>
					</thead>
					<tbody>
						${list
							.map(
								(r) => `
							<tr>
								<td>${frappe.utils.escape_html(r.article)}</td>
								<td class="text-right">${fmt_num(r.order_qty)}</td>
								<td class="text-right">${fmt_num(r.planned_qty)}</td>
								<td class="text-right"><b>${fmt_num(r.total_till_now)}</b></td>
							</tr>`
							)
							.join("")}
						<tr style="background:#f8f9fa;font-weight:600;">
							<td>${__("Grand Total")}</td>
							<td class="text-right">${fmt_num(grand.order_qty)}</td>
							<td class="text-right">${fmt_num(grand.planned_qty)}</td>
							<td class="text-right">${fmt_num(grand.total_till_now)}</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	`;

	wrapper.html(html);
}

function flt_local(value) {
	const n = Number(value);
	return Number.isFinite(n) ? n : 0;
}

function fmt_num(value) {
	return flt_local(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}
