// Copyright (c) 2025, Manufacturing Addon and contributors
// For license information, please see license.txt

frappe.ui.form.on('Subcontractor Production Billing', {
	refresh: function(frm) {
		// Add custom button to generate billing
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Generate Billing'), function() {
				frm.events.generate_billing(frm);
			}, __('Actions'));
			
			// Add button to create rate cards for items without rates
			if (frm.doc.billing_items && frm.doc.billing_items.length > 0) {
				var items_without_rates = frm.doc.billing_items.filter(function(item) {
					return !item.rate || item.rate <= 0;
				});
				
				if (items_without_rates.length > 0) {
					frm.add_custom_button(__('Create Rate Cards for Missing Items'), function() {
						frm.events.create_rate_cards(frm, items_without_rates);
					}, __('Actions'));
					
					// Add button to refresh rates (in case rate cards were added after generation)
					frm.add_custom_button(__('Refresh Rates'), function() {
						frm.events.refresh_rates(frm);
					}, __('Actions'));
				}
			}
		}
	},
	
	create_rate_cards: function(frm, items_without_rates) {
		if (!frm.doc.supplier) {
			frappe.msgprint(__('Please select a Supplier first'));
			return;
		}
		
		var item_codes = items_without_rates.map(function(item) {
			return item.item_code;
		});
		
		frappe.confirm(
			__('This will create {0} Subcontractor Rate Card(s) for items without rates. Continue?', [item_codes.length]),
			function() {
				// Yes - open rate card creation dialog
				frappe.prompt([
					{
						fieldtype: 'Date',
						fieldname: 'valid_from',
						label: __('Valid From'),
						reqd: 1,
						default: frappe.datetime.get_today()
					},
					{
						fieldtype: 'Date',
						fieldname: 'valid_to',
						label: __('Valid To (Optional)')
					},
					{
						fieldtype: 'Currency',
						fieldname: 'default_rate',
						label: __('Default Rate Per PCS'),
						description: __('This rate will be used for all items. You can edit individual rate cards later.')
					}
				], function(values) {
					// Create rate cards
					frappe.call({
						method: 'manufacturing_addon.manufacturing_addon.doctype.subcontractor_production_billing.subcontractor_production_billing.create_rate_cards_for_items',
						args: {
							supplier: frm.doc.supplier,
							item_codes: item_codes,
							valid_from: values.valid_from,
							valid_to: values.valid_to,
							default_rate: values.default_rate || 0
						},
						callback: function(r) {
							if (r.message) {
								frappe.msgprint(__('Created {0} Rate Card(s). Please refresh and regenerate billing.', [r.message]));
								frm.reload_doc();
							}
						},
						freeze: true,
						freeze_message: __('Creating Rate Cards...')
					});
				}, __('Create Rate Cards'), __('Create'));
			},
			function() {
				// No
			}
		);
	},
	
	generate_billing: function(frm) {
		if (!frm.doc.supplier) {
			frappe.msgprint(__('Please select a Supplier first'));
			return;
		}
		
		frappe.confirm(
			__('This will generate billing items from Delivery Notes and Production Reports. Continue?'),
			function() {
				// Yes
				frappe.call({
					method: 'generate_billing',
					doc: frm.doc,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(__('Generated {0} billing items', [r.message]));
							frm.reload_doc();
						}
					},
					freeze: true,
					freeze_message: __('Generating billing items...')
				});
			},
			function() {
				// No
			}
		);
	},
	
	refresh_rates: function(frm) {
		if (!frm.doc.supplier) {
			frappe.msgprint(__('Please select a Supplier first'));
			return;
		}
		
		if (!frm.doc.billing_items || frm.doc.billing_items.length === 0) {
			frappe.msgprint(__('No billing items to refresh rates for'));
			return;
		}
		
		frappe.call({
			method: 'refresh_rates',
			doc: frm.doc,
			callback: function(r) {
				if (r.message) {
					frappe.msgprint(__('Refreshed rates for {0} item(s)', [r.message.updated]));
					if (r.message.missing && r.message.missing.length > 0) {
						frappe.msgprint(__('Rate still not found for: {0}', [r.message.missing.join(', ')]), indicator="orange");
					}
					frm.reload_doc();
				}
			},
			freeze: true,
			freeze_message: __('Refreshing rates...')
		});
	}
});
