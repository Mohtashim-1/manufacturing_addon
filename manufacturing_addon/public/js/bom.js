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
		_sync_bom_carton_display(frm);
    },
	quantity(frm) {
		_sync_bom_carton_display(frm);
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

function _sync_bom_carton_display(frm) {
	if (!frm.fields_dict.custom_qty_ctn && !frm.fields_dict.custom_carton_item) {
		return;
	}
	const items = frm.doc.items || [];
	let best = null;
	items.forEach((row) => {
		const code = (row.item_code || "").toUpperCase();
		const name = (row.item_name || "").toUpperCase();
		if (!(code.startsWith("CARTON") || name.includes("CARTON"))) {
			return;
		}
		const score = code.startsWith("CARTON") || name.startsWith("CARTON") ? 0 : 1;
		const cand = { item_code: row.item_code, qty: flt(row.qty), score, idx: row.idx };
		if (!best || score < best.score || (score === best.score && cand.idx < best.idx)) {
			best = cand;
		}
	});
	const carton_item = best ? best.item_code : "";
	const carton_qty = best ? flt(best.qty) : 0;
	const bom_qty = flt(frm.doc.quantity);
	let qty_ctn = bom_qty;
	if (bom_qty && carton_qty) {
		qty_ctn = bom_qty / carton_qty;
	}
	if (frm.fields_dict.custom_carton_item && frm.doc.custom_carton_item !== carton_item) {
		frm.set_value("custom_carton_item", carton_item || null);
	}
	if (frm.fields_dict.custom_qty_ctn && flt(frm.doc.custom_qty_ctn) !== flt(qty_ctn)) {
		frm.set_value("custom_qty_ctn", qty_ctn || 0);
	}
}

frappe.ui.form.on("BOM Item", {
	item_code(frm) {
		_sync_bom_carton_display(frm);
	},
	qty(frm) {
		_sync_bom_carton_display(frm);
	},
	items_remove(frm) {
		_sync_bom_carton_display(frm);
	},
});
