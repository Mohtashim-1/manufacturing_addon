// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Order Transfer Manager", {
    refresh: function(frm) {
        console.log("🔍 DEBUG: refresh() called for Work Order Transfer Manager");
        
        // Set company field if not set
        if (!frm.doc.company) {
            frm.set_value("company", frappe.defaults.get_default("company"));
        }
        
        // Set up initial filters for sales_order field
        frm.trigger("setup_sales_order_filter");
        
        // Refresh stock snapshots for grid when form opens, but not during submission
        // Check if we're in the middle of a submit action
        if (frm.doc.name && !frm.doc.__islocal && frm.doc.docstatus === 0 && !frm._submitting) {
            frm.trigger("refresh_stock_snapshots");
        }
        
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
        
        // Add quick view buttons for related documents
        frm.add_custom_button(__("View Sales Order"), function() {
            if (frm.doc.sales_order) {
                frappe.set_route("Form", "Sales Order", frm.doc.sales_order);
            } else {
                frappe.msgprint(__("No Sales Order linked"));
            }
        }, __("Quick View"));
        
        frm.add_custom_button(__("View Work Orders"), function() {
            frm.trigger("show_work_orders");
        }, __("Quick View"));
        
        frm.add_custom_button(__("View Raw Material Transfers"), function() {
            frm.trigger("show_raw_material_transfers");
        }, __("Quick View"));
        
        frm.add_custom_button(__("View Stock Entries"), function() {
            frm.trigger("show_stock_entries");
        }, __("Quick View"));
    },
    
    before_save: function(frm) {
        console.log("🔍 DEBUG: before_save() called");
        frm._submitting = true;
    },
    
    after_save: function(frm) {
        console.log("🔍 DEBUG: after_save() called");
        frm._submitting = false;
    },
    
    validate: function(frm) {
        // Ensure company is set in all child rows
        let company = frm.doc.company || frappe.defaults.get_default("company");
        
        if (frm.doc.transfer_items && frm.doc.transfer_items.length > 0) {
            frm.doc.transfer_items.forEach(function(item) {
                if (!item.company) {
                    item.company = company;
                }
            });
        }
        
        if (frm.doc.work_order_details && frm.doc.work_order_details.length > 0) {
            frm.doc.work_order_details.forEach(function(item) {
                if (!item.company) {
                    item.company = company;
                }
            });
        }
        
        if (frm.doc.work_order_summary && frm.doc.work_order_summary.length > 0) {
            frm.doc.work_order_summary.forEach(function(item) {
                if (!item.company) {
                    item.company = company;
                }
            });
        }
    },
    
    setup_company_in_child_tables: function(frm) {
        // Ensure company is set in all child table items
        let company = frm.doc.company || frappe.defaults.get_default("company");
        
        if (frm.doc.transfer_items && frm.doc.transfer_items.length > 0) {
            frm.doc.transfer_items.forEach(function(item) {
                if (!item.company) {
                    item.company = company;
                }
            });
            frm.refresh_field("transfer_items");
        }
        
        if (frm.doc.work_order_details && frm.doc.work_order_details.length > 0) {
            frm.doc.work_order_details.forEach(function(item) {
                if (!item.company) {
                    item.company = company;
                }
            });
            frm.refresh_field("work_order_details");
        }
        
        if (frm.doc.work_order_summary && frm.doc.work_order_summary.length > 0) {
            frm.doc.work_order_summary.forEach(function(item) {
                if (!item.company) {
                    item.company = company;
                }
            });
            frm.refresh_field("work_order_summary");
        }
    },
    
    refresh_stock_snapshots: function(frm) {
        if (!frm.doc.name) return;
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.update_transfer_quantities",
            args: {
                doc_name: frm.doc.name,
                transfer_doc_name: "" // just refresh snapshots without a transfer
            },
            callback: function() {
                frm.refresh_field("transfer_items");
            }
        });
    },
    
    setup_sales_order_filter: function(frm) {
        console.log("🔍 DEBUG: setup_sales_order_filter() called");
        // Set up initial filter for sales_order field
        frm.set_query("sales_order", function() {
            let filters = {
                docstatus: 1  // Only submitted sales orders
            };
            
            // If customer is selected, add customer filter
            if (frm.doc.customer) {
                filters.customer = frm.doc.customer;
            }
            
            return { filters: filters };
        });
        
        // Set up warehouse filters
        frm.set_query("source_warehouse", function() {
            return {
                filters: {
                    is_group: 0  // Only show actual warehouses, not groups
                }
            };
        });
        
        frm.set_query("target_warehouse", function() {
            return {
                filters: {
                    is_group: 0  // Only show actual warehouses, not groups
                }
            };
        });
    },
    
    customer: function(frm) {
        console.log("🔍 DEBUG: customer event triggered");
        if (frm.doc.customer) {
            console.log("🔍 DEBUG: Customer selected:", frm.doc.customer);
            
            // Set filter for sales_order field to show only sales orders for this customer
            frm.set_query("sales_order", function() {
                return {
                    filters: {
                        customer: frm.doc.customer,
                        docstatus: 1  // Only submitted sales orders
                    }
                };
            });
            
            // Clear sales order if it doesn't match the selected customer
            if (frm.doc.sales_order) {
                frappe.call({
                    method: "frappe.client.get_value",
                    args: {
                        doctype: "Sales Order",
                        filters: { name: frm.doc.sales_order },
                        fieldname: "customer"
                    },
                    callback: function(r) {
                        if (r.message && r.message.customer && r.message.customer !== frm.doc.customer) {
                            // Sales order belongs to different customer, clear it
                            frm.set_value("sales_order", "");
                        }
                    }
                });
            }
        } else {
            // If no customer selected, clear the filter
            frm.set_query("sales_order", function() {
                return {
                    filters: {
                        docstatus: 1  // Only submitted sales orders
                    }
                };
            });
        }
    },
    
    sales_order: function(frm) {
        console.log("🔍 DEBUG: sales_order event triggered");
        if (frm.doc.sales_order) {
            console.log("🔍 DEBUG: Sales order selected:", frm.doc.sales_order);
            // Fetch customer from sales order (if not already set)
            if (!frm.doc.customer) {
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
            }
            
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
                        
                        // Ensure company is set in child tables after reload
                        setTimeout(function() {
                            frm.trigger("setup_company_in_child_tables");
                        }, 1000);
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
                            // Reload the form to show updated transfer quantities
                            frm.reload_doc();
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
            `This will create a Raw Material Transfer document with ALL pending raw materials using a background job.\n\nThis may take a few minutes for large datasets.\n\n${pending_summary}`,
            function() {
                // User confirmed - start background job
                frm.trigger("start_background_transfer_job");
            },
            function() {
                // User cancelled
                console.log("🔍 DEBUG: User cancelled all pending transfer creation");
            }
        );
    },
    
    start_background_transfer_job: function(frm) {
        console.log("🔍 DEBUG: Starting background transfer job");
        
        // Show progress dialog
        let progress_dialog = new frappe.ui.Dialog({
            title: __("Creating Raw Material Transfer"),
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'progress_html',
                    options: `
                        <div style="text-align: center; padding: 20px;">
                            <div class="progress-bar" style="width: 100%; height: 20px; background-color: #f0f0f0; border-radius: 10px; overflow: hidden;">
                                <div class="progress-fill" style="width: 0%; height: 100%; background-color: #5cb85c; transition: width 0.3s ease;"></div>
                            </div>
                            <div style="margin-top: 10px; font-size: 14px;">
                                <span class="progress-text">Starting background job...</span>
                            </div>
                            <div style="margin-top: 5px; font-size: 12px; color: #666;">
                                <span class="progress-details">Processing ${frm.doc.transfer_items.filter(item => flt(item.pending_qty) > 0).length} items</span>
                            </div>
                        </div>
                    `
                }
            ],
            primary_action_label: __("Close"),
            primary_action: function() {
                progress_dialog.hide();
            }
        });
        
        progress_dialog.show();
        
        // Start the background job
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.create_all_pending_transfer_background",
            args: {
                doc_name: frm.doc.name
            },
            callback: function(r) {
                console.log("🔍 DEBUG: Background job started callback:", r);
                if (r.message && r.message.success) {
                    // Update progress
                    let progress_fill = progress_dialog.get_field('progress_html').$wrapper.find('.progress-fill');
                    let progress_text = progress_dialog.get_field('progress_html').$wrapper.find('.progress-text');
                    let progress_details = progress_dialog.get_field('progress_html').$wrapper.find('.progress-details');
                    
                    progress_fill.css('width', '50%');
                    progress_text.text("Background job started successfully");
                    progress_details.text("Waiting for completion...");
                    
                    // Set up real-time listeners
                    frappe.realtime.on('raw_material_transfer_created', function(data) {
                        console.log("🔍 DEBUG: Raw material transfer created:", data);
                        progress_fill.css('width', '100%');
                        progress_text.text("Raw Material Transfer created successfully!");
                        progress_details.text(`Document: ${data.doc_name}`);
                        
                        // Show success message and offer to open the document
                        setTimeout(function() {
                            progress_dialog.hide();
                            frappe.show_alert(__("Raw Material Transfer document created successfully!"), 5);
                            // Reload the form to show updated transfer quantities
                            frm.reload_doc();
                            
                            frappe.confirm(
                                __("Would you like to open the newly created Raw Material Transfer document?"),
                                function() {
                                    // User wants to open the document
                                    frappe.set_route("Form", "Raw Material Transfer", data.doc_name);
                                },
                                function() {
                                    // User doesn't want to open it
                                    console.log("User chose not to open the document");
                                }
                            );
                        }, 2000);
                    });
                    
                    frappe.realtime.on('raw_material_transfer_error', function(data) {
                        console.log("🔍 DEBUG: Raw material transfer error:", data);
                        progress_fill.css('width', '100%').css('background-color', '#d9534f');
                        progress_text.text("Error occurred during creation");
                        progress_details.text(data.message);
                        
                        setTimeout(function() {
                            progress_dialog.hide();
                            frappe.show_alert(__("Error creating Raw Material Transfer: ") + data.message, 8);
                        }, 3000);
                    });
                    
                } else {
                    progress_dialog.hide();
                    frappe.show_alert(__("Error starting background job: ") + (r.message ? r.message.message : "Unknown error"), 5);
                }
            }
        });
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
                                        // Reload the form to show updated transfer quantities
                                        frm.reload_doc();
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
    },
    
    show_work_orders: function(frm) {
        console.log("🔍 DEBUG: show_work_orders() called");
        if (!frm.doc.sales_order) {
            frappe.msgprint(__("No Sales Order linked"));
            return;
        }
        
        // Show work orders in a dialog
        let d = new frappe.ui.Dialog({
            title: __("Work Orders for Sales Order: ") + frm.doc.sales_order,
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'work_orders_html',
                    options: '<div style="text-align: center; padding: 20px;">Loading work orders...</div>'
                }
            ],
            size: 'large'
        });
        
        d.show();
        
        // Fetch work orders
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Work Order",
                filters: { sales_order: frm.doc.sales_order },
                fields: ["name", "production_item", "qty", "material_transferred_for_manufacturing", "produced_qty", "status", "docstatus"],
                order_by: "creation desc"
            },
            callback: function(r) {
                if (r.message) {
                    let html = '<div style="max-height: 400px; overflow-y: auto;">';
                    html += '<table class="table table-bordered">';
                    html += '<thead><tr><th>Work Order</th><th>Item</th><th>Qty</th><th>Transferred</th><th>Produced</th><th>Status</th><th>Action</th></tr></thead>';
                    html += '<tbody>';
                    
                    r.message.forEach(function(wo) {
                        html += '<tr>';
                        html += `<td>${wo.name}</td>`;
                        html += `<td>${wo.production_item}</td>`;
                        html += `<td>${wo.qty}</td>`;
                        html += `<td>${wo.material_transferred_for_manufacturing || 0}</td>`;
                        html += `<td>${wo.produced_qty || 0}</td>`;
                        html += `<td><span class="label label-${wo.docstatus === 1 ? 'success' : 'default'}">${wo.status}</span></td>`;
                        html += `<td><button class="btn btn-xs btn-default" onclick="frappe.set_route('Form', 'Work Order', '${wo.name}')">View</button></td>`;
                        html += '</tr>';
                    });
                    
                    html += '</tbody></table></div>';
                    
                    d.get_field('work_orders_html').$wrapper.html(html);
                } else {
                    d.get_field('work_orders_html').$wrapper.html('<div style="text-align: center; padding: 20px; color: #666;">No work orders found</div>');
                }
            }
        });
    },
    
    show_raw_material_transfers: function(frm) {
        console.log("🔍 DEBUG: show_raw_material_transfers() called");
        if (!frm.doc.name) {
            frappe.msgprint(__("Please save the document first"));
            return;
        }
        
        // Show raw material transfers in a dialog
        let d = new frappe.ui.Dialog({
            title: __("Raw Material Transfers"),
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'transfers_html',
                    options: '<div style="text-align: center; padding: 20px;">Loading transfers...</div>'
                }
            ],
            size: 'large'
        });
        
        d.show();
        
        // Fetch raw material transfers
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Raw Material Transfer",
                filters: { work_order_transfer_manager: frm.doc.name },
                fields: ["name", "posting_date", "total_transfer_qty", "total_items", "docstatus", "stock_entry"],
                order_by: "creation desc"
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    let html = '<div style="max-height: 400px; overflow-y: auto;">';
                    html += '<table class="table table-bordered">';
                    html += '<thead><tr><th>Transfer</th><th>Date</th><th>Items</th><th>Total Qty</th><th>Status</th><th>Stock Entry</th><th>Action</th></tr></thead>';
                    html += '<tbody>';
                    
                    r.message.forEach(function(transfer) {
                        html += '<tr>';
                        html += `<td>${transfer.name}</td>`;
                        html += `<td>${transfer.posting_date}</td>`;
                        html += `<td>${transfer.total_items || 0}</td>`;
                        html += `<td>${transfer.total_transfer_qty || 0}</td>`;
                        html += `<td><span class="label label-${transfer.docstatus === 1 ? 'success' : 'default'}">${transfer.docstatus === 1 ? 'Submitted' : 'Draft'}</span></td>`;
                        html += `<td>${transfer.stock_entry || '-'}</td>`;
                        html += `<td><button class="btn btn-xs btn-default" onclick="frappe.set_route('Form', 'Raw Material Transfer', '${transfer.name}')">View</button></td>`;
                        html += '</tr>';
                    });
                    
                    html += '</tbody></table></div>';
                    
                    d.get_field('transfers_html').$wrapper.html(html);
                } else {
                    d.get_field('transfers_html').$wrapper.html('<div style="text-align: center; padding: 20px; color: #666;">No raw material transfers found</div>');
                }
            }
        });
    },
    
    show_stock_entries: function(frm) {
        console.log("🔍 DEBUG: show_stock_entries() called");
        if (!frm.doc.sales_order) {
            frappe.msgprint(__("No Sales Order linked"));
            return;
        }
        
        // Show stock entries in a dialog
        let d = new frappe.ui.Dialog({
            title: __("Stock Entries for Sales Order: ") + frm.doc.sales_order,
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'stock_entries_html',
                    options: '<div style="text-align: center; padding: 20px;">Loading stock entries...</div>'
                }
            ],
            size: 'large'
        });
        
        d.show();
        
        // Fetch stock entries
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Stock Entry",
                filters: { 
                    custom_cost_center: ["like", "%" + frm.doc.sales_order + "%"],
                    docstatus: ["!=", 2]  // Not cancelled
                },
                fields: ["name", "stock_entry_type", "posting_date", "posting_time", "docstatus", "custom_cost_center"],
                order_by: "creation desc"
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    let html = '<div style="max-height: 400px; overflow-y: auto;">';
                    html += '<table class="table table-bordered">';
                    html += '<thead><tr><th>Stock Entry</th><th>Type</th><th>Date</th><th>Time</th><th>Status</th><th>Cost Center</th><th>Action</th></tr></thead>';
                    html += '<tbody>';
                    
                    r.message.forEach(function(se) {
                        html += '<tr>';
                        html += `<td>${se.name}</td>`;
                        html += `<td>${se.stock_entry_type}</td>`;
                        html += `<td>${se.posting_date}</td>`;
                        html += `<td>${se.posting_time || '-'}</td>`;
                        html += `<td><span class="label label-${se.docstatus === 1 ? 'success' : 'default'}">${se.docstatus === 1 ? 'Submitted' : 'Draft'}</span></td>`;
                        html += `<td>${se.custom_cost_center || '-'}</td>`;
                        html += `<td><button class="btn btn-xs btn-default" onclick="frappe.set_route('Form', 'Stock Entry', '${se.name}')">View</button></td>`;
                        html += '</tr>';
                    });
                    
                    html += '</tbody></table></div>';
                    
                    d.get_field('stock_entries_html').$wrapper.html(html);
                } else {
                    d.get_field('stock_entries_html').$wrapper.html('<div style="text-align: center; padding: 20px; color: #666;">No stock entries found</div>');
                }
            }
        });
    },
    
    source_warehouse: function(frm) {
        console.log("🔍 DEBUG: source_warehouse event triggered");
        if (frm.doc.source_warehouse && frm.doc.transfer_items) {
            // Update warehouse field and refresh actual quantities in transfer items
            frm.doc.transfer_items.forEach(function(item) {
                item.warehouse = frm.doc.source_warehouse;
                // Reset actual quantity - will be updated when form is saved/reloaded
                item.actual_qty_at_warehouse = 0;
            });
            frm.refresh_field("transfer_items");
            
            // Show message to user
            frappe.show_alert(__("Warehouse updated. Please save and reload to see updated actual quantities."), 3);
        }
    },
    
    target_warehouse: function(frm) {
        console.log("🔍 DEBUG: target_warehouse event triggered");
        // Add any target warehouse specific logic here if needed
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