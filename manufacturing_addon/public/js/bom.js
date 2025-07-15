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


frappe.ui.form.on('BOM', {
    custom_get_items: function(frm) {
        if (!frm.doc.custom_bom_template) {
            frappe.msgprint("Please select a BOM Template first.");
            return;
        }
        // If the BOM is new (unsaved), save it first
        if (frm.is_new()) {
            frm.save().then(() => {
                fetch_items_from_template(frm);
            });
        } else {
            fetch_items_from_template(frm);
        }
    }
});

function fetch_items_from_template(frm) {
    frappe.call({
        method: "manufacturing_addon.manufacturing_addon.doctype.bom.bom.get_bom_items_from_template_api",
        args: {
            bom_name: frm.doc.name
        },
        callback: function(r) {
            if (!r.exc) {
                frappe.msgprint(__("Items fetched from BOM Template"));
                frm.reload_doc(); // reload to reflect new items
            }
        }
    });
}

// BOM Item form events
frappe.ui.form.on("BOM Item", {
    refresh: function(frm) {
        // Make fields readonly if item is frozen from template
        if (frm.doc.custom_frozen_from_template) {
            frm.set_read_only(['item_code', 'qty', 'uom', 'rate', 'description', 'source_warehouse']);
        }
    },
    
    custom_frozen_from_template: function(frm) {
        // Update readonly status when freeze field changes
        if (frm.doc.custom_frozen_from_template) {
            frm.set_read_only(['item_code', 'qty', 'uom', 'rate', 'description', 'source_warehouse']);
        } else {
            frm.set_read_only(['item_code', 'qty', 'uom', 'rate', 'description', 'source_warehouse'], false);
        }
    }
});




frappe.ui.form.on('BOM', {
    refresh: function (frm) {
        // Check if the user is an Administrator or has the System Manager role
        // if (frappe.user.has_role('System Manager') || frappe.user.name === 'Administrator') {
        if (frm.doc.custom_bom_template) {
            frm.set_df_property('items', 'cannot_add_rows', 1);
        } 
    }
});
