// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Order Transfer Manager", {
    refresh: function(frm) {
        console.log("🔍 DEBUG: refresh() called for Work Order Transfer Manager");
        
        // Add custom buttons based on document status
        if (frm.doc.docstatus === 0) {
            // Draft state - show fetch and submit buttons
            frm.add_custom_button(__("Fetch Work Orders"), function() {
                console.log("🔍 DEBUG: Fetch Work Orders button clicked");
                frm.trigger("fetch_work_orders");
            }, __("Actions"));
            
            frm.add_custom_button(__("Create Raw Material Transfer"), function() {
                console.log("🔍 DEBUG: Create Raw Material Transfer button clicked");
                frm.trigger("create_raw_material_transfer");
            }, __("Actions"));
            
            frm.add_custom_button(__("Select All Raw Materials"), function() {
                console.log("🔍 DEBUG: Select All Raw Materials button clicked");
                frm.trigger("select_all_items");
            }, __("Actions"));
            
            frm.add_custom_button(__("Deselect All"), function() {
                console.log("🔍 DEBUG: Deselect All button clicked");
                frm.trigger("deselect_all_items");
            }, __("Actions"));
        } else if (frm.doc.docstatus === 1) {
            // Submitted state - show the new "Create All Pending Transfer" button
            frm.add_custom_button(__("Create All Pending Transfer"), function() {
                console.log("🔍 DEBUG: Create All Pending Transfer button clicked");
                frm.trigger("create_all_pending_transfer");
            }, __("Actions")).addClass("btn-primary");
            
            // Also show the regular transfer button for selective transfers
            frm.add_custom_button(__("Create Remaining Transfer"), function() {
                console.log("🔍 DEBUG: Create Remaining Transfer button clicked");
                frm.trigger("create_remaining_transfer");
            }, __("Actions"));
            
            frm.add_custom_button(__("Create Selective Transfer"), function() {
                console.log("🔍 DEBUG: Create Selective Transfer button clicked");
                frm.trigger("create_raw_material_transfer");
            }, __("Actions"));
        }
    },
    
    sales_order: function(frm) {
        console.log("🔍 DEBUG: sales_order event triggered");
        if (frm.doc.sales_order) {
            console.log("🔍 DEBUG: Sales order selected:", frm.doc.sales_order);
            // Fetch customer from sales order
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Sales Order",
                    filters: { name: frm.doc.sales_order },
                    fieldname: "customer"
                },
                callback: function(r) {
                    console.log("🔍 DEBUG: Customer fetch callback:", r);
                    if (r.message && r.message.customer) {
                        frm.set_value("customer", r.message.customer);
                    }
                }
            });
            
            // Fetch work order data
            frm.trigger("fetch_work_orders");
        }
    },
    
    fetch_work_orders: function(frm) {
        console.log("🔍 DEBUG: fetch_work_orders() called");
        if (!frm.doc.sales_order) {
            console.log("🔍 DEBUG: No sales order selected");
            frappe.msgprint(__("Please select a Sales Order first"));
            return;
        }
        
        console.log("🔍 DEBUG: Starting fetch_work_orders for sales_order:", frm.doc.sales_order);
        
        // Show a simple loading message instead of progress bar
        frappe.show_alert(__("Fetching work orders and calculating raw materials..."), 3);
        
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.populate_work_order_tables",
            args: {
                sales_order: frm.doc.sales_order,
                doc_name: frm.doc.name
            },
            timeout: 60, // 60 second timeout for server-side processing
            callback: function(r) {
                console.log("🔍 DEBUG: Server-side populate callback received:", r);
                if (r.message && r.message.success) {
                    console.log("🔍 DEBUG: Server-side populate successful:", r.message.message);
                    frappe.show_alert(__("Work orders and raw materials loaded successfully!"), 3);
                    
                    // If a new document was created, redirect to it
                    if (r.message.doc_name && r.message.doc_name !== frm.doc.name) {
                        console.log("🔍 DEBUG: Redirecting to new document:", r.message.doc_name);
                        frappe.set_route("Form", "Work Order Transfer Manager", r.message.doc_name);
                    } else {
                        // Reload the form to show the populated data
                        console.log("🔍 DEBUG: Reloading current form");
                        frm.reload_doc();
                    }
                } else {
                    console.log("🔍 DEBUG: Server-side populate failed:", r.message);
                    frappe.show_alert(__("Error loading work orders. Please try again."), 5);
                }
            },
            error: function(r) {
                console.error("❌ DEBUG: Error in server-side populate:", r);
                frappe.show_alert(__("Error loading work orders. Please try again."), 5);
            }
        });
    },
    
    create_raw_material_transfer: function(frm) {
        console.log("🔍 DEBUG: create_raw_material_transfer() called");
        if (!frm.doc.name) {
            console.log("🔍 DEBUG: Document not saved");
            frappe.msgprint(__("Please save the document first"));
            return;
        }
        
        // Validate that items are selected
        let selected_items = frm.doc.transfer_items.filter(item => item.select_for_transfer && flt(item.transfer_qty) > 0);
        console.log("🔍 DEBUG: Selected raw materials count:", selected_items.length);
        
        if (selected_items.length === 0) {
            console.log("🔍 DEBUG: No raw materials selected for transfer");
            frappe.msgprint(__("Please select raw materials and enter transfer quantities"));
            return;
        }
        
        // Show confirmation dialog
        let selected_summary = selected_items.map(item => 
            `${item.item_code}: ${item.transfer_qty} ${item.uom}`
        ).join('\n');
        
        frappe.confirm(
            `Are you sure you want to create a Raw Material Transfer document for the following raw materials?\n\n${selected_summary}`,
            function() {
                // User confirmed
                frappe.call({
                    method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.create_raw_material_transfer_doc",
                    args: {
                        doc_name: frm.doc.name
                    },
                    callback: function(r) {
                        console.log("🔍 DEBUG: Create raw material transfer callback:", r);
                        if (r.message && r.message.success) {
                            frappe.show_alert(__("Raw Material Transfer document created successfully!"), 3);
                            // Redirect to the new Raw Material Transfer document
                            frappe.set_route("Form", "Raw Material Transfer", r.message.doc_name);
                        } else {
                            frappe.show_alert(__("Error creating Raw Material Transfer: ") + (r.message ? r.message.message : "Unknown error"), 5);
                        }
                    }
                });
            },
            function() {
                // User cancelled
                console.log("🔍 DEBUG: User cancelled raw material transfer creation");
            }
        );
    },
    
    create_transfer: function(frm) {
        console.log("🔍 DEBUG: create_transfer() called");
        if (!frm.doc.name) {
            console.log("🔍 DEBUG: Document not saved");
            frappe.msgprint(__("Please save the document first"));
            return;
        }
        
        // Validate that items are selected
        let selected_items = frm.doc.transfer_items.filter(item => item.select_for_transfer && flt(item.transfer_qty) > 0);
        console.log("🔍 DEBUG: Selected raw materials count:", selected_items.length);
        
        if (selected_items.length === 0) {
            console.log("🔍 DEBUG: No raw materials selected for transfer");
            frappe.msgprint(__("Please select raw materials and enter transfer quantities"));
            return;
        }
        
        // Show confirmation dialog
        let selected_summary = selected_items.map(item => 
            `${item.item_code}: ${item.transfer_qty} ${item.uom}`
        ).join('\n');
        
        frappe.confirm(
            `Are you sure you want to create a Stock Entry for the following raw materials?\n\n${selected_summary}`,
            function() {
                // User confirmed
                frappe.call({
                    method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.create_selective_transfer",
                    args: {
                        doc_name: frm.doc.name
                    },
                    callback: function(r) {
                        console.log("🔍 DEBUG: Create transfer callback:", r);
                        if (r.message && r.message.success) {
                            frappe.show_alert(__("Raw Material Transfer created successfully!"), 3);
                            frm.reload_doc();
                        } else {
                            frappe.show_alert(__("Error creating transfer: ") + (r.message ? r.message.message : "Unknown error"), 5);
                        }
                    }
                });
            },
            function() {
                // User cancelled
                console.log("🔍 DEBUG: User cancelled transfer creation");
            }
        );
    },
    
    create_all_pending_transfer: function(frm) {
        console.log("🔍 DEBUG: create_all_pending_transfer() called");
        if (!frm.doc.name) {
            console.log("🔍 DEBUG: Document not saved");
            frappe.msgprint(__("Please save the document first"));
            return;
        }
        
        // Check if document is submitted
        if (frm.doc.docstatus !== 1) {
            console.log("🔍 DEBUG: Document not submitted");
            frappe.msgprint(__("Please submit the document first"));
            return;
        }
        
        // Get all pending items
        let pending_items = frm.doc.transfer_items.filter(item => flt(item.pending_qty) > 0);
        console.log("🔍 DEBUG: Pending raw materials count:", pending_items.length);
        
        if (pending_items.length === 0) {
            console.log("🔍 DEBUG: No pending raw materials found");
            frappe.msgprint(__("No raw materials with pending quantities found"));
            return;
        }
        
        // Show confirmation dialog
        let pending_summary = pending_items.map(item => 
            `${item.item_code}: ${item.pending_qty} ${item.uom}`
        ).join('\n');
        
        frappe.confirm(
            `This will create a Raw Material Transfer document with ALL pending raw materials.\n\nYou can then remove any items you don't want to transfer.\n\n${pending_summary}`,
            function() {
                // User confirmed
                frappe.call({
                    method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.create_all_pending_transfer",
                    args: {
                        doc_name: frm.doc.name
                    },
                    callback: function(r) {
                        console.log("🔍 DEBUG: Create all pending transfer callback:", r);
                        if (r.message && r.message.success) {
                            frappe.show_alert(__("Raw Material Transfer document created successfully!"), 3);
                            // Redirect to the new Raw Material Transfer document
                            if (r.message.doc_name) {
                                frappe.set_route("Form", "Raw Material Transfer", r.message.doc_name);
                            }
                        } else {
                            frappe.show_alert(__("Error creating transfer: ") + (r.message ? r.message.message : "Unknown error"), 5);
                        }
                    }
                });
            },
            function() {
                // User cancelled
                console.log("🔍 DEBUG: User cancelled all pending transfer creation");
            }
        );
    },
    
    select_all_items: function(frm) {
        console.log("🔍 DEBUG: select_all_raw_materials() called");
        frm.doc.transfer_items.forEach(function(item) {
            if (flt(item.pending_qty) > 0) {
                item.select_for_transfer = 1;
                item.transfer_qty = item.pending_qty;
            }
        });
        frm.refresh_field("transfer_items");
        frappe.show_alert(__("All raw materials selected for transfer"), 3);
    },
    
    deselect_all_items: function(frm) {
        console.log("🔍 DEBUG: deselect_all_items() called");
        frm.doc.transfer_items.forEach(function(item) {
            item.select_for_transfer = 0;
            item.transfer_qty = 0;
        });
        frm.refresh_field("transfer_items");
        frappe.show_alert(__("All items deselected"), 3);
    },
    
    create_remaining_transfer: function(frm) {
        console.log("🔍 DEBUG: create_remaining_transfer() called");
        
        if (!frm.doc.name) {
            frappe.msgprint(__("Please save the document first"));
            return;
        }
        
        if (frm.doc.docstatus !== 1) {
            frappe.msgprint(__("Please submit the document first"));
            return;
        }
        
        // Get remaining pending items (after previous transfers)
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.get_remaining_pending_items",
            args: {
                doc_name: frm.doc.name
            },
            callback: function(r) {
                console.log("🔍 DEBUG: Get remaining pending items callback:", r);
                if (r.message && r.message.length > 0) {
                    let remaining_summary = r.message.map(item => 
                        `${item.item_code}: ${item.pending_qty} ${item.uom}`
                    ).join('\n');
                    
                    frappe.confirm(
                        `This will create a Raw Material Transfer document with remaining pending raw materials.\n\n${remaining_summary}`,
                        function() {
                            // User confirmed
                            frappe.call({
                                method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.create_all_pending_transfer",
                                args: {
                                    doc_name: frm.doc.name
                                },
                                callback: function(r) {
                                    console.log("🔍 DEBUG: Create remaining transfer callback:", r);
                                    if (r.message && r.message.success) {
                                        frappe.show_alert(__("Raw Material Transfer document created successfully!"), 3);
                                        if (r.message.doc_name) {
                                            frappe.set_route("Form", "Raw Material Transfer", r.message.doc_name);
                                        }
                                    } else {
                                        frappe.show_alert(__("Error creating transfer: ") + (r.message ? r.message.message : "Unknown error"), 5);
                                    }
                                }
                            });
                        },
                        function() {
                            console.log("🔍 DEBUG: User cancelled remaining transfer creation");
                        }
                    );
                } else {
                    frappe.msgprint(__("No remaining pending items found"));
                }
            }
        });
    }
});

// Field events for transfer items table
frappe.ui.form.on("Work Order Transfer Items Table", {
    select_for_transfer: function(frm, cdt, cdn) {
        console.log("🔍 DEBUG: select_for_transfer event triggered");
        let row = locals[cdt][cdn];
        if (row.select_for_transfer) {
            // Auto-fill transfer quantity with pending quantity
            row.transfer_qty = row.pending_qty;
        } else {
            // Clear transfer quantity when deselected
            row.transfer_qty = 0;
        }
        frm.refresh_field("transfer_items");
    },
    
    transfer_qty: function(frm, cdt, cdn) {
        console.log("🔍 DEBUG: transfer_qty event triggered");
        let row = locals[cdt][cdn];
        // Validate transfer quantity
        if (flt(row.transfer_qty) > flt(row.pending_qty)) {
            frappe.msgprint(__("Transfer quantity cannot exceed pending quantity"));
            row.transfer_qty = row.pending_qty;
            frm.refresh_field("transfer_items");
        }
    }
}); 