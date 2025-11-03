// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on('Raw Material Issuance', {
	refresh(frm) {
		// Add custom buttons
		if (frm.doc.status === 'Draft') {
			frm.add_custom_button('Get Items → Sales Order', () => {
				frm.call('get_from_sales_order').then((r) => {
					if (r.message) {
						frappe.show_alert(r.message);
					}
					frm.refresh_field('items');
				});
			});
			
			frm.add_custom_button('Get Items → Transfer Planning (Pending)', () => {
				console.log('=== Get Items from Planning - START ===');
				console.log('Planning document:', frm.doc.planning);
				console.log('Full form doc:', frm.doc);
				
				if (!frm.doc.planning) {
					console.log('ERROR: No planning document selected');
					frappe.msgprint({
						title: __('Validation'),
						message: __('Please select a Planning document first.'),
						indicator: 'orange'
					});
					return;
				}
				
				console.log('Calling get_from_planning method...');
				frm.call('get_from_planning').then((r) => {
					console.log('=== Response from get_from_planning ===');
					console.log('Response:', r);
					console.log('Message:', r.message);
					console.log('Items before refresh:', frm.doc.items);
					
					if (r.message) {
						frappe.show_alert({
							message: r.message,
							indicator: 'green'
						}, 3);
					}
					
					frm.refresh_field('items');
					console.log('Items after refresh:', frm.doc.items);
					console.log('=== Get Items from Planning - END ===');
				}).catch((err) => {
					console.error('=== ERROR in get_from_planning ===');
					console.error('Error object:', err);
					console.error('Error message:', err.message);
					console.error('Full error:', JSON.stringify(err, null, 2));
					
					let error_msg = err.message || 'Error loading items from planning';
					frappe.msgprint({
						title: __('Error'),
						message: error_msg,
						indicator: 'red'
					});
				});
			});
			
			frm.add_custom_button('Recalc Availability', () => {
				frm.call('recalc_availability').then((r) => {
					if (r.message) {
						frappe.show_alert(r.message);
					}
					frm.refresh_field('items');
				});
			});
		}
		
		// Show link to Stock Entry if submitted
		if (frm.doc.status === 'Submitted' && frm.doc.stock_entry) {
			frm.add_custom_button(__('View Stock Entry'), () => {
				frappe.set_route('Form', 'Stock Entry', frm.doc.stock_entry);
			});
		}
	},
	
	planning(frm) {
		// When planning is selected, auto-fill company and warehouses
		if (frm.doc.planning) {
			frappe.db.get_value('Raw Material Transfer Planning', frm.doc.planning, 
				['company', 'from_warehouse', 'to_warehouse'], (r) => {
					if (r) {
						if (r.company) frm.set_value('company', r.company);
						if (r.from_warehouse) frm.set_value('from_warehouse', r.from_warehouse);
						if (r.to_warehouse) frm.set_value('to_warehouse', r.to_warehouse);
					}
				}
			);
		}
	},
	
	sales_order(frm) {
		// Auto-fill company from sales order
		if (frm.doc.sales_order) {
			frappe.db.get_value('Sales Order', frm.doc.sales_order, 'company', (r) => {
				if (r && r.company) {
					frm.set_value('company', r.company);
				}
			});
		}
	},
	
	validate(frm) {
		// Block negative or zero quantities
		(frm.doc.items || []).forEach(r => {
			if (!r.qty || r.qty <= 0) {
				frappe.throw(`Qty must be > 0 for ${r.item_code}`);
			}
		});
	}
});

// Child table events for items
frappe.ui.form.on('RMTI Item', {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.item_code) {
			// Fetch item details
			frappe.db.get_value('Item', row.item_code, ['item_name', 'stock_uom'], (r) => {
				if (r) {
					frappe.model.set_value(cdt, cdn, {
						item_name: r.item_name,
						stock_uom: r.stock_uom
					});
					// Recalculate availability
					if (frm.doc.from_warehouse) {
						frm.call('recalc_availability').then(() => {
							frm.refresh_field('items');
						});
					}
				}
			});
		}
	},
	
	qty(frm, cdt, cdn) {
		// Validate qty against pending if linked to planning
		const row = locals[cdt][cdn];
		if (row.planning_row && row.qty) {
			frappe.db.get_value('RMTP Raw Material', row.planning_row, 'pending_qty', (r) => {
				if (r && row.qty > r.pending_qty) {
					frappe.msgprint({
						title: __('Warning'),
						indicator: 'orange',
						message: __('Quantity exceeds pending quantity in planning row')
					});
				}
			});
		}
	}
});

