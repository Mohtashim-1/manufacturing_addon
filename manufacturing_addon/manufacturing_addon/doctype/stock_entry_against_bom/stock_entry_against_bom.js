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

