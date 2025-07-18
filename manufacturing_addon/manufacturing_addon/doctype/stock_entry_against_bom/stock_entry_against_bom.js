// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Entry Against BOM', {
    refresh: function(frm) {
        frm.add_custom_button(__('Get Item (Custom)'), function() {
            frm.trigger('get_item');
        });
    },

    get_item: function(frm) {
        if (!frm.doc.sales_order) {
            frappe.msgprint('Please select a Sales Order first.');
            return;
        }
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.stock_entry_against_bom.stock_entry_against_bom.get_items_and_raw_materials",
            args: {
                sales_order: frm.doc.sales_order
            },
            callback: function(r) {
                if (r.message) {
                    // Clear existing rows
                    frm.clear_table('stock_entry_item_table');
                    frm.clear_table('stock_entry_required_item_table');
                    
                    // Add items to stock_entry_item_table
                    (r.message.items || []).forEach(function(row) {
                        let d = frm.add_child('stock_entry_item_table');
                        d.item = row.item;
                        d.bom = row.bom;
                        d.qty = row.qty;
                    });

                    // Add raw materials to stock_entry_required_item_table
                    (r.message.raw_materials || []).forEach(function(row) {
                        let d = frm.add_child('stock_entry_required_item_table');
                        d.item = row.item;
                        d.qty = row.qty;
                        d.uom = row.uom;
                    });

                    frm.refresh_field('stock_entry_item_table');
                    frm.refresh_field('stock_entry_required_item_table');
                }
            }
        });
    },

    recalculate_raw_materials: function(frm) {
        console.log('recalculate_raw_materials triggered');
        if (!frm.doc.stock_entry_item_table || frm.doc.stock_entry_item_table.length === 0) {
            // Clear raw materials table if no items
            frm.clear_table('stock_entry_required_item_table');
            frm.refresh_field('stock_entry_required_item_table');
            return;
        }
        
        // In Frappe, deleted rows are removed from the array, so we can use all current items
        let items = frm.doc.stock_entry_item_table;
        console.log('Items in table:', items);
        
        if (items.length === 0) {
            frm.clear_table('stock_entry_required_item_table');
            frm.refresh_field('stock_entry_required_item_table');
            return;
        }
        
        // Call server method to recalculate raw materials
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.stock_entry_against_bom.stock_entry_against_bom.recalculate_raw_materials",
            args: {
                items: items
            },
            callback: function(r) {
                console.log('Server response:', r);
                if (r.message) {
                    // Clear and repopulate raw materials table
                    frm.clear_table('stock_entry_required_item_table');
                    (r.message.raw_materials || []).forEach(function(row) {
                        let d = frm.add_child('stock_entry_required_item_table');
                        d.item = row.item;
                        d.qty = row.qty;
                        d.uom = row.uom;
                    });
                    frm.refresh_field('stock_entry_required_item_table');
                }
            }
        });
    }
});

// Add debouncing to prevent multiple rapid calls
let recalculateTimeout;

// Handle changes in stock_entry_item_table
frappe.ui.form.on('Stock Entry Item Table', {
    stock_entry_item_table_add: function(frm, cdt, cdn) {
        console.log('Row added to stock_entry_item_table');
        // Clear existing timeout and set new one
        clearTimeout(recalculateTimeout);
        recalculateTimeout = setTimeout(function() {
            frm.trigger('recalculate_raw_materials');
        }, 500); // 500ms delay
    },
    
    stock_entry_item_table_remove: function(frm, cdt, cdn) {
        console.log('Row removed from stock_entry_item_table');
        // Clear existing timeout and set new one
        clearTimeout(recalculateTimeout);
        recalculateTimeout = setTimeout(function() {
            frm.trigger('recalculate_raw_materials');
        }, 500); // 500ms delay
    },
    
    qty: function(frm, cdt, cdn) {
        console.log('Qty changed in stock_entry_item_table');
        // Clear existing timeout and set new one
        clearTimeout(recalculateTimeout);
        recalculateTimeout = setTimeout(function() {
            frm.trigger('recalculate_raw_materials');
        }, 500); // 500ms delay
    }
});

