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
			
			frm.add_custom_button('Refresh Issued Qty', () => {
				frm.call('refresh_issued_qty').then(() => {
					frm.refresh_fields(['rmtp_raw_material', 'total_issued_qty', 'total_pending_qty', 'status']);
				});
			});
		}
		
		// Add Create button group (standard ERPNext pattern)
		if (frm.doc.docstatus === 1 && frm.doc.status !== 'Cancelled') {
			// Check if there are pending items
			const has_pending = frm.doc.rmtp_raw_material && frm.doc.rmtp_raw_material.some(
				row => (row.pending_qty || 0) > 0
			);
			
			if (has_pending && frappe.model.can_create("Raw Material Issuance")) {
				frm.add_custom_button(
					__('Raw Material Issuance'),
					() => {
						frappe.model.open_mapped_doc({
							method: "manufacturing_addon.manufacturing_addon.doctype.raw_material_transfer_planning.raw_material_transfer_planning.make_raw_material_issuance",
							frm: frm,
							freeze: true,
							freeze_message: __("Creating Raw Material Issuance...")
						});
					},
					__('Create')
				);
				frm.page.set_inner_btn_group_as_primary(__('Create'));
			}
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
