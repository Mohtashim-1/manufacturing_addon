// Custom Purchase Order JavaScript for UOM conversion
// Allows user to enter qty (Purchase UOM) and stock_qty (Stock UOM) when they differ
// Automatically calculates conversion_factor from qty and stock_qty

frappe.ui.form.on("Purchase Order Item", {
	item_code: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		console.log("[PO Item] item_code changed:", {
			item_code: item.item_code,
			uom: item.uom,
			stock_uom: item.stock_uom
		});
		
		if (item.item_code && item.uom && item.stock_uom) {
			// If UOM != Stock UOM, user can enter both qty and stock_qty
			if (item.uom != item.stock_uom) {
				// Auto-fetch conversion factor from Item master if not set
				if (!item.conversion_factor || item.conversion_factor == 1) {
					fetch_conversion_factor_from_item(frm, cdt, cdn);
				}
			} else {
				// If UOM == Stock UOM, set conversion_factor to 1
				frappe.model.set_value(cdt, cdn, "conversion_factor", 1);
				update_stock_qty_from_qty(frm, cdt, cdn);
			}
		}
	},

	uom: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		if (item.item_code && item.uom && item.stock_uom) {
			// If UOM changed and != Stock UOM, fetch conversion factor
			if (item.uom != item.stock_uom) {
				fetch_conversion_factor_from_item(frm, cdt, cdn);
			} else {
				// If UOM == Stock UOM, set conversion_factor to 1
				frappe.model.set_value(cdt, cdn, "conversion_factor", 1);
				update_stock_qty_from_qty(frm, cdt, cdn);
			}
		}
	},

	stock_uom: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		if (item.item_code && item.uom && item.stock_uom) {
			// If Stock UOM changed and != UOM, fetch conversion factor
			if (item.uom != item.stock_uom) {
				fetch_conversion_factor_from_item(frm, cdt, cdn);
			} else {
				// If UOM == Stock UOM, set conversion_factor to 1
				frappe.model.set_value(cdt, cdn, "conversion_factor", 1);
				update_stock_qty_from_qty(frm, cdt, cdn);
			}
		}
	},

	qty: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		console.log("[PO Item] qty changed:", {
			item_code: item.item_code,
			qty: item.qty,
			stock_qty: item.stock_qty,
			conversion_factor: item.conversion_factor,
			uom: item.uom,
			stock_uom: item.stock_uom
		});
		
		if (item.item_code && item.uom && item.stock_uom) {
			if (item.uom != item.stock_uom) {
				// If UOM != Stock UOM and user manually set stock_qty, don't overwrite it
				if (item._manual_stock_qty) {
					// Recalculate conversion_factor from qty and stock_qty
					if (item.qty && item.qty > 0 && item.stock_qty && item.stock_qty > 0) {
						var new_conversion_factor = flt(item.stock_qty) / flt(item.qty);
						console.log("[PO Item] Recalculating conversion_factor from qty and stock_qty:", new_conversion_factor);
						frappe.model.set_value(cdt, cdn, "conversion_factor", new_conversion_factor);
					}
				} else {
					// Update stock_qty from qty and conversion_factor
					update_stock_qty_from_qty(frm, cdt, cdn);
				}
			} else {
				// If UOM == Stock UOM, stock_qty = qty
				update_stock_qty_from_qty(frm, cdt, cdn);
			}
		}
	},

	stock_qty: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		console.log("[PO Item] stock_qty changed:", {
			item_code: item.item_code,
			qty: item.qty,
			stock_qty: item.stock_qty,
			conversion_factor: item.conversion_factor,
			uom: item.uom,
			stock_uom: item.stock_uom
		});
		
		// Store exact user-entered value
		item._user_entered_stock_qty = flt(item.stock_qty);
		item._manual_stock_qty = true;
		
		if (item.item_code && item.uom && item.stock_uom && item.uom != item.stock_uom) {
			// If UOM != Stock UOM, calculate conversion_factor from stock_qty and qty
			if (item.qty && item.qty > 0 && item.stock_qty && item.stock_qty > 0) {
				var new_conversion_factor = flt(item.stock_qty) / flt(item.qty);
				console.log("[PO Item] Auto-calculating conversion_factor from stock_qty:", new_conversion_factor);
				frappe.model.set_value(cdt, cdn, "conversion_factor", new_conversion_factor);
			}
		} else if (item.uom == item.stock_uom) {
			// If UOM == Stock UOM, update qty to match stock_qty
			if (item.stock_qty && item.stock_qty > 0) {
				frappe.model.set_value(cdt, cdn, "qty", item.stock_qty);
			}
		}
	},

	conversion_factor: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		console.log("[PO Item] conversion_factor changed:", {
			item_code: item.item_code,
			qty: item.qty,
			stock_qty: item.stock_qty,
			conversion_factor: item.conversion_factor,
			manual_stock_qty: item._manual_stock_qty
		});
		
		if (item.item_code && item.uom && item.stock_uom && item.uom != item.stock_uom) {
			// If user manually set stock_qty, don't overwrite it
			if (item._manual_stock_qty) {
				console.log("[PO Item] Skipping stock_qty update - user manually set it");
				// Recalculate qty from stock_qty and conversion_factor
				if (item.stock_qty && item.stock_qty > 0 && item.conversion_factor && item.conversion_factor > 0) {
					var new_qty = flt(item.stock_qty) / flt(item.conversion_factor);
					console.log("[PO Item] Recalculating qty from stock_qty and conversion_factor:", new_qty);
					frappe.model.set_value(cdt, cdn, "qty", new_qty);
				}
			} else {
				// Update stock_qty from qty and conversion_factor
				update_stock_qty_from_qty(frm, cdt, cdn);
			}
		}
	}
});

// Function to fetch conversion factor from Item master
function fetch_conversion_factor_from_item(frm, cdt, cdn) {
	var item = locals[cdt][cdn];
	if (!item.item_code || !item.uom || !item.stock_uom) {
		return;
	}
	
	if (item.uom == item.stock_uom) {
		frappe.model.set_value(cdt, cdn, "conversion_factor", 1);
		return;
	}
	
	// Fetch conversion factor from Item master
	frappe.call({
		method: "erpnext.stock.get_item_details.get_conversion_factor",
		args: {
			item_code: item.item_code,
			uom: item.uom
		},
		callback: function(r) {
			if (r.message && r.message.conversion_factor) {
				var conversion_factor = r.message.conversion_factor;
				console.log("[PO Item] Fetched conversion_factor from Item master:", conversion_factor);
				frappe.model.set_value(cdt, cdn, "conversion_factor", conversion_factor, function() {
					update_stock_qty_from_qty(frm, cdt, cdn);
				});
			} else {
				// Default to 1 if not found
				frappe.model.set_value(cdt, cdn, "conversion_factor", 1);
				update_stock_qty_from_qty(frm, cdt, cdn);
			}
		}
	});
}

// Function to update stock_qty from qty and conversion_factor
function update_stock_qty_from_qty(frm, cdt, cdn) {
	var item = locals[cdt][cdn];
	if (!item || !item.qty) {
		return;
	}
	
	if (item.uom && item.stock_uom && item.uom != item.stock_uom) {
		if (item.conversion_factor && item.conversion_factor > 0) {
			var new_stock_qty = flt(item.qty) * flt(item.conversion_factor);
			console.log("[PO Item] Updating stock_qty from qty:", new_stock_qty);
			// Only update if user hasn't manually set it
			if (!item._manual_stock_qty) {
				frappe.model.set_value(cdt, cdn, "stock_qty", new_stock_qty);
			}
		}
	} else {
		// If UOM == Stock UOM, stock_qty = qty
		frappe.model.set_value(cdt, cdn, "stock_qty", item.qty);
	}
}

frappe.ui.form.on("Purchase Order", {
	onload: function(frm) {
		// Make stock_qty field editable when form loads
		if (frm.fields_dict.items && frm.fields_dict.items.grid) {
			frm.fields_dict.items.grid.update_docfield_property("stock_qty", "read_only", 0);
			console.log("[PO] Made stock_qty field editable");
		}
	},
	
	validate: function(frm) {
		// Check if user is System Manager
		var is_system_manager = frappe.user.has_role("System Manager");
		var docstatus = frm.doc.docstatus || 0;
		
		console.log("[PO Validation] System Manager check:", {
			is_system_manager: is_system_manager,
			docstatus: docstatus,
			doc_name: frm.doc.name
		});
		
		// System Manager exemption: Only allow exemption when creating/editing draft (docstatus = 0)
		// During submission/approval (docstatus = 1), System Manager must also follow validation
		if (is_system_manager && docstatus === 0) {
			console.log("[PO] System Manager detected - skipping Material Request validation (draft mode)");
			return;
		}
		
		if (is_system_manager && docstatus === 1) {
			console.log("[PO] System Manager detected but document is submitted - validation applies");
		}
		
		// Check if any item has Material Request
		var has_material_request = false;
		console.log("[PO Validation] Checking Material Request requirement...");
		console.log("[PO Validation] Items count:", frm.doc.items ? frm.doc.items.length : 0);
		
		// Check if there are items
		if (!frm.doc.items || frm.doc.items.length === 0) {
			frappe.msgprint({
				title: __("Validation Error"),
				message: __("Purchase Order must have at least one item."),
				indicator: "red"
			});
			frappe.validated = false;
			return;
		}
		
		// Check each item for Material Request - ALL items must have Material Request
		var items_without_mr = [];
		for (var i = 0; i < frm.doc.items.length; i++) {
			var item = frm.doc.items[i];
			console.log("[PO Validation] Item " + (i+1) + ":", {
				item_code: item.item_code,
				material_request: item.material_request
			});
			if (!item.material_request) {
				items_without_mr.push({
					row: i + 1,
					item_code: item.item_code || "N/A"
				});
				console.log("[PO Validation] Item " + (i+1) + " MISSING Material Request!");
			} else {
				console.log("[PO Validation] Material Request found in item " + (i+1));
			}
		}
		
		// If any item is missing Material Request, prevent save
		if (items_without_mr.length > 0) {
			console.log("[PO Validation] ERROR: " + items_without_mr.length + " item(s) missing Material Request!");
			
			// Build formatted error message with HTML
			var error_msg = "<div style='font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;'>";
			error_msg += "<div style='color: #c62828; font-weight: 600; font-size: 14px; margin-bottom: 12px;'>";
			error_msg += "⚠️ " + __("Material Request Required");
			error_msg += "</div>";
			error_msg += "<div style='color: #333; font-size: 13px; margin-bottom: 16px; line-height: 1.6;'>";
			error_msg += __("Purchase Order cannot be created without Material Request. The following item(s) are missing Material Request:");
			error_msg += "</div>";
			error_msg += "<div style='background-color: #fff3cd; border-left: 3px solid #ffc107; padding: 12px; margin-bottom: 16px; border-radius: 4px;'>";
			error_msg += "<ul style='margin: 0; padding-left: 20px; color: #856404;'>";
			for (var j = 0; j < items_without_mr.length; j++) {
				error_msg += "<li style='margin-bottom: 8px;'><strong>Row " + items_without_mr[j].row + ":</strong> " + items_without_mr[j].item_code + "</li>";
			}
			error_msg += "</ul>";
			error_msg += "</div>";
			error_msg += "<div style='color: #666; font-size: 12px; font-style: italic;'>";
			error_msg += __("Please add Material Request to all items or contact a System Manager.");
			error_msg += "</div>";
			error_msg += "</div>";
			
			frappe.msgprint({
				title: __("Validation Error"),
				message: error_msg,
				indicator: "red"
			});
			frappe.validated = false;
		} else {
			console.log("[PO Validation] Validation passed - All items have Material Request");
		}
	},
	
	before_save: function(frm) {
		return new Promise(function(resolve, reject) {
			// Check if user is System Manager
			var is_system_manager = frappe.user.has_role("System Manager");
			var docstatus = frm.doc.docstatus || 0;
			
			console.log("[PO before_save] System Manager check:", {
				is_system_manager: is_system_manager,
				docstatus: docstatus,
				doc_name: frm.doc.name
			});
			
			// System Manager exemption: Only allow exemption when creating/editing draft (docstatus = 0)
			// During submission/approval (docstatus = 1), System Manager must also follow validation
			if (is_system_manager && docstatus === 0) {
				console.log("[PO before_save] System Manager detected - skipping Material Request validation (draft mode)");
				resolve();
				return;
			}
			
			if (is_system_manager && docstatus === 1) {
				console.log("[PO before_save] System Manager detected but document is submitted - validation applies");
			}
			
			// Check if any item has Material Request
			var has_material_request = false;
			console.log("[PO before_save] Checking Material Request requirement...");
			console.log("[PO before_save] Items count:", frm.doc.items ? frm.doc.items.length : 0);
			
			// Check if there are items
			if (!frm.doc.items || frm.doc.items.length === 0) {
				frappe.msgprint({
					title: __("Validation Error"),
					message: __("Purchase Order must have at least one item."),
					indicator: "red"
				});
				reject(__("Purchase Order must have items"));
				return;
			}
			
			// Check each item for Material Request - ALL items must have Material Request
			var items_without_mr = [];
			for (var i = 0; i < frm.doc.items.length; i++) {
				var item = frm.doc.items[i];
				console.log("[PO before_save] Item " + (i+1) + ":", {
					item_code: item.item_code,
					material_request: item.material_request
				});
				if (!item.material_request) {
					items_without_mr.push({
						row: i + 1,
						item_code: item.item_code || "N/A"
					});
					console.log("[PO before_save] Item " + (i+1) + " MISSING Material Request!");
				} else {
					console.log("[PO before_save] Material Request found in item " + (i+1));
				}
			}
			
			// If any item is missing Material Request, prevent save
			if (items_without_mr.length > 0) {
				console.log("[PO before_save] ERROR: " + items_without_mr.length + " item(s) missing Material Request!");
				
				// Build formatted error message with HTML
				var error_msg = "<div style='font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;'>";
				error_msg += "<div style='color: #c62828; font-weight: 600; font-size: 14px; margin-bottom: 12px;'>";
				error_msg += "⚠️ " + __("Material Request Required");
				error_msg += "</div>";
				error_msg += "<div style='color: #333; font-size: 13px; margin-bottom: 16px; line-height: 1.6;'>";
				error_msg += __("Purchase Order cannot be created without Material Request. The following item(s) are missing Material Request:");
				error_msg += "</div>";
				error_msg += "<div style='background-color: #fff3cd; border-left: 3px solid #ffc107; padding: 12px; margin-bottom: 16px; border-radius: 4px;'>";
				error_msg += "<ul style='margin: 0; padding-left: 20px; color: #856404;'>";
				for (var j = 0; j < items_without_mr.length; j++) {
					error_msg += "<li style='margin-bottom: 8px;'><strong>Row " + items_without_mr[j].row + ":</strong> " + items_without_mr[j].item_code + "</li>";
				}
				error_msg += "</ul>";
				error_msg += "</div>";
				error_msg += "<div style='color: #666; font-size: 12px; font-style: italic;'>";
				error_msg += __("Please add Material Request to all items or contact a System Manager.");
				error_msg += "</div>";
				error_msg += "</div>";
				
				frappe.msgprint({
					title: __("Validation Error"),
					message: error_msg,
					indicator: "red"
				});
				reject(__("Purchase Order requires Material Request for all items"));
			} else {
				console.log("[PO before_save] Validation passed - All items have Material Request");
				resolve();
			}
		});
	},
	
	refresh: function(frm) {
		// Make stock_qty field editable
		if (frm.fields_dict.items && frm.fields_dict.items.grid) {
			frm.fields_dict.items.grid.update_docfield_property("stock_qty", "read_only", 0);
			console.log("[PO] Made stock_qty field editable");
		}
		
		// Add watcher to preserve exact stock_qty value
		setTimeout(function() {
			if (frm.fields_dict.items && frm.fields_dict.items.grid) {
				frm.fields_dict.items.grid.wrapper.on('change blur', 'input[data-fieldname="stock_qty"]', function() {
					var $input = $(this);
					var row = $input.closest('.grid-row');
					var row_name = row.attr('data-name');
					if (row_name) {
						var item = locals['Purchase Order Item'][row_name];
						if (item && item._user_entered_stock_qty !== undefined) {
							var current_value = flt($input.val());
							// If value was rounded/changed, restore exact user value
							if (Math.abs(current_value - item._user_entered_stock_qty) > 0.0001) {
								console.log("[PO] DOM Watcher: Restoring exact stock_qty from", current_value, "to", item._user_entered_stock_qty);
								$input.val(item._user_entered_stock_qty);
								item.stock_qty = item._user_entered_stock_qty;
								refresh_field("stock_qty", row_name, "items");
							}
						}
					}
				});
			}
		}, 500);
	}
});


