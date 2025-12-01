// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Report", {
    get_data(frm){
        frm.call({
            method:"get_data1",
            doc: frm.doc,
            args:{

            },
            callback:function(r){
                frm.reload_doc()
            }
        })
    }
});

