// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

const SC_DEBUG = true;
const NESTED_STYLE_DOCTYPE = "Report Style Contractor";

function sc_log(...args) {
    if (SC_DEBUG) {
        console.log("[style_contractors]", ...args);
    }
}

function style_contractor_meta_ready() {
    return Boolean(
        frappe.meta.docfield_list[NESTED_STYLE_DOCTYPE]?.length ||
            frappe.get_meta(NESTED_STYLE_DOCTYPE)?.fields?.length
    );
}

function with_style_contractor_meta(callback) {
    if (style_contractor_meta_ready()) {
        sc_log("meta: already loaded", {
            docfield_count: frappe.meta.docfield_list[NESTED_STYLE_DOCTYPE]?.length || 0,
        });
        callback();
        return;
    }

    sc_log("meta: fetching", NESTED_STYLE_DOCTYPE);
    frappe.model.with_doctype(NESTED_STYLE_DOCTYPE, () => {
        sc_log("meta: loaded", {
            docfield_count: frappe.meta.docfield_list[NESTED_STYLE_DOCTYPE]?.length || 0,
            field_names: (frappe.meta.docfield_list[NESTED_STYLE_DOCTYPE] || []).map(
                (d) => d.fieldname
            ),
        });
        callback();
    });
}

function preload_style_contractor_meta() {
    with_style_contractor_meta(() => {});
}

frappe.ui.form.on("Stitching Report", {
    onload(frm) {
        preload_style_contractor_meta();
        bind_style_contractor_model_sync(frm);
    },
    refresh(frm) {
        preload_style_contractor_meta();
        bind_style_contractor_model_sync(frm);
        (frm.doc.stitching_report_ct || []).forEach((ct_row) => {
            const local_row = locals["Stitching Report CT"]?.[ct_row.name];
            if (local_row) {
                ensure_style_contractors_in_locals(local_row);
            }
        });
        render_stitching_article_summary(frm);
        if (!frm.is_new()) {
            frm.add_custom_button(__("Load Style Contractors"), () => {
                frm.call({
                    method: "load_style_contractors",
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __("Loading style contractors from Item..."),
                    callback() {
                        frm.reload_doc();
                        frappe.show_alert({
                            message: __("Style contractors updated from Item master."),
                            indicator: "green",
                        });
                    },
                });
            }, __("Actions"));
        }
    },

    before_save(frm) {
        frappe._from_link = null;
        snapshot_style_contractors(frm);
        sync_all_style_contractors_to_frm_doc(frm);
    },

    after_save(frm) {
        restore_style_contractors_after_save(frm);
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
    stitching_qty(frm, cdt, cdn) {
        recalc_stitching_subassembly_style_contractors(frm, cdt, cdn);
        render_stitching_article_summary(frm);
    },
    form_render(frm, cdt, cdn) {
        sc_log("form_render", { cdt, cdn, idx: locals[cdt]?.[cdn]?.idx });
        with_style_contractor_meta(() => {
            setTimeout(() => {
                setup_style_contractors_panel(frm, cdt, cdn);
                // Recalc zip/button qty = BOM unit × stitching entry when opening the row.
                recalc_stitching_subassembly_style_contractors(frm, cdt, cdn);
            }, 0);
        });
    },
});

frappe.ui.form.on("Report Style Contractor", {
    async split_qty(frm, cdt, cdn) {
        const row = locals[cdt]?.[cdn];
        const ct_row = locals["Stitching Report CT"]?.[row?.parent];
        if (is_subassembly_row(row)) {
            const unit_qty = await ensure_subassembly_unit_qty(row, ct_row?.so_item);
            const split_work = Number(row.split_qty || 0) || Number(ct_row?.stitching_qty || 0) || 0;
            row.qty = split_work > 0 ? split_work * unit_qty : unit_qty;
            row.amount = row.qty * (Number(row.rate || 0) || 0);
            row.is_subassembly = 1;
            row.unit_qty = unit_qty;
        } else {
            row.amount = (Number(row.split_qty || 0) || 0) * (Number(row.rate || 0) || 0);
        }
        sync_style_contractor_to_parent_frm(frm, cdt, cdn);
        refresh_nested_style_contractor_grid(frm, row?.parent);
    },
    qty(frm, cdt, cdn) {
        // User can override calculated qty; keep amount in sync.
        update_report_style_amount(cdt, cdn);
        sync_style_contractor_to_parent_frm(frm, cdt, cdn);
    },
    rate(frm, cdt, cdn) {
        update_report_style_amount(cdt, cdn);
        sync_style_contractor_to_parent_frm(frm, cdt, cdn);
    },
    contractor(frm, cdt, cdn) {
        sync_style_contractor_to_parent_frm(frm, cdt, cdn);
        const row = locals[cdt][cdn];
        if (row.is_mandatory && !row.contractor) {
            frappe.show_alert({
                message: __("This style is mandatory — please select a contractor."),
                indicator: "orange",
            });
        }
    },
});

function bind_style_contractor_model_sync(frm) {
    if (frm._style_contractor_model_bound) {
        return;
    }
    frm._style_contractor_model_bound = true;

    frappe.model.on(NESTED_STYLE_DOCTYPE, "*", function (fieldname, value, doc) {
        const ct_row = locals["Stitching Report CT"]?.[doc?.parent];
        if (!ct_row || ct_row.parent !== frm.docname) {
            return;
        }

        if (["qty", "rate"].includes(fieldname)) {
            update_report_style_amount(doc.doctype, doc.name);
        }
        sync_style_contractors_to_frm_doc(frm, doc.parent, ct_row);
        frm.dirty();
    });
}

function ensure_style_contractors_in_locals(ct_row) {
    if (!ct_row?.style_contractors?.length) {
        return;
    }

    if (!locals[NESTED_STYLE_DOCTYPE]) {
        locals[NESTED_STYLE_DOCTYPE] = {};
    }

    ct_row.style_contractors.forEach((sc) => {
        if (!sc) {
            return;
        }

        sc.doctype = sc.doctype || NESTED_STYLE_DOCTYPE;
        sc.parent = sc.parent || ct_row.name;
        sc.parenttype = sc.parenttype || "Stitching Report CT";
        sc.parentfield = sc.parentfield || "style_contractors";

        if (sc.name) {
            locals[NESTED_STYLE_DOCTYPE][sc.name] = sc;
        }
    });
}

function sync_style_contractors_from_frm_doc(frm, cdt, cdn) {
    const row = locals[cdt]?.[cdn];
    if (!row) {
        return 0;
    }

    if ((row.style_contractors || []).length) {
        return row.style_contractors.length;
    }

    const frm_row = (frm.doc.stitching_report_ct || []).find((r) => r.name === cdn);
    if (!frm_row?.style_contractors?.length) {
        return 0;
    }

    row.style_contractors = frm_row.style_contractors;
    ensure_style_contractors_in_locals(row);

    sc_log("synced style_contractors from frm.doc", {
        cdn,
        count: row.style_contractors.length,
        contractors: row.style_contractors.map((sc) => sc.contractor),
    });
    return row.style_contractors.length;
}

function setup_style_contractors_panel(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    sync_style_contractors_from_frm_doc(frm, cdt, cdn);
    ensure_style_contractors_in_locals(row);
    const nested_ctx = get_nested_style_contractor_context(frm, cdn);

    sc_log("setup_style_contractors_panel", {
        row_name: cdn,
        so_item: row?.so_item,
        combo_item: row?.combo_item,
        article: row?.article,
        existing_rows: (row?.style_contractors || []).length,
        nested_ctx,
    });

    if (!row?.so_item) {
        sc_log("skip: no so_item on CT row");
        return;
    }

    bind_style_contractor_grid(frm, cdt, cdn, nested_ctx);

    if ((row.style_contractors || []).length) {
        sc_log("already has style_contractors, refreshing nested grid only");
        refresh_nested_style_contractor_grid(frm, cdn, nested_ctx);
        return;
    }

    ensure_style_contractors_for_row(frm, cdt, cdn, nested_ctx);
}

function get_nested_style_contractor_context(frm, cdn) {
    const grid = frm.fields_dict.stitching_report_ct?.grid;
    const grid_row = grid?.grid_rows_by_docname?.[cdn];
    const nested_control = grid_row?.grid_form?.fields_dict?.style_contractors;
    const nested_grid = nested_control?.grid;

    return {
        has_parent_grid: !!grid,
        has_grid_row: !!grid_row,
        has_grid_form: !!grid_row?.grid_form,
        has_nested_control: !!nested_control,
        has_nested_grid: !!nested_grid,
        nested_doctype: nested_grid?.doctype,
        nested_docfields_count: nested_grid?.docfields?.length || 0,
        nested_visible_columns_count: nested_grid?.visible_columns?.length || 0,
        nested_data_count: nested_grid?.data?.length || 0,
        nested_df_fieldname: nested_grid?.df?.fieldname,
        nested_df_options: nested_grid?.df?.options,
    };
}

function ensure_style_contractors_for_row(frm, cdt, cdn, nested_ctx) {
    const row = locals[cdt][cdn];
    sync_style_contractors_from_frm_doc(frm, cdt, cdn);

    if (!row?.so_item) {
        sc_log("ensure: skip, no so_item");
        return;
    }
    if ((row.style_contractors || []).length) {
        sc_log("ensure: skip, already populated", row.style_contractors.length);
        refresh_nested_style_contractor_grid(frm, cdn, nested_ctx);
        return;
    }

    sc_log("ensure: fetching defaults from server (no saved rows)", {
        so_item: row.so_item,
        combo_item: row.combo_item,
        article: row.article,
    });

    frappe.call({
        method:
            "manufacturing_addon.manufacturing_addon.doctype.stitching_report.stitching_report.get_style_contractors_for_line",
        args: {
            so_item: row.so_item,
            combo_item: row.combo_item,
            article: row.article,
            work_qty: Number(row.stitching_qty || 0) || 0,
        },
        callback(r) {
            sc_log("ensure: server response", r);
            const styles = r.message || [];
            if (!styles.length) {
                sc_log("ensure: no styles returned for this line");
                return;
            }

            if ((row.style_contractors || []).length) {
                sc_log("ensure: rows added while waiting, skip insert");
                refresh_nested_style_contractor_grid(frm, cdn);
                return;
            }

            styles.forEach((sc, i) => {
                const child = frappe.model.add_child(row, "style_contractors");
                Object.assign(child, sc);
                sc_log("ensure: added child", i + 1, child);
            });

            recalc_stitching_subassembly_style_contractors(frm, cdt, cdn);
            sync_style_contractors_to_frm_doc(frm, cdn, row);
            sc_log("ensure: row.style_contractors count", row.style_contractors.length);
            refresh_nested_style_contractor_grid(frm, cdn);
            frm.dirty();
        },
        error(r) {
            console.error("[style_contractors] ensure: API error", r);
        },
    });
}

function sync_style_contractors_to_frm_doc(frm, cdn, row) {
    const frm_row = (frm.doc.stitching_report_ct || []).find((r) => r.name === cdn);
    if (frm_row) {
        frm_row.style_contractors = row.style_contractors;
    }
}

function snapshot_style_contractors(frm) {
    frm._style_contractors_snapshot = {};
    (frm.doc.stitching_report_ct || []).forEach((ct_row) => {
        const local_row = locals["Stitching Report CT"]?.[ct_row.name];
        const rows = local_row?.style_contractors || ct_row.style_contractors;
        if (rows?.length) {
            frm._style_contractors_snapshot[ct_row.name] = frappe.utils.deep_clone(rows);
        }
    });
}

function sync_all_style_contractors_to_frm_doc(frm) {
    (frm.doc.stitching_report_ct || []).forEach((ct_row) => {
        const local_row = locals["Stitching Report CT"]?.[ct_row.name];
        if (local_row?.style_contractors?.length) {
            ct_row.style_contractors = frappe.utils.deep_clone(local_row.style_contractors);
            sc_log("before_save: synced CT row", ct_row.name, {
                count: ct_row.style_contractors.length,
                qtys: ct_row.style_contractors.map((r) => r.qty),
            });
        }
    });
}

function sync_style_contractor_to_parent_frm(frm, cdt, cdn) {
    const row = locals[cdt]?.[cdn];
    if (!row?.parent || !frm) {
        return;
    }
    const ct_row = locals["Stitching Report CT"]?.[row.parent];
    if (!ct_row) {
        return;
    }
    sync_style_contractors_to_frm_doc(frm, row.parent, ct_row);
    frm.dirty();
}

function restore_style_contractors_after_save(frm) {
    const snapshot = frm._style_contractors_snapshot || {};
    (frm.doc.stitching_report_ct || []).forEach((ct_row) => {
        const local_row = locals["Stitching Report CT"]?.[ct_row.name];
        if (!local_row) {
            return;
        }

        const rows = snapshot[ct_row.name]?.length
            ? frappe.utils.deep_clone(snapshot[ct_row.name])
            : ct_row.style_contractors;

        if (!rows?.length) {
            return;
        }

        ct_row.style_contractors = rows;
        local_row.style_contractors = rows;
        ensure_style_contractors_in_locals(local_row);
        sc_log("after_save: restored style_contractors", ct_row.name, {
            count: rows.length,
            qtys: rows.map((r) => r.qty),
        });
    });
    delete frm._style_contractors_snapshot;
}

function refresh_nested_style_contractor_grid(frm, cdn, nested_ctx) {
    const grid = frm.fields_dict.stitching_report_ct?.grid;
    const grid_row = grid?.grid_rows_by_docname?.[cdn];
    const nested_control = grid_row?.grid_form?.fields_dict?.style_contractors;
    const row = locals["Stitching Report CT"]?.[cdn];

    sc_log("refresh_nested_grid", {
        cdn,
        row_style_count: (row?.style_contractors || []).length,
        has_nested_control: !!nested_control,
        has_nested_grid: !!nested_control?.grid,
        before: nested_ctx || get_nested_style_contractor_context(frm, cdn),
    });

    if (!nested_control?.grid) {
        sc_log("refresh_nested_grid: nested grid not found — grid form may not be open yet");
        return;
    }

    ensure_style_contractors_in_locals(row);

    const nested_grid = nested_control.grid;
    nested_grid.visible_columns = null;
    nested_control.doc = row;
    nested_grid.setup_fields();
    nested_grid.setup_visible_columns();
    nested_grid.refresh();

    sc_log("refresh_nested_grid: after refresh", get_nested_style_contractor_context(frm, cdn));
}

function bind_style_contractor_grid(frm, cdt, cdn, nested_ctx) {
    const grid = frm.fields_dict.stitching_report_ct?.grid;
    if (!grid) {
        sc_log("bind: no parent grid");
        return;
    }
    const row = locals[cdt][cdn];
    const grid_row = grid.grid_rows_by_docname?.[cdn];
    const nested = grid_row?.grid_form?.fields_dict?.style_contractors?.grid;
    if (!nested) {
        sc_log("bind: nested grid missing", nested_ctx || get_nested_style_contractor_context(frm, cdn));
        return;
    }
    if (nested._style_contractor_bound) {
        sc_log("bind: already bound");
        return;
    }
    nested._style_contractor_bound = true;
    const contractor_df = frappe.meta.get_docfield("Report Style Contractor", "contractor");
    if (contractor_df) {
        contractor_df.get_query = () => ({
            filters: { stitching: 1 },
        });
    }
    nested.add_custom_button(__("Split Contractor"), () => {
        const selected = nested.get_selected();
        if (selected?.length !== 1) {
            frappe.msgprint(__("Select one style row to split between contractors."));
            return;
        }
        const source = locals[NESTED_STYLE_DOCTYPE]?.[selected[0]];
        const ct_row = locals[cdt]?.[cdn];
        if (!source?.style || !ct_row) {
            return;
        }
        const child = frappe.model.add_child(ct_row, "style_contractors");
        Object.assign(child, {
            style: source.style,
            rate: source.rate,
            unit_qty: source.unit_qty,
            is_subassembly: source.is_subassembly,
            is_mandatory: source.is_mandatory,
            operation: source.operation,
            combo_item: source.combo_item,
            item_style_row: source.item_style_row,
            contractor: "",
            split_qty: 0,
            qty: 0,
            amount: 0,
        });
        sync_style_contractors_to_frm_doc(frm, cdn, ct_row);
        refresh_nested_style_contractor_grid(frm, cdn);
        frm.dirty();
    });
}

function update_report_style_amount(cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row) return;
    const qty = Number(row.qty || 1) || 1;
    const rate = Number(row.rate || 0) || 0;
    frappe.model.set_value(cdt, cdn, "amount", qty * rate);
}

function is_subassembly_style_name(styleName) {
    const name = String(styleName || "").toUpperCase();
    return name.includes("ZIP") || name.includes("BUTTON") || name.includes("SUB");
}

function is_subassembly_row(sc) {
    return Boolean(sc?.is_subassembly) || is_subassembly_style_name(sc?.style);
}

async function ensure_subassembly_unit_qty(sc, so_item) {
    if (!is_subassembly_row(sc)) {
        return Number(sc.unit_qty || 0) || 1;
    }
    // Prefer live BOM qty so Item Style qty=1 does not stick as unit_qty
    if (so_item && sc.style) {
        try {
            const res = await frappe.xcall(
                "manufacturing_addon.manufacturing_addon.utils.subassembly_bom.get_subassembly_bom_qty",
                { item_code: so_item, style_name: sc.style }
            );
            const unit = Number(res?.qty_per_unit || 0);
            if (unit > 0) {
                sc.unit_qty = unit;
                sc.is_subassembly = 1;
                return unit;
            }
        } catch (e) {
            console.error("[style_contractors] BOM unit qty fetch failed", e);
        }
    }
    return Number(sc.unit_qty || 1) || 1;
}

async function recalc_stitching_subassembly_style_contractors(frm, cdt, cdn) {
    const row = locals[cdt]?.[cdn];
    if (!row?.style_contractors?.length) {
        return;
    }
    const work_qty = Number(row.stitching_qty || 0) || 0;
    const by_style = {};
    row.style_contractors.forEach((sc) => {
        if (!sc?.style) {
            return;
        }
        (by_style[sc.style] = by_style[sc.style] || []).push(sc);
    });

    for (const rows of Object.values(by_style)) {
        if (rows.length === 1 && work_qty > 0 && !Number(rows[0].split_qty)) {
            rows[0].split_qty = work_qty;
        }
        for (const sc of rows) {
            const split_work = Number(sc.split_qty || 0) || work_qty;
            if (is_subassembly_row(sc)) {
                const unit_qty = await ensure_subassembly_unit_qty(sc, row.so_item);
                // qty = BOM zip/button per piece × stitching entry (user can still edit after)
                sc.qty = split_work > 0 ? split_work * unit_qty : unit_qty;
                sc.amount = sc.qty * (Number(sc.rate || 0) || 0);
                sc.is_subassembly = 1;
                sc.unit_qty = unit_qty;
                if (sc.name && locals[NESTED_STYLE_DOCTYPE]?.[sc.name]) {
                    Object.assign(locals[NESTED_STYLE_DOCTYPE][sc.name], sc);
                }
            } else if (split_work > 0) {
                sc.amount = split_work * (Number(sc.rate || 0) || 0);
            }
        }
    }
    sync_style_contractors_to_frm_doc(frm, cdn, row);
    refresh_nested_style_contractor_grid(frm, cdn);
    frm.dirty();
}

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
