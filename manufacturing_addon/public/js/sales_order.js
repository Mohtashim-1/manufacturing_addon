// Validate item-customer restriction when item_code is selected
frappe.ui.form.on("Sales Order Item", {
    item_code: function(frm, cdt, cdn) {
        let item = locals[cdt][cdn];
        update_cost_of_product(frm, cdt, cdn);

        // Ensure both item_code and customer are selected
        if (!item.item_code || !frm.doc.customer) return;

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Item",
                name: item.item_code
            },
            callback: function(response) {
                if (response.message) {
                    let item_doc = response.message;

                    // Skip if marked as global item
                    if (item_doc.custom_global_item == 1) return;

                    let allowed_customers = item_doc.custom_allowed_customers || [];
                    let is_allowed = allowed_customers.some(row => row.customer === frm.doc.customer);

                    if (!is_allowed) {
                        frappe.throw(`🚫 <b>Restricted Item!</b><br><br>
                        ❌ The item <b>${item.item_code}</b> cannot be sold to <b>${frm.doc.customer}</b>.<br>
                        🔒 Please select another item or contact the administrator.`);
                    }
                }
            }
        });

    },

    bom_no: function(frm, cdt, cdn) {
        update_cost_of_product(frm, cdt, cdn);
    }
});

// Add custom button on Sales Order
frappe.ui.form.on("Sales Order", {
    refresh: function(frm) {
        console.log("[Manufacturing Addon][Sales Order] refresh", {
            name: frm.doc.name,
            is_new: frm.is_new(),
            docstatus: frm.doc.docstatus,
            status: frm.doc.status
        });
        // Add custom button if Sales Order is already saved
        if (!frm.is_new()) {
            (frm.doc.items || []).forEach(row => {
                if (row.item_code && !row.custom_cost_of_product) {
                    update_cost_of_product(frm, row.doctype, row.name);
                }
            });

            frm.add_custom_button(__("Create Order Sheet"), function () {
                frappe.call({
                    method: "manufacturing_addon.manufacturing_addon.doctype.order_sheet.order_sheet.create_order_sheet_from_sales_order",
                    args: {
                        sales_order: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __("Creating Order Sheet..."),
                    callback: function (r) {
                        if (!r.message || !r.message.order_sheet) return;

                        frappe.show_alert({
                            message: __("Order Sheet {0} created", [r.message.order_sheet]),
                            indicator: "green"
                        }, 5);

                        frappe.set_route("Form", "Order Sheet", r.message.order_sheet);
                    }
                });
            }, __("Create"));
            
            // Add Close button if Sales Order is submitted and not already closed
            if (frm.doc.docstatus === 1 && frm.doc.status !== "Closed") {
                frm.add_custom_button(__('Close Sales Order'), function () {
                    frappe.confirm(
                        __('Are you sure you want to close this Sales Order? This will also disable the associated Cost Center.'),
                        function() {
                            frappe.call({
                                method: "manufacturing_addon.manufacturing_addon.doctype.sales_order.sales_order.close_sales_order_and_cost_center",
                                args: {
                                    sales_order_name: frm.doc.name
                                },
                                callback: function (r) {
                                    if (r.message && r.message.status === "success") {
                                        frappe.msgprint(__('Sales Order closed successfully!'));
                                        frm.reload_doc();
                                    } else if (r.message && r.message.status === "already_closed") {
                                        frappe.msgprint(__('Sales Order is already closed.'));
                                    } else {
                                        frappe.msgprint(__('Error closing Sales Order. Please try again.'));
                                    }
                                }
                            });
                        }
                    );
                }, __("Actions"));

                frappe.call({
                    method: "manufacturing_addon.manufacturing_addon.doctype.sales_order.sales_order.can_update_submitted_sales_order",
                    args: {
                        sales_order_name: frm.doc.name
                    },
                    callback: function (r) {
                        if (!r.message || !r.message.allowed) return;

                        frm.add_custom_button(__("Enable Update"), function () {
                            enable_submitted_sales_order_editing(frm);
                        }, __("Actions"));
                    }
                });
            }
        }
    },

    currency: function(frm) {
        refresh_cost_of_product_for_all_rows(frm);
    },

    conversion_rate: function(frm) {
        refresh_cost_of_product_for_all_rows(frm);
    },

    dashboard_update: function(frm) {
        const count = (frm.dashboard_data && frm.dashboard_data.count) || {};
        const internalLinks = count.internal_links_found || [];
        const manufacturing = (frm.dashboard_data && frm.dashboard_data.transactions || [])
            .find((group) => group.label === __("Manufacturing"));

        // Re-enable links when indirect manufacturing docs exist (via Order Sheet).
        internalLinks.forEach((link) => {
            if (!link.names || !link.names.length) return;
            const $el = $(frm.dashboard.transactions_area).find(
                `.document-link[data-doctype="${link.doctype}"]`
            );
            $el.attr("data-names", link.names.join(","));
            $el.find("a").removeAttr("disabled");
        });

        if (manufacturing && frappe.boot.developer_mode) {
            console.log("[Manufacturing Addon][Sales Order] connections", {
                sales_order: frm.doc.name,
                cutting: internalLinks.find((l) => l.doctype === "Cutting Report"),
                stitching: internalLinks.find((l) => l.doctype === "Stitching Report"),
            });
        }
    }
});


function enable_submitted_sales_order_editing(frm) {
    if (frm.__submitted_update_enabled) return;

    const layoutFields = new Set([
        "Section Break",
        "Column Break",
        "Tab Break",
        "HTML",
        "Heading",
        "Button",
        "Image",
        "Fold"
    ]);

    frm.meta.fields.forEach(df => {
        if (!df.fieldname || layoutFields.has(df.fieldtype)) return;

        if (df.fieldtype === "Table") {
            const grid = frm.fields_dict[df.fieldname] && frm.fields_dict[df.fieldname].grid;
            if (!grid) return;

            df.read_only = 0;
            df.allow_on_submit = 1;
            grid.df.read_only = 0;
            grid.df.allow_on_submit = 1;
            grid.cannot_add_rows = false;
            grid.cannot_delete_rows = false;

            (grid.docfields || []).forEach(childDf => {
                if (!childDf.fieldname || layoutFields.has(childDf.fieldtype)) return;
                grid.update_docfield_property(childDf.fieldname, "read_only", 0);
                grid.update_docfield_property(childDf.fieldname, "allow_on_submit", 1);
            });

            grid.refresh();
            return;
        }

        frm.set_df_property(df.fieldname, "read_only", 0);
        frm.set_df_property(df.fieldname, "allow_on_submit", 1);
    });

    frm.__submitted_update_enabled = true;
    frm.enable_save();
    frm.page.set_primary_action(__("Update"), function () {
        frm.save("Update");
    });
    frm.refresh_fields();

    frappe.show_alert({
        message: __("Submitted Sales Order editing enabled"),
        indicator: "orange"
    });
}


function update_cost_of_product(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row || !row.item_code) return;

    frappe.call({
        method: "manufacturing_addon.manufacturing_addon.doctype.sales_order.sales_order.get_sales_order_item_cost_of_product",
        args: {
            item_code: row.item_code,
            bom_no: row.bom_no,
            company: frm.doc.company,
            currency: frm.doc.currency,
            conversion_rate: frm.doc.conversion_rate
        },
        callback: function(r) {
            frappe.model.set_value(
                cdt,
                cdn,
                "custom_cost_of_product",
                (r.message && r.message.cost_of_product) || 0
            );
        }
    });
}


function refresh_cost_of_product_for_all_rows(frm) {
    (frm.doc.items || []).forEach(row => {
        if (row.item_code) {
            update_cost_of_product(frm, row.doctype, row.name);
        }
    });
}



// frappe.ui.form.on('Sales Order', {
//     refresh: function (frm) {
//         // frappe.msgprint('1')
//         if (!frm.is_new()) {
//             frm.add_custom_button(__('Create Order Sheet'), function () {
//                 frappe.call({
//                     method: "manufacturing_addon.api.create_order_sheet",
//                     args: {
//                         sales_order: frm.doc.name
//                     },
//                     callback: function (r) {
//                         if (r.message) {
//                             frappe.msgprint(__('Order Sheet {0} Created', [r.message]));
//                             // frappe.set_route('Form', 'Order Sheet', r.message);
//                         }
//                     }
//                 });
//             }, __("Actions"));
//         }
//     }
// });
