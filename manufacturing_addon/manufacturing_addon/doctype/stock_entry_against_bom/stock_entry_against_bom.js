// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Entry Against BOM', {
	refresh: function(frm) {
		// Add custom button
		frm.add_custom_button(__('Get Items'), function() {
			frm.call({
				method: 'get_items_and_raw_materials',
				args: {
					sales_order: frm.doc.sales_order
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('stock_entry_item_table', r.message.items || []);
						frm.set_value('stock_entry_required_item_table', r.message.raw_materials || []);
						frm.refresh_field('stock_entry_item_table');
						frm.refresh_field('stock_entry_required_item_table');
					}
				}
			});
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

// Set up expense_account field query
frappe.ui.form.on('Stock Entry Against BOM', {
	expense_account: function(frm) {
		// This will be handled in the server-side method
	}
});

// Set up the query for expense_account field
frappe.ui.form.on('Stock Entry Against BOM', {
	onload: function(frm) {
		frm.fields_dict.expense_account.get_query = function() {
			return {
				filters: {
					"account_type": "Expenses",
					"report_type": "Profit and Loss",
					"is_group": 0
				}
			};
		};
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

