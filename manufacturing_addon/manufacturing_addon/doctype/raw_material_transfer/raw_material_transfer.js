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
            item.transfer_qty = 0;
        });
        
        frm.refresh_field("raw_materials");
        frappe.show_alert(__("All transfer quantities cleared"), 3);
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
    }
});
