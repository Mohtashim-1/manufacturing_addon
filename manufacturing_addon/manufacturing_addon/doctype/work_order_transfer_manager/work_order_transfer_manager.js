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
        
        // Only load dashboard if document is saved and not being edited
        if (frm.doc.name && !frm.doc.__islocal && !frm.is_dirty()) {
            // Add a small delay to ensure form is fully loaded
            setTimeout(() => {
                frm.trigger("load_dashboard_status");
            }, 200);
        }
        
        // Add manual refresh button for dashboard
        if (frm.doc.name && !frm.doc.__islocal) {
            frm.add_custom_button(__('🔄 Refresh Dashboard'), function() {
                frm.trigger("load_dashboard_status");
            }, __('Quick View'));
        }
        
        // Add Fetch Work Order button if sales order is selected but no work orders loaded yet
        if (frm.doc.sales_order && (!frm.doc.transfer_status || frm.doc.transfer_status === "Pending")) {
            frm.add_custom_button(__('📋 Fetch Work Order'), function() {
                frm.trigger("fetch_work_orders");
            }, __('Actions'));
        }
        
        // Add transfer-related buttons for submitted documents
        if (frm.doc.name && !frm.doc.__islocal && frm.doc.docstatus === 1) {
            // Create All Pending Transfer button
            frm.add_custom_button(__('🚀 Create All Pending Transfer'), function() {
                frm.trigger("create_all_pending_transfer");
            }, __('Actions'));
            
            // Create Remaining Transfer button
            frm.add_custom_button(__('🔄 Create Remaining Transfer'), function() {
                frm.trigger("create_remaining_transfer");
            }, __('Actions'));
            
            // Select All Items button
            frm.add_custom_button(__('✅ Select All Items'), function() {
                frm.trigger("select_all_items");
            }, __('Actions'));
            
            // Deselect All Items button
            frm.add_custom_button(__('❌ Deselect All Items'), function() {
                frm.trigger("deselect_all_items");
            }, __('Actions'));
        }
    },
    
    onload: function(frm) {
        // Load dashboard data when form loads, but only for saved documents
        if (frm.doc.name && !frm.doc.__islocal) {
            // Add a small delay to ensure form is fully loaded
            setTimeout(() => {
                frm.trigger("load_dashboard_status");
            }, 100);
        }
    },
    
    load_dashboard_status: function(frm) {
        // Don't load dashboard if form is dirty (has unsaved changes)
        if (frm.is_dirty()) {
            console.log("Dashboard loading skipped - form has unsaved changes");
            return;
        }
        
        // Don't load if already loading
        if (frm.dashboard_loading) {
            return;
        }
        
        // Don't load if form is in a transitional state (saving, submitting, etc.)
        if (frm.saving || frm.submitting) {
            console.log("Dashboard loading skipped - form is in transitional state");
            return;
        }
        
        // Don't load if form is being validated
        if (frm.validating) {
            console.log("Dashboard loading skipped - form is being validated");
            return;
        }
        
        // Don't load if dashboard is disabled
        if (frm.dashboard_disabled) {
            console.log("Dashboard loading skipped - dashboard is disabled");
            return;
        }
        
        frm.dashboard_loading = true;
        
        // Show loading spinner without affecting form state
        if (frm.fields_dict.dashboard_status) {
            const wrapper = $(frm.fields_dict.dashboard_status.wrapper);
            $(wrapper).empty();
            $(wrapper).append(`
                <div style="padding: 40px; text-align: center; color: #666;">
                    <div style="display: inline-block; width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #1976d2; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                    <div style="margin-top: 15px; font-size: 14px;">Loading dashboard data...</div>
                </div>
                <style>
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
            `);
        }
        
        // Use a completely isolated call to avoid any form state interference
        const original_dirty_state = frm.is_dirty();
        const original_unsaved_flag = frm.doc.__unsaved;
        
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.get_wotm_dashboard_data",
            args: {
                doc_name: frm.doc.name
            },
            callback: function(r) {
                frm.dashboard_loading = false;
                
                // Ensure form dirty state is preserved exactly as it was
                if (original_dirty_state !== frm.is_dirty()) {
                    console.log("Dashboard loading affected form dirty state - restoring");
                    frm.doc.__unsaved = original_unsaved_flag;
                    if (original_dirty_state) {
                        frm.$wrapper.addClass("dirty").removeClass("clean");
                    } else {
                        frm.$wrapper.removeClass("dirty").addClass("clean");
                    }
                }
                
                if (r.message) {
                    frm.events.render_dashboard_status(frm, r.message);
                } else {
                    // Show error message if no data
                    if (frm.fields_dict.dashboard_status) {
                        const wrapper = $(frm.fields_dict.dashboard_status.wrapper);
                        $(wrapper).empty();
                        $(wrapper).append('<div style="padding: 20px; text-align: center; color: #666;">No dashboard data available</div>');
                    }
                }
            },
            error: function(r) {
                frm.dashboard_loading = false;
                console.error('Error loading dashboard data:', r);
                
                // Ensure form dirty state is preserved exactly as it was
                if (original_dirty_state !== frm.is_dirty()) {
                    console.log("Dashboard loading affected form dirty state - restoring");
                    frm.doc.__unsaved = original_unsaved_flag;
                    if (original_dirty_state) {
                        frm.$wrapper.addClass("dirty").removeClass("clean");
                    } else {
                        frm.$wrapper.removeClass("dirty").addClass("clean");
                    }
                }
                
                // Show error message in the field if available
                if (frm.fields_dict.dashboard_status) {
                    const wrapper = $(frm.fields_dict.dashboard_status.wrapper);
                    $(wrapper).empty();
                    $(wrapper).append('<div style="padding: 20px; text-align: center; color: #d32f2f;">Error loading dashboard data</div>');
                }
            }
        });
    },
    
    render_dashboard_status: function(frm, data) {
        // Prevent rendering if form is in a transitional state
        if (frm._submitting || frm._saving || frm._validating || frm._dashboard_locked) {
            console.log('🔍 DEBUG: Skipping dashboard render - form is in transitional state or dashboard is locked');
            return;
        }
        
        if (frm.fields_dict.dashboard_status) {
            const wrapper = $(frm.fields_dict.dashboard_status.wrapper);
            const dashboard_html = create_wotm_dashboard_html(data);
            $(wrapper).empty();
            $(dashboard_html).appendTo(wrapper);
            
            // Mark that auto refresh has been used
            frm._dashboard_auto_refresh_used = true;
            console.log('🔍 DEBUG: Auto refresh marked as used - manual refresh required for future updates');
        }
    },
    
    force_load_dashboard_status: function(frm) {
        console.log('🔍 DEBUG: force_load_dashboard_status called - bypassing all checks');
        
        if (!frm.fields_dict.dashboard_status) {
            console.error('❌ ERROR: dashboard_status field not found!');
            return;
        }
        
        frm.call({
            method: 'manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.get_wotm_dashboard_data',
            args: { doc_name: frm.doc.name },
            callback: function(r) {
                console.log('🔍 DEBUG: Force API response received:', r);
                if (r.message) {
                    console.log('🔍 DEBUG: Force rendering dashboard with data:', r.message);
                    // Reset auto refresh flag for manual refresh
                    frm._dashboard_auto_refresh_used = false;
                    frm.events.render_dashboard_status(frm, r.message);
                } else {
                    console.warn('⚠️ WARNING: No dashboard data received in force load');
                }
            },
            error: function(r) {
                console.error('❌ ERROR force loading dashboard data:', r);
            }
        });
    },
    
    // Reload dashboard when items are updated - but only if not saving
    transfer_items: function(frm) {
        // Completely disable dashboard reloads during form operations
        // Dashboard will be reloaded manually after save/submit operations
        console.log("🔍 DEBUG: transfer_items changed - dashboard reload disabled");
    },
    
    work_order_details: function(frm) {
        // Completely disable dashboard reloads during form operations
        // Dashboard will be reloaded manually after save/submit operations
        console.log("🔍 DEBUG: work_order_details changed - dashboard reload disabled");
    },
    
    work_order_summary: function(frm) {
        // Completely disable dashboard reloads during form operations
        // Dashboard will be reloaded manually after save/submit operations
        console.log("🔍 DEBUG: work_order_summary changed - dashboard reload disabled");
    },
    
    // Add save events to prevent dashboard interference
    before_save: function(frm) {
        // Set flag to prevent dashboard loading during save
        frm.saving = true;
        frm.dashboard_disabled = true;
        
        // Clear any pending dashboard reloads
        if (frm.dashboard_reload_timeout) {
            clearTimeout(frm.dashboard_reload_timeout);
            frm.dashboard_reload_timeout = null;
        }
    },
    
    before_submit: function(frm) {
        console.log("🔍 DEBUG: before_submit() called");
        frm._submitting = true;
        
        // Clear any pending dashboard reload
        if (frm._dashboard_reload_timeout) {
            clearTimeout(frm._dashboard_reload_timeout);
            frm._dashboard_reload_timeout = null;
        }
        
        // Prevent any dashboard operations during submit
        frm._dashboard_locked = true;
    },
    
    after_submit: function(frm) {
        console.log("🔍 DEBUG: after_submit() called");
        frm._submitting = false;
        frm._form_modified = false; // Reset form modification flag
        frm._dashboard_locked = false; // Unlock dashboard operations
        frm._stock_refresh_done = false; // Reset stock refresh flag
        
        // Reset auto refresh flag to allow one more automatic refresh after submit
        frm._dashboard_auto_refresh_used = false;
        
        // Reload dashboard after submit is complete
        setTimeout(() => {
            if (frm.doc.name && !frm.doc.__islocal) {
                frm.trigger("load_dashboard_status");
            }
        }, 1000);
    },
    
    after_save: function(frm) {
        // Clear saving flag
        frm.saving = false;
        
        // Re-enable dashboard after a delay
        setTimeout(() => {
            frm.dashboard_disabled = false;
        }, 500);
        
        // Reload dashboard after successful save with a longer delay
        setTimeout(() => {
            frm.trigger("load_dashboard_status");
        }, 1000);
    },
    
    // Clean up when form is destroyed
    onload_post_render: function(frm) {
        // Set up cleanup when form is destroyed
        frm.$wrapper.on('destroy', function() {
            if (frm._dashboard_reload_timeout) {
                clearTimeout(frm._dashboard_reload_timeout);
                frm._dashboard_reload_timeout = null;
            }
        });
    },
    
    // Add validation to prevent dashboard interference
    validate: function(frm) {
        // Set validating flag
        frm.validating = true;
        frm.dashboard_disabled = true;
        
        // Clear any pending dashboard reloads during validation
        if (frm.dashboard_reload_timeout) {
            clearTimeout(frm.dashboard_reload_timeout);
            frm.dashboard_reload_timeout = null;
        }
        
        // Simple validation - just set company if needed
        let company = frm.doc.company || frappe.defaults.get_default("company");
        
        if (frm.doc.transfer_items && frm.doc.transfer_items.length > 0) {
            frm.doc.transfer_items.forEach(function(item) {
                if (!item.company) {
                    item.company = company;
                }
            });
        }
        
        // Clear validating flag after a short delay
        setTimeout(() => {
            frm.validating = false;
            frm.dashboard_disabled = false;
        }, 100);
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
        
        // Only refresh stock snapshots if the form is not being saved/submitted
        // and if the document hasn't been modified locally
        if (frm._submitting || frm._saving || frm._validating || frm._form_modified) {
            console.log("🔍 DEBUG: Skipping stock snapshot refresh - form is in transitional state or has been modified");
            return;
        }
        
        // Mark that stock refresh is being done
        frm._stock_refresh_done = true;
        
        // Use a read-only method to get stock snapshots without modifying the document
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.get_stock_snapshots_only",
            args: {
                doc_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message && r.message.success && !frm._submitting && !frm._saving && !frm._validating) {
                    // Update the actual quantities in the form without saving to database
                    if (r.message.stock_data && frm.doc.transfer_items) {
                        r.message.stock_data.forEach(function(stock_item) {
                            let form_item = frm.doc.transfer_items.find(item => item.item_code === stock_item.item_code);
                            if (form_item) {
                                form_item.actual_qty_at_warehouse = stock_item.actual_qty_at_warehouse;
                                form_item.actual_qty_at_company = stock_item.actual_qty_at_company;
                            }
                        });
                        frm.refresh_field("transfer_items");
                        console.log("🔍 DEBUG: Stock snapshots refreshed successfully");
                    }
                }
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
         console.log("🔍 DEBUG: Starting background transfer job (no UI)");
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.create_all_pending_transfer_background",
            args: {
                doc_name: frm.doc.name
            },
            freeze: false,
            callback: function(r) {
                console.log("🔍 DEBUG: Background job started callback:", r);
                if (r.message && r.message.success) {
                    frappe.show_alert({ message: __("Background job started"), indicator: "green" });
                } else {
                    frappe.show_alert({ message: __("Error starting background job"), indicator: "red" });
                }
            },
            error: function(err) {
                console.error("❌ DEBUG: Error starting background job:", err);
                frappe.show_alert({ message: __("Error starting background job"), indicator: "red" });
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
    },

    update_transfer_status: function(frm) {
        console.log("🔍 DEBUG: update_transfer_status() called");
        if (!frm.doc.name) {
            frappe.msgprint(__("Please save the document first"));
            return;
        }
        
        // Check if document is submitted
        if (frm.doc.docstatus !== 1) {
            frappe.msgprint(__("This function is only available for submitted documents"));
            return;
        }
        
        // Show confirmation dialog
        frappe.confirm(
            __("This will update the transfer status and quantities based on all submitted Raw Material Transfers. Continue?"),
            function() {
                // User confirmed
                frappe.show_alert(__("Updating transfer status..."), 3);
                
                frappe.call({
                    method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.update_transfer_quantities",
                    args: {
                        doc_name: frm.doc.name
                    },
                    callback: function(r) {
                        console.log("🔍 DEBUG: Update transfer status callback:", r);
                        if (r.message && r.message.success) {
                            frappe.show_alert(__("Transfer status updated successfully!"), 3);
                            // Reload the form to show updated data
                            frm.reload_doc();
                        } else {
                            frappe.show_alert(__("Error updating transfer status: ") + (r.message ? r.message.message : "Unknown error"), 5);
                        }
                    },
                    error: function(r) {
                        console.error("❌ DEBUG: Error updating transfer status:", r);
                        frappe.show_alert(__("Error updating transfer status. Please try again."), 5);
                    }
                });
            },
            function() {
                // User cancelled
                console.log("🔍 DEBUG: User cancelled transfer status update");
            }
        );
    },

    test_dashboard: function(frm) {
        console.log("🔍 DEBUG: Testing dashboard functionality");
        
        // Test if dashboard field exists
        if (frm.fields_dict.dashboard_status) {
            console.log("✅ Dashboard field found");
            frappe.show_alert(__("Dashboard field is working! ✅"), 3);
        } else {
            console.log("❌ Dashboard field not found");
            frappe.show_alert(__("Dashboard field not found! ❌"), 5);
        }
        
        // Test API call
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.get_wotm_dashboard_data",
            args: {
                doc_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message) {
                    console.log("✅ API call successful");
                    frappe.show_alert(__("API call successful! ✅"), 3);
                } else {
                    console.log("❌ API call failed");
                    frappe.show_alert(__("API call failed! ❌"), 5);
                }
            },
            error: function(r) {
                console.log("❌ API call error:", r);
                frappe.show_alert(__("API call error! ❌"), 5);
            }
        });
    },

    // Add field change handler to prevent dashboard interference
    field_change: function(frm, fieldname, value) {
        // Clear any pending dashboard reloads when fields change
        if (frm.dashboard_reload_timeout) {
            clearTimeout(frm.dashboard_reload_timeout);
            frm.dashboard_reload_timeout = null;
        }
    },


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

function create_wotm_dashboard_html(data) {
    let html = `
        <div style="padding: 20px; background: #f8f9fa; border-radius: 8px; margin: 10px 0;">
            <!-- Header Section -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div>
                    <h3 style="margin: 0; color: #333; font-size: 18px;">${data.customer_name || data.customer}</h3>
                    <p style="margin: 5px 0; color: #666; font-size: 12px;">WOTM: ${data.wotm_name}</p>
                    <p style="margin: 5px 0; color: #666; font-size: 12px;">Sales Order: ${data.sales_order}</p>
                    <p style="margin: 5px 0; color: #666; font-size: 12px;">Date: ${data.posting_date}</p>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 20px; font-weight: bold; color: ${data.status_info.status_color};">${data.status_info.status}</div>
                    <div style="color: #666; font-size: 12px;">${data.status_info.message}</div>
                    <button onclick="cur_frm.trigger('load_dashboard_status')" style="margin-top: 10px; padding: 5px 10px; background: #1976d2; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">🔄 Refresh</button>
                </div>
            </div>

            <!-- KPI Cards -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
                <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #1976d2;">${data.total_work_orders}</div>
                    <div style="color: #666; font-size: 12px;">Total Work Orders</div>
                </div>
                <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #2e7d32;">${data.total_transferred}</div>
                    <div style="color: #666; font-size: 12px;">Total Transferred</div>
                </div>
                <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #f57c00;">${data.total_pending}</div>
                    <div style="color: #666; font-size: 12px;">Total Pending</div>
                </div>
                <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #1976d2;">${data.total_raw_materials}</div>
                    <div style="color: #666; font-size: 12px;">Raw Materials</div>
                </div>
            </div>

            <!-- Progress Bars -->
            <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px;">
                <h4 style="margin: 0 0 15px 0; color: #333; font-size: 16px;">Transfer Progress Overview</h4>
                
                <!-- Overall Transfer Progress -->
                <div style="margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-size: 14px; color: #333;">Overall Transfer Progress</span>
                        <span style="font-size: 14px; font-weight: bold; color: #2e7d32;">${data.overall_transfer_percentage}%</span>
                    </div>
                    <div style="background: #e0e0e0; height: 12px; border-radius: 6px; overflow: hidden;">
                        <div style="background: #2e7d32; height: 100%; width: ${data.overall_transfer_percentage}%; transition: width 0.3s;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 11px; color: #666;">
                        <span>Transferred: ${data.total_transferred}</span>
                        <span>Pending: ${data.total_pending}</span>
                    </div>
                </div>
                
                <!-- Work Order Progress -->
                <div style="margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-size: 14px; color: #333;">Work Order Progress</span>
                        <span style="font-size: 14px; font-weight: bold; color: #f57c00;">${data.work_order_progress_percentage}%</span>
                    </div>
                    <div style="background: #e0e0e0; height: 12px; border-radius: 6px; overflow: hidden;">
                        <div style="background: #f57c00; height: 100%; width: ${data.work_order_progress_percentage}%; transition: width 0.3s;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 11px; color: #666;">
                        <span>Completed: ${data.completed_work_orders}</span>
                        <span>Total: ${data.total_work_orders}</span>
                    </div>
                </div>
            </div>

            <!-- Work Order Summary Table -->
            <div style="background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px;">
                <h4 style="margin: 0; padding: 15px; background: #f8f9fa; border-bottom: 1px solid #e0e0e0; font-size: 16px;">Work Order Summary</h4>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                        <thead>
                            <tr style="background: #f8f9fa;">
                                <th style="padding: 10px; text-align: left; border-bottom: 1px solid #e0e0e0;">Item</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">Ordered</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">Transferred</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">Pending</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">Progress %</th>
                            </tr>
                        </thead>
                        <tbody>
    `;
    
    data.work_order_summary.forEach(item => {
        let progress_color = item.progress_percentage >= 100 ? '#2e7d32' : item.progress_percentage > 0 ? '#f57c00' : '#d32f2f';
        
        html += `
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e0e0e0;">
                    <div style="font-weight: bold; font-size: 11px;">${item.item_code}</div>
                    <div style="font-size: 10px; color: #666;">${item.item_name}</div>
                </td>
                <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">${item.total_ordered_qty}</td>
                <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">
                    <span style="color: #2e7d32; font-weight: bold;">${item.total_transferred_qty}</span>
                </td>
                <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">
                    <span style="color: #d32f2f; font-weight: bold;">${item.total_pending_qty}</span>
                </td>
                <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">
                    <div style="display: flex; align-items: center; justify-content: center;">
                        <div style="width: 40px; background: #e0e0e0; height: 6px; border-radius: 3px; margin-right: 5px;">
                            <div style="background: ${progress_color}; height: 100%; width: ${item.progress_percentage}%; border-radius: 3px;"></div>
                        </div>
                        <span style="font-size: 10px; color: ${progress_color}; font-weight: bold;">${item.progress_percentage}%</span>
                    </div>
                </td>
            </tr>
        `;
    });
    
    html += `
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Raw Materials Table -->
            <div style="background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h4 style="margin: 0; padding: 15px; background: #f8f9fa; border-bottom: 1px solid #e0e0e0; font-size: 16px;">Raw Materials Transfer Status</h4>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                        <thead>
                            <tr style="background: #f8f9fa;">
                                <th style="padding: 10px; text-align: left; border-bottom: 1px solid #e0e0e0;">Item</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">Required</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">Transferred</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">Pending</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">Status</th>
                                <th style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">Progress %</th>
                            </tr>
                        </thead>
                        <tbody>
    `;
    
    data.raw_materials.forEach(item => {
        let status_color = item.item_transfer_status === 'Completed' ? '#2e7d32' : item.item_transfer_status === 'In Progress' ? '#f57c00' : '#d32f2f';
        let progress_color = item.item_transfer_percentage >= 100 ? '#2e7d32' : item.item_transfer_percentage > 0 ? '#f57c00' : '#d32f2f';
        
        html += `
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e0e0e0;">
                    <div style="font-weight: bold; font-size: 11px;">${item.item_code}</div>
                    <div style="font-size: 10px; color: #666;">${item.item_name}</div>
                </td>
                <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">${item.total_required_qty}</td>
                <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">
                    <span style="color: #2e7d32; font-weight: bold;">${item.transferred_qty_so_far}</span>
                </td>
                <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">
                    <span style="color: #d32f2f; font-weight: bold;">${item.pending_qty}</span>
                </td>
                <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">
                    <span style="color: ${status_color}; font-weight: bold; font-size: 10px;">${item.item_transfer_status}</span>
                </td>
                <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0;">
                    <div style="display: flex; align-items: center; justify-content: center;">
                        <div style="width: 40px; background: #e0e0e0; height: 6px; border-radius: 3px; margin-right: 5px;">
                            <div style="background: ${progress_color}; height: 100%; width: ${item.item_transfer_percentage}%; border-radius: 3px;"></div>
                        </div>
                        <span style="font-size: 10px; color: ${progress_color}; font-weight: bold;">${item.item_transfer_percentage}%</span>
                    </div>
                </td>
            </tr>
        `;
    });
    
    html += `
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
    
    return html;
} 