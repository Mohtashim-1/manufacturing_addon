frappe.pages['order-tracking'].on_page_load = function(wrapper) {
	console.log('[Order Tracking] Page load function called');
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Order Tracking Dashboard',
		single_column: true
	});
	console.log('[Order Tracking] App page created');
	
	// Create dashboard container
	let $container = $(`
		<div class="order-tracking-dashboard" style="padding: 20px;">
			<!-- Header Section -->
			<div class="dashboard-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 10px; margin-bottom: 25px; color: white;">
				<div class="row">
					<div class="col-md-12">
						<h2 style="color: white; margin: 0; font-weight: 600;">
							<i class="fa fa-dashboard"></i> Order Tracking Dashboard
						</h2>
						<p style="color: rgba(255,255,255,0.9); margin: 5px 0 0 0;">Track your manufacturing orders across all stages</p>
					</div>
				</div>
			</div>
			
			<!-- Filters Section -->
			<div class="filters-section" style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
				<div class="row">
					<div class="col-md-3">
						<div id="filter_customer_field"></div>
					</div>
					<div class="col-md-3">
						<div id="filter_sales_order_field"></div>
					</div>
					<div class="col-md-3">
						<div id="filter_order_sheet_field"></div>
					</div>
					<div class="col-md-3">
						<label style="font-weight: 600; font-size: 13px; color: #495057; margin-bottom: 5px;">&nbsp;</label>
						<div>
							<button class="btn btn-primary btn-block mb-2" onclick="loadDashboardData()">
								<i class="fa fa-refresh"></i> Refresh
							</button>
							<button class="btn btn-success btn-block" onclick="triggerDailyOrderSheetEmail()">
								<i class="fa fa-envelope"></i> Send Email Now
							</button>
						</div>
					</div>
				</div>
			</div>
			
			<!-- Summary Cards -->
			<div class="summary-cards row" id="summary-cards" style="margin-bottom: 25px;">
				<!-- Cards will be dynamically generated -->
			</div>
			
			<!-- Progress Overview -->
			<div class="progress-section" style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
				<h4 style="margin-bottom: 20px; color: #495057;">
					<i class="fa fa-line-chart"></i> Production Progress Overview
				</h4>
				<div id="progress-charts" class="row">
					<!-- Charts will be dynamically generated -->
				</div>
			</div>
			
			<!-- Detailed Table -->
			<div class="detailed-table-section" style="background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
				<div class="d-flex justify-content-between align-items-center" style="margin-bottom: 20px;">
					<h4 style="margin: 0; color: #495057;">
						<i class="fa fa-table"></i> Order Details
					</h4>
					<div class="d-flex align-items-center" style="gap: 8px;">
						<button class="btn btn-outline-secondary btn-sm" onclick="expandAllRows()">Expand All</button>
						<button class="btn btn-outline-secondary btn-sm" onclick="collapseAllRows()">Collapse All</button>
						<div style="width: 300px;">
							<input type="text" id="table-search-input" class="form-control" placeholder="Search orders, items, sizes, colors..." style="font-size: 13px;" />
						</div>
					</div>
				</div>
				<div class="table-responsive" style="max-height: 600px; overflow-y: auto;">
					<table class="table table-bordered table-hover table-sm" id="order-details-table" style="font-size: 12px;">
						<thead style="position: sticky; top: 0; background-color: #f8f9fa; z-index: 10;">
							<tr>
								<th>Order Sheet</th>
								<th>Item</th>
								<th>Size</th>
								<th>Color</th>
								<th>Order Qty</th>
								<th>Planned Qty</th>
								<th>PCS</th>
								<th colspan="5" class="text-center bg-info text-white">CUTTING</th>
								<th colspan="5" class="text-center bg-warning text-white">STITCHING</th>
								<th colspan="5" class="text-center bg-success text-white">PACKING</th>
							</tr>
							<tr>
								<th></th>
								<th></th>
								<th></th>
								<th></th>
								<th></th>
								<th></th>
								<th></th>
								<th class="bg-info text-white">Qty</th>
								<th class="bg-info text-white">Finished</th>
								<th class="bg-info text-white">Planned %</th>
								<th class="bg-info text-white">Qty %</th>
								<th class="bg-info text-white">Status</th>
								<th class="bg-warning text-white">Qty</th>
								<th class="bg-warning text-white">Finished</th>
								<th class="bg-warning text-white">Planned %</th>
								<th class="bg-warning text-white">Qty %</th>
								<th class="bg-warning text-white">Status</th>
								<th class="bg-success text-white">Qty</th>
								<th class="bg-success text-white">Finished</th>
								<th class="bg-success text-white">Planned %</th>
								<th class="bg-success text-white">Qty %</th>
								<th class="bg-success text-white">Status</th>
							</tr>
						</thead>
						<tbody id="order-details-body">
							<tr>
								<td colspan="23" class="text-center text-muted" style="padding: 40px;">
									<i class="fa fa-spinner fa-spin fa-2x"></i><br>
									Loading dashboard data...
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</div>
	`);
	
	$(wrapper).append($container);
	console.log('[Order Tracking] Container appended to wrapper');
	
	// Setup table search functionality
	setupTableSearch();
	
	// Initialize link fields - use longer delay to ensure DOM is ready
	setTimeout(function() {
		console.log('[Order Tracking] setTimeout callback executing...');
		console.log('[Order Tracking] Starting initialization...');
		console.log('[Order Tracking] Filter containers exist:', {
			customer: $('#filter_customer_field').length,
			sales_order: $('#filter_sales_order_field').length,
			order_sheet: $('#filter_order_sheet_field').length
		});
		try {
			setupLinkFields();
			console.log('[Order Tracking] setupLinkFields completed');
		} catch(e) {
			console.error('[Order Tracking] Error in setupLinkFields:', e);
		}
		// Auto-load all data on page load
		try {
			loadDashboardData();
			console.log('[Order Tracking] loadDashboardData called');
		} catch(e) {
			console.error('[Order Tracking] Error in loadDashboardData:', e);
		}
	}, 300);
}

function setupLinkFields() {
	console.log('[Order Tracking] setupLinkFields called');
	console.log('[Order Tracking] link_fields_initialized:', window.link_fields_initialized);
	
	// Prevent duplicate initialization
	if (window.link_fields_initialized) {
		console.log('[Order Tracking] Link fields already initialized, skipping...');
		return;
	}
	
	// Remove any existing field instances first
	if (window.customer_field) {
		try {
			if (window.customer_field.$wrapper) window.customer_field.$wrapper.remove();
			if (window.customer_field.$input_area) window.customer_field.$input_area.remove();
			if (window.customer_field.input_area) $(window.customer_field.input_area).remove();
		} catch(e) {}
		window.customer_field = null;
	}
	if (window.sales_order_field) {
		try {
			if (window.sales_order_field.$wrapper) window.sales_order_field.$wrapper.remove();
			if (window.sales_order_field.$input_area) window.sales_order_field.$input_area.remove();
			if (window.sales_order_field.input_area) $(window.sales_order_field.input_area).remove();
		} catch(e) {}
		window.sales_order_field = null;
	}
	if (window.order_sheet_field) {
		try {
			if (window.order_sheet_field.$wrapper) window.order_sheet_field.$wrapper.remove();
			if (window.order_sheet_field.$input_area) window.order_sheet_field.$input_area.remove();
			if (window.order_sheet_field.input_area) $(window.order_sheet_field.input_area).remove();
		} catch(e) {}
		window.order_sheet_field = null;
	}
	
	// Aggressively clear ALL content - remove everything
	console.log('[Order Tracking] Clearing filter containers...');
	$('#filter_customer_field').empty().html('');
	$('#filter_sales_order_field').empty().html('');
	$('#filter_order_sheet_field').empty().html('');
	
	// Remove any and all child elements that might exist
	$('#filter_customer_field').children().remove();
	$('#filter_sales_order_field').children().remove();
	$('#filter_order_sheet_field').children().remove();
	
	// Remove any form groups, inputs, labels, etc.
	$('#filter_customer_field').find('*').remove();
	$('#filter_sales_order_field').find('*').remove();
	$('#filter_order_sheet_field').find('*').remove();
	
	console.log('[Order Tracking] Filter containers cleared. Current children count:', {
		customer: $('#filter_customer_field').children().length,
		sales_order: $('#filter_sales_order_field').children().length,
		order_sheet: $('#filter_order_sheet_field').children().length
	});
	
	// Create Customer Link field with proper label
	let $customer_wrapper = $(`
		<div class="form-group">
			<label style="font-weight: 600; font-size: 13px; color: #495057; margin-bottom: 5px;">Customer</label>
			<div id="customer_link_field"></div>
		</div>
	`).appendTo($('#filter_customer_field'));
	
	window.customer_field = frappe.ui.form.make_control({
		df: {
			fieldtype: 'Link',
			fieldname: 'customer',
			options: 'Customer',
			placeholder: 'Select Customer',
			label: '', // Don't show label as we have custom label above
			change: function() {
				// Clear dependent fields when customer changes
				if (window.sales_order_field) {
					window.sales_order_field.set_value('');
				}
				if (window.order_sheet_field) {
					window.order_sheet_field.set_value('');
				}
			}
		},
		parent: $('#customer_link_field'),
		render_input: true,
		only_input: true
	});
	window.customer_field.make_input();
	
	// Hide any label area created by the control (we have custom label)
	if (window.customer_field.label_area) {
		window.customer_field.label_area.hide();
	}
	if (window.customer_field.$label) {
		window.customer_field.$label.hide();
	}
	
	// Ensure Link field autocomplete is properly initialized
	setTimeout(function() {
		if (window.customer_field && window.customer_field.setup_awesomeplete) {
			window.customer_field.setup_awesomeplete();
		}
	}, 200);
	
	// Create Sales Order Link field with proper label
	let $sales_order_wrapper = $(`
		<div class="form-group">
			<label style="font-weight: 600; font-size: 13px; color: #495057; margin-bottom: 5px;">Sales Order</label>
			<div id="sales_order_link_field"></div>
		</div>
	`).appendTo($('#filter_sales_order_field'));
	
	window.sales_order_field = frappe.ui.form.make_control({
		df: {
			fieldtype: 'Link',
			fieldname: 'sales_order',
			options: 'Sales Order',
			placeholder: 'Select Sales Order',
			label: '', // Don't show label as we have custom label above
			get_query: function() {
				let customer = window.customer_field ? window.customer_field.get_value() : '';
				let filters = { docstatus: ['!=', 2] };
				if (customer) {
					filters.customer = customer;
				}
				return {
					filters: filters
				};
			},
			change: function() {
				// Clear dependent field when sales order changes
				if (window.order_sheet_field) {
					window.order_sheet_field.set_value('');
				}
			}
		},
		parent: $('#sales_order_link_field'),
		render_input: true,
		only_input: true
	});
	window.sales_order_field.make_input();
	
	// Hide and remove any label area created by the control (we have custom label)
	if (window.sales_order_field.label_area) {
		window.sales_order_field.label_area.hide().remove();
	}
	if (window.sales_order_field.$label) {
		window.sales_order_field.$label.hide().remove();
	}
	
	// Remove any duplicate label elements - but keep our form-group label
	setTimeout(function() {
		// Only remove labels that are NOT inside our form-group
		$('#filter_sales_order_field').find('label').filter(function() {
			return !$(this).closest('.form-group').length;
		}).remove();
		
		// Check for duplicate input fields - but keep Link field inputs
		const salesOrderInputs = $('#filter_sales_order_field input[type="text"]');
		const linkInputs = $('#filter_sales_order_field .link-field input[type="text"]');
		if (salesOrderInputs.length > linkInputs.length) {
			console.log('[Order Tracking] Found', salesOrderInputs.length - linkInputs.length, 'non-Link sales order inputs, removing');
			salesOrderInputs.filter(function() {
				return !$(this).closest('.link-field').length;
			}).closest('.form-group, .input-group').remove();
		}
	}, 100);
	
	// Ensure Link field autocomplete is properly initialized
	setTimeout(function() {
		if (window.sales_order_field && window.sales_order_field.setup_awesomeplete) {
			window.sales_order_field.setup_awesomeplete();
		}
	}, 200);
	
	// Create Order Sheet Link field with proper label
	let $order_sheet_wrapper = $(`
		<div class="form-group">
			<label style="font-weight: 600; font-size: 13px; color: #495057; margin-bottom: 5px;">Order Sheet</label>
			<div id="order_sheet_link_field"></div>
		</div>
	`).appendTo($('#filter_order_sheet_field'));
	
	window.order_sheet_field = frappe.ui.form.make_control({
		df: {
			fieldtype: 'Link',
			fieldname: 'order_sheet',
			options: 'Order Sheet',
			placeholder: 'Select Order Sheet',
			label: '', // Don't show label as we have custom label above
			get_query: function() {
				let salesOrder = window.sales_order_field ? window.sales_order_field.get_value() : '';
				let filters = {};
				if (salesOrder) {
					filters.sales_order = salesOrder;
				}
				return {
					filters: filters
				};
			}
		},
		parent: $('#order_sheet_link_field'),
		render_input: true,
		only_input: true
	});
	window.order_sheet_field.make_input();
	
	// Hide and remove any label area created by the control (we have custom label)
	if (window.order_sheet_field.label_area) {
		window.order_sheet_field.label_area.hide().remove();
	}
	if (window.order_sheet_field.$label) {
		window.order_sheet_field.$label.hide().remove();
	}
	
	// Remove any duplicate label elements - but keep our form-group label
	setTimeout(function() {
		// Only remove labels that are NOT inside our form-group
		$('#filter_order_sheet_field').find('label').filter(function() {
			return !$(this).closest('.form-group').length;
		}).remove();
		
		// Check for duplicate input fields - but keep Link field inputs
		const orderSheetInputs = $('#filter_order_sheet_field input[type="text"]');
		const linkInputs = $('#filter_order_sheet_field .link-field input[type="text"]');
		if (orderSheetInputs.length > linkInputs.length) {
			console.log('[Order Tracking] Found', orderSheetInputs.length - linkInputs.length, 'non-Link order sheet inputs, removing');
			orderSheetInputs.filter(function() {
				return !$(this).closest('.link-field').length;
			}).closest('.form-group, .input-group').remove();
		}
	}, 100);
	
	// Ensure Link field autocomplete is properly initialized
	setTimeout(function() {
		if (window.order_sheet_field && window.order_sheet_field.setup_awesomeplete) {
			window.order_sheet_field.setup_awesomeplete();
		}
	}, 200);
	
	// Mark as initialized
	window.link_fields_initialized = true;
	
	// Final cleanup - remove any remaining duplicates after a short delay
	setTimeout(function() {
		console.log('[Order Tracking] Performing final duplicate cleanup...');
		
		// Check each filter container and ensure only one form-group exists
		['customer', 'sales_order', 'order_sheet'].forEach(function(fieldType) {
			const container = $('#filter_' + fieldType + '_field');
			const formGroups = container.children('.form-group');
			
			console.log('[Order Tracking]', fieldType, '- Found', formGroups.length, 'form-groups');
			
			if (formGroups.length > 1) {
				// Find the form-group that contains our Link field (has .link-field inside)
				const linkFormGroups = formGroups.filter(function() {
					return $(this).find('.link-field').length > 0;
				});
				
				if (linkFormGroups.length > 0) {
					console.log('[Order Tracking]', fieldType, '- Found', linkFormGroups.length, 'Link field form-group(s)');
					// Keep only the first Link field form-group, remove all others
					if (linkFormGroups.length > 1) {
						linkFormGroups.slice(1).remove();
					}
					// Remove all form-groups that don't contain a Link field
					formGroups.filter(function() {
						return $(this).find('.link-field').length === 0;
					}).remove();
				} else {
					console.log('[Order Tracking]', fieldType, '- No Link field found, keeping first form-group');
					// Fallback: keep first, remove rest
					formGroups.slice(1).remove();
				}
			}
			
			// Double-check: if still more than one form-group, force removal
			const remainingFormGroups = container.children('.form-group');
			if (remainingFormGroups.length > 1) {
				console.log('[Order Tracking]', fieldType, '- Still', remainingFormGroups.length, 'form-groups after cleanup, forcing removal');
				
				// Find form-groups with Link field
				const linkFormGroups = remainingFormGroups.filter(function() {
					return $(this).find('.link-field').length > 0;
				});
				
				if (linkFormGroups.length > 0) {
					console.log('[Order Tracking]', fieldType, '- Found', linkFormGroups.length, 'Link field form-group(s), keeping first, removing', remainingFormGroups.length - 1, 'others');
					// Keep only the FIRST Link field form-group, remove ALL others
					const keepThis = linkFormGroups.first();
					remainingFormGroups.not(keepThis).remove();
				} else {
					console.log('[Order Tracking]', fieldType, '- No Link field found, keeping first form-group, removing', remainingFormGroups.length - 1, 'others');
					// No Link field found, keep first and remove rest
					remainingFormGroups.slice(1).remove();
				}
				
				// Final verification - force to only one
				const finalCount = container.children('.form-group').length;
				if (finalCount > 1) {
					console.log('[Order Tracking]', fieldType, '- WARNING: Still', finalCount, 'form-groups after all cleanup! Forcing to keep only first');
					const firstWithLink = container.children('.form-group').filter(function() {
						return $(this).find('.link-field').length > 0;
					}).first();
					
					if (firstWithLink.length > 0) {
						container.children('.form-group').not(firstWithLink).remove();
					} else {
						container.children('.form-group').slice(1).remove();
					}
				}
			}
		});
		
		console.log('[Order Tracking] Final cleanup complete');
		console.log('[Order Tracking] Final state (direct children):', {
			customer: $('#filter_customer_field').children('.form-group').length,
			sales_order: $('#filter_sales_order_field').children('.form-group').length,
			order_sheet: $('#filter_order_sheet_field').children('.form-group').length
		});
		
		// Force final cleanup - if still duplicates, remove all except first
		['customer', 'sales_order', 'order_sheet'].forEach(function(fieldType) {
			const container = $('#filter_' + fieldType + '_field');
			const finalFormGroups = container.children('.form-group');
			if (finalFormGroups.length > 1) {
				console.log('[Order Tracking] FINAL FIX:', fieldType, '- Force removing', finalFormGroups.length - 1, 'duplicate form-groups');
				// Find one with Link field, or just keep first
				const withLink = finalFormGroups.filter(function() {
					return $(this).find('.link-field').length > 0;
				}).first();
				
				if (withLink.length > 0) {
					finalFormGroups.not(withLink).remove();
				} else {
					finalFormGroups.slice(1).remove();
				}
			}
		});
		
		console.log('[Order Tracking] After final fix:', {
			customer: $('#filter_customer_field').children('.form-group').length,
			sales_order: $('#filter_sales_order_field').children('.form-group').length,
			order_sheet: $('#filter_order_sheet_field').children('.form-group').length
		});

		// Ensure each filter has only one visible text input.
		enforceSingleVisibleInput('#filter_customer_field');
		enforceSingleVisibleInput('#filter_sales_order_field');
		enforceSingleVisibleInput('#filter_order_sheet_field');
	}, 500);
}

function enforceSingleVisibleInput(containerSelector) {
	const $container = $(containerSelector);
	const $inputs = $container.find('input[type="text"]:visible');
	if ($inputs.length <= 1) return;

	// Keep the first visible input, remove the rest safely.
	$inputs.slice(1).each(function() {
		const $input = $(this);
		const $removeTarget = $input.closest('.link-field, .control-input-wrapper, .form-group, .frappe-control');
		if ($removeTarget.length) {
			$removeTarget.remove();
		} else {
			$input.remove();
		}
	});
}

function loadDashboardData() {
	// Get values from Link fields if they exist, otherwise use empty values
	let customer = null;
	let salesOrder = null;
	let orderSheet = null;
	
	if (window.customer_field) {
		customer = window.customer_field.get_value();
	}
	if (window.sales_order_field) {
		salesOrder = window.sales_order_field.get_value();
	}
	if (window.order_sheet_field) {
		orderSheet = window.order_sheet_field.get_value();
	}
	
	// If no filter is selected, show all data (pass null values)
	frappe.call({
		method: 'manufacturing_addon.manufacturing_addon.page.order_tracking.order_tracking.get_dashboard_data',
		args: {
			customer: customer || null,
			sales_order: salesOrder || null,
			order_sheet: orderSheet || null
		},
		freeze: true,
		freeze_message: __('Loading dashboard data...'),
		callback: function(r) {
			if (r.message) {
				renderDashboard(r.message);
			}
		},
		error: function(r) {
			frappe.msgprint({
				message: __('Error loading dashboard data'),
				indicator: 'red',
				title: __('Error')
			});
		}
	});
}

function triggerDailyOrderSheetEmail() {
	frappe.confirm(
		__('Send daily active order-sheet email now? This will send the report with previous-day data only.'),
		function() {
			frappe.call({
				method: 'manufacturing_addon.manufacturing_addon.daily_order_sheet_email.trigger_daily_active_order_sheet_email',
				freeze: true,
				freeze_message: __('Sending order-sheet email...'),
				callback: function(r) {
					frappe.msgprint({
						title: __('Email Queued'),
						indicator: 'green',
						message: __(r.message || 'Daily active order-sheet email has been queued.')
					});
				},
				error: function() {
					frappe.msgprint({
						title: __('Error'),
						indicator: 'red',
						message: __('Unable to send email. Please check permissions and email queue.')
					});
				}
			});
		}
	);
}

function renderDashboard(data) {
	// Render Summary Cards
	renderSummaryCards(data.summary || {});
	
	// Render Progress Charts
	renderProgressCharts(data.summary || {});
	
	// Render Detailed Table
	renderDetailedTable(data.details || []);
}

function renderSummaryCards(summary) {
	const cardsHtml = `
		<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
			<div class="card text-white" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border: none; border-radius: 10px;">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-center">
						<div>
							<h6 class="card-subtitle mb-2" style="opacity: 0.9;">Total Orders</h6>
							<h2 class="mb-0" style="font-weight: 700;">${summary.total_orders || 0}</h2>
						</div>
						<div style="font-size: 40px; opacity: 0.5;">
							<i class="fa fa-file-text"></i>
						</div>
					</div>
				</div>
			</div>
		</div>
		<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
			<div class="card text-white" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border: none; border-radius: 10px;">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-center">
						<div>
							<h6 class="card-subtitle mb-2" style="opacity: 0.9;">Total Order Qty</h6>
							<h2 class="mb-0" style="font-weight: 700;">${formatNumber(summary.total_order_qty || 0)}</h2>
						</div>
						<div style="font-size: 40px; opacity: 0.5;">
							<i class="fa fa-cubes"></i>
						</div>
					</div>
				</div>
			</div>
		</div>
		<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
			<div class="card text-white" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border: none; border-radius: 10px;">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-center">
						<div>
							<h6 class="card-subtitle mb-2" style="opacity: 0.9;">Cutting Progress</h6>
							<h2 class="mb-0" style="font-weight: 700;">${formatPercentage(summary.cutting_progress || 0)}%</h2>
						</div>
						<div style="font-size: 40px; opacity: 0.5;">
							<i class="fa fa-scissors"></i>
						</div>
					</div>
				</div>
			</div>
		</div>
		<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
			<div class="card text-white" style="background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); border: none; border-radius: 10px;">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-center">
						<div>
							<h6 class="card-subtitle mb-2" style="opacity: 0.9;">Stitching Progress</h6>
							<h2 class="mb-0" style="font-weight: 700;">${formatPercentage(summary.stitching_progress || 0)}%</h2>
						</div>
						<div style="font-size: 40px; opacity: 0.5;">
							<i class="fa fa-cogs"></i>
						</div>
					</div>
				</div>
			</div>
		</div>
		<div class="col-lg-2 col-md-4 col-sm-6 mb-3">
			<div class="card text-white" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); border: none; border-radius: 10px;">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-center">
						<div>
							<h6 class="card-subtitle mb-2" style="opacity: 0.9;">Packing Progress</h6>
							<h2 class="mb-0" style="font-weight: 700;">${formatPercentage(summary.packing_progress || 0)}%</h2>
						</div>
						<div style="font-size: 40px; opacity: 0.5;">
							<i class="fa fa-archive"></i>
						</div>
					</div>
				</div>
			</div>
		</div>
	`;
	
	$('#summary-cards').html(cardsHtml);
}

function renderProgressCharts(summary) {
	const chartsHtml = `
		<div class="col-md-6 mb-3">
			<div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
				<h6 style="color: #495057; margin-bottom: 15px;">Cutting Progress</h6>
				<div class="progress" style="height: 30px; border-radius: 15px;">
					<div class="progress-bar bg-info" role="progressbar" 
						style="width: ${summary.cutting_progress || 0}%; line-height: 30px; font-weight: 600;">
						${formatPercentage(summary.cutting_progress || 0)}%
					</div>
				</div>
				<div class="mt-2" style="font-size: 12px; color: #6c757d;">
					Finished: ${formatNumber(summary.cutting_finished || 0)} / Planned: ${formatNumber(summary.cutting_planned || 0)}
				</div>
			</div>
		</div>
		<div class="col-md-6 mb-3">
			<div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
				<h6 style="color: #495057; margin-bottom: 15px;">Stitching Progress</h6>
				<div class="progress" style="height: 30px; border-radius: 15px;">
					<div class="progress-bar bg-warning" role="progressbar" 
						style="width: ${summary.stitching_progress || 0}%; line-height: 30px; font-weight: 600;">
						${formatPercentage(summary.stitching_progress || 0)}%
					</div>
				</div>
				<div class="mt-2" style="font-size: 12px; color: #6c757d;">
					Finished: ${formatNumber(summary.stitching_finished || 0)} / Planned: ${formatNumber(summary.stitching_planned || 0)}
				</div>
			</div>
		</div>
		<div class="col-md-6 mb-3">
			<div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
				<h6 style="color: #495057; margin-bottom: 15px;">Packing Progress</h6>
				<div class="progress" style="height: 30px; border-radius: 15px;">
					<div class="progress-bar bg-success" role="progressbar" 
						style="width: ${summary.packing_progress || 0}%; line-height: 30px; font-weight: 600;">
						${formatPercentage(summary.packing_progress || 0)}%
					</div>
				</div>
				<div class="mt-2" style="font-size: 12px; color: #6c757d;">
					Finished: ${formatNumber(summary.packing_finished || 0)} / Planned: ${formatNumber(summary.packing_planned || 0)}
				</div>
			</div>
		</div>
		<div class="col-md-6 mb-3">
			<div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px;">
				<h6 style="color: #495057; margin-bottom: 15px;">Overall Progress</h6>
				<div class="progress" style="height: 30px; border-radius: 15px;">
					<div class="progress-bar" role="progressbar" 
						style="width: ${summary.overall_progress || 0}%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); line-height: 30px; font-weight: 600;">
						${formatPercentage(summary.overall_progress || 0)}%
					</div>
				</div>
				<div class="mt-2" style="font-size: 12px; color: #6c757d;">
					Complete: ${formatNumber(summary.packing_finished_finished_items || summary.packing_finished || 0)} / Total: ${formatNumber(summary.total_order_qty || 0)}
				</div>
			</div>
		</div>
	`;
	
	$('#progress-charts').html(chartsHtml);
}

// Store original details for search filtering
let originalTableDetails = [];

function setupTableSearch() {
	// Setup search input handler
	$(document).on('keyup', '#table-search-input', function() {
		const searchTerm = $(this).val().toLowerCase();
		filterTableRows(searchTerm);
	});

	// Parent row expand/collapse handler
	$(document).on('click', '.os-parent-toggle', function() {
		const $toggle = $(this);
		const groupKey = $toggle.attr('data-group');
		const isExpanded = $toggle.attr('data-expanded') === '1';
		const $children = getChildRowsByGroup(groupKey);

		if (isExpanded) {
			$children.hide();
			$toggle.attr('data-expanded', '0').find('.os-toggle-icon').text('▸');
		} else {
			$children.show();
			$toggle.attr('data-expanded', '1').find('.os-toggle-icon').text('▾');
		}
	});
}

function filterTableRows(searchTerm) {
	const rows = $('#order-details-body tr').not('.no-results');
	
	if (!searchTerm || searchTerm.trim() === '') {
		$('#order-details-body tr.no-results').remove();
		// Restore default collapsed state when search is cleared
		rows.show();
		applyDefaultCollapsedState();
		return;
	}
	
	let visibleCount = 0;
	rows.hide();

	rows.each(function() {
		const $row = $(this);
		const rowText = $row.text().toLowerCase();
		
		// Show row if search term matches any text in the row
		if (rowText.includes(searchTerm)) {
			$row.show();
			visibleCount++;

			// If child matched, show parent and keep group expanded
			if ($row.hasClass('os-child-row')) {
				const groupKey = $row.attr('data-parent-group');
				const $parent = getParentRowByGroup(groupKey);
				$parent.show();
				setGroupExpanded(groupKey, true);
			}

			// If parent matched, show all its children for quick review
			if ($row.hasClass('os-parent-row')) {
				const groupKey = $row.attr('data-parent-group');
				const $children = getChildRowsByGroup(groupKey);
				$children.show();
				visibleCount += $children.length;
				setGroupExpanded(groupKey, true);
			}
		} else {
			$row.hide();
		}
	});
	
	// Show message if no results
	if (visibleCount === 0) {
		const tbody = $('#order-details-body');
		if (tbody.find('tr.no-results').length === 0) {
			tbody.append(`
				<tr class="no-results">
					<td colspan="23" class="text-center text-muted" style="padding: 40px;">
						<i class="fa fa-search fa-2x"></i><br>
						No results found for "${searchTerm}"
					</td>
				</tr>
			`);
		}
	} else {
		$('#order-details-body tr.no-results').remove();
	}
}

function applyDefaultCollapsedState() {
	$('tr.os-child-row').hide();
	$('.os-parent-toggle').attr('data-expanded', '0');
	$('.os-parent-toggle .os-toggle-icon').text('▸');
}

function setGroupExpanded(groupKey, expanded) {
	const $parentToggle = $(`.os-parent-toggle[data-group="${groupKey}"]`);
	if (!$parentToggle.length) return;
	$parentToggle.attr('data-expanded', expanded ? '1' : '0');
	$parentToggle.find('.os-toggle-icon').text(expanded ? '▾' : '▸');
}

function getChildRowsByGroup(groupKey) {
	return $('tr.os-child-row').filter(function() {
		return $(this).attr('data-parent-group') === groupKey;
	});
}

function getParentRowByGroup(groupKey) {
	return $('tr.os-parent-row').filter(function() {
		return $(this).attr('data-parent-group') === groupKey;
	});
}

function expandAllRows() {
	$('tr.os-child-row').show();
	$('.os-parent-toggle').attr('data-expanded', '1');
	$('.os-parent-toggle .os-toggle-icon').text('▾');
}

function collapseAllRows() {
	applyDefaultCollapsedState();
}

function renderDetailedTable(details) {
	// Store original details for potential future use
	originalTableDetails = details;
	
	const tbody = $('#order-details-body');
	tbody.empty();
	
	// Clear search input when table is re-rendered
	$('#table-search-input').val('');
	
	if (details.length === 0) {
		tbody.append(`
			<tr>
				<td colspan="23" class="text-center text-muted" style="padding: 40px;">
					<i class="fa fa-info-circle fa-2x"></i><br>
					No data found for the selected filters
				</td>
			</tr>
		`);
		return;
	}
	
	// Build a map of parent order_qty for bundle items
	const parentOrderQtyMap = {};
	const childCountMap = {};
	const childAggregates = {};
	details.forEach(function(row) {
		if (row.is_parent === true) {
			// Store parent's order_qty keyed by order_sheet and item
			const key = `${row.order_sheet}||${row.item}`;
			parentOrderQtyMap[key] = row.order_qty || 0;
			if (!childCountMap[key]) {
				childCountMap[key] = 0;
			}
		} else if (row.bundle_item && row.bundle_item !== null) {
			const parentKey = `${row.order_sheet}||${row.item}`;
			childCountMap[parentKey] = (childCountMap[parentKey] || 0) + 1;
			if (!childAggregates[parentKey]) {
				childAggregates[parentKey] = {
					cutting_qty: 0,
					cutting_finished: 0,
					cutting_planned: 0,
					cutting_normalized_finished: 0,
					stitching_qty: 0,
					stitching_finished: 0,
					stitching_planned: 0,
					stitching_normalized_finished: 0
				};
			}
			childAggregates[parentKey].cutting_qty += (row.cutting_qty || 0);
			childAggregates[parentKey].cutting_finished += (row.cutting_finished || 0);
			childAggregates[parentKey].cutting_planned += (row.cutting_planned || 0);
			childAggregates[parentKey].cutting_normalized_finished += (row.cutting_finished || 0) / ((row.pcs || 1) || 1);
			childAggregates[parentKey].stitching_qty += (row.stitching_qty || 0);
			childAggregates[parentKey].stitching_finished += (row.stitching_finished || 0);
			childAggregates[parentKey].stitching_planned += (row.stitching_planned || 0);
			childAggregates[parentKey].stitching_normalized_finished += (row.stitching_finished || 0) / ((row.pcs || 1) || 1);
		}
	});
	
	details.forEach(function(row) {
		// Calculate percentages based on finished qty vs order qty
		// Allow percentages above 100% if finished exceeds order qty
		// For bundle items, use parent's order_qty
		let orderQty = row.order_qty || 0;
		const parentKey = `${row.order_sheet}||${row.item}`;
		const parentAgg = childAggregates[parentKey] || null;
		// Determine if this is a parent row (finished item) or child row (bundle item)
		const isParent = row.is_parent === true;
		const isBundleItem = row.bundle_item && row.bundle_item !== null;

		if (row.bundle_item && row.bundle_item !== null) {
			// For bundle items, get parent's order_qty
			orderQty = parentOrderQtyMap[parentKey] || 0;
		}

		let displayCuttingQty = row.cutting_qty || 0;
		let displayCuttingFinished = row.cutting_finished || 0;
		let displayCuttingPlanned = row.cutting_planned || 0;
		let displayStitchingQty = row.stitching_qty || 0;
		let displayStitchingFinished = row.stitching_finished || 0;
		let displayStitchingPlanned = row.stitching_planned || 0;

		// Parent row should show summed child values for cutting/stitching
		if (isParent && parentAgg) {
			displayCuttingQty = parentAgg.cutting_qty;
			displayCuttingFinished = parentAgg.cutting_finished;
			displayCuttingPlanned = parentAgg.cutting_planned || displayCuttingPlanned;
			displayStitchingQty = parentAgg.stitching_qty;
			displayStitchingFinished = parentAgg.stitching_finished;
			displayStitchingPlanned = parentAgg.stitching_planned || displayStitchingPlanned;
		}
		
		// Percentage rule:
		// Cutting/Stitching base qty = Finished / PCS
		// Planned % = base qty / planned qty
		// Qty % = base qty / order qty
		const rowPcs = row.pcs || 1;
		const cuttingBaseQty = isParent && parentAgg
			? parentAgg.cutting_normalized_finished
			: (displayCuttingFinished / (rowPcs || 1));
		const stitchingBaseQty = isParent && parentAgg
			? parentAgg.stitching_normalized_finished
			: (displayStitchingFinished / (rowPcs || 1));
		const packingBaseQty = row.packing_finished || 0;

		const cuttingPlannedQty = isParent
			? (row.planned_qty || displayCuttingPlanned || 0)
			: (row.cutting_planned || row.planned_qty || 0);
		const stitchingPlannedQty = isParent
			? (row.planned_qty || displayStitchingPlanned || 0)
			: (row.stitching_planned || row.planned_qty || 0);
		const packingPlannedQty = row.planned_qty || row.packing_planned || 0;

		const cuttingPlannedPercent = cuttingPlannedQty > 0 ? (cuttingBaseQty / cuttingPlannedQty * 100) : 0;
		const cuttingQtyPercent = orderQty > 0 ? (cuttingBaseQty / orderQty * 100) : 0;
		const stitchingPlannedPercent = stitchingPlannedQty > 0 ? (stitchingBaseQty / stitchingPlannedQty * 100) : 0;
		const stitchingQtyPercent = orderQty > 0 ? (stitchingBaseQty / orderQty * 100) : 0;
		const packingPlannedPercent = packingPlannedQty > 0 ? (packingBaseQty / packingPlannedQty * 100) : 0;
		const packingQtyPercent = orderQty > 0 ? (packingBaseQty / orderQty * 100) : 0;

		const cuttingStatus = getStatusBadge(cuttingQtyPercent);
		const stitchingStatus = getStatusBadge(stitchingQtyPercent);
		const packingStatus = getStatusBadge(packingQtyPercent);
		
		// Style for parent vs child rows
		let rowClass = '';
		let rowStyle = '';
		if (isParent) {
			rowClass = 'font-weight-bold';
			rowStyle = 'background-color: #f8f9fa;';
		} else if (isBundleItem) {
			rowStyle = 'background-color: #ffffff; padding-left: 30px;';
		}
		
		// Display item name - show bundle item name if it's a bundle item
		let displayItem = row.item || '';
		const rowGroupKey = `${row.order_sheet}||${row.item}`;
		const hasChildren = isParent && (childCountMap[rowGroupKey] || 0) > 0;

		if (isBundleItem) {
			displayItem = `  └─ ${row.bundle_item || ''}`;
		} else if (hasChildren) {
			displayItem = `
				<span class="os-parent-toggle" data-group="${rowGroupKey}" data-expanded="0" style="cursor: pointer; user-select: none;">
					<span class="os-toggle-icon">▸</span> ${displayItem}
				</span>
			`;
		}
		
		const tr = $(`
			<tr class="${rowClass} ${isBundleItem ? 'os-child-row' : 'os-parent-row'}"
				data-parent-group="${rowGroupKey}"
				style="${rowStyle}${isBundleItem ? 'display: none;' : ''}">
				<td>${isBundleItem ? '' : (row.order_sheet || '')}</td>
				<td>${displayItem}</td>
				<td>${isBundleItem ? '' : (row.size || '')}</td>
				<td>${isBundleItem ? '' : (row.color || '')}</td>
				<td class="text-right">${isBundleItem ? '' : formatNumber(row.order_qty || 0)}</td>
				<td class="text-right">${isBundleItem ? '' : formatNumber(row.planned_qty || 0)}</td>
				<td class="text-right">${formatNumber(row.pcs || 0)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-info text-white'}">${formatNumber(displayCuttingQty)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-info text-white'}">${formatNumber(displayCuttingFinished)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-info text-white'}">${formatPercentage(cuttingPlannedPercent)}%</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-info text-white'}">${formatPercentage(cuttingQtyPercent)}%</td>
				<td class="text-center ${isBundleItem ? '' : 'bg-info text-white'}">${cuttingStatus}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-warning text-white'}">${formatNumber(displayStitchingQty)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-warning text-white'}">${formatNumber(displayStitchingFinished)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-warning text-white'}">${formatPercentage(stitchingPlannedPercent)}%</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-warning text-white'}">${formatPercentage(stitchingQtyPercent)}%</td>
				<td class="text-center ${isBundleItem ? '' : 'bg-warning text-white'}">${stitchingStatus}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-success text-white'}">${isBundleItem ? '-' : formatNumber(row.packing_qty || 0)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-success text-white'}">${isBundleItem ? '-' : formatNumber(row.packing_finished || 0)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-success text-white'}">${isBundleItem ? '-' : formatPercentage(packingPlannedPercent) + '%'}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-success text-white'}">${isBundleItem ? '-' : formatPercentage(packingQtyPercent) + '%'}</td>
				<td class="text-center ${isBundleItem ? '' : 'bg-success text-white'}">${isBundleItem ? '-' : packingStatus}</td>
			</tr>
		`);
		tbody.append(tr);
	});

	applyDefaultCollapsedState();
}

function getStatusBadge(percent) {
	if (percent >= 100) {
		// Show "Over Complete" or "Complete" based on percentage
		if (percent > 100) {
			return '<span class="badge badge-success" style="background-color: #28a745;">Complete (' + formatPercentage(percent) + '%)</span>';
		}
		return '<span class="badge badge-success">Complete</span>';
	} else if (percent >= 75) {
		return '<span class="badge badge-info">In Progress</span>';
	} else if (percent > 0) {
		return '<span class="badge badge-warning">Started</span>';
	} else {
		return '<span class="badge badge-secondary">Not Started</span>';
	}
}

function formatNumber(num) {
	if (num == null || num === '') return '0';
	return parseFloat(num).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function formatPercentage(num) {
	if (num == null || num === '') return '0';
	return parseFloat(num).toFixed(1);
}
