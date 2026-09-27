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
				if (!frm.doc.planning) {
					frappe.msgprint({
						title: __('Validation'),	
						message: __('Please select a Planning document first.'),
						indicator: 'orange'
					});
					return;
				}
				
				frm.call('get_from_planning').then((r) => {
					if (r.message) {
						frappe.show_alert({
							message: r.message,
							indicator: 'green'
						}, 3);
					}
					frm.refresh_field('items');
				}).catch((err) => {
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

		if (!frm.is_new() && frm.doc.docstatus === 0 && frm.doc.from_warehouse) {
			frm.add_custom_button(__('Show Blocking Reservations'), () => {
				frappe.call({
					method:
						'manufacturing_addon.manufacturing_addon.utils.rmi_stock_reservation.get_blocking_reservations_for_rmi',
					args: { issuance_name: frm.doc.name },
					freeze: true,
					callback: (r) => {
						const rows = r.message || [];
						if (!rows.length) {
							frappe.msgprint({
								title: __('No Blocking Reservations'),
								message: __(
									'No open reservations from other Sales Orders / vouchers for these items in {0}. Same-SO Production Plan reservations are consumed automatically on submit.',
									[frm.doc.from_warehouse]
								),
								indicator: 'green',
							});
							return;
						}

						const html = [
							`<p>${__(
								'These quantities are reserved for other vouchers and will block submit. Open each SRE and use Actions → Unreserve Remaining.'
							)}</p>`,
							'<table class="table table-bordered"><thead><tr>',
							`<th>${__('SRE')}</th><th>${__('Item')}</th><th>${__('Open Qty')}</th>`,
							`<th>${__('Voucher')}</th><th>${__('Status')}</th>`,
							'</tr></thead><tbody>',
						];
						rows.forEach((row) => {
							html.push(
								'<tr>',
								`<td><a href="/desk/stock-reservation-entry/${encodeURIComponent(row.name)}">${frappe.utils.escape_html(row.name)}</a></td>`,
								`<td>${frappe.utils.escape_html(row.item_code)}</td>`,
								`<td>${flt(row.open_qty)}</td>`,
								`<td>${frappe.utils.escape_html(row.voucher_type)}: ${frappe.utils.escape_html(row.voucher_no)}</td>`,
								`<td>${frappe.utils.escape_html(row.status)}</td>`,
								'</tr>'
							);
						});
						html.push('</tbody></table>');
						frappe.msgprint({
							title: __('Blocking Reservations'),
							message: html.join(''),
							indicator: 'orange',
						});
					},
				});
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
		// Note: Allowing quantities to exceed pending on planning rows
		// This allows flexibility for additional material requirements
		// No validation needed - user can issue more than planned
	}
});

