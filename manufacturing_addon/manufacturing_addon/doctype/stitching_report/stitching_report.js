// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Stitching Report", {
    get_data(frm){
        console.log("[Stitching Report JS] get_data called");
        console.log("[Stitching Report JS] Order Sheet:", frm.doc.order_sheet);
        
        if (!frm.doc.order_sheet) {
            frappe.msgprint(__("Please select an Order Sheet first."));
            return;
        }
        
        frm.call({
            method:"get_data1",
            doc: frm.doc,
            args: {},
            freeze: true,
            freeze_message: __("Fetching data from Order Sheet..."),
            callback: function(r) {
                console.log("[Stitching Report JS] get_data1 response:", r);
                if (r.message) {
                    console.log("[Stitching Report JS] Success");
                }
                frm.reload_doc();
            },
            error: function(r) {
                console.error("[Stitching Report JS] Error:", r);
                frappe.msgprint(__("Error fetching data: {0}", [r.message || r.exc]));
            }
        });
    }
});
