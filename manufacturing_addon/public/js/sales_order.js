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
        // Add custom button if Sales Order is already saved
        if (!frm.is_new()) {
            frm.add_custom_button(__('Create Order Sheet'), function () {
                frappe.call({
                    method: "manufacturing_addon.api.create_order_sheet",
                    args: {
                        sales_order: frm.doc.name
                    },
                    callback: function (r) {
                        if (r.message) {
                            frappe.msgprint(__('Order Sheet {0} Created', [r.message]));
                            // frappe.set_route('Form', 'Order Sheet', r.message); // Uncomment if navigation is desired
                        }
                    }
                });
            }, __("Actions"));
            
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
