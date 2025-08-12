// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bulk Work Order Manager", {
    refresh: function(frm) {
        // Add custom buttons
        frm.add_custom_button(__("Refresh Data"), function() {
            frm.trigger("refresh_data");
        }, __("Actions"));
        
        frm.add_custom_button(__("Auto Fill Delivery"), function() {
            frm.trigger("auto_fill_delivery");
        }, __("Actions"));
    },
    
    sales_order: function(frm) {
        if (frm.doc.sales_order) {
            // Fetch customer from sales order
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Sales Order",
                    filters: { name: frm.doc.sales_order },
                    fieldname: "customer"
                },
                callback: function(r) {
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
        if (!frm.doc.sales_order) {
            frappe.msgprint(__("Please select a Sales Order first"));
            return;
        }
        
        console.log("🔍 DEBUG: Starting fetch_work_orders for sales_order:", frm.doc.sales_order);
        
        // Show a simple loading message instead of progress bar
        frappe.show_alert(__("Fetching and populating work orders..."), 3);
        
        frappe.call({
            method: "manufacturing_addon.manufacturing_addon.doctype.bulk_work_order_manager.bulk_work_order_manager.populate_work_order_tables",
            args: {
                sales_order: frm.doc.sales_order,
                doc_name: frm.doc.name
            },
            timeout: 60, // 60 second timeout for server-side processing
            callback: function(r) {
                console.log("🔍 DEBUG: Server-side populate callback received:", r);
                if (r.message && r.message.success) {
                    console.log("🔍 DEBUG: Server-side populate successful:", r.message.message);
                    frappe.show_alert(__("Work orders populated successfully!"), 3);
                    
                    // If a new document was created, redirect to it
                    if (r.message.doc_name && r.message.doc_name !== frm.doc.name) {
                        console.log("🔍 DEBUG: Redirecting to new document:", r.message.doc_name);
                        frappe.set_route("Form", "Bulk Work Order Manager", r.message.doc_name);
                    } else {
                        // Reload the form to show the populated data
                        frm.reload_doc();
                    }
                } else {
                    console.log("🔍 DEBUG: Server-side populate failed:", r.message);
                    frappe.show_alert(__("Error populating work orders. Please try again."), 5);
                }
            },
            error: function(r) {
                console.error("❌ DEBUG: Error in server-side populate:", r);
                frappe.show_alert(__("Error populating work orders. Please try again."), 5);
            }
        });
    },
    
    populate_work_order_data: function(frm, work_orders) {
        try {
            console.log("🔍 DEBUG: Starting populate_work_order_data with", work_orders.length, "work orders");
            
            // Clear existing data
            frm.clear_table("work_order_details");
            frm.clear_table("work_order_summary");
            frm.clear_table("bulk_delivery_items");
            
            console.log("🔍 DEBUG: Cleared existing tables");
            
            // TEST: Add a simple test row to work_order_summary first
            console.log("🔍 DEBUG: Adding test row to work_order_summary");
            frm.add_child("work_order_summary", {
                item_code: "TEST-ITEM",
                item_name: "Test Item",
                total_ordered_qty: 100,
                total_delivered_qty: 50,
                total_pending_qty: 50,
                work_order_count: 1,
                status: "Partially Delivered"
            });
            frm.refresh_field("work_order_summary");
            console.log("🔍 DEBUG: Test row added to work_order_summary");
            
            // Now process the actual work orders
        
        // Group work orders by item
        let item_summary = {};
        
        work_orders.forEach(function(wo, index) {
            console.log(`🔍 DEBUG: Processing work order ${index + 1}:`, wo);
            
            if (!item_summary[wo.production_item]) {
                console.log(`🔍 DEBUG: Creating new item summary for ${wo.production_item}`);
                item_summary[wo.production_item] = {
                    item_code: wo.production_item,
                    item_name: wo.item_name,
                    total_ordered_qty: 0,
                    total_delivered_qty: 0,
                    total_pending_qty: 0,
                    work_orders: []
                };
            }
            
            let ordered_qty = flt(wo.qty);
            let delivered_qty = flt(wo.produced_qty);
            let pending_qty = ordered_qty - delivered_qty;
            
            console.log(`🔍 DEBUG: Quantities - Ordered: ${ordered_qty}, Delivered: ${delivered_qty}, Pending: ${pending_qty}`);
            
            item_summary[wo.production_item].total_ordered_qty += ordered_qty;
            item_summary[wo.production_item].total_delivered_qty += delivered_qty;
            item_summary[wo.production_item].total_pending_qty += pending_qty;
            item_summary[wo.production_item].work_orders.push(wo);
            
            // Add to work order details
            let detail_row = {
                work_order: wo.name,
                item_code: wo.production_item,
                item_name: wo.item_name,
                ordered_qty: ordered_qty,
                delivered_qty: delivered_qty,
                pending_qty: pending_qty,
                work_order_status: wo.status
            };
            
            console.log(`🔍 DEBUG: Adding work order detail:`, detail_row);
            frm.add_child("work_order_details", detail_row);
        });
        
        console.log("🔍 DEBUG: Item summary created:", item_summary);
        
        // Add to work order summary
        Object.values(item_summary).forEach(function(summary, index) {
            console.log(`🔍 DEBUG: Adding work order summary ${index + 1}:`, summary);
            
            let summary_row = {
                item_code: summary.item_code,
                item_name: summary.item_name,
                total_ordered_qty: summary.total_ordered_qty,
                total_delivered_qty: summary.total_delivered_qty,
                total_pending_qty: summary.total_pending_qty,
                work_order_count: summary.work_orders.length,
                status: get_delivery_status(summary.total_delivered_qty, summary.total_ordered_qty)
            };
            
            frm.add_child("work_order_summary", summary_row);
            
            // Add to bulk delivery items if there's pending quantity
            if (summary.total_pending_qty > 0) {
                console.log(`🔍 DEBUG: Adding bulk delivery item for ${summary.item_code} with pending qty ${summary.total_pending_qty}`);
                
                let delivery_row = {
                    item_code: summary.item_code,
                    item_name: summary.item_name,
                    total_pending_qty: summary.total_pending_qty,
                    delivery_qty: 0,
                    uom: "Nos",
                    warehouse: ""
                };
                
                frm.add_child("bulk_delivery_items", delivery_row);
            }
        });
        
        console.log("🔍 DEBUG: Refreshing form fields");
        frm.refresh_field("work_order_details");
        frm.refresh_field("work_order_summary");
        frm.refresh_field("bulk_delivery_items");
        
        console.log("🔍 DEBUG: populate_work_order_data completed successfully");
        frappe.msgprint(__("Work order data loaded successfully"));
        } catch (error) {
            console.error("❌ DEBUG: Error in populate_work_order_data:", error);
            frappe.show_alert(__("Error populating work order data: ") + error.message, 5);
        }
    },
    
    refresh_data: function(frm) {
        frm.trigger("fetch_work_orders");
    },
    
    auto_fill_delivery: function(frm) {
        // Auto-fill delivery quantities with pending quantities
        frm.doc.bulk_delivery_items.forEach(function(item) {
            if (item.total_pending_qty > 0) {
                item.delivery_qty = item.total_pending_qty;
            }
        });
        frm.refresh_field("bulk_delivery_items");
        frappe.msgprint(__("Delivery quantities auto-filled with pending quantities"));
    },
    
    auto_detect_type: function(frm) {
        // Auto-detect stock entry type based on items
        if (frm.doc.auto_detect_type) {
            frm.set_value("stock_entry_type", "Material Transfer for Manufacture");
            frm.refresh_field("stock_entry_type");
        }
    }
});

// Field events
frappe.ui.form.on("Bulk Work Order Manager", {
    auto_detect_type: function(frm) {
        frm.trigger("auto_detect_type");
    }
});

// Helper function
function get_delivery_status(delivered_qty, ordered_qty) {
    delivered_qty = flt(delivered_qty);
    ordered_qty = flt(ordered_qty);
    
    if (delivered_qty == 0) {
        return "Pending";
    } else if (delivered_qty >= ordered_qty) {
        return "Fully Delivered";
    } else {
        return "Partially Delivered";
    }
} 