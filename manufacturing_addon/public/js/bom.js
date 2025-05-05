//  finished item filter

frappe.ui.form.on('BOM', {
    onload(frm) {
        set_item_query(frm);
    },
    refresh(frm) {
        set_item_query(frm);
    },
    custom_customer(frm) {
        set_item_query(frm);
    }
});

function set_item_query(frm) {
    frm.set_query('item', () => {
        // frappe.msgprint('1')
        if (!frm.doc.custom_customer) {
            frappe.msgprint('Please select a customer first');
            return {};
        }

        return {
            query: 'manufacturing_addon.api.filter_items_by_customer',
            filters: {
                custom_customer: frm.doc.custom_customer
            }
        };
    });
}
