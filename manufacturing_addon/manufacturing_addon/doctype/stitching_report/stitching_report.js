// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Stitching Report", {
    refresh(frm) {
        render_stitching_article_summary(frm);
    },

    stitching_report_ct(frm) {
        render_stitching_article_summary(frm);
    },

    get_data(frm){
        console.log("[Stitching Report JS] get_data called");
        console.log("[Stitching Report JS] Order Sheet:", frm.doc.order_sheet);
        
        if (!frm.doc.order_sheet) {
            frappe.msgprint(__("Please select an Order Sheet first."));
            return;
        }
        
        frm.call({
            method:"get_data1",
            doc: frm.doc,
            args: {},
            freeze: true,
            freeze_message: __("Fetching data from Order Sheet..."),
            callback: function(r) {
                console.log("[Stitching Report JS] get_data1 response:", r);
                if (r.message) {
                    console.log("[Stitching Report JS] Success");
                }
                frm.reload_doc();
            },
            error: function(r) {
                console.error("[Stitching Report JS] Error:", r);
                frappe.msgprint(__("Error fetching data: {0}", [r.message || r.exc]));
            }
        });
    },
});

frappe.ui.form.on("Stitching Report CT", {
    stitching_qty(frm) {
        render_stitching_article_summary(frm);
    },
});

function render_stitching_article_summary(frm) {
    const wrapper = frm.fields_dict.stitching_article_summary && frm.fields_dict.stitching_article_summary.$wrapper;
    if (!wrapper) return;

    const rows = frm.doc.stitching_report_ct || [];
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
                total_till_now: 0,
            };
        }
        grouped[article].order_qty += to_num(row.order_qty);
        grouped[article].planned_qty += to_num(row.planned_qty);
        grouped[article].total_till_now += to_num(row.total_copy1);
    }

    const list = Object.values(grouped).sort((a, b) => a.article.localeCompare(b.article));
    const grand = list.reduce(
        (acc, r) => {
            acc.order_qty += r.order_qty;
            acc.planned_qty += r.planned_qty;
            acc.total_till_now += r.total_till_now;
            return acc;
        },
        { order_qty: 0, planned_qty: 0, total_till_now: 0 }
    );

    const html = `
        <div style="margin-top:8px;">
            <div class="text-muted small" style="margin-bottom:8px;">
                ${__("Article-wise summary totals from current Stitching Report rows")}
            </div>
            <div class="table-responsive">
                <table class="table table-bordered table-sm" style="margin-bottom:0;">
                    <thead>
                        <tr>
                            <th>${__("Article")}</th>
                            <th class="text-right">${__("Order Qty")}</th>
                            <th class="text-right">${__("Planned Qty")}</th>
                            <th class="text-right">${__("Total Stitching Till Now")}</th>
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
                                <td class="text-right"><b>${format_num(r.total_till_now)}</b></td>
                            </tr>`
                            )
                            .join("")}
                        <tr style="background:#f8f9fa;font-weight:600;">
                            <td>${__("Grand Total")}</td>
                            <td class="text-right">${format_num(grand.order_qty)}</td>
                            <td class="text-right">${format_num(grand.planned_qty)}</td>
                            <td class="text-right">${format_num(grand.total_till_now)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;

    wrapper.html(html);
}

function to_num(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
}

function format_num(value) {
    return to_num(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}
