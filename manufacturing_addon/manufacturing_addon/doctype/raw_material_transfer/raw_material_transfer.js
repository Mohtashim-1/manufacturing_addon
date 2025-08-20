// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Raw Material Transfer", {
    refresh: function(frm) {
        console.log("🔍 DEBUG: refresh() called for Raw Material Transfer");
        
        // Add custom buttons based on document status
        if (frm.doc.docstatus === 0) {
            // Draft state - show action buttons
            frm.add_custom_button(__("Set All Transfer Qty to Pending"), function() {
                frm.trigger("set_all_transfer_qty_to_pending");
            }, __("Actions"));
            
            frm.add_custom_button(__("Clear All Transfer Qty"), function() {
                frm.trigger("clear_all_transfer_qty");
            }, __("Actions"));
            
            // Bulk delete buttons for better performance
            frm.add_custom_button(__("Bulk Delete Selected"), function() {
                frm.trigger("bulk_delete_selected");
            }, __("Actions"));
            
            frm.add_custom_button(__("Clear All Rows"), function() {
                frm.trigger("bulk_clear_all_rows");
            }, __("Actions"));
        }
    },
    
    stock_entry_type: function(frm) {
        console.log("🔍 DEBUG: stock_entry_type event triggered");
        if (frm.doc.stock_entry_type) {
            console.log("🔍 DEBUG: Stock entry type selected:", frm.doc.stock_entry_type);
        }
    },
    
    set_all_transfer_qty_to_pending: function(frm) {
        console.log("🔍 DEBUG: set_all_transfer_qty_to_pending() called");
        
        if (!frm.doc.raw_materials || frm.doc.raw_materials.length === 0) {
            frappe.msgprint(__("No raw materials found"));
            return;
        }
        
        frm.doc.raw_materials.forEach(function(item) {
            if (flt(item.pending_qty) > 0) {
                item.transfer_qty = item.pending_qty;
            }
        });
        
        frm.refresh_field("raw_materials");
        frappe.show_alert(__("All transfer quantities set to pending quantities"), 3);
    },
    
    clear_all_transfer_qty: function(frm) {
        console.log("🔍 DEBUG: clear_all_transfer_qty() called");
        
        if (!frm.doc.raw_materials || frm.doc.raw_materials.length === 0) {
            frappe.msgprint(__("No raw materials found"));
            return;
        }
        
        frm.doc.raw_materials.forEach(function(item) {
            item.transfer_qty = item.pending_qty; // Set to pending quantity instead of 0
        });
        
        frm.refresh_field("raw_materials");
        frappe.show_alert(__("All transfer quantities set to pending quantities"), 3);
    },
    
    bulk_delete_selected: function(frm) {
        console.log("🔍 DEBUG: bulk_delete_selected() called");
        
        if (!frm.doc.raw_materials || frm.doc.raw_materials.length === 0) {
            frappe.msgprint(__("No raw materials found"));
            return;
        }
        
        // Get selected rows from the grid
        let selected_rows = [];
        frm.doc.raw_materials.forEach(function(item, index) {
            if (item.select_for_delete) {
                selected_rows.push(index);
            }
        });
        
        if (selected_rows.length === 0) {
            frappe.msgprint(__("Please select rows to delete"));
            return;
        }
        
        frappe.confirm(
            __("Are you sure you want to delete {0} selected rows?", [selected_rows.length]),
            function() {
                // User confirmed
                frappe.call({
                    method: "manufacturing_addon.manufacturing_addon.doctype.raw_material_transfer.raw_material_transfer.bulk_delete_raw_material_rows",
                    args: {
                        doc_name: frm.doc.name,
                        row_indices: selected_rows
                    },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert(r.message.message, 3);
                            frm.reload_doc();
                        } else {
                            frappe.msgprint(__("Error: {0}", [r.message ? r.message.message : "Unknown error"]));
                        }
                    }
                });
            },
            function() {
                // User cancelled
                frappe.show_alert(__("Operation cancelled"), 3);
            }
        );
    },
    
    bulk_clear_all_rows: function(frm) {
        console.log("🔍 DEBUG: bulk_clear_all_rows() called");
        
        if (!frm.doc.raw_materials || frm.doc.raw_materials.length === 0) {
            frappe.msgprint(__("No raw materials found"));
            return;
        }
        
        frappe.confirm(
            __("Are you sure you want to clear all {0} rows?", [frm.doc.raw_materials.length]),
            function() {
                // User confirmed
                frappe.call({
                    method: "manufacturing_addon.manufacturing_addon.doctype.raw_material_transfer.raw_material_transfer.bulk_clear_all_raw_material_rows",
                    args: {
                        doc_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert(r.message.message, 3);
                            frm.reload_doc();
                        } else {
                            frappe.msgprint(__("Error: {0}", [r.message ? r.message.message : "Unknown error"]));
                        }
                    }
                });
            },
            function() {
                // User cancelled
                frappe.show_alert(__("Operation cancelled"), 3);
            }
        );
    }
});

// Field events for raw materials table
frappe.ui.form.on("Raw Material Transfer Items Table", {
    transfer_qty: function(frm, cdt, cdn) {
        console.log("🔍 DEBUG: transfer_qty event triggered");
        let row = locals[cdt][cdn];
        
        // Validate transfer quantity
        if (flt(row.transfer_qty) > flt(row.pending_qty)) {
            frappe.msgprint(__("Transfer quantity cannot exceed pending quantity"));
            row.transfer_qty = row.pending_qty;
            frm.refresh_field("raw_materials");
        }
        
        if (flt(row.transfer_qty) < 0) {
            frappe.msgprint(__("Transfer quantity cannot be negative"));
            row.transfer_qty = 0;
            frm.refresh_field("raw_materials");
        }
        
        if (flt(row.transfer_qty) === 0) {
            frappe.msgprint(__("Transfer quantity must be greater than 0"));
            row.transfer_qty = row.pending_qty;
            frm.refresh_field("raw_materials");
        }
    }
});
