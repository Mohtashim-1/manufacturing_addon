// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on('Raw Material Transfer Planning', {
	refresh(frm) {
		console.log('[RMT Planning] Refresh event triggered', {
			docname: frm.doc.name,
			is_new: frm.is_new(),
			status: frm.doc.status,
			sales_order: frm.doc.sales_order,
			docstatus: frm.doc.docstatus
		});
		
		// Add standard buttons in "Get Items From" group
		// Allow even for new documents (user needs to set Sales Order first)
		if (frm.doc.status !== 'Cancelled') {
			// Get Finished from Sales Order - standard button
			console.log('[RMT Planning] Adding "Get Finished from Sales Order" button');
			
			// Define handler function first
			function getFinishedFromSalesOrder() {
				console.log('[RMT Planning] ===== Get Finished from Sales Order button clicked =====');
				console.log('[RMT Planning] Button click handler fired', {
					sales_order: frm.doc.sales_order,
					is_new: frm.is_new(),
					docname: frm.doc.name,
					docstatus: frm.doc.docstatus,
					timestamp: new Date().toISOString()
				});
					
					// Use the sales_order value as-is (it might be a single Sales Order with a name like "-6616,6658,6715")
					let sales_order_value = frm.doc.sales_order ? String(frm.doc.sales_order).trim() : '';
					console.log('[RMT Planning] Using Sales Order value as-is:', sales_order_value);
				
				if (!sales_order_value || sales_order_value === '') {
					console.warn('[RMT Planning] Sales Order not set');
					frappe.msgprint(__('Please set Sales Order first.'));
					return;
				}
				
				// For new/unsaved documents, save first
				// docstatus 0 means saved but not submitted, which is fine
				// Only prevent if document has no name (truly new/unsaved)
				if (!frm.doc.name) {
					console.warn('[RMT Planning] Document is unsaved, needs to be saved first');
					frappe.msgprint(__('Please save the document first before fetching items.'));
					return;
				}
				
				console.log('[RMT Planning] Calling get_finished_from_sales_order method with Sales Order:', sales_order_value);
				
				frm.call({
					method: 'get_finished_from_sales_order',
					doc: frm.doc,
					callback: function(r) {
						console.log('[RMT Planning] get_finished_from_sales_order callback', {
							has_exc: !!r.exc,
							has_message: !!r.message,
							has_finished_items: !!(r.message && r.message.finished_items),
							finished_items_count: r.message && r.message.finished_items ? r.message.finished_items.length : 0,
							full_response: r
						});
						
						if (r.exc) {
							console.error('[RMT Planning] Error in get_finished_from_sales_order:', r.exc);
							frappe.msgprint({
								title: __('Error'),
								message: __('Error fetching items: {0}', [r.exc]),
								indicator: 'red'
							});
							return;
						}
						
						if (r.message && r.message.finished_items) {
							console.log('[RMT Planning] Setting finished_items:', r.message.finished_items);
							// Set the child table with the returned data
							frm.set_value('finished_items', r.message.finished_items).then(() => {
								console.log('[RMT Planning] finished_items set successfully');
								frm.refresh_field('finished_items');
							}).catch((err) => {
								console.error('[RMT Planning] Error setting finished_items:', err);
							});
						} else {
							console.warn('[RMT Planning] No finished_items in response:', r.message);
						}
						
						if (r.message && r.message.message) {
							console.log('[RMT Planning] Success message:', r.message.message);
							frappe.show_alert({
								message: r.message.message,
								indicator: 'green'
							}, 3);
						}
					}
				}).catch((err) => {
					console.error('[RMT Planning] Error calling get_finished_from_sales_order:', err);
					frappe.msgprint({
						title: __('Error'),
						message: __('Error fetching items: {0}', [err.message || err]),
						indicator: 'red'
					});
				});
			}
			
			// Add button with group
			const btn = frm.add_custom_button(__('Get Finished from Sales Order'), getFinishedFromSalesOrder, __('Get Items From'));
			console.log('[RMT Planning] "Get Finished from Sales Order" button added (with group), button element:', btn);
			
			// Also manually attach click handler as backup
			setTimeout(() => {
				// Find the button by text
				const buttons = $(document).find('.btn:contains("Get Finished from Sales Order")');
				console.log('[RMT Planning] Found buttons by text:', buttons.length);
				
				buttons.each(function() {
					const $btn = $(this);
					if (!$btn.data('rmt-handler-attached')) {
						console.log('[RMT Planning] Attaching direct click handler to button:', this);
						$btn.on('click', function(e) {
							console.log('[RMT Planning] Direct click handler fired!', e);
							e.preventDefault();
							e.stopPropagation();
							getFinishedFromSalesOrder();
						});
						$btn.data('rmt-handler-attached', true);
					}
				});
			}, 500);
			
			// Explode BOMs - standard button
			console.log('[RMT Planning] Adding "Explode BOMs" button');
			try {
				const explodeBomsHandler = function() {
					console.log('[RMT Planning] ===== Explode BOMs button clicked =====');
					console.log('[RMT Planning] Explode BOMs button clicked', {
						finished_items_count: frm.doc.finished_items ? frm.doc.finished_items.length : 0,
						docname: frm.doc.name,
						company: frm.doc.company,
						finished_items: frm.doc.finished_items
					});
					
					if (!frm.doc.finished_items || frm.doc.finished_items.length === 0) {
						frappe.msgprint(__('No finished items found. Please use "Get Finished from Sales Order" first.'));
						return;
					}
					
					if (!frm.doc.company) {
						frappe.msgprint(__('Please set Company first.'));
						return;
					}
					
					frm.call({
						method: 'explode_boms',
						doc: frm.doc,
						freeze: true,
						freeze_message: __('Exploding BOMs...')
					}).then((r) => {
						console.log('[RMT Planning] explode_boms completed', {
							response: r,
							rmtp_raw_material_count: frm.doc.rmtp_raw_material ? frm.doc.rmtp_raw_material.length : 0,
							message: r.message
						});
						frm.refresh_fields(['rmtp_raw_material', 'total_planned_qty', 'total_issued_qty', 'total_pending_qty', 'status']);
						if (r.message && r.message.message) {
							frappe.show_alert({
								message: r.message.message,
								indicator: 'green'
							}, 3);
						}
					}).catch((err) => {
						console.error('[RMT Planning] Error in explode_boms:', err);
						frappe.msgprint({
							title: __('Error'),
							message: __('Error exploding BOMs: {0}', [err.message || err]),
							indicator: 'red'
						});
					});
				};
				
				const btn = frm.add_custom_button(__('Explode BOMs'), explodeBomsHandler, __('Get Items From'));
				console.log('[RMT Planning] "Explode BOMs" button added successfully, button element:', btn);
				
				// Also manually attach click handler as backup
				setTimeout(() => {
					// Find the button by text (try both variations)
					let buttons = $(document).find('.btn:contains("Explode BOMs")');
					if (buttons.length === 0) {
						buttons = $(document).find('.btn:contains("Explode BOM")');
					}
					// Also try finding by data attribute
					if (buttons.length === 0) {
						buttons = $(document).find('[data-fieldname="explode_bom"]');
					}
					console.log('[RMT Planning] Found "Explode BOM" buttons:', buttons.length);
					
					buttons.each(function() {
						const $btn = $(this);
						const btnText = $btn.text().trim();
						console.log('[RMT Planning] Checking button:', btnText, this);
						
						// Check if this is the explode BOM button (by text or data attribute)
						if ((btnText.includes('Explode BOM') || $btn.attr('data-fieldname') === 'explode_bom') && 
						    !$btn.data('rmt-explode-handler-attached')) {
							console.log('[RMT Planning] Attaching direct click handler to "Explode BOM" button:', this);
							$btn.on('click', function(e) {
								console.log('[RMT Planning] Direct click handler fired for "Explode BOM"!', e);
								e.preventDefault();
								e.stopPropagation();
								explodeBomsHandler();
							});
							$btn.data('rmt-explode-handler-attached', true);
						}
					});
				}, 500);
			} catch (err) {
				console.error('[RMT Planning] Error adding "Explode BOMs" button:', err);
			}
			
			// Refresh Availability - Actions group
			frm.add_custom_button(
				__('Refresh Availability'),
				() => {
					console.log('[RMT Planning] Refresh Availability button clicked');
					frm.call('refresh_availability').then((r) => {
						console.log('[RMT Planning] refresh_availability completed', { response: r });
						frm.refresh_field('rmtp_raw_material');
					}).catch((err) => {
						console.error('[RMT Planning] Error in refresh_availability:', err);
					});
				},
				__('Actions')
			);
			
			// Refresh Issued Qty - Actions group
			frm.add_custom_button(
				__('Refresh Issued Qty'),
				() => {
					console.log('[RMT Planning] Refresh Issued Qty button clicked');
					frm.call('refresh_issued_qty').then((r) => {
						console.log('[RMT Planning] refresh_issued_qty completed', { response: r });
						frm.refresh_fields(['rmtp_raw_material', 'total_issued_qty', 'total_pending_qty', 'status']);
					}).catch((err) => {
						console.error('[RMT Planning] Error in refresh_issued_qty:', err);
					});
				},
				__('Actions')
			);
		}
		
		// Add Create button group (standard ERPNext pattern)
		if (frm.doc.docstatus === 1 && frm.doc.status !== 'Cancelled') {
			// Check if there are pending items
			const has_pending = frm.doc.rmtp_raw_material && frm.doc.rmtp_raw_material.some(
				row => (row.pending_qty || 0) > 0
			);
			
			console.log('[RMT Planning] Create button check', {
				has_pending: has_pending,
				can_create: frappe.model.can_create("Raw Material Issuance"),
				docstatus: frm.doc.docstatus
			});
			
			if (has_pending && frappe.model.can_create("Raw Material Issuance")) {
				frm.add_custom_button(
					__('Raw Material Issuance'),
					() => {
						console.log('[RMT Planning] Create Raw Material Issuance button clicked');
						frappe.model.open_mapped_doc({
							method: "manufacturing_addon.manufacturing_addon.doctype.raw_material_transfer_planning.raw_material_transfer_planning.make_raw_material_issuance",
							frm: frm,
							freeze: true,
							freeze_message: __("Creating Raw Material Issuance...")
						}).then(() => {
							console.log('[RMT Planning] Raw Material Issuance created successfully');
						}).catch((err) => {
							console.error('[RMT Planning] Error creating Raw Material Issuance:', err);
						});
					},
					__('Create')
				);
				frm.page.set_inner_btn_group_as_primary(__('Create'));
			}
		}
		
		// Add Create Work Order Transfer Manager button
		// Remove any existing "Create Work Order Transfer Manager" button first
		// Then add new button that creates WOTM using doc.name
		if (frm.doc.docstatus >= 0 && frm.doc.name && frm.doc.status !== 'Cancelled') {
			// Remove existing button if any (by finding and removing it)
			setTimeout(() => {
				const existingBtn = $(document).find('.btn:contains("Create Work Order Transfer Manager")');
				if (existingBtn.length > 0) {
					console.log('[RMT Planning] Removing existing "Create Work Order Transfer Manager" button');
					existingBtn.remove();
				}
			}, 100);
			
			// Add new button
			// frm.add_custom_button(
			// 	__('Work Order Transfer Manager'),
			// 	() => {
			// 		console.log('[RMT Planning] Create Work Order Transfer Manager button clicked', {
			// 			doc_name: frm.doc.name,
			// 			sales_order: frm.doc.sales_order
			// 		});
					
			// 		if (!frm.doc.name) {
			// 			frappe.msgprint(__('Please save the document first.'));
			// 			return;
			// 		}
					
			// 		if (!frm.doc.sales_order) {
			// 			frappe.msgprint(__('Sales Order is required in Raw Material Transfer Planning.'));
			// 			return;
			// 		}
					
			// 		frappe.call({
			// 			method: 'manufacturing_addon.manufacturing_addon.doctype.work_order_transfer_manager.work_order_transfer_manager.create_from_raw_material_transfer_planning',
			// 			args: {
			// 				rmtp_name: frm.doc.name
			// 			},
			// 			freeze: true,
			// 			freeze_message: __('Creating Work Order Transfer Manager...'),
			// 			callback: function(r) {
			// 				if (r.message && r.message.success) {
			// 					frappe.show_alert({
			// 						message: __('WOTM created: ') + r.message.doc_name,
			// 						indicator: 'green'
			// 					}, 5);
			// 					frappe.set_route('Form', 'Work Order Transfer Manager', r.message.doc_name);
			// 				} else {
			// 					frappe.msgprint({
			// 						title: __('Error'),
			// 						message: __('Error creating WOTM: ') + (r.message && r.message.message ? r.message.message : __('Unknown error')),
			// 						indicator: 'red'
			// 					});
			// 				}
			// 			},
			// 			error: function(err) {
			// 				console.error('[RMT Planning] Error creating WOTM:', err);
			// 				frappe.msgprint({
			// 					title: __('Error'),
			// 					message: __('Server error while creating WOTM: ') + (err.message || err),
			// 					indicator: 'red'
			// 				});
			// 			}
			// 		});
			// 	},
			// 	__('Create')
			// );
		}
	},
	
	company(frm) {
		console.log('[RMT Planning] Company changed:', frm.doc.company);
		// Auto-set from/to warehouses based on company if needed
		if (frm.doc.company) {
			// Optional: set default warehouses based on company settings
		}
	},
	
	sales_order(frm) {
		console.log('[RMT Planning] Sales Order changed:', frm.doc.sales_order);
		// Optional: fetch company from sales order
		if (frm.doc.sales_order) {
			frappe.db.get_value('Sales Order', frm.doc.sales_order, 'company', (r) => {
				console.log('[RMT Planning] Fetched company from Sales Order:', r);
				if (r && r.company) {
					frm.set_value('company', r.company);
				}
			});
		}
	}
});
