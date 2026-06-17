// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

init_report_style_contractors({
    parent_doctype: "Checking Report",
    ct_doctype: "Checking Report CT",
    ct_fieldname: "checking_report_ct",
    contractor_filter: { checking: 1 },
    operation: "Checking",
    api_method:
        "manufacturing_addon.manufacturing_addon.doctype.checking_report.checking_report.get_style_contractors_for_line",
});

frappe.ui.form.on("Checking Report", {
    refresh(frm) {
        render_checking_article_summary(frm);
    },

    checking_report_ct(frm) {
        render_checking_article_summary(frm);
    },

    get_data(frm) {
        console.log("[Checking Report JS] get_data called");
        console.log("[Checking Report JS] Order Sheet:", frm.doc.order_sheet);

        if (!frm.doc.order_sheet) {
            frappe.msgprint(__("Please select an Order Sheet first."));
            return;
        }

        frm.call({
            method: "get_data1",
            doc: frm.doc,
            args: {},
            freeze: true,
            freeze_message: __("Fetching data from Order Sheet..."),
            callback: function (r) {
                console.log("[Checking Report JS] get_data1 response:", r);
                if (r.message) {
                    console.log("[Checking Report JS] Success");
                }
                frm.reload_doc();
            },
            error: function (r) {
                console.error("[Checking Report JS] Error:", r);
                frappe.msgprint(__("Error fetching data: {0}", [r.message || r.exc]));
            },
        });
    },
});

frappe.ui.form.on("Checking Report CT", {
    checking_qty(frm) {
        render_checking_article_summary(frm);
    },
});

function render_checking_article_summary(frm) {
    const wrapper = frm.fields_dict.checking_article_summary && frm.fields_dict.checking_article_summary.$wrapper;
    if (!wrapper) return;

    const rows = frm.doc.checking_report_ct || [];
    if (!rows.length) {
        wrapper.html(
            `<div class="text-muted" style="padding:12px;">${__("No rows available for article-wise summary.")}</div>`
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
                finished_stitched_qty: 0,
                finished_checked_qty: 0,
                checking_qty: 0,
                total_till_now: 0,
            };
        }
        grouped[article].order_qty += flt_local(row.order_qty);
        grouped[article].planned_qty += flt_local(row.planned_qty);
        grouped[article].finished_stitched_qty += flt_local(row.finished_stitched_qty);
        grouped[article].finished_checked_qty += flt_local(row.finished_checked_qty);
        grouped[article].checking_qty += flt_local(row.checking_qty);
        grouped[article].total_till_now += flt_local(row.total_copy1);
    }

    const list = Object.values(grouped);
    const grand = list.reduce(
        (acc, r) => {
            acc.order_qty += r.order_qty;
            acc.planned_qty += r.planned_qty;
            acc.finished_stitched_qty += r.finished_stitched_qty;
            acc.finished_checked_qty += r.finished_checked_qty;
            acc.checking_qty += r.checking_qty;
            acc.total_till_now += r.total_till_now;
            return acc;
        },
        {
            order_qty: 0,
            planned_qty: 0,
            finished_stitched_qty: 0,
            finished_checked_qty: 0,
            checking_qty: 0,
            total_till_now: 0,
        }
    );

    wrapper.html(`
        <div style="margin-top:8px;">
            <div class="text-muted small" style="margin-bottom:8px;">
                ${__("Article-wise summary")}
            </div>
            <div class="table-responsive">
                <table class="table table-bordered table-sm" style="margin-bottom:0;">
                    <thead>
                        <tr>
                            <th>${__("Article")}</th>
                            <th class="text-right">${__("Order Qty")}</th>
                            <th class="text-right">${__("Planned Qty")}</th>
                            <th class="text-right">${__("Stitched")}</th>
                            <th class="text-right">${__("Checked")}</th>
                            <th class="text-right">${__("Checking Qty")}</th>
                            <th class="text-right">${__("Total Till Now")}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${list
                            .map(
                                (r) => `
                            <tr>
                                <td>${frappe.utils.escape_html(r.article)}</td>
                                <td class="text-right">${format_num(r.order_qty)}</td>
                                <td class="text-right">${format_num(r.planned_qty)}</td>
                                <td class="text-right">${format_num(r.finished_stitched_qty)}</td>
                                <td class="text-right">${format_num(r.finished_checked_qty)}</td>
                                <td class="text-right">${format_num(r.checking_qty)}</td>
                                <td class="text-right"><b>${format_num(r.total_till_now)}</b></td>
                            </tr>`
                            )
                            .join("")}
                        <tr style="background:#f8f9fa;font-weight:600;">
                            <td>${__("Total")}</td>
                            <td class="text-right">${format_num(grand.order_qty)}</td>
                            <td class="text-right">${format_num(grand.planned_qty)}</td>
                            <td class="text-right">${format_num(grand.finished_stitched_qty)}</td>
                            <td class="text-right">${format_num(grand.finished_checked_qty)}</td>
                            <td class="text-right">${format_num(grand.checking_qty)}</td>
                            <td class="text-right">${format_num(grand.total_till_now)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    `);
}

function flt_local(value) {
    return Number(value || 0) || 0;
}

function format_num(value) {
    return flt_local(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}
