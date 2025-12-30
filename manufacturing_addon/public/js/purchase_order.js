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

