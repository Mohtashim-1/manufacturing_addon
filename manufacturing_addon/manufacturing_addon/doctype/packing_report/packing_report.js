// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Packing Report", {
    get_data(frm){
        console.log("[Packing Report JS] get_data called");
        console.log("[Packing Report JS] Order Sheet:", frm.doc.order_sheet);
        
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
                console.log("[Packing Report JS] get_data1 response:", r);
                if (r.message) {
                    console.log("[Packing Report JS] Success");
                }
                frm.reload_doc().then(function() {
                    console.log("[Packing Report JS] Document reloaded, checking bundle_items...");
                    if (frm.doc.packing_report_ct) {
                        frm.doc.packing_report_ct.forEach(function(row, idx) {
                            console.log(`[Packing Report JS] After reload - Row ${idx + 1}:`, {
                                name: row.name,
                                so_item: row.so_item,
                                bundle_items_exists: !!row.bundle_items,
                                bundle_items_length: row.bundle_items ? row.bundle_items.length : 0
                            });
                            
                            // If bundle_items is missing, fetch it from database
                            if (!row.bundle_items && row.name) {
                                console.log(`[Packing Report JS] bundle_items missing for row ${idx + 1}, fetching from database...`);
                                frappe.call({
                                    method: "frappe.client.get_value",
                                    args: {
                                        doctype: "Packing Report CT",
                                        filters: { name: row.name },
                                        fieldname: ["bundle_items"]
                                    },
                                    callback: function(response) {
                                        if (response.message && response.message.bundle_items) {
                                            console.log(`[Packing Report JS] Fetched bundle_items from DB, length:`, response.message.bundle_items.length);
                                            row.bundle_items = response.message.bundle_items;
                                            // Trigger refresh to render
                                            frm.refresh_field("packing_report_ct");
                                        } else {
                                            console.log(`[Packing Report JS] bundle_items not found in database either`);
                                        }
                                    }
                                });
                            }
                        });
                    }
                });
            },
            error: function(r) {
                console.error("[Packing Report JS] Error:", r);
                frappe.msgprint(__("Error fetching data: {0}", [r.message || r.exc]));
            }
        });
    },
    
    refresh(frm) {
        console.log("[Packing Report JS] refresh called");
        console.log("[Packing Report JS] packing_report_ct exists:", !!frm.fields_dict.packing_report_ct);
        
        // HTML fields in child tables should render automatically
        // But we can force refresh if needed
        if (frm.fields_dict.packing_report_ct && frm.fields_dict.packing_report_ct.grid) {
            console.log("[Packing Report JS] Grid exists, checking rows...");
            let grid = frm.fields_dict.packing_report_ct.grid;
            let grid_rows = Object.keys(grid.grid_rows_by_docname || {});
            console.log("[Packing Report JS] Grid rows:", grid_rows);
            console.log("[Packing Report JS] Grid rows count:", grid_rows.length);
            
            // Check each row for bundle_items
            if (frm.doc.packing_report_ct) {
                console.log("[Packing Report JS] packing_report_ct rows:", frm.doc.packing_report_ct.length);
                frm.doc.packing_report_ct.forEach(function(row, idx) {
                    console.log(`[Packing Report JS] ========== Row ${idx + 1} ==========`);
                    console.log(`[Packing Report JS] Row name:`, row.name);
                    console.log(`[Packing Report JS] Row so_item:`, row.so_item);
                    console.log(`[Packing Report JS] Row bundle_items exists:`, !!row.bundle_items);
                    console.log(`[Packing Report JS] Row bundle_items length:`, row.bundle_items ? row.bundle_items.length : 0);
                    console.log(`[Packing Report JS] Row bundle_items preview:`, row.bundle_items ? row.bundle_items.substring(0, 150) + "..." : "None");
                    
                    if (row.bundle_items) {
                        let grid_row = grid.grid_rows_by_docname[row.name];
                        console.log(`[Packing Report JS] Grid row for ${row.name}:`, grid_row ? "FOUND" : "NOT FOUND");
                        
                        if (grid_row) {
                            console.log(`[Packing Report JS] Grid row exists`);
                            console.log(`[Packing Report JS] Grid row grid_form:`, grid_row.grid_form ? "EXISTS" : "NOT EXISTS");
                            
                            if (grid_row.grid_form) {
                                console.log(`[Packing Report JS] Grid form exists`);
                                console.log(`[Packing Report JS] Grid form fields_dict keys:`, Object.keys(grid_row.grid_form.fields_dict || {}));
                                
                                let bundle_field = grid_row.grid_form.fields_dict.bundle_items;
                                console.log(`[Packing Report JS] Bundle field:`, bundle_field ? "FOUND" : "NOT FOUND");
                                
                                if (bundle_field) {
                                    console.log(`[Packing Report JS] Bundle field details:`, {
                                        fieldtype: bundle_field.df ? bundle_field.df.fieldtype : "NO DF",
                                        fieldname: bundle_field.df ? bundle_field.df.fieldname : "NO DF",
                                        has_wrapper: !!bundle_field.$wrapper,
                                        wrapper_visible: bundle_field.$wrapper ? bundle_field.$wrapper.is(':visible') : "NO WRAPPER",
                                        current_html_length: bundle_field.$wrapper ? (bundle_field.$wrapper.html() ? bundle_field.$wrapper.html().length : 0) : "NO WRAPPER"
                                    });
                                    
                                    // Force set HTML content for Long Text field (which contains HTML)
                                    if (bundle_field.df && bundle_field.df.fieldtype === 'Long Text') {
                                        console.log(`[Packing Report JS] Field type is Long Text, setting HTML content...`);
                                        // For Long Text field, set value and then render as HTML
                                        bundle_field.set_value(row.bundle_items);
                                        
                                        // Render HTML in the field wrapper
                                        if (bundle_field.$wrapper) {
                                            let textarea = bundle_field.$wrapper.find('textarea');
                                            if (textarea.length) {
                                                // Replace textarea with HTML content
                                                textarea.hide();
                                                let htmlDiv = bundle_field.$wrapper.find('.bundle-items-html');
                                                if (!htmlDiv.length) {
                                                    htmlDiv = $('<div class="bundle-items-html" style="padding: 10px; border: 1px solid #ddd; background: #f9f9f9; max-height: 200px; overflow-y: auto;"></div>');
                                                    textarea.after(htmlDiv);
                                                }
                                                htmlDiv.html(row.bundle_items);
                                                console.log(`[Packing Report JS] ✓ HTML content rendered for row ${idx + 1}`);
                                            }
                                        }
                                        console.log(`[Packing Report JS] Content length:`, row.bundle_items.length);
                                    } else {
                                        console.log(`[Packing Report JS] ✗ Field type is NOT Long Text:`, bundle_field.df ? bundle_field.df.fieldtype : "NO DF");
                                    }
                                } else {
                                    console.log(`[Packing Report JS] ✗ Bundle field NOT found in grid form fields_dict`);
                                    console.log(`[Packing Report JS] Available fields:`, Object.keys(grid_row.grid_form.fields_dict || {}));
                                }
                            } else {
                                console.log(`[Packing Report JS] ✗ Grid form NOT found`);
                            }
                        } else {
                            console.log(`[Packing Report JS] ✗ Grid row NOT found for name: ${row.name}`);
                            console.log(`[Packing Report JS] Available grid row names:`, Object.keys(grid.grid_rows_by_docname || {}));
                        }
                    } else {
                        console.log(`[Packing Report JS] ✗ No bundle_items in row ${idx + 1}`);
                    }
                    console.log(`[Packing Report JS] ==========================================`);
                });
            } else {
                console.log("[Packing Report JS] ✗ No packing_report_ct rows in doc");
            }
            
            // Force grid refresh
            setTimeout(function() {
                console.log("[Packing Report JS] Forcing grid refresh...");
                frm.fields_dict.packing_report_ct.grid.refresh();
            }, 500);
        } else {
            console.log("[Packing Report JS] ✗ Grid NOT found");
        }
    }
});

// Ensure HTML field renders properly in child table
frappe.ui.form.on("Packing Report CT", {
    refresh_field(frm, cdt, cdn) {
        console.log("[Packing Report CT JS] refresh_field called", {cdt, cdn});
        
        // HTML field should render automatically, but we can ensure it does
        let row = locals[cdt][cdn];
        console.log("[Packing Report CT JS] Row data:", {
            name: row.name,
            so_item: row.so_item,
            bundle_items: row.bundle_items ? row.bundle_items.substring(0, 100) + "..." : "None"
        });
        
        if (row && row.bundle_items) {
            console.log("[Packing Report CT JS] Bundle items found, length:", row.bundle_items.length);
            
            // Force refresh of the HTML field
            setTimeout(function() {
                console.log("[Packing Report CT JS] setTimeout callback executing");
                let grid = frm.fields_dict.packing_report_ct.grid;
                if (grid) {
                    let grid_row = grid.grid_rows_by_docname[cdn];
                    console.log("[Packing Report CT JS] Grid row:", grid_row ? "Found" : "NOT Found");
                    
                    if (grid_row && grid_row.grid_form) {
                        console.log("[Packing Report CT JS] Grid form exists");
                        let bundle_field = grid_row.grid_form.fields_dict.bundle_items;
                        console.log("[Packing Report CT JS] Bundle field:", bundle_field ? "Found" : "NOT Found");
                        
                        if (bundle_field) {
                            console.log("[Packing Report CT JS] Bundle field details:", {
                                fieldtype: bundle_field.df.fieldtype,
                                fieldname: bundle_field.df.fieldname,
                                wrapper_exists: !!bundle_field.$wrapper,
                                current_html: bundle_field.$wrapper ? bundle_field.$wrapper.html() : "No wrapper"
                            });
                            
                            if (bundle_field.df.fieldtype === 'Long Text') {
                                bundle_field.set_value(row.bundle_items);
                                // Render HTML in the field wrapper
                                if (bundle_field.$wrapper) {
                                    let textarea = bundle_field.$wrapper.find('textarea');
                                    if (textarea.length) {
                                        textarea.hide();
                                        let htmlDiv = bundle_field.$wrapper.find('.bundle-items-html');
                                        if (!htmlDiv.length) {
                                            htmlDiv = $('<div class="bundle-items-html" style="padding: 10px; border: 1px solid #ddd; background: #f9f9f9; max-height: 200px; overflow-y: auto;"></div>');
                                            textarea.after(htmlDiv);
                                        }
                                        htmlDiv.html(row.bundle_items);
                                        console.log("[Packing Report CT JS] Long Text HTML content rendered");
                                    }
                                }
                            } else {
                                console.log("[Packing Report CT JS] Field type is NOT Long Text:", bundle_field.df.fieldtype);
                            }
                        }
                    }
                } else {
                    console.log("[Packing Report CT JS] Grid NOT found");
                }
            }, 100);
        } else {
            console.log("[Packing Report CT JS] No bundle_items in row");
        }
    }
});
