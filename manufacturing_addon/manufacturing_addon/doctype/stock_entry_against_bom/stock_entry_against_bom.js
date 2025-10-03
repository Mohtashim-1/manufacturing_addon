// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Entry Against BOM', {
	refresh: function(frm) {
		// Add custom button
		frm.add_custom_button(__('Get Items'), function() {
			// Get the current production_qty_type from the form
			let production_qty_type = frm.doc.production_qty_type || 'Under Order Qty';
			
			// If Over Order Qty is selected, show custom quantity dialog
			if (production_qty_type === 'Over Order Qty') {
				show_custom_quantity_dialog(frm, production_qty_type);
			} else {
				// For Under Order Qty, fetch items directly
				fetch_items_with_quantities(frm, production_qty_type);
			}
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
	
	production_qty_type: function(frm) {
		// Show information about the selected production quantity type
		if (frm.doc.production_qty_type) {
			let message = '';
			if (frm.doc.production_qty_type === 'Under Order Qty') {
				message = __('Under Order Qty: Only remaining quantities (ordered - delivered) will be fetched from Sales Order.');
			} else if (frm.doc.production_qty_type === 'Over Order Qty') {
				message = __('Over Order Qty: Full ordered quantities will be fetched from Sales Order, regardless of delivery status.');
			}
			
			if (message) {
				frappe.show_alert({
					message: message,
					indicator: 'blue'
				});
			}
		}
	}
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

// Global variable to store custom quantities
let stored_custom_quantities = {};

// Function to show custom quantity dialog for Over Order Qty
function show_custom_quantity_dialog(frm, production_qty_type) {
	// First get the sales order items to show in the dialog
	frm.call({
		method: 'get_sales_order_items_for_custom_quantities',
		args: {
			sales_order: frm.doc.sales_order
		},
		callback: function(r) {
			if (r.message && r.message.success) {
				let items = r.message.items.filter(item => item.will_be_included);
				
				if (items.length === 0) {
					frappe.msgprint(__('No items found in the Sales Order'));
					return;
				}
				
				// Pre-fill items with stored custom quantities if available
				items.forEach(function(item) {
					if (stored_custom_quantities[item.item_code]) {
						item.custom_qty = stored_custom_quantities[item.item_code];
					} else {
						item.custom_qty = item.ordered_qty;
					}
				});
				
				// Create custom quantity dialog
				let d = new frappe.ui.Dialog({
					title: __('Set Custom Quantities for Over Order Production'),
					fields: [
						{
							fieldtype: 'HTML',
							fieldname: 'info',
							options: '<div class="alert alert-info">' +
								'<strong>Over Order Production:</strong> You can set custom quantities for each item. ' +
								'Leave blank to use the original ordered quantity.' +
								'</div>'
						},
						{
							fieldtype: 'HTML',
							fieldname: 'items_table',
							options: create_items_table_html(items)
						}
					],
					primary_action_label: __('Get Items with Custom Quantities'),
					primary_action: function() {
						process_custom_quantities(d, frm, production_qty_type);
					},
					secondary_action_label: __('Use Ordered Quantities'),
					secondary_action: function() {
						d.hide();
						fetch_items_with_quantities(frm, production_qty_type);
					}
				});
				
				d.show();
			} else {
				frappe.msgprint(__('Error fetching Sales Order items: ') + (r.message.error || 'Unknown error'));
			}
		}
	});
}

// Function to create HTML table with editable input fields
function create_items_table_html(items) {
	let html = `
		<style>
			.custom-quantities-table {
				max-height: 400px;
				overflow-y: auto;
			}
			.custom-quantities-table table {
				margin-bottom: 0;
			}
			.custom-quantities-table th {
				background-color: #f8f9fa;
				font-weight: bold;
				position: sticky;
				top: 0;
				z-index: 10;
			}
			.custom-qty-input {
				width: 100%;
				min-width: 120px;
			}
			.custom-quantities-table td {
				vertical-align: middle;
			}
		</style>
		<div class="custom-quantities-table">
			<div class="text-right mb-2">
				<button type="button" class="btn btn-sm btn-secondary" onclick="reset_to_ordered_quantities(this)">
					<i class="fa fa-refresh"></i> Reset to Ordered Qty
				</button>
			</div>
			<table class="table table-bordered table-striped">
				<thead>
					<tr>
						<th style="width: 15%;">Item Code</th>
						<th style="width: 25%;">Item Name</th>
						<th style="width: 12%;">Ordered Qty</th>
						<th style="width: 12%;">Delivered Qty</th>
						<th style="width: 12%;">Remaining Qty</th>
						<th style="width: 24%;">Custom Qty</th>
					</tr>
				</thead>
				<tbody>
	`;
	
	items.forEach(function(item, index) {
		html += `
			<tr>
				<td><strong>${item.item_code}</strong></td>
				<td>${item.item_name}</td>
				<td class="text-right">${item.ordered_qty}</td>
				<td class="text-right">${item.delivered_qty}</td>
				<td class="text-right">${item.remaining_qty}</td>
				<td>
					<input type="number" 
						   class="form-control custom-qty-input" 
						   data-item-code="${item.item_code}"
						   value="${item.custom_qty || item.ordered_qty}"
						   min="0"
						   step="0.01"
						   placeholder="Enter custom qty"
						   style="text-align: right;">
				</td>
			</tr>
		`;
	});
	
	html += `
				</tbody>
			</table>
		</div>
	`;
	
	return html;
}

// Function to reset all custom quantities to ordered quantities
function reset_to_ordered_quantities(button) {
	// Find the dialog from the button
	let dialog = $(button).closest('.modal-dialog').data('dialog');
	if (!dialog) {
		// Fallback: find the closest table
		$(button).closest('.custom-quantities-table').find('.custom-qty-input').each(function() {
			let $input = $(this);
			let itemCode = $input.data('item-code');
			let $row = $input.closest('tr');
			let orderedQty = parseFloat($row.find('td:nth-child(3)').text());
			$input.val(orderedQty);
			// Update stored quantities
			stored_custom_quantities[itemCode] = orderedQty;
		});
	} else {
		// Use dialog method
		$(dialog.fields_dict.items_table.$wrapper).find('.custom-qty-input').each(function() {
			let $input = $(this);
			let itemCode = $input.data('item-code');
			let $row = $input.closest('tr');
			let orderedQty = parseFloat($row.find('td:nth-child(3)').text());
			$input.val(orderedQty);
			// Update stored quantities
			stored_custom_quantities[itemCode] = orderedQty;
		});
	}
	
	frappe.show_alert({
		message: __('All quantities reset to ordered quantities'),
		indicator: 'green'
	});
}

// Function to process custom quantities and fetch items
function process_custom_quantities(dialog, frm, production_qty_type) {
	console.log('DEBUG: process_custom_quantities called');
	let custom_quantities = {};
	let has_custom_qty = false;
	
	// Get custom quantities from input fields
	$(dialog.fields_dict.items_table.$wrapper).find('.custom-qty-input').each(function() {
		let itemCode = $(this).data('item-code');
		let customQty = parseFloat($(this).val());
		
		console.log('DEBUG: Item', itemCode, 'Custom Qty:', customQty);
		
		// Store the custom quantity (even if 0 or empty)
		stored_custom_quantities[itemCode] = customQty;
		
		if (customQty && customQty > 0) {
			custom_quantities[itemCode] = customQty;
			has_custom_qty = true;
		}
	});
	
	console.log('DEBUG: Custom quantities collected:', custom_quantities);
	console.log('DEBUG: Stored custom quantities:', stored_custom_quantities);
	
	// Validate custom quantities
	let invalid_items = [];
	$(dialog.fields_dict.items_table.$wrapper).find('.custom-qty-input').each(function() {
		let itemCode = $(this).data('item-code');
		let customQty = parseFloat($(this).val());
		
		if ($(this).val() !== '' && (isNaN(customQty) || customQty <= 0)) {
			invalid_items.push(itemCode);
		}
	});
	
	if (invalid_items.length > 0) {
		frappe.msgprint(__('Please enter valid quantities (greater than 0) for: ') + invalid_items.join(', '));
		return;
	}
	
	console.log('DEBUG: Hiding dialog and fetching items');
	dialog.hide();
	
	// Fetch items with custom quantities
	fetch_items_with_quantities(frm, production_qty_type, custom_quantities);
}

// Function to fetch items with quantities
function fetch_items_with_quantities(frm, production_qty_type, custom_quantities = null) {
	console.log('DEBUG: fetch_items_with_quantities called');
	console.log('DEBUG: production_qty_type:', production_qty_type);
	console.log('DEBUG: custom_quantities:', custom_quantities);
	
	frm.call({
		method: 'get_items_and_raw_materials',
		args: {
			sales_order: frm.doc.sales_order,
			production_qty_type: production_qty_type,
			custom_quantities: custom_quantities
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
						new_row.qty = item.qty; // This should be the custom quantity
						new_row.issued_qty = 0;
						new_row.remaining_qty = item.qty;
						new_row.transfer_status = "Pending";
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
				
				// Trigger validation to recalculate totals
				frm.trigger('validate');
				
				// Show message about production quantity type used
				let message = __('Items fetched using {0} mode', [production_qty_type]);
				if (r.message.custom_quantities_used) {
					message += __(' with custom quantities');
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
	},
	
	before_save: function(frm) {
		// Ensure custom quantities are preserved before save
		console.log('DEBUG: before_save triggered');
		console.log('DEBUG: Current stock_entry_item_table:', frm.doc.stock_entry_item_table);
		
		// If we have stored custom quantities, ensure they are applied
		if (Object.keys(stored_custom_quantities).length > 0) {
			console.log('DEBUG: Applying stored custom quantities before save');
			frm.doc.stock_entry_item_table.forEach(function(row) {
				if (stored_custom_quantities[row.item]) {
					console.log('DEBUG: Updating', row.item, 'from', row.qty, 'to', stored_custom_quantities[row.item]);
					row.qty = stored_custom_quantities[row.item];
					row.remaining_qty = stored_custom_quantities[row.item] - (row.issued_qty || 0);
				}
			});
		}
	},
	
	on_submit: function(frm) {
		// Clear stored custom quantities after successful submit
		console.log('DEBUG: on_submit triggered - clearing stored custom quantities');
		stored_custom_quantities = {};
	},
	
	sales_order: function(frm) {
		// Clear stored custom quantities when sales order changes
		if (frm.doc.sales_order) {
			console.log('DEBUG: Sales order changed - clearing stored custom quantities');
			stored_custom_quantities = {};
		}
	}
});

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

