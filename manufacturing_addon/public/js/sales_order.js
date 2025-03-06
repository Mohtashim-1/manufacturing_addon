frappe.ui.form.on('Sales Order', {
    refresh: function (frm) {
        // frappe.msgprint('1')
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
                            // frappe.set_route('Form', 'Order Sheet', r.message);
                        }
                    }
                });
            }, __("Actions"));
        }
    }
});
