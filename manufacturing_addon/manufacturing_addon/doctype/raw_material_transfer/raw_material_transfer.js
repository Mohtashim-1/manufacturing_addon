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
            
            // Extra quantity distribution buttons
            frm.add_custom_button(__("Transfer Summary"), function() {
                frm.trigger("show_transfer_summary");
            }, __("Summary"));
            
            frm.add_custom_button(__("Refresh Transferred Qty"), function() {
                frm.trigger("refresh_transferred_quantities");
            }, __("Actions"));
            
            frm.add_custom_button(__("Sync Warehouse Info"), function() {
                frm.trigger("update_child_warehouses");
            }, __("Actions"));
            
            frm.add_custom_button(__("Debug Warehouse Sync"), function() {
                frm.trigger("debug_warehouse_sync");
            }, __("Actions"));
            
            frm.add_custom_button(__("Debug BOM Allocation"), function() {
                frm.trigger("debug_bom_allocation");
            }, __("Actions"));
        }
    },
    
    stock_entry_type: function(frm) {
        console.log("🔍 DEBUG: stock_entry_type event triggered");
        if (frm.doc.stock_entry_type) {
            console.log("🔍 DEBUG: Stock entry type selected:", frm.doc.stock_entry_type);
        }
    },
    
    source_warehouse: function(frm) {
        console.log("🔍 DEBUG: source_warehouse event triggered");
        if (frm.doc.source_warehouse) {
            console.log("🔍 DEBUG: Source warehouse selected:", frm.doc.source_warehouse);
            frm.trigger("update_child_warehouses_client_side");
        }
    },
    
    target_warehouse: function(frm) {
        console.log("🔍 DEBUG: target_warehouse event triggered");
        if (frm.doc.target_warehouse) {
            console.log("🔍 DEBUG: Target warehouse selected:", frm.doc.target_warehouse);
            frm.trigger("update_child_warehouses_client_side");
        }
    },
    
    update_child_warehouses_client_side: function(frm) {
        console.log("🔍 DEBUG: update_child_warehouses_client_side() called");
        console.log("🔍 DEBUG: Parent source_warehouse:", frm.doc.source_warehouse);
        console.log("🔍 DEBUG: Parent target_warehouse:", frm.doc.target_warehouse);
        
        if (!frm.doc.raw_materials || frm.doc.raw_materials.length === 0) {
            console.log("🔍 DEBUG: No raw materials found, skipping warehouse update");
            return;
        }
        
        console.log("🔍 DEBUG: Found", frm.doc.raw_materials.length, "raw materials");
        
        let updated_count = 0;
        
        frm.doc.raw_materials.forEach(function(item, index) {
            console.log(`🔍 DEBUG: Processing item ${index}: ${item.item_code}`);
            console.log(`🔍 DEBUG: Current source_warehouse: ${item.source_warehouse}`);
            console.log(`🔍 DEBUG: Current target_warehouse: ${item.target_warehouse}`);
            
            let item_updated = false;
            
            // Update source_warehouse if parent has it and child doesn't or it's different
            if (frm.doc.source_warehouse && item.source_warehouse !== frm.doc.source_warehouse) {
                console.log(`🔍 DEBUG: Updating source_warehouse from ${item.source_warehouse} to ${frm.doc.source_warehouse}`);
                item.source_warehouse = frm.doc.source_warehouse;
                item_updated = true;
            }
            
            // Update target_warehouse if parent has it and child doesn't or it's different
            if (frm.doc.target_warehouse && item.target_warehouse !== frm.doc.target_warehouse) {
                console.log(`🔍 DEBUG: Updating target_warehouse from ${item.target_warehouse} to ${frm.doc.target_warehouse}`);
                item.target_warehouse = frm.doc.target_warehouse;
                item_updated = true;
            }
            
            if (item_updated) {
                updated_count++;
                console.log(`🔍 DEBUG: Item ${item.item_code} was updated`);
            } else {
                console.log(`🔍 DEBUG: Item ${item.item_code} was not updated`);
            }
        });
        
        console.log(`🔍 DEBUG: Total items updated: ${updated_count}`);
        
        if (updated_count > 0) {
            frm.refresh_field("raw_materials");
            frappe.show_alert(__("Updated warehouse information for {0} items", [updated_count]), 3);
            console.log(`🔍 DEBUG: Updated warehouse information for ${updated_count} items`);
        } else {
            console.log("🔍 DEBUG: No items were updated");
        }
    },
    
    update_child_warehouses: function(frm) {
        console.log("🔍 DEBUG: update_child_warehouses() called");
        
        if (!frm.doc.raw_materials || frm.doc.raw_materials.length === 0) {
            console.log("🔍 DEBUG: No raw materials found, skipping warehouse update");
            frappe.msgprint(__("No raw materials found"));
            return;
        }
        
        // Call server-side method for comprehensive sync
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.raw_material_transfer.raw_material_transfer.sync_warehouse_information",
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
    
    debug_warehouse_sync: function(frm) {
        console.log("🔍 DEBUG: debug_warehouse_sync() called");
        console.log("🔍 DEBUG: Document name:", frm.doc.name);
        console.log("🔍 DEBUG: Parent source_warehouse:", frm.doc.source_warehouse);
        console.log("🔍 DEBUG: Parent target_warehouse:", frm.doc.target_warehouse);
        console.log("🔍 DEBUG: Raw materials count:", frm.doc.raw_materials ? frm.doc.raw_materials.length : 0);
        
        if (frm.doc.raw_materials && frm.doc.raw_materials.length > 0) {
            frm.doc.raw_materials.forEach(function(item, index) {
                console.log(`🔍 DEBUG: Item ${index}:`);
                console.log(`  - item_code: ${item.item_code}`);
                console.log(`  - source_warehouse: ${item.source_warehouse}`);
                console.log(`  - target_warehouse: ${item.target_warehouse}`);
                console.log(`  - Should update source: ${frm.doc.source_warehouse && item.source_warehouse !== frm.doc.source_warehouse}`);
                console.log(`  - Should update target: ${frm.doc.target_warehouse && item.target_warehouse !== frm.doc.target_warehouse}`);
            });
        }
        
        // Test the sync function
        frm.trigger("update_child_warehouses_client_side");
    },
    
    debug_bom_allocation: function(frm) {
        console.log("🔍 DEBUG: debug_bom_allocation() called");
        
        if (!frm.doc.name) {
            frappe.msgprint(__("Please save the document first"));
            return;
        }
        
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.raw_material_transfer.raw_material_transfer.debug_bom_allocation",
            args: {
                doc_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message && r.message.success) {
                    show_bom_debug_dialog(r.message.debug_info);
                } else {
                    frappe.msgprint(__("Error: {0}", [r.message ? r.message.message : "Unknown error"]));
                }
            }
        });
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
    },
    
    
    show_transfer_summary: function(frm) {
        console.log("🔍 DEBUG: show_transfer_summary() called");
        
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.raw_material_transfer.raw_material_transfer.get_transfer_summary",
            args: {
                doc_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message && r.message.success) {
                    show_summary_dialog(r.message.summary);
                } else {
                    frappe.msgprint(__("Error: {0}", [r.message ? r.message.message : "Unknown error"]));
                }
            }
        });
    },
    
    refresh_transferred_quantities: function(frm) {
        console.log("🔍 DEBUG: refresh_transferred_quantities() called");
        
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.raw_material_transfer.raw_material_transfer.refresh_transferred_quantities",
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
    }
});

function show_summary_dialog(summary) {
    let items_html = '';
    
    summary.items.forEach(function(item) {
        let status_color = '';
        if (item.transfer_status === 'Fully Transferred') {
            status_color = 'color: #28a745; font-weight: bold;';
        } else if (item.transfer_status === 'Partially Transferred') {
            status_color = 'color: #ffc107; font-weight: bold;';
        } else {
            status_color = 'color: #6c757d;';
        }
        
        items_html += `
            <tr>
                <td>${item.item_code}</td>
                <td>${item.item_name}</td>
                <td style="text-align: right;">${item.pending_qty.toFixed(2)}</td>
                <td style="text-align: right;">${item.transfer_qty.toFixed(2)}</td>
                <td style="text-align: right; font-weight: bold; color: #007bff;">${item.transferred_so_far.toFixed(2)}</td>
                <td style="text-align: right;">${item.extra_qty.toFixed(2)}</td>
                <td style="text-align: right;">${item.target_qty.toFixed(2)}</td>
                <td style="text-align: right;">${item.expected_qty.toFixed(2)}</td>
                <td style="${status_color}">${item.transfer_status}</td>
                <td>${item.uom}</td>
            </tr>
        `;
    });
    
    let summary_html = `
        <div style="margin-bottom: 20px;">
            <h4>Transfer Summary</h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                <div style="padding: 10px; background-color: #f8f9fa; border-radius: 4px;">
                    <strong>Total Items:</strong> ${summary.total_items}
                </div>
                <div style="padding: 10px; background-color: #e3f2fd; border-radius: 4px;">
                    <strong>Total Pending:</strong> ${summary.total_pending_qty.toFixed(2)}
                </div>
                <div style="padding: 10px; background-color: #fff3e0; border-radius: 4px;">
                    <strong>Total Transfer (Planned):</strong> ${summary.total_transfer_qty.toFixed(2)}
                </div>
                <div style="padding: 10px; background-color: #007bff; color: white; border-radius: 4px;">
                    <strong>Total Transferred (Actual):</strong> ${summary.total_transferred_so_far.toFixed(2)}
                </div>
                <div style="padding: 10px; background-color: #f3e5f5; border-radius: 4px;">
                    <strong>Total Extra:</strong> ${summary.total_extra_qty.toFixed(2)}
                </div>
                <div style="padding: 10px; background-color: #e8f5e8; border-radius: 4px;">
                    <strong>Total Target:</strong> ${summary.total_target_qty.toFixed(2)}
                </div>
                <div style="padding: 10px; background-color: #fff8e1; border-radius: 4px;">
                    <strong>Total Expected:</strong> ${summary.total_expected_qty.toFixed(2)}
                </div>
            </div>
        </div>
        
        <div style="max-height: 400px; overflow-y: auto;">
            <table class="table table-bordered table-sm" style="font-size: 12px;">
                <thead style="background-color: #f8f9fa; position: sticky; top: 0;">
                    <tr>
                        <th>Item Code</th>
                        <th>Item Name</th>
                        <th style="text-align: right;">Pending</th>
                        <th style="text-align: right;">Transfer (Planned)</th>
                        <th style="text-align: right; color: #007bff;">Transferred (Actual)</th>
                        <th style="text-align: right;">Extra</th>
                        <th style="text-align: right;">Target</th>
                        <th style="text-align: right;">Expected</th>
                        <th>Status</th>
                        <th>UOM</th>
                    </tr>
                </thead>
                <tbody>
                    ${items_html}
                </tbody>
            </table>
        </div>
    `;
    
    let d = new frappe.ui.Dialog({
        title: __('Transfer Summary'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'summary_content',
                options: summary_html
            }
        ],
        primary_action: {
            label: __('Close'),
            action: function() {
                d.hide();
            }
        }
    });
    
    d.show();
}

function show_bom_debug_dialog(debug_info) {
    let items_html = '';
    
    for (let item_code in debug_info) {
        let item_info = debug_info[item_code];
        let status_color = item_info.can_allocate ? 'color: #28a745; font-weight: bold;' : 'color: #dc3545; font-weight: bold;';
        let status_text = item_info.can_allocate ? 'CAN ALLOCATE' : 'CANNOT ALLOCATE';
        
        items_html += `
            <div style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
                <h4 style="${status_color}">${item_code} - ${status_text}</h4>
                <div style="margin-left: 20px;">
        `;
        
        for (let wo of item_info.work_orders) {
            let wo_status = '';
            if (wo.bom_found && wo.item_in_bom) {
                wo_status = '<span style="color: #28a745;">✓ In BOM</span>';
            } else if (wo.bom_found && !wo.item_in_bom) {
                wo_status = '<span style="color: #ffc107;">⚠ Not in BOM</span>';
            } else {
                wo_status = '<span style="color: #dc3545;">✗ No BOM</span>';
            }
            
            items_html += `
                <div style="margin-bottom: 10px;">
                    <strong>Work Order:</strong> ${wo.work_order}<br>
                    <strong>Production Item:</strong> ${wo.production_item}<br>
                    <strong>BOM:</strong> ${wo.bom_name || 'Not found'}<br>
                    <strong>Status:</strong> ${wo_status}
                </div>
            `;
        }
        
        items_html += `
                </div>
            </div>
        `;
    }
    
    let debug_html = `
        <div style="max-height: 500px; overflow-y: auto;">
            <h3>BOM Allocation Debug Information</h3>
            <p>This shows which raw materials can be allocated to work orders and why.</p>
            ${items_html}
        </div>
    `;
    
    let d = new frappe.ui.Dialog({
        title: __('BOM Allocation Debug'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'debug_content',
                options: debug_html
            }
        ],
        primary_action: {
            label: __('Close'),
            action: function() {
                d.hide();
            }
        }
    });
    
    d.show();
}

// Helper function to distribute extra quantity automatically
function distribute_extra_quantity_automatically(frm, extra_qty, current_cdt, current_cdn) {
    console.log(`🔍 DEBUG: Distributing extra quantity ${extra_qty} automatically`);
    
    // Get all rows with pending quantity > 0 AND sufficient stock in source warehouse
    let eligible_rows = [];
    frm.doc.raw_materials.forEach(function(item, index) {
        let source_warehouse = item.source_warehouse || item.warehouse;
        let actual_qty = flt(item.actual_qty_at_warehouse || 0);
        
        // Check if item has stock in source warehouse
        if (flt(item.pending_qty) > 0 && actual_qty > 0) {
            eligible_rows.push({
                item: item,
                index: index,
                cdt: 'raw_materials',
                cdn: frm.doc.raw_materials[index].name
            });
        }
    });
    
    if (eligible_rows.length === 0) {
        // If no items have stock, just add extra to the original item
        let current_row = locals[current_cdt][current_cdn];
        current_row.extra_qty = flt(current_row.extra_qty || 0) + extra_qty;
        current_row.target_qty = flt(current_row.pending_qty || 0) + flt(current_row.extra_qty || 0);
        current_row.expected_qty = flt(current_row.transfer_qty || 0) + flt(current_row.extra_qty || 0);
        update_row_transfer_status(current_row);
        
        frappe.show_alert(__("Extra quantity {0} added to current item only (no other items have stock)", [extra_qty]), 3);
        return;
    }
    
    // Calculate average extra per item
    let avg_extra_per_item = extra_qty / eligible_rows.length;
    console.log(`🔍 DEBUG: Average extra per item: ${avg_extra_per_item}`);
    
    // Distribute extra quantities
    eligible_rows.forEach(function(row_data) {
        let item = row_data.item;
        
        // Add average extra to this item
        item.extra_qty = flt(item.extra_qty || 0) + avg_extra_per_item;
        
        // Update target and expected quantities
        item.target_qty = flt(item.pending_qty || 0) + flt(item.extra_qty || 0);
        item.expected_qty = flt(item.transfer_qty || 0) + flt(item.extra_qty || 0);
        
        // Update transfer status
        update_row_transfer_status(item);
        
        console.log(`🔍 DEBUG: Item ${item.item_code} - Extra: ${item.extra_qty}, Target: ${item.target_qty}`);
    });
    
    // Show success message
    frappe.show_alert(__("Extra quantity {0} distributed across {1} items with stock", [extra_qty, eligible_rows.length]), 3);
}

// Helper function to update row quantities
function update_row_quantities(row) {
    // Update target quantity (pending + extra)
    row.target_qty = flt(row.pending_qty || 0) + flt(row.extra_qty || 0);
    
    // Update expected quantity (transfer + extra)
    row.expected_qty = flt(row.transfer_qty || 0) + flt(row.extra_qty || 0);
    
    // Update transfer status
    update_row_transfer_status(row);
}

// Helper function to update transfer status
function update_row_transfer_status(row) {
    let transferred_so_far = flt(row.transferred_qty_so_far || 0);
    let total_required = transferred_so_far + flt(row.pending_qty || 0);
    
    if (transferred_so_far >= total_required) {
        row.transfer_status = "Fully Transferred";
    } else if (transferred_so_far > 0) {
        row.transfer_status = "Partially Transferred";
    } else {
        row.transfer_status = "Pending";
    }
}

// Field events for raw materials table
frappe.ui.form.on("Raw Material Transfer Items Table", {
    // Event when a new row is added
    raw_materials_add: function(frm, cdt, cdn) {
        console.log("🔍 DEBUG: raw_materials_add event triggered");
        let row = locals[cdt][cdn];
        
        // Set warehouse fields from parent if they exist
        if (frm.doc.source_warehouse && !row.source_warehouse) {
            row.source_warehouse = frm.doc.source_warehouse;
            console.log(`🔍 DEBUG: Set source_warehouse for new item ${row.item_code} to ${frm.doc.source_warehouse}`);
        }
        
        if (frm.doc.target_warehouse && !row.target_warehouse) {
            row.target_warehouse = frm.doc.target_warehouse;
            console.log(`🔍 DEBUG: Set target_warehouse for new item ${row.item_code} to ${frm.doc.target_warehouse}`);
        }
        
        frm.refresh_field("raw_materials");
    },
    
    // Event when source_warehouse changes in child table
    source_warehouse: function(frm, cdt, cdn) {
        console.log("🔍 DEBUG: Child table source_warehouse event triggered");
        let row = locals[cdt][cdn];
        
        // If child row source_warehouse is cleared, sync from parent
        if (!row.source_warehouse && frm.doc.source_warehouse) {
            row.source_warehouse = frm.doc.source_warehouse;
            frm.refresh_field("raw_materials");
            console.log(`🔍 DEBUG: Synced source_warehouse from parent for item ${row.item_code}`);
        }
    },
    
    // Event when target_warehouse changes in child table
    target_warehouse: function(frm, cdt, cdn) {
        console.log("🔍 DEBUG: Child table target_warehouse event triggered");
        let row = locals[cdt][cdn];
        
        // If child row target_warehouse is cleared, sync from parent
        if (!row.target_warehouse && frm.doc.target_warehouse) {
            row.target_warehouse = frm.doc.target_warehouse;
            frm.refresh_field("raw_materials");
            console.log(`🔍 DEBUG: Synced target_warehouse from parent for item ${row.item_code}`);
        }
    },
    transfer_qty: function(frm, cdt, cdn) {
        console.log("🔍 DEBUG: transfer_qty event triggered");
        let row = locals[cdt][cdn];
        
        // Get pending quantity
        let pending_qty = flt(row.pending_qty || 0);
        let transfer_qty = flt(row.transfer_qty || 0);
        
        // Check stock availability in source warehouse first
        let source_warehouse = row.source_warehouse || row.warehouse;
        let actual_qty = flt(row.actual_qty_at_warehouse || 0);
        
        // If actual_qty_at_warehouse is 0, try to get stock from source warehouse
        if (actual_qty === 0 && source_warehouse) {
            frappe.call({
                method: "erpnext.stock.utils.get_stock_balance",
                args: {
                    item_code: row.item_code,
                    warehouse: source_warehouse,
                    with_valuation_rate: false
                },
                callback: function(r) {
                    if (r.message && r.message.qty) {
                        actual_qty = flt(r.message.qty);
                    }
                },
                async: false
            });
        }
        
        if (transfer_qty > actual_qty) {
            frappe.msgprint(__("Insufficient stock for {0}. Available: {1}, Required: {2} in source warehouse {3}. Please reduce the transfer quantity.", [row.item_code, actual_qty, transfer_qty, source_warehouse]));
            // Don't automatically change the value, let user decide
            frm.refresh_field("raw_materials");
            return;
        }
        
        // Calculate additional transfer quantity if transfer_qty exceeds total available
        let total_required_qty = flt(row.total_required_qty || 0);
        let extra_qty = flt(row.extra_qty || 0);
        let transferred_qty_so_far = flt(row.transferred_qty_so_far || 0);
        let actual_qty_at_warehouse = flt(row.actual_qty_at_warehouse || 0);
        let current_total_available = total_required_qty + extra_qty + flt(row.additional_transfer_qty || 0);
        let additional_transfer_qty = 0;
        
        // Check if transfer_qty exceeds actual stock in warehouse
        if (transfer_qty > actual_qty_at_warehouse) {
            // Auto-calculate additional_transfer_qty if not already set
            if (flt(row.additional_transfer_qty || 0) === 0) {
                additional_transfer_qty = transfer_qty - actual_qty_at_warehouse;
                row.additional_transfer_qty = additional_transfer_qty;
                console.log(`🔍 DEBUG: Auto-calculated additional_transfer_qty: ${additional_transfer_qty} for ${row.item_code}`);
            } else {
                additional_transfer_qty = flt(row.additional_transfer_qty || 0);
            }
        }
        
        // Also check if transfer_qty exceeds current total available
        if (transfer_qty > current_total_available) {
            additional_transfer_qty = transfer_qty - current_total_available;
            row.additional_transfer_qty = additional_transfer_qty;
            console.log(`🔍 DEBUG: Transfer qty ${transfer_qty} exceeds current total available ${current_total_available}, additional transfer: ${additional_transfer_qty}`);
        }
        
        // Update additional_transfer_qty field
        row.additional_transfer_qty = additional_transfer_qty;
        
        // Calculate new total_available_qty = total_required_qty + extra_qty + additional_transfer_qty
        let new_total_available_qty = total_required_qty + extra_qty + additional_transfer_qty;
        row.total_available_qty = new_total_available_qty;
        
        // Calculate new pending_qty = total_available_qty - transferred_qty_so_far
        let new_pending_qty = new_total_available_qty - transferred_qty_so_far;
        row.pending_qty = new_pending_qty;
        
        // Update target_qty and expected_qty
        row.target_qty = new_total_available_qty;
        row.expected_qty = flt(row.transfer_qty || 0);
        
        // Update transfer status
        update_row_transfer_status(row);
        
        if (additional_transfer_qty > 0) {
            console.log(`🔍 DEBUG: New total_available_qty: ${new_total_available_qty}, new pending_qty: ${new_pending_qty}`);
            frappe.show_alert(__("Additional transfer quantity {0} added for {1}", [additional_transfer_qty, row.item_code]), 3);
        }
        
        // Normal validation for quantities within limits
        if (transfer_qty < 0) {
            frappe.msgprint(__("Transfer quantity cannot be negative"));
            row.transfer_qty = 0;
            frm.refresh_field("raw_materials");
            return;
        }
        
        // Update quantities for this row
        update_row_quantities(row);
        
        frm.refresh_field("raw_materials");
    },
    
    extra_qty: function(frm, cdt, cdn) {
        console.log("🔍 DEBUG: extra_qty event triggered");
        let row = locals[cdt][cdn];
        
        // Validate extra quantity
        if (flt(row.extra_qty) < 0) {
            frappe.msgprint(__("Extra quantity cannot be negative"));
            row.extra_qty = 0;
        }
        
        // Update row quantities using helper function
        update_row_quantities(row);
        
        frm.refresh_field("raw_materials");
    }
});
