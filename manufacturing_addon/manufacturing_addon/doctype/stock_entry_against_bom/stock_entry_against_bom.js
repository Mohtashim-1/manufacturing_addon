// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Entry Against BOM', {
	refresh: function(frm) {
		// Add custom button
		frm.add_custom_button(__('Get Items'), function() {
			// Directly fetch items with remaining quantities
			fetch_items_with_quantities(frm);
		});

		// Add Transfer Item button
		frm.add_custom_button(__('Transfer Item'), function() {
			frm.call({
				method: 'show_transfer_dialog',
				args: {
					docname: frm.doc.name
				},
				callback: function(r) {
					if (r.message) {
						show_transfer_dialog(frm, r.message);
					}
				}
			});
		});

		// Add "Create Transfer Form" button
		frm.add_custom_button(__('Create Transfer Form'), function() {
			frappe.call({
				method: 'manufacturing_addon.manufacturing_addon.doctype.stock_entry_against_bom.stock_entry_against_bom.create_transfer_form_from_bom',
				args: {
					bom_docname: frm.doc.name
				},
				callback: function(r) {
					if (r.message) {
						frappe.set_route('Form', 'Transfer Form', r.message);
					}
				}
			});
		}, __('Actions'));

		// Add "Apply Row Colors" button for testing
		frm.add_custom_button(__('Apply Row Colors'), function() {
			applyRowStyling(frm);
			frappe.msgprint(__('Row colors applied! Check console for debug info.'));
		}, __('Debug'));
	},

	stock_entry_type: function(frm) {
		// Auto-set expense account based on stock entry type
		if (frm.doc.stock_entry_type) {
			frm.call({
				method: 'get_default_expense_account',
				args: {
					stock_entry_type: frm.doc.stock_entry_type
				},
				callback: function(r) {
					if (r.message && r.message.expense_account) {
						frm.set_value('expense_account', r.message.expense_account);
					}
				}
			});
		}
	},
	
});

// Function to show transfer dialog
function show_transfer_dialog(frm, items) {
	let d = new frappe.ui.Dialog({
		title: __('Transfer Items'),
		fields: [
			{
				fieldtype: 'Select',
				fieldname: 'item_type',
				label: __('Item Type'),
				options: 'Finished Items\nRaw Materials',
				default: 'Finished Items',
				list_view: true,
				onchange: function() {
					update_item_list();
				}
			},
			{
				fieldtype: 'Link',
				fieldname: 'item_code',
				label: __('Item'),
				options: 'Item',
				get_query: function() {
					return {
						filters: {
							'name': ['in', get_available_items()]
						}
					};
				},
				onchange: function() {
					update_available_qty();
				}
			},
			{
				fieldtype: 'Float',
				fieldname: 'qty_to_transfer',
				label: __('Quantity to Transfer'),
				onchange: function() {
					validate_qty();
				}
			},
			{
				fieldtype: 'Read Only',
				fieldname: 'available_qty',
				label: __('Available Quantity')
			}
		],
		primary_action: {
			label: __('Transfer'),
			action: function() {
				transfer_item();
			}
		}
	});

	function get_available_items() {
		let item_type = d.get_value('item_type');
		let items = [];
		
		if (item_type === 'Finished Items') {
			frm.doc.stock_entry_item_table.forEach(function(row) {
				if (row.remaining_qty > 0) {
					items.push(row.item);
				}
			});
		} else {
			frm.doc.stock_entry_required_item_table.forEach(function(row) {
				if (row.remaining_qty > 0) {
					items.push(row.item);
				}
			});
		}
		
		return items;
	}

	function update_item_list() {
		d.set_value('item_code', '');
		d.set_value('qty_to_transfer', '');
		d.set_value('available_qty', '');
	}

	function update_available_qty() {
		let item_code = d.get_value('item_code');
		let item_type = d.get_value('item_type');
		let available_qty = 0;
		
		if (item_type === 'Finished Items') {
			frm.doc.stock_entry_item_table.forEach(function(row) {
				if (row.item === item_code) {
					available_qty = row.remaining_qty;
				}
			});
		} else {
			frm.doc.stock_entry_required_item_table.forEach(function(row) {
				if (row.item === item_code) {
					available_qty = row.remaining_qty;
				}
			});
		}
		
		d.set_value('available_qty', available_qty);
	}

	function validate_qty() {
		let qty_to_transfer = d.get_value('qty_to_transfer');
		let available_qty = d.get_value('available_qty');
		
		if (qty_to_transfer > available_qty) {
			frappe.msgprint(__('Quantity to transfer cannot exceed available quantity'));
			d.set_value('qty_to_transfer', available_qty);
		}
	}

	function transfer_item() {
		let item_code = d.get_value('item_code');
		let qty_to_transfer = d.get_value('qty_to_transfer');
		let item_type = d.get_value('item_type');
		
		if (!item_code || !qty_to_transfer) {
			frappe.msgprint(__('Please select item and quantity'));
			return;
		}
		
		frm.call({
			method: 'create_transfer_stock_entry',
			args: {
				docname: frm.doc.name,
				item_code: item_code,
				qty_to_transfer: qty_to_transfer,
				item_type: item_type === 'Finished Items' ? 'finished' : 'raw'
			},
			callback: function(r) {
				if (r.message) {
					frappe.msgprint(__('Transfer completed successfully. Stock Entry: ') + r.message);
					d.hide();
					frm.reload_doc();
				}
			}
		});
	}

	d.show();
}



// Function to fetch items with quantities
function fetch_items_with_quantities(frm) {
	console.log('DEBUG: fetch_items_with_quantities called');
	
	frm.call({
		method: 'get_items_and_raw_materials',
		args: {
			sales_order: frm.doc.sales_order
		},
		callback: function(r) {
			console.log('DEBUG: Response received:', r);
			if (r.message) {
				console.log('DEBUG: Setting items:', r.message.items);
				console.log('DEBUG: Setting raw materials:', r.message.raw_materials);
				
				// Clear existing items first
				frm.clear_table('stock_entry_item_table');
				frm.clear_table('stock_entry_required_item_table');
				
				// Add items with custom quantities
				if (r.message.items && r.message.items.length > 0) {
					r.message.items.forEach(function(item) {
						let new_row = frm.add_child('stock_entry_item_table');
						new_row.item = item.item;
						new_row.bom = item.bom;
						new_row.order_qty = item.ordered_qty || 0; // Original ordered quantity from Sales Order
						new_row.qty = item.qty; // Remaining quantity to be processed
						new_row.issued_qty = item.issued_qty || 0; // Already issued/transferred quantity
						new_row.remaining_qty = item.remaining_qty || item.qty; // Remaining quantity to be processed
						new_row.excess_qty = item.excess_qty || 0; // Excess quantity if any
						
						// Set transfer status based on quantities
						if (item.remaining_qty === 0 && item.issued_qty > 0) {
							new_row.transfer_status = "Fully Transferred";
							// Add CSS class for styling
							new_row._row_class = "fully-transferred-row";
						} else if (item.issued_qty > 0) {
							new_row.transfer_status = "Partially Transferred";
							new_row._row_class = "partially-transferred-row";
						} else {
							new_row.transfer_status = "Pending";
							new_row._row_class = "pending-row";
						}
					});
				}
				
				// Add raw materials
				if (r.message.raw_materials && r.message.raw_materials.length > 0) {
					r.message.raw_materials.forEach(function(raw_material) {
						let new_row = frm.add_child('stock_entry_required_item_table');
						new_row.item = raw_material.item;
						new_row.qty = raw_material.qty;
						new_row.uom = raw_material.uom;
						new_row.issued_qty = 0;
						new_row.remaining_qty = raw_material.qty;
						new_row.transfer_status = "Pending";
					});
				}
				
				// Refresh fields and recalculate totals
				frm.refresh_field('stock_entry_item_table');
				frm.refresh_field('stock_entry_required_item_table');
				
				// Apply row styling after refresh
				setTimeout(() => {
					applyRowStyling(frm);
				}, 500);
				
				// Trigger validation to recalculate totals
				frm.trigger('validate');
				
				// Show success message with detailed information
				let message = __('Items fetched successfully! All items from Sales Order are displayed with current status.');
				
				// Count completed items
				let completedItems = 0;
				let pendingItems = 0;
				let excessItems = [];
				
				r.message.items.forEach(function(item) {
					if (item.remaining_qty === 0 && item.issued_qty > 0) {
						completedItems++;
					} else if (item.remaining_qty > 0) {
						pendingItems++;
					}
				});
				
				// Check for excess quantities
				if (r.message.excess_quantities) {
					for (let item in r.message.excess_quantities) {
						if (r.message.excess_quantities[item] > 0) {
							excessItems.push(`${item}: ${r.message.excess_quantities[item]}`);
						}
					}
				}
				
				message += `\n\n📊 Status Summary:`;
				message += `\n✅ Completed: ${completedItems} items`;
				message += `\n⏳ Pending: ${pendingItems} items`;
				
				if (excessItems.length > 0) {
					message += `\n\n⚠️ Excess quantities detected:`;
					excessItems.forEach(item => {
						message += `\n• ${item}`;
					});
				}
				
				frappe.msgprint(message);
			} else {
				console.log('DEBUG: No message in response');
			}
		}
	});
}

// Set up the form onload event
frappe.ui.form.on('Stock Entry Against BOM', {
	onload: function(frm) {
		// Initialize form when loaded
		console.log("Stock Entry Against BOM form loaded");
		// Initialize quantities for existing items
		initialize_quantities(frm);
		// Add CSS styling
		addRowStylingCSS();
		// Set up table observer
		setupTableObserver(frm);
	},
	
});

// Function to set up a MutationObserver to watch for table changes
function setupTableObserver(frm) {
	// Wait for the table to be rendered
	setTimeout(() => {
		const tableContainer = frm.fields_dict.stock_entry_item_table.wrapper;
		if (tableContainer) {
			// Create a MutationObserver to watch for changes in the table
			const observer = new MutationObserver((mutations) => {
				mutations.forEach((mutation) => {
					if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
						// Table has been updated, apply styling
						setTimeout(() => {
							applyRowStyling(frm);
						}, 100);
					}
				});
			});
			
			// Start observing
			observer.observe(tableContainer, {
				childList: true,
				subtree: true
			});
			
			console.log('DEBUG: Table observer set up');
		}
	}, 1000);
}

// Function to add CSS styling for row highlighting
function addRowStylingCSS() {
	// Check if CSS is already added
	if (document.getElementById('stock-entry-row-styling')) {
		return;
	}
	
	const style = document.createElement('style');
	style.id = 'stock-entry-row-styling';
	style.textContent = `
		.fully-transferred-row {
			background-color: #d4edda !important;
			border-left: 4px solid #28a745 !important;
		}
		.fully-transferred-row:hover {
			background-color: #c3e6cb !important;
		}
		.partially-transferred-row {
			background-color: #fff3cd !important;
			border-left: 4px solid #ffc107 !important;
		}
		.partially-transferred-row:hover {
			background-color: #ffeaa7 !important;
		}
		.pending-row {
			background-color: #f8f9fa !important;
			border-left: 4px solid #6c757d !important;
		}
		.pending-row:hover {
			background-color: #e9ecef !important;
		}
		/* Make the styling more prominent */
		.fully-transferred-row td {
			font-weight: 500 !important;
		}
		.partially-transferred-row td {
			font-weight: 500 !important;
		}
	`;
	document.head.appendChild(style);
}

// Function to apply row styling based on transfer status
function applyRowStyling(frm) {
	if (!frm.doc.stock_entry_item_table) {
		console.log('DEBUG: No stock_entry_item_table found');
		return;
	}
	
	console.log('DEBUG: Applying row styling for', frm.doc.stock_entry_item_table.length, 'items');
	
	// Find the table container - try multiple selectors
	let tableContainer = frm.fields_dict.stock_entry_item_table.wrapper;
	if (!tableContainer) {
		tableContainer = document.querySelector('[data-fieldname="stock_entry_item_table"]');
	}
	if (!tableContainer) {
		tableContainer = document.querySelector('.frappe-table[data-fieldname="stock_entry_item_table"]');
	}
	
	if (!tableContainer) {
		console.log('DEBUG: Table container not found');
		return;
	}
	
	console.log('DEBUG: Table container found:', tableContainer);
	
	// Get all table rows - try multiple selectors
	let rows = tableContainer.querySelectorAll('tbody tr');
	if (rows.length === 0) {
		rows = tableContainer.querySelectorAll('tr[data-idx]');
	}
	if (rows.length === 0) {
		rows = tableContainer.querySelectorAll('.grid-row');
	}
	
	console.log('DEBUG: Found', rows.length, 'rows');
	
		rows.forEach((row, index) => {
		if (index < frm.doc.stock_entry_item_table.length) {
			const item = frm.doc.stock_entry_item_table[index];
			console.log('DEBUG: Row', index, 'Item:', item.item);
			console.log('DEBUG: Row', index, 'Order Qty:', item.ordered_qty, 'Issued Qty:', item.issued_qty, 'Remaining Qty:', item.remaining_qty, 'Excess Qty:', item.excess_qty);
			console.log('DEBUG: Row', index, 'Status:', item.transfer_status);
			
			// Remove existing classes
			row.classList.remove('fully-transferred-row', 'partially-transferred-row', 'pending-row');
			
			// Check if item is fully transferred based on quantities
			const isFullyTransferred = (item.remaining_qty === 0 && item.issued_qty > 0) || 
									  (item.issued_qty > 0 && item.remaining_qty === 0);
			const isPartiallyTransferred = item.issued_qty > 0 && item.remaining_qty > 0;
			
			console.log('DEBUG: Row', index, 'isFullyTransferred:', isFullyTransferred, 'isPartiallyTransferred:', isPartiallyTransferred);
			
			// Add appropriate class based on transfer status
			if (isFullyTransferred) {
				row.classList.add('fully-transferred-row');
				// Apply inline styles as backup
				row.style.backgroundColor = '#d4edda';
				row.style.borderLeft = '4px solid #28a745';
				row.style.fontWeight = '500';
				console.log('DEBUG: Applied green styling to row', index);
			} else if (isPartiallyTransferred) {
				row.classList.add('partially-transferred-row');
				row.style.backgroundColor = '#fff3cd';
				row.style.borderLeft = '4px solid #ffc107';
				row.style.fontWeight = '500';
				console.log('DEBUG: Applied yellow styling to row', index);
			} else {
				row.classList.add('pending-row');
				row.style.backgroundColor = '#f8f9fa';
				row.style.borderLeft = '4px solid #6c757d';
				console.log('DEBUG: Applied gray styling to row', index);
			}
		}
	});
}

// Function to initialize quantities for existing items
function initialize_quantities(frm) {
	if (frm.doc.stock_entry_item_table && frm.doc.stock_entry_item_table.length > 0) {
		frm.doc.stock_entry_item_table.forEach(function(row) {
			// If order_qty is not set, try to get it from the backend
			if (!row.order_qty && row.item) {
				// This will be handled by the backend when fetching items
			}
			
			// Ensure remaining_qty is calculated correctly
			if (row.order_qty && row.issued_qty !== undefined) {
				row.remaining_qty = Math.max(0, (row.order_qty || 0) - (row.issued_qty || 0) - (row.qty || 0));
			}
		});
		frm.refresh_field('stock_entry_item_table');
	}
}

// Handle child table events with debouncing
let debounceTimer;

frappe.ui.form.on('Stock Entry Item Table', {
	item: function(frm, cdt, cdn) {
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			recalculateRawMaterials(frm);
		}, 500);
	},
	qty: function(frm, cdt, cdn) {
		// Update remaining quantity when qty changes
		let row = locals[cdt][cdn];
		if (row.order_qty && row.issued_qty !== undefined) {
			// Calculate remaining as: order_qty - issued_qty - current_qty
			// But since qty represents what we want to process, remaining should be order_qty - issued_qty - qty
			row.remaining_qty = Math.max(0, (row.order_qty || 0) - (row.issued_qty || 0) - (row.qty || 0));
			
			// Update transfer status based on new quantities
			if (row.remaining_qty === 0 && row.issued_qty > 0) {
				row.transfer_status = "Fully Transferred";
			} else if (row.issued_qty > 0) {
				row.transfer_status = "Partially Transferred";
			} else {
				row.transfer_status = "Pending";
			}
		}
		frm.refresh_field('stock_entry_item_table');
		
		// Apply row styling after refresh
		setTimeout(() => {
			applyRowStyling(frm);
		}, 100);
		
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			recalculateRawMaterials(frm);
		}, 500);
	},
	stock_entry_item_table_remove: function(frm, cdt, cdn) {
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			recalculateRawMaterials(frm);
		}, 500);
	}
});

function recalculateRawMaterials(frm) {
	if (!frm.doc.sales_order) return;
	
	// Filter out deleted rows
	let items = frm.doc.stock_entry_item_table.filter(row => !row.is_deleted);
	
	frm.call({
		method: 'recalculate_raw_materials',
		args: {
			items: items
		},
		callback: function(r) {
			if (r.message && r.message.raw_materials) {
				frm.set_value('stock_entry_required_item_table', r.message.raw_materials);
				frm.refresh_field('stock_entry_required_item_table');
			}
		}
	});
}

