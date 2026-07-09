// Copyright (c) 2026, Manufacturing Addon contributors
// Shared nested Style Contractors grid for manufacturing reports.

const NESTED_STYLE_DOCTYPE = "Report Style Contractor";

function init_report_style_contractors(config) {
    const SC_DEBUG = config.debug !== false;
    const {
        parent_doctype,
        ct_doctype,
        ct_fieldname,
        contractor_filter,
        api_method,
        operation,
        load_method = "load_style_contractors",
        work_qty_field,
    } = config;

    function sc_log(...args) {
        if (SC_DEBUG) {
            console.log(`[style_contractors:${parent_doctype}]`, ...args);
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
            callback();
            return;
        }
        frappe.model.with_doctype(NESTED_STYLE_DOCTYPE, callback);
    }

    function preload_style_contractor_meta() {
        with_style_contractor_meta(() => {});
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
            sc.parenttype = sc.parenttype || ct_doctype;
            sc.parentfield = sc.parentfield || "style_contractors";
            if (sc.name) {
                locals[NESTED_STYLE_DOCTYPE][sc.name] = sc;
            }
        });
    }

    function sync_style_contractors_to_frm_doc(frm, cdn, row) {
        const frm_row = (frm.doc[ct_fieldname] || []).find((r) => r.name === cdn);
        if (frm_row) {
            frm_row.style_contractors = row.style_contractors;
        }
    }

    function sync_style_contractors_from_frm_doc(frm, cdt, cdn) {
        const row = locals[cdt]?.[cdn];
        if (!row) {
            return 0;
        }
        if ((row.style_contractors || []).length) {
            return row.style_contractors.length;
        }
        const frm_row = (frm.doc[ct_fieldname] || []).find((r) => r.name === cdn);
        if (!frm_row?.style_contractors?.length) {
            return 0;
        }
        row.style_contractors = frm_row.style_contractors;
        ensure_style_contractors_in_locals(row);
        return row.style_contractors.length;
    }

    function update_report_style_amount(cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row) {
            return;
        }
        const qty = Number(row.qty || 1) || 1;
        const rate = Number(row.rate || 0) || 0;
        frappe.model.set_value(cdt, cdn, "amount", qty * rate);
    }

    function recalc_subassembly_style_contractors(frm, cdt, cdn) {
        if (!work_qty_field) {
            return;
        }
        const row = locals[cdt]?.[cdn];
        if (!row?.style_contractors?.length) {
            return;
        }
        const work_qty = Number(row[work_qty_field] || 0) || 0;
        row.style_contractors.forEach((sc) => {
            if (!sc?.is_subassembly) {
                return;
            }
            const unit_qty = Number(sc.unit_qty || 0) || 1;
            const total_qty = work_qty > 0 ? work_qty * unit_qty : unit_qty;
            sc.qty = total_qty;
            sc.amount = total_qty * (Number(sc.rate || 0) || 0);
            if (sc.name && locals[NESTED_STYLE_DOCTYPE]?.[sc.name]) {
                locals[NESTED_STYLE_DOCTYPE][sc.name].qty = sc.qty;
                locals[NESTED_STYLE_DOCTYPE][sc.name].amount = sc.amount;
            }
        });
        sync_style_contractors_to_frm_doc(frm, cdn, row);
        refresh_nested_style_contractor_grid(frm, cdn);
        frm.dirty();
    }

    function sync_style_contractor_to_parent_frm(frm, cdt, cdn) {
        const row = locals[cdt]?.[cdn];
        if (!row?.parent || !frm) {
            return;
        }
        const ct_row = locals[ct_doctype]?.[row.parent];
        if (!ct_row) {
            return;
        }
        sync_style_contractors_to_frm_doc(frm, row.parent, ct_row);
        frm.dirty();
    }

    function snapshot_style_contractors(frm) {
        frm._style_contractors_snapshot = {};
        (frm.doc[ct_fieldname] || []).forEach((ct_row) => {
            const local_row = locals[ct_doctype]?.[ct_row.name];
            const rows = local_row?.style_contractors || ct_row.style_contractors;
            if (rows?.length) {
                frm._style_contractors_snapshot[ct_row.name] = frappe.utils.deep_clone(rows);
            }
        });
    }

    function sync_all_style_contractors_to_frm_doc(frm) {
        (frm.doc[ct_fieldname] || []).forEach((ct_row) => {
            const local_row = locals[ct_doctype]?.[ct_row.name];
            if (local_row?.style_contractors?.length) {
                ct_row.style_contractors = frappe.utils.deep_clone(local_row.style_contractors);
                sc_log("before_save: synced CT row", ct_row.name, {
                    count: ct_row.style_contractors.length,
                    qtys: ct_row.style_contractors.map((r) => r.qty),
                });
            }
        });
    }

    function restore_style_contractors_after_save(frm) {
        const snapshot = frm._style_contractors_snapshot || {};
        (frm.doc[ct_fieldname] || []).forEach((ct_row) => {
            const local_row = locals[ct_doctype]?.[ct_row.name];
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
        });
        delete frm._style_contractors_snapshot;
    }

    function get_nested_style_contractor_context(frm, cdn) {
        const grid = frm.fields_dict[ct_fieldname]?.grid;
        const grid_row = grid?.grid_rows_by_docname?.[cdn];
        const nested_control = grid_row?.grid_form?.fields_dict?.style_contractors;
        const nested_grid = nested_control?.grid;
        return {
            has_parent_grid: !!grid,
            has_grid_row: !!grid_row,
            has_nested_control: !!nested_control,
            has_nested_grid: !!nested_grid,
        };
    }

    function refresh_nested_style_contractor_grid(frm, cdn) {
        const grid = frm.fields_dict[ct_fieldname]?.grid;
        const grid_row = grid?.grid_rows_by_docname?.[cdn];
        const nested_control = grid_row?.grid_form?.fields_dict?.style_contractors;
        const row = locals[ct_doctype]?.[cdn];
        if (!nested_control?.grid) {
            return;
        }
        ensure_style_contractors_in_locals(row);
        nested_control.grid.visible_columns = null;
        nested_control.doc = row;
        nested_control.grid.setup_fields();
        nested_control.grid.setup_visible_columns();
        nested_control.grid.refresh();
    }

    function bind_style_contractor_grid(frm, cdt, cdn) {
        const grid = frm.fields_dict[ct_fieldname]?.grid;
        if (!grid) {
            return;
        }
        const grid_row = grid.grid_rows_by_docname?.[cdn];
        const nested = grid_row?.grid_form?.fields_dict?.style_contractors?.grid;
        if (!nested || nested._style_contractor_bound) {
            return;
        }
        nested._style_contractor_bound = true;
        const contractor_df = frappe.meta.get_docfield("Report Style Contractor", "contractor");
        if (contractor_df) {
            contractor_df.get_query = () => ({ filters: contractor_filter });
        }
    }

    function ensure_style_contractors_for_row(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        sync_style_contractors_from_frm_doc(frm, cdt, cdn);
        if (!row?.so_item || (row.style_contractors || []).length) {
            refresh_nested_style_contractor_grid(frm, cdn);
            return;
        }

        frappe.call({
            method: api_method,
            args: {
                so_item: row.so_item,
                combo_item: row.combo_item,
                article: row.article,
                operation,
                work_qty: work_qty_field ? Number(row[work_qty_field] || 0) || 0 : 0,
            },
            callback(r) {
                const styles = r.message || [];
                if (!styles.length || (row.style_contractors || []).length) {
                    refresh_nested_style_contractor_grid(frm, cdn);
                    return;
                }
                styles.forEach((sc) => {
                    const child = frappe.model.add_child(row, "style_contractors");
                    Object.assign(child, sc);
                });
                recalc_subassembly_style_contractors(frm, cdt, cdn);
                sync_style_contractors_to_frm_doc(frm, cdn, row);
                refresh_nested_style_contractor_grid(frm, cdn);
                frm.dirty();
            },
        });
    }

    function setup_style_contractors_panel(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        sync_style_contractors_from_frm_doc(frm, cdt, cdn);
        ensure_style_contractors_in_locals(row);
        if (!row?.so_item) {
            return;
        }
        bind_style_contractor_grid(frm, cdt, cdn);
        if ((row.style_contractors || []).length) {
            refresh_nested_style_contractor_grid(frm, cdn);
            return;
        }
        ensure_style_contractors_for_row(frm, cdt, cdn);
    }

    function bind_style_contractor_model_sync(frm) {
        if (frm._style_contractor_model_bound) {
            return;
        }
        frm._style_contractor_model_bound = true;
        frappe.model.on(NESTED_STYLE_DOCTYPE, "*", function (fieldname, value, doc) {
            const ct_row = locals[ct_doctype]?.[doc?.parent];
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

    frappe.ui.form.on(parent_doctype, {
        onload(frm) {
            preload_style_contractor_meta();
            bind_style_contractor_model_sync(frm);
        },
        refresh(frm) {
            preload_style_contractor_meta();
            bind_style_contractor_model_sync(frm);
            (frm.doc[ct_fieldname] || []).forEach((ct_row) => {
                const local_row = locals[ct_doctype]?.[ct_row.name];
                if (local_row) {
                    ensure_style_contractors_in_locals(local_row);
                }
            });
            if (!frm.is_new()) {
                frm.add_custom_button(__("Load Style Contractors"), () => {
                    frm.call({
                        method: load_method,
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
    });

    const ct_handlers = {
        form_render(frm, cdt, cdn) {
            with_style_contractor_meta(() => {
                setTimeout(() => setup_style_contractors_panel(frm, cdt, cdn), 0);
            });
        },
    };
    if (work_qty_field) {
        ct_handlers[work_qty_field] = function (frm, cdt, cdn) {
            recalc_subassembly_style_contractors(frm, cdt, cdn);
        };
    }
    frappe.ui.form.on(ct_doctype, ct_handlers);

    frappe.ui.form.on("Report Style Contractor", {
        qty(frm, cdt, cdn) {
            const row = locals[cdt]?.[cdn];
            if (row?.is_subassembly) {
                return;
            }
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
}
