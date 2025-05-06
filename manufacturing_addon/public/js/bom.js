frappe.ui.form.on('BOM', {
    onload(frm) {
        if (frm.doc.custom_filter_based_on === "Customer") {
            set_item_filter(frm);
            set_item_query(frm);
        }
    },
    refresh(frm) {
        if (frm.doc.custom_filter_based_on === "Customer") {
            set_item_filter(frm);
            set_item_query(frm);
        }
    },
    custom_customer(frm) {
        if (frm.doc.custom_filter_based_on === "Customer") {
            set_item_filter(frm);
            set_item_query(frm);
            fetch_party_specific_group(frm);
        }
    },
    custom_filter_based_on(frm) {
        if (frm.doc.custom_filter_based_on === "Customer") {
            set_item_filter(frm);
            set_item_query(frm);
        }
    }
});

function fetch_party_specific_group(frm) {
    if (!frm.doc.custom_customer) return;

    frappe.call({
        method: "manufacturing_addon.api.get_party_specific_item_group",
        args: {
            customer: frm.doc.custom_customer
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value("custom_party_specific_group", r.message);
            } else {
                frappe.msgprint("No Party Specific Item Group found for this customer.");
                frm.set_value("custom_party_specific_group", null);
            }
        }
    });
}

function set_item_query(frm) {
    frm.set_query('item', () => {
        if (!frm.doc.custom_party_specific_group) {
            frappe.msgprint("Please select a Party Specific Item Group first.");
            return {};
        }

        return {
            filters: {
                item_group: frm.doc.custom_party_specific_group
            }
        };
    });
}
function set_item_filter(frm) {
    frm.fields_dict["items"].grid.get_field("item_code").get_query = function(doc, cdt, cdn) {
        if (frm.doc.custom_filter_based_on !== "Customer") {
            return {};  // Don't apply any filter if not Customer
        }

        if (!frm.doc.custom_customer) {
            frappe.msgprint("Please select a customer first.");
            return {};
        }

        return {
            query: "manufacturing_addon.api.filter_items_by_customer",
            filters: {
                custom_customer: frm.doc.custom_customer
            }
        };
    };
}
