frappe.ui.form.on('Item', {
    refresh: function(frm) {
        // fabric treatment
        if (frm.doc.custom_item_category) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Category',
                    filters: { name: frm.doc.custom_item_category },
                    fieldname: 'fabric_treatment'
                },
                callback: function(r) {
                    if (r.message && r.message.fabric_treatment) {
                        frm.set_df_property('custom_fabric_treatment', 'hidden', 0); // Show field
                    } else {
                        frm.set_df_property('custom_fabric_treatment', 'hidden', 1); // Hide field
                    }
                }
            });
        }
        // article
        if (frm.doc.custom_item_category) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Category',
                    filters: { name: frm.doc.custom_item_category },
                    fieldname: 'article'
                },
                callback: function(r) {
                    if (r.message && r.message.article) {
                        frm.set_df_property('custom_article', 'hidden', 0); // Show field
                    } else {
                        frm.set_df_property('custom_article', 'hidden', 1); // Hide field
                    }
                }
            });
        }
        // finished item
        if (frm.doc.custom_item_category) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Category',
                    filters: { name: frm.doc.custom_item_category },
                    fieldname: 'finished_item'
                },
                callback: function(r) {
                    if (r.message && r.message.finished_item) {
                        frm.set_df_property('custom_finished_item', 'hidden', 0); // Show field
                    } else {
                        frm.set_df_property('custom_finished_item', 'hidden', 1); // Hide field
                    }
                }
            });
        }
        
        // design
        
        if (frm.doc.custom_item_category) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Category',
                    filters: { name: frm.doc.custom_item_category },
                    fieldname: 'design'
                },
                callback: function(r) {
                    if (r.message && r.message.design) {
                        frm.set_df_property('custom_design', 'hidden', 0); // Show field
                    } else {
                        frm.set_df_property('custom_design', 'hidden', 1); // Hide field
                    }
                }
            });
        }
        
        // micron
        
        if (frm.doc.custom_item_category) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Category',
                    filters: { name: frm.doc.custom_item_category },
                    fieldname: 'micron'
                },
                callback: function(r) {
                    if (r.message && r.message.micron) {
                        frm.set_df_property('custom_micron', 'hidden', 0); // Show field
                    } else {
                        frm.set_df_property('custom_micron', 'hidden', 1); // Hide field
                    }
                }
            });
        }
        
        // gsm
        
        if (frm.doc.custom_item_category) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Category',
                    filters: { name: frm.doc.custom_item_category },
                    fieldname: 'gsm'
                },
                callback: function(r) {
                    if (r.message && r.message.gsm) {
                        frm.set_df_property('custom_gsm', 'hidden', 0); // Show field
                    } else {
                        frm.set_df_property('custom_gsm', 'hidden', 1); // Hide field
                    }
                }
            });
        }
        
        // length
        
         if (frm.doc.custom_item_category) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Category',
                    filters: { name: frm.doc.custom_item_category },
                    fieldname: 'length1'
                },
                callback: function(r) {
                    if (r.message && r.message.length1) {
                        frm.set_df_property('custom_length', 'hidden', 0); // Show field
                    } else {
                        frm.set_df_property('custom_length', 'hidden', 1); // Hide field
                    }
                }
            });
        }
        
        // width
        
        if (frm.doc.custom_item_category) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Category',
                    filters: { name: frm.doc.custom_width },
                    fieldname: 'width'
                },
                callback: function(r) {
                    if (r.message && r.message.width) {
                        frm.set_df_property('custom_width', 'hidden', 0); // Show field
                    } else {
                        frm.set_df_property('custom_width', 'hidden', 1); // Hide field
                    }
                }
            });
        }
        
        // size
        
         if (frm.doc.custom_item_category) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Category',
                    filters: { name: frm.doc.custom_item_category },
                    fieldname: 'size'
                },
                callback: function(r) {
                    if (r.message && r.message.size) {
                        frm.set_df_property('custom_size', 'hidden', 0); // Show field
                    } else {
                        frm.set_df_property('custom_size', 'hidden', 1); // Hide field
                    }
                }
            });
        }
        
        // ply
        
         if (frm.doc.custom_item_category) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Category',
                    filters: { name: frm.doc.custom_item_category },
                    fieldname: 'ply'
                },
                callback: function(r) {
                    if (r.message && r.message.ply) {
                        frm.set_df_property('custom_ply', 'hidden', 0); // Show field
                    } else {
                        frm.set_df_property('custom_ply', 'hidden', 1); // Hide field
                    }
                }
            });
        }
        
    }
});
