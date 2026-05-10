// Validate item-customer restriction when item_code is selected
frappe.ui.form.on("Sales Order Item", {
    item_code: function(frm, cdt, cdn) {
        let item = locals[cdt][cdn];

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
            }
        }
    },

    dashboard_update: function(frm) {
        const dashboardData = frm.dashboard_data || {};
        const transactions = dashboardData.transactions || [];
        const count = dashboardData.count || {};
        const internalLinks = count.internal_links_found || [];

        console.log("[Manufacturing Addon][Sales Order] dashboard_update", {
            sales_order: frm.doc.name,
            transactions,
            internal_links_found: internalLinks,
            manufacturing_group: transactions.find(group => group.label === "Manufacturing"),
            order_sheet_link: internalLinks.find(link => link.doctype === "Order Sheet"),
            cutting_report_link: internalLinks.find(link => link.doctype === "Cutting Report"),
            stitching_report_link: internalLinks.find(link => link.doctype === "Stitching Report"),
            packing_report_link: internalLinks.find(link => link.doctype === "Packing Report")
        });
    }
});



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
