// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on('Raw Material Transfer Planning', {
	refresh(frm) {
		// Add custom buttons
		if (!frm.is_new() && frm.doc.status !== 'Cancelled') {
			frm.add_custom_button('Get Finished from Sales Order', () => {
				frm.call('get_finished_from_sales_order').then(() => {
					frm.refresh_field('finished_items');
				});
			});
			
			frm.add_custom_button('Explode BOMs', () => {
				frm.call('explode_boms').then(() => {
					frm.refresh_fields(['rmtp_raw_material', 'total_planned_qty', 'total_pending_qty', 'status']);
				});
			});
			
			frm.add_custom_button('Refresh Availability', () => {
				frm.call('refresh_availability').then(() => {
					frm.refresh_field('rmtp_raw_material');
				});
			});
		}
	},
	
	company(frm) {
		// Auto-set from/to warehouses based on company if needed
		if (frm.doc.company) {
			// Optional: set default warehouses based on company settings
		}
	},
	
	sales_order(frm) {
		// Optional: fetch company from sales order
		if (frm.doc.sales_order) {
			frappe.db.get_value('Sales Order', frm.doc.sales_order, 'company', (r) => {
				if (r && r.company) {
					frm.set_value('company', r.company);
				}
			});
		}
	}
});
