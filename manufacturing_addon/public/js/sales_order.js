frappe.ui.form.on("Sales Order", {
    refresh: function(frm) {
        frm.doc.items.forEach(function(item) {
            frappe.call({
                method: "frappe.client.get",
                args: {
                    doctype: "Item",
                    name: item.item_code
                },
                callback: function(response) {
                    if (response.message) {
                        let item_doc = response.message;
                        
                        // Skip validation if custom_global_item is set to 1
                        if (item_doc.custom_global_item == 1) {
                            return;
                        }

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
        });
    }
});

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
