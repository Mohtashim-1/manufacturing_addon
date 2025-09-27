// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on("Extra Qty Request", {
	refresh(frm) {
		// Add a button to refresh actual quantities
		if (frm.doc.docstatus === 0) { // Only show for draft documents
			frm.add_custom_button(__('Refresh Stock Quantities'), function() {
				frm.call('refresh_actual_quantities').then(function(r) {
					if (r.message && r.message.status === 'success') {
						frappe.show_alert({
							message: r.message.message,
							indicator: 'green'
						});
						frm.refresh_field('extra_qty_request_item');
					}
				});
			}, __('Actions'));
		}
	},
	
	onload(frm) {
		// Automatically refresh actual quantities when document is loaded
		if (frm.doc.docstatus === 0 && frm.doc.extra_qty_request_item && frm.doc.extra_qty_request_item.length > 0) {
			frm.call('refresh_actual_quantities').then(function(r) {
				if (r.message && r.message.status === 'success') {
					frm.refresh_field('extra_qty_request_item');
				}
			});
		}
	}
});
