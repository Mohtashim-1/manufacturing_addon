// Custom Purchase Receipt JavaScript for UOM conversion and rate locking

frappe.provide("erpnext.stock");

// Override Purchase Receipt Item handlers
frappe.ui.form.on("Purchase Receipt Item", {
	item_code: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		console.log("[PR Item] item_code changed:", {
			item_code: item.item_code,
			purchase_order_item: item.purchase_order_item,
			rate: item.rate,
			price_list_rate: item.price_list_rate
		});
		
		// If item has PO reference and rate is set, capture it as original
		// ERPNext already sets the rate from PO when items are loaded, so we just capture it
		if (item.purchase_order_item && item.rate && flt(item.rate) > 0 && !item._original_rate) {
			item._original_rate = flt(item.rate);
			// Also capture price_list_rate from PO if available
			if (item.price_list_rate && flt(item.price_list_rate) > 0) {
				item._original_price_list_rate = flt(item.price_list_rate);
				console.log("[PR Item] Captured rate and price_list_rate as original (from PO):", item._original_rate, item._original_price_list_rate);
			} else {
				console.log("[PR Item] Captured rate as original (from PO):", item._original_rate);
			}
		}
		
		if (item.item_code && item.uom && item.stock_uom) {
			// Auto-fetch conversion factor if UOM != Stock UOM
			if (item.uom != item.stock_uom) {
				fetch_conversion_factor(frm, cdt, cdn);
			}
		}
	},

	uom: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		if (item.item_code && item.uom && item.stock_uom) {
			// If UOM changed and != Stock UOM, fetch conversion factor
			if (item.uom != item.stock_uom) {
				fetch_conversion_factor(frm, cdt, cdn);
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
				fetch_conversion_factor(frm, cdt, cdn);
			} else {
				// If UOM == Stock UOM, set conversion_factor to 1
				frappe.model.set_value(cdt, cdn, "conversion_factor", 1);
				update_stock_qty_from_qty(frm, cdt, cdn);
			}
		}
	},

	qty: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		console.log("[PR Item] qty changed:", {
			item_code: item.item_code,
			qty: item.qty,
			stock_qty: item.stock_qty,
			conversion_factor: item.conversion_factor,
			rate: item.rate,
			original_rate: item._original_rate
		});
		
		// Store original rate before any calculations
		if (!item._original_rate && item.rate) {
			item._original_rate = flt(item.rate);
			console.log("[PR Item] Stored original rate:", item._original_rate);
		}
		
		// Only update stock_qty if conversion_factor exists and user hasn't manually set stock_qty
		// Don't update if user is manually editing stock_qty
		if (item.qty && item.conversion_factor && !item._manual_stock_qty) {
			var stock_qty = flt(item.qty) * flt(item.conversion_factor);
			console.log("[PR Item] Auto-updating stock_qty from qty:", stock_qty);
			frappe.model.set_value(cdt, cdn, "stock_qty", stock_qty);
		}
		
		// Recalculate amount with locked rate
		recalculate_amount_with_locked_rate(frm, cdt, cdn);
	},

	stock_qty: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		var userEnteredStockQty = flt(item.stock_qty);
		
		console.log("[PR Item] stock_qty changed:", {
			item_code: item.item_code,
			qty: item.qty,
			stock_qty: item.stock_qty,
			conversion_factor: item.conversion_factor,
			rate: item.rate,
			original_rate: item._original_rate
		});
		
		// Mark that user is manually editing stock_qty
		item._manual_stock_qty = true;
		item._user_entered_stock_qty = userEnteredStockQty; // Store exact value user entered
		
		// Set flag to prevent rate recalculation
		item._prevent_rate_recalc = true;
		
		// Store original rate before any calculations
		if (!item._original_rate && item.rate && flt(item.rate) > 0) {
			item._original_rate = flt(item.rate);
			console.log("[PR Item] Stored original rate:", item._original_rate);
		}
		
		// Lock the rate and price_list_rate immediately to prevent any changes
		if (item._original_rate && item._original_rate > 0) {
			if (Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
				console.log("[PR Item] Locking rate in stock_qty handler from", item.rate, "to", item._original_rate);
				frappe.model.set_value(cdt, cdn, "rate", item._original_rate);
			}
		}
		
		// Also lock price_list_rate
		if (item._original_price_list_rate && item._original_price_list_rate > 0) {
			if (Math.abs(flt(item.price_list_rate) - item._original_price_list_rate) > 0.01) {
				console.log("[PR Item] Locking price_list_rate in stock_qty handler from", item.price_list_rate, "to", item._original_price_list_rate);
				item.price_list_rate = item._original_price_list_rate;
				refresh_field("price_list_rate", cdn, "items");
			}
		}
		
		// Auto-calculate conversion_factor from stock_qty and qty
		// This is the key requirement: when user enters stock_qty, conversion_factor should auto-calculate
		if (item.stock_qty && item.qty && item.qty > 0) {
			var conversion_factor = flt(item.stock_qty) / flt(item.qty);
			console.log("[PR Item] Auto-calculating conversion_factor from stock_qty:", conversion_factor);
			
			// Set conversion_factor and lock rate immediately
			frappe.model.set_value(cdt, cdn, "conversion_factor", conversion_factor, function() {
				// Immediately lock rate and price_list_rate using set_value to ensure UI updates
				if (item._original_rate && item._original_rate > 0) {
					if (Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
						console.log("[PR Item] Locking rate after conversion_factor change from", item.rate, "to", item._original_rate);
						frappe.model.set_value(cdt, cdn, "rate", item._original_rate, function() {
							// Verify it's correct
							if (Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
								console.log("[PR Item] Rate still wrong! Forcing again...");
								item.rate = item._original_rate;
								refresh_field("rate", cdn, "items");
							}
						});
					}
				}
				
				// Also lock price_list_rate
				if (item._original_price_list_rate && item._original_price_list_rate > 0) {
					if (Math.abs(flt(item.price_list_rate) - item._original_price_list_rate) > 0.01) {
						console.log("[PR Item] Locking price_list_rate after conversion_factor change from", item.price_list_rate, "to", item._original_price_list_rate);
						item.price_list_rate = item._original_price_list_rate;
						refresh_field("price_list_rate", cdn, "items");
					}
				}
				
				// Restore stock_qty to exact value user entered (prevent rounding)
				if (item._user_entered_stock_qty && Math.abs(flt(item.stock_qty) - item._user_entered_stock_qty) > 0.0001) {
					item.stock_qty = item._user_entered_stock_qty;
					refresh_field("stock_qty", cdn, "items");
				}
				
				recalculate_amount_with_locked_rate(frm, cdt, cdn);
				
				// Clear flag after a delay
				setTimeout(function() {
					item._prevent_rate_recalc = false;
				}, 300);
			});
		} else {
			// Recalculate amount with locked rate
			recalculate_amount_with_locked_rate(frm, cdt, cdn);
			// Clear flag
			setTimeout(function() {
				item._prevent_rate_recalc = false;
			}, 200);
		}
	},

	conversion_factor: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		console.log("[PR Item] conversion_factor changed:", {
			item_code: item.item_code,
			qty: item.qty,
			stock_qty: item.stock_qty,
			conversion_factor: item.conversion_factor,
			rate: item.rate,
			original_rate: item._original_rate,
			manual_stock_qty: item._manual_stock_qty
		});
		
		// Set flag to prevent rate recalculation from standard ERPNext code
		item._prevent_rate_recalc = true;
		
		// Store original rate before any calculations
		if (!item._original_rate && item.rate && flt(item.rate) > 0) {
			item._original_rate = flt(item.rate);
			console.log("[PR Item] Stored original rate:", item._original_rate);
		}
		
		// IMMEDIATELY lock rate and price_list_rate - do this synchronously, not in callback
		if (item._original_rate && item._original_rate > 0) {
			if (Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
				console.log("[PR Item] Rate was changed! Locking immediately from", item.rate, "to", item._original_rate);
				// Set rate immediately and verify multiple times
				item.rate = item._original_rate;
				frappe.model.set_value(cdt, cdn, "rate", item._original_rate, function() {
					// Verify and force again if needed
					setTimeout(function() {
						if (Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
							console.log("[PR Item] Rate still wrong after conversion_factor! Forcing again...");
							item.rate = item._original_rate;
							frappe.model.set_value(cdt, cdn, "rate", item._original_rate);
							refresh_field("rate", cdn, "items");
						}
					}, 50);
				});
			}
		}
		
		// Also lock price_list_rate if we have original
		if (item._original_price_list_rate && item._original_price_list_rate > 0) {
			if (Math.abs(flt(item.price_list_rate) - item._original_price_list_rate) > 0.01) {
				console.log("[PR Item] price_list_rate was changed! Locking from", item.price_list_rate, "to", item._original_price_list_rate);
				item.price_list_rate = item._original_price_list_rate;
				refresh_field("price_list_rate", cdn, "items");
			}
		}
		
		// Only update stock_qty if user hasn't manually set it
		// If user manually changed stock_qty, don't override it
		if (item.qty && item.conversion_factor && !item._manual_stock_qty) {
			var stock_qty = flt(item.qty) * flt(item.conversion_factor);
			console.log("[PR Item] Auto-updating stock_qty from conversion_factor:", stock_qty);
			frappe.model.set_value(cdt, cdn, "stock_qty", stock_qty);
		} else if (item._manual_stock_qty) {
			console.log("[PR Item] Skipping stock_qty update - user manually set it");
			// Restore exact user-entered value if it was rounded
			if (item._user_entered_stock_qty && flt(item.stock_qty) != item._user_entered_stock_qty) {
				item.stock_qty = item._user_entered_stock_qty;
				refresh_field("stock_qty", cdn, "items");
			}
		}
		
		// Recalculate amount with locked rate
		recalculate_amount_with_locked_rate(frm, cdt, cdn);
		
		// Clear the flag after a delay - longer delay to prevent rate changes
		setTimeout(function() {
			item._prevent_rate_recalc = false;
		}, 300);
	},

	rate: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		var itemKey = cdn;
		
		console.log("[PR Item] rate changed:", {
			item_code: item.item_code,
			rate: item.rate,
			original_rate: item._original_rate,
			qty: item.qty,
			prevent_recalc: item._prevent_rate_recalc,
			allow_rate_change: item._allow_rate_change,
			purchase_order_item: item.purchase_order_item
		});
		
		// If rate change is already being processed, skip to avoid infinite loop
		if (rateChangeInProgress[itemKey]) {
			console.log("[PR Item] Rate change already in progress, skipping");
			return;
		}
		
		// IMPORTANT: If item has PO reference and we don't have original rate yet, capture it NOW
		// This happens when rate is first set from PO
		if (item.purchase_order_item && !item._original_rate && item.rate && flt(item.rate) > 0) {
			item._original_rate = flt(item.rate);
			// Also capture price_list_rate if available
			if (item.price_list_rate && flt(item.price_list_rate) > 0 && !item._original_price_list_rate) {
				item._original_price_list_rate = flt(item.price_list_rate);
				item._price_list_rate_captured = true;
				console.log("[PR Item] *** CAPTURED PO RATE AND PRICE_LIST_RATE AS ORIGINAL ***:", item._original_rate, item._original_price_list_rate);
			} else {
				console.log("[PR Item] *** CAPTURED PO RATE AS ORIGINAL ***:", item._original_rate);
			}
		}
		
		// If user explicitly allowed rate change (e.g., manual edit), allow it once
		if (item._allow_rate_change) {
			item._original_rate = flt(item.rate);
			item._allow_rate_change = false;
			console.log("[PR Item] User manually changed rate, updating original rate to:", item._original_rate);
			recalculate_amount_with_locked_rate(frm, cdt, cdn);
			return;
		}
		
		// If we're preventing rate recalculation (e.g., during conversion_factor change), restore immediately
		if (item._prevent_rate_recalc && item._original_rate && item._original_rate > 0) {
			console.log("[PR Item] Preventing rate change during conversion_factor update. Restoring to:", item._original_rate);
			rateChangeInProgress[itemKey] = true;
			item.rate = item._original_rate;
			// Force update the field value
			frappe.model.set_value(cdt, cdn, "rate", item._original_rate, function() {
				// After setting, verify it's correct
				if (flt(item.rate) != item._original_rate) {
					console.log("[PR Item] Rate still wrong after set_value! Forcing again...");
					item.rate = item._original_rate;
					refresh_field("rate", cdn, "items");
				}
				setTimeout(function() {
					delete rateChangeInProgress[itemKey];
				}, 200);
			});
			return;
		}
		
		// If we have a locked rate and it's being changed by system (not user), restore it IMMEDIATELY
		if (item._original_rate && item._original_rate > 0 && Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
			console.log("[PR Item] Rate changed from locked value! Restoring IMMEDIATELY from", item.rate, "to", item._original_rate);
			rateChangeInProgress[itemKey] = true;
			// Restore immediately using set_value to ensure UI updates
			frappe.model.set_value(cdt, cdn, "rate", item._original_rate, function() {
				// Double-check and force if needed
				if (Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
					console.log("[PR Item] Rate still incorrect after restore! Forcing again...");
					item.rate = item._original_rate;
					refresh_field("rate", cdn, "items");
				}
				setTimeout(function() {
					delete rateChangeInProgress[itemKey];
				}, 100);
			});
			return;
		}
		
		// Store the rate as original rate when first set (if not already stored)
		if (!item._original_rate && item.rate && flt(item.rate) > 0) {
			item._original_rate = flt(item.rate);
			console.log("[PR Item] Stored original rate:", item._original_rate);
		}   
		
		// Recalculate amount
		recalculate_amount_with_locked_rate(frm, cdt, cdn);
	},

	purchase_order_item: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		console.log("[PR Item] purchase_order_item changed:", {
			item_code: item.item_code,
			purchase_order_item: item.purchase_order_item,
			current_rate: item.rate,
			price_list_rate: item.price_list_rate
		});
		
		// When PO item is set, capture the current rate and price_list_rate as original
		// ERPNext already sets the rate from PO when purchase_order_item is set, so we capture it
		if (item.purchase_order_item && item.rate && flt(item.rate) > 0) {
			if (!item._original_rate) {
				item._original_rate = flt(item.rate);
				item._rate_locked = true; // Mark that rate is locked
			}
			// Also capture price_list_rate if available and not already captured
			if (item.price_list_rate && flt(item.price_list_rate) > 0 && !item._original_price_list_rate) {
				item._original_price_list_rate = flt(item.price_list_rate);
				item._price_list_rate_captured = true;
				console.log("[PR Item] Captured rate and price_list_rate as original (from PO):", item._original_rate, item._original_price_list_rate);
			} else if (!item._original_price_list_rate) {
				console.log("[PR Item] Captured rate as original (from PO):", item._original_rate, "- price_list_rate not available yet");
			}
		}
		
		// Also fetch conversion factor if UOM != Stock UOM
		if (item.item_code && item.uom && item.stock_uom && item.uom != item.stock_uom) {
			fetch_conversion_factor(frm, cdt, cdn);
		}
	},
	
	price_list_rate: function(frm, cdt, cdn) {
		var item = locals[cdt][cdn];
		console.log("[PR Item] price_list_rate changed:", {
			item_code: item.item_code,
			price_list_rate: item.price_list_rate,
			original_price_list_rate: item._original_price_list_rate,
			rate: item.rate,
			original_rate: item._original_rate,
			purchase_order_item: item.purchase_order_item
		});
		
		// If we have original price_list_rate from PO, restore it
		if (item._original_price_list_rate && item._original_price_list_rate > 0) {
			if (Math.abs(flt(item.price_list_rate) - item._original_price_list_rate) > 0.01) {
				console.log("[PR Item] price_list_rate changed! Restoring from", item.price_list_rate, "to", item._original_price_list_rate);
				item.price_list_rate = item._original_price_list_rate;
				refresh_field("price_list_rate", cdn, "items");
			}
		} else if (item.purchase_order_item && item.price_list_rate && flt(item.price_list_rate) > 0 && !item._original_price_list_rate && !item._price_list_rate_captured && !item._rate_locked) {
			// Store as original ONLY if:
			// 1. Item has PO reference
			// 2. price_list_rate is available
			// 3. Not already captured
			// 4. Rate hasn't been locked yet (meaning this is the initial load, not a recalculation)
			// Set a flag to indicate we've tried to capture it
			item._price_list_rate_captured = true;
			item._original_price_list_rate = flt(item.price_list_rate);
			console.log("[PR Item] *** CAPTURED PO price_list_rate AS ORIGINAL ***:", item._original_price_list_rate);
		}
		// Don't store as original if it's not from PO or if rate has already been locked (recalculation)
		
		// If rate is being recalculated from price_list_rate, restore it
		if (item._original_rate && item._original_rate > 0) {
			if (Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
				console.log("[PR Item] Rate changed due to price_list_rate! Restoring to", item._original_rate);
				item._prevent_rate_recalc = true;
				frappe.model.set_value(cdt, cdn, "rate", item._original_rate, function() {
					delete item._prevent_rate_recalc;
				});
			}
		}
	}
});

// Function to fetch conversion factor from Item master or PO
function fetch_conversion_factor(frm, cdt, cdn) {
	var item = locals[cdt][cdn];
	
	console.log("[PR Item] fetch_conversion_factor called:", {
		item_code: item.item_code,
		uom: item.uom,
		stock_uom: item.stock_uom,
		current_conversion_factor: item.conversion_factor,
		purchase_order_item: item.purchase_order_item
	});
	
	if (!item.item_code || !item.uom || !item.stock_uom || item.uom == item.stock_uom) {
		console.log("[PR Item] Skipping fetch_conversion_factor - invalid conditions");
		return;
	}

	// Only fetch if conversion_factor is not already set (don't override user's manual entry)
	if (item.conversion_factor && flt(item.conversion_factor) > 0) {
		console.log("[PR Item] Conversion factor already set, skipping fetch:", item.conversion_factor);
		return;
	}

	// Priority 1: Get from PO item if PR is against PO
	if (item.purchase_order_item) {
		console.log("[PR Item] Fetching conversion_factor from PO item:", item.purchase_order_item);
		frappe.db.get_value("Purchase Order Item", item.purchase_order_item, "conversion_factor", function(r) {
			if (r && r.conversion_factor) {
				console.log("[PR Item] Got conversion_factor from PO:", r.conversion_factor);
				frappe.model.set_value(cdt, cdn, "conversion_factor", r.conversion_factor);
				update_stock_qty_from_qty(frm, cdt, cdn);
				return;
			}
			// If not found in PO, try Item master
			fetch_from_item_master(frm, cdt, cdn);
		});
	} else {
		// Priority 2: Get from Item master
		fetch_from_item_master(frm, cdt, cdn);
	}
}

// Function to fetch conversion factor from Item master
function fetch_from_item_master(frm, cdt, cdn) {
	var item = locals[cdt][cdn];
	
	console.log("[PR Item] Fetching conversion_factor from Item master:", item.item_code);
	
	if (!item.item_code || !item.uom || !item.stock_uom) {
		return;
	}

	frappe.call({
		method: "erpnext.stock.get_item_details.get_conversion_factor",
		args: {
			item_code: item.item_code,
			uom: item.uom
		},
		callback: function(r) {
			if (r && r.message && r.message.conversion_factor) {
				console.log("[PR Item] Got conversion_factor from Item master:", r.message.conversion_factor);
				frappe.model.set_value(cdt, cdn, "conversion_factor", r.message.conversion_factor);
				update_stock_qty_from_qty(frm, cdt, cdn);
			} else {
				console.log("[PR Item] No conversion_factor found in Item master");
			}
		}
	});
}

// Function to update stock_qty from qty and conversion_factor
function update_stock_qty_from_qty(frm, cdt, cdn) {
	var item = locals[cdt][cdn];
	if (item.qty && item.conversion_factor && !item._manual_stock_qty) {
		var stock_qty = flt(item.qty) * flt(item.conversion_factor);
		console.log("[PR Item] update_stock_qty_from_qty:", stock_qty);
		frappe.model.set_value(cdt, cdn, "stock_qty", stock_qty);
	}
}

// Function to recalculate amount with locked rate
function recalculate_amount_with_locked_rate(frm, cdt, cdn) {
	var item = locals[cdt][cdn];
	
	console.log("[PR Item] recalculate_amount_with_locked_rate called:", {
		item_code: item.item_code,
		rate: item.rate,
		original_rate: item._original_rate,
		qty: item.qty
	});
	
	// Store original rate if not already stored
	if (!item._original_rate && item.rate && flt(item.rate) > 0) {
		item._original_rate = flt(item.rate);
		console.log("[PR Item] Stored original rate in recalculate:", item._original_rate);
	}
	
	// If rate was set before, keep it locked
	if (item._original_rate && item._original_rate > 0) {
		// Restore rate if it was changed (this prevents rate from auto-changing)
		if (flt(item.rate) != item._original_rate) {
			console.log("[PR Item] Rate changed! Restoring from", item.rate, "to", item._original_rate);
			frappe.model.set_value(cdt, cdn, "rate", item._original_rate, function() {
				// After restoring rate, calculate amount
				calculate_amount_from_locked_rate(frm, cdt, cdn);
			});
		} else {
			// Calculate amount = qty × rate (rate is locked)
			calculate_amount_from_locked_rate(frm, cdt, cdn);
		}
	} else if (item.rate && item.qty) {
		// If rate is set but not stored as original, store it now
		item._original_rate = flt(item.rate);
		console.log("[PR Item] Stored original rate (else branch):", item._original_rate);
		calculate_amount_from_locked_rate(frm, cdt, cdn);
	}
}

// Function to calculate amount from locked rate
function calculate_amount_from_locked_rate(frm, cdt, cdn) {
	var item = locals[cdt][cdn];
	var locked_rate = item._original_rate || flt(item.rate);
	
	console.log("[PR Item] calculate_amount_from_locked_rate:", {
		item_code: item.item_code,
		qty: item.qty,
		locked_rate: locked_rate,
		calculated_amount: item.qty && locked_rate ? flt(item.qty) * locked_rate : 0
	});
	
	if (item.qty && locked_rate && locked_rate > 0) {
		var amount = flt(item.qty) * locked_rate;
		frappe.model.set_value(cdt, cdn, "amount", amount);
	}
}

// Override Purchase Receipt form handlers
frappe.ui.form.on("Purchase Receipt", {
	onload: function(frm) {
		// Capture rates when form is loaded
		// If item has PO reference, the rate is already set from PO by ERPNext, so we just capture it
		if (frm.doc.items) {
			frm.doc.items.forEach(function(item) {
				if (item.rate && flt(item.rate) > 0 && !item._original_rate) {
					item._original_rate = flt(item.rate);
					item._rate_locked = true; // Mark that rate is locked
					// Also capture price_list_rate if available
					if (item.price_list_rate && flt(item.price_list_rate) > 0 && !item._original_price_list_rate) {
						item._original_price_list_rate = flt(item.price_list_rate);
						item._price_list_rate_captured = true;
					}
					if (item.purchase_order_item) {
						console.log("[PR] Onload: Captured rate and price_list_rate as original (from PO) for item:", item.item_code, item._original_rate, item._original_price_list_rate);
					} else {
						console.log("[PR] Onload: Stored current rate as original for item:", item.item_code, item._original_rate);
					}
				}
			});
		}
		
		// Add aggressive watcher to prevent rate changes at DOM level
		setTimeout(function() {
			if (frm.fields_dict.items && frm.fields_dict.items.grid) {
				// Watch for any changes to rate field
				frm.fields_dict.items.grid.wrapper.on('change blur input keyup', 'input[data-fieldname="rate"]', function() {
					var $input = $(this);
					var row = $input.closest('.grid-row');
					var row_name = row.attr('data-name');
					if (row_name) {
						var item = locals['Purchase Receipt Item'][row_name];
						if (item && item._original_rate && item._original_rate > 0) {
							var current_value = flt($input.val());
							if (Math.abs(current_value - item._original_rate) > 0.01) {
								console.log("[PR] DOM Watcher: Preventing rate change from", current_value, "to", item._original_rate);
								$input.val(item._original_rate);
								item.rate = item._original_rate;
								// Force update using set_value
								frappe.model.set_value('Purchase Receipt Item', row_name, "rate", item._original_rate, function() {
									refresh_field("rate", row_name, "items");
								});
							}
						}
					}
				});
				
				// Also add a periodic check to ensure rate stays locked
				var rateCheckInterval = setInterval(function() {
					if (!frm || frm.doc.doctype !== "Purchase Receipt" || frm.doc.docstatus > 0) {
						clearInterval(rateCheckInterval);
						return;
					}
					
					if (frm.doc.items) {
						frm.doc.items.forEach(function(item) {
							if (item._original_rate && item._original_rate > 0) {
								if (Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
									console.log("[PR] Periodic Check: Rate changed! Restoring from", item.rate, "to", item._original_rate);
									item.rate = item._original_rate;
									frappe.model.set_value('Purchase Receipt Item', item.name, "rate", item._original_rate, function() {
										refresh_field("rate", item.name, "items");
									});
								}
								
								// Also check DOM value
								var $rateInput = frm.fields_dict.items.grid.wrapper.find('input[data-fieldname="rate"][data-name="' + item.name + '"]');
								if ($rateInput.length) {
									var domValue = flt($rateInput.val());
									if (Math.abs(domValue - item._original_rate) > 0.01) {
										console.log("[PR] Periodic Check: DOM rate wrong! Restoring from", domValue, "to", item._original_rate);
										$rateInput.val(item._original_rate);
										item.rate = item._original_rate;
										refresh_field("rate", item.name, "items");
									}
								}
							}
						});
					}
				}, 300); // Check every 300ms
				
				// Store interval ID so we can clear it later
				frm._rateCheckInterval = rateCheckInterval;
				
				// Add watcher to preserve exact stock_qty value
				frm.fields_dict.items.grid.wrapper.on('change blur', 'input[data-fieldname="stock_qty"]', function() {
					var $input = $(this);
					var row = $input.closest('.grid-row');
					var row_name = row.attr('data-name');
					if (row_name) {
						var item = locals['Purchase Receipt Item'][row_name];
						if (item && item._user_entered_stock_qty !== undefined) {
							var current_value = flt($input.val());
							// If value was rounded/changed, restore exact user value
							if (Math.abs(current_value - item._user_entered_stock_qty) > 0.0001) {
								console.log("[PR] DOM Watcher: Restoring exact stock_qty from", current_value, "to", item._user_entered_stock_qty);
								$input.val(item._user_entered_stock_qty);
								item.stock_qty = item._user_entered_stock_qty;
								refresh_field("stock_qty", row_name, "items");
							}
						}
					}
				});
			}
		}, 500);
	},
	
	refresh: function(frm) {
		// Make stock_qty field editable
		if (frm.fields_dict.items && frm.fields_dict.items.grid) {
			frm.fields_dict.items.grid.update_docfield_property("stock_qty", "read_only", 0);
			console.log("[PR] Made stock_qty field editable");
		}
		
		// Store original rates for all items when form is refreshed
		// If item has PO reference, ERPNext already set the rate from PO, so we just capture it
		if (frm.doc.items) {
			frm.doc.items.forEach(function(item) {
				if (item.rate && flt(item.rate) > 0 && !item._original_rate) {
					item._original_rate = flt(item.rate);
					item._rate_locked = true; // Mark that rate is locked
					// Also capture price_list_rate if available
					if (item.price_list_rate && flt(item.price_list_rate) > 0 && !item._original_price_list_rate) {
						item._original_price_list_rate = flt(item.price_list_rate);
						item._price_list_rate_captured = true;
					}
					if (item.purchase_order_item) {
						console.log("[PR] Refresh: Captured rate and price_list_rate as original (from PO) for item:", item.item_code, item._original_rate, item._original_price_list_rate);
					} else {
						console.log("[PR] Refresh: Stored current rate as original for item:", item.item_code, item._original_rate);
					}
				}
				
				// Also verify and restore rate and price_list_rate if they're wrong
				if (item._original_rate && item._original_rate > 0) {
					if (Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
						console.log("[PR] Refresh: Rate is wrong! Restoring from", item.rate, "to", item._original_rate);
						item.rate = item._original_rate;
						refresh_field("rate", item.name, "items");
					}
				}
				
				if (item._original_price_list_rate && item._original_price_list_rate > 0) {
					if (Math.abs(flt(item.price_list_rate) - item._original_price_list_rate) > 0.01) {
						console.log("[PR] Refresh: price_list_rate is wrong! Restoring from", item.price_list_rate, "to", item._original_price_list_rate);
						item.price_list_rate = item._original_price_list_rate;
						refresh_field("price_list_rate", item.name, "items");
					}
				}
			});
		}
	},
	
	// Override before_save to ensure rates are locked
	before_save: function(frm) {
		if (frm.doc.items) {
			frm.doc.items.forEach(function(item) {
				if (item._original_rate && item._original_rate > 0) {
					if (Math.abs(flt(item.rate) - item._original_rate) > 0.01) {
						console.log("[PR] Before save: Restoring rate from", item.rate, "to", item._original_rate);
						item.rate = item._original_rate;
					}
				}
				
				if (item._original_price_list_rate && item._original_price_list_rate > 0) {
					if (Math.abs(flt(item.price_list_rate) - item._original_price_list_rate) > 0.01) {
						console.log("[PR] Before save: Restoring price_list_rate from", item.price_list_rate, "to", item._original_price_list_rate);
						item.price_list_rate = item._original_price_list_rate;
					}
				}
			});
		}
	}
});

// Store reference to prevent rate changes from standard ERPNext code
var rateChangeInProgress = {};

// Override calculate_stock_uom_rate and apply_price_list to prevent rate recalculation
if (typeof erpnext !== 'undefined' && erpnext.TransactionController) {
	var originalCalculateStockUomRate = erpnext.TransactionController.prototype.calculate_stock_uom_rate;
	var inCalculateStockUomRate = {}; // Track which items are being processed to prevent recursion
	
	erpnext.TransactionController.prototype.calculate_stock_uom_rate = function(doc, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		var itemKey = cdn || (item ? item.name : null);
		
		// Prevent infinite recursion
		if (inCalculateStockUomRate[itemKey]) {
			console.log("[PR] Override: Skipping calculate_stock_uom_rate - already processing", itemKey);
			return;
		}
		
		// If this is Purchase Receipt and item has locked rate, prevent rate recalculation
		if (doc.doctype === "Purchase Receipt" && item && item._original_rate && item._original_rate > 0) {
			// Mark as being processed
			inCalculateStockUomRate[itemKey] = true;
			
			try {
				// Store original rate and price_list_rate before calculation
				var locked_rate = item._original_rate;
				var locked_price_list_rate = item._original_price_list_rate;
				
				// Call original method
				originalCalculateStockUomRate.call(this, doc, cdt, cdn);
				
				// Immediately restore rate and price_list_rate if they were changed
				// Don't use refresh_field as it triggers handlers that cause recursion
				if (Math.abs(flt(item.rate) - locked_rate) > 0.01) {
					console.log("[PR] Override: calculate_stock_uom_rate changed rate from", item.rate, "to", locked_rate);
					item.rate = locked_rate;
					item.base_rate = locked_rate * (doc.conversion_rate || 1);
					// Set flag to prevent rate handler from running
					item._prevent_rate_recalc = true;
					setTimeout(function() {
						delete item._prevent_rate_recalc;
					}, 100);
				}
				
				if (locked_price_list_rate && Math.abs(flt(item.price_list_rate) - locked_price_list_rate) > 0.01) {
					console.log("[PR] Override: calculate_stock_uom_rate changed price_list_rate from", item.price_list_rate, "to", locked_price_list_rate);
					item.price_list_rate = locked_price_list_rate;
					item.base_price_list_rate = locked_price_list_rate * (doc.conversion_rate || 1);
				}
			} finally {
				// Always clear the flag
				delete inCalculateStockUomRate[itemKey];
			}
		} else {
			// Normal behavior for other doctypes
			originalCalculateStockUomRate.call(this, doc, cdt, cdn);
		}
	};
	
	// Override apply_price_list to prevent rate recalculation from price_list_rate
	var originalApplyPriceList = erpnext.TransactionController.prototype.apply_price_list;
	var inApplyPriceList = {}; // Track which items are being processed to prevent recursion
	
	erpnext.TransactionController.prototype.apply_price_list = function(item, reset_plc_conversion) {
		var doc = this.frm ? this.frm.doc : null;
		var itemKey = item ? (item.name || item.item_code) : null;
		
		// Prevent infinite recursion
		if (inApplyPriceList[itemKey]) {
			console.log("[PR] Override: Skipping apply_price_list - already processing", itemKey);
			return;
		}
		
		// If this is Purchase Receipt and item has locked rate, prevent rate recalculation
		if (doc && doc.doctype === "Purchase Receipt" && item && item._original_rate && item._original_rate > 0) {
			// Mark as being processed
			inApplyPriceList[itemKey] = true;
			
			try {
				var locked_rate = item._original_rate;
				var locked_price_list_rate = item._original_price_list_rate;
				
				// Call original method
				originalApplyPriceList.call(this, item, reset_plc_conversion);
				
				// Restore locked values immediately
				// Don't use refresh_field as it triggers handlers that cause recursion
				if (Math.abs(flt(item.rate) - locked_rate) > 0.01) {
					console.log("[PR] Override: apply_price_list changed rate from", item.rate, "to", locked_rate);
					item.rate = locked_rate;
					if (doc && doc.conversion_rate) {
						item.base_rate = locked_rate * doc.conversion_rate;
					}
					// Set flag to prevent rate handler from running
					item._prevent_rate_recalc = true;
					setTimeout(function() {
						delete item._prevent_rate_recalc;
					}, 100);
				}
				
				if (locked_price_list_rate && Math.abs(flt(item.price_list_rate) - locked_price_list_rate) > 0.01) {
					console.log("[PR] Override: apply_price_list changed price_list_rate from", item.price_list_rate, "to", locked_price_list_rate);
					item.price_list_rate = locked_price_list_rate;
					if (doc && doc.conversion_rate) {
						item.base_price_list_rate = locked_price_list_rate * doc.conversion_rate;
					}
				}
			} finally {
				// Always clear the flag
				delete inApplyPriceList[itemKey];
			}
		} else {
			// Normal behavior for other doctypes
			originalApplyPriceList.call(this, item, reset_plc_conversion);
		}
	};
	
	console.log("[PR] Overrode calculate_stock_uom_rate and apply_price_list methods");
}


