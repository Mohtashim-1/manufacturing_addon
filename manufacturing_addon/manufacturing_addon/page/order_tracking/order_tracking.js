frappe.pages['order-tracking'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Order Tracking Dashboard',
		single_column: true
	});
	
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
						<label style="font-weight: 600; font-size: 13px; color: #495057; margin-bottom: 5px;">Customer</label>
						<div class="input-group">
							<input type="text" id="filter_customer" class="form-control" placeholder="Select Customer" />
							<div class="input-group-append">
								<button class="btn btn-sm btn-secondary" type="button" onclick="selectCustomer()" title="Select Customer">
									<i class="fa fa-search"></i>
								</button>
							</div>
						</div>
					</div>
					<div class="col-md-3">
						<label style="font-weight: 600; font-size: 13px; color: #495057; margin-bottom: 5px;">Sales Order</label>
						<div class="input-group">
							<input type="text" id="filter_sales_order" class="form-control" placeholder="Select Sales Order" />
							<div class="input-group-append">
								<button class="btn btn-sm btn-secondary" type="button" onclick="selectSalesOrder()" title="Select Sales Order">
									<i class="fa fa-search"></i>
								</button>
							</div>
						</div>
					</div>
					<div class="col-md-3">
						<label style="font-weight: 600; font-size: 13px; color: #495057; margin-bottom: 5px;">Order Sheet</label>
						<div class="input-group">
							<input type="text" id="filter_order_sheet" class="form-control" placeholder="Select Order Sheet" />
							<div class="input-group-append">
								<button class="btn btn-sm btn-secondary" type="button" onclick="selectOrderSheet()" title="Select Order Sheet">
									<i class="fa fa-search"></i>
								</button>
							</div>
						</div>
					</div>
					<div class="col-md-3">
						<label style="font-weight: 600; font-size: 13px; color: #495057; margin-bottom: 5px;">&nbsp;</label>
						<div>
							<button class="btn btn-primary btn-block" onclick="loadDashboardData()">
								<i class="fa fa-refresh"></i> Load Dashboard
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
				<h4 style="margin-bottom: 20px; color: #495057;">
					<i class="fa fa-table"></i> Order Details
				</h4>
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
								<th colspan="4" class="text-center bg-info text-white">CUTTING</th>
								<th colspan="4" class="text-center bg-warning text-white">STITCHING</th>
								<th colspan="4" class="text-center bg-success text-white">PACKING</th>
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
								<th class="bg-info text-white">%</th>
								<th class="bg-info text-white">Status</th>
								<th class="bg-warning text-white">Qty</th>
								<th class="bg-warning text-white">Finished</th>
								<th class="bg-warning text-white">%</th>
								<th class="bg-warning text-white">Status</th>
								<th class="bg-success text-white">Qty</th>
								<th class="bg-success text-white">Finished</th>
								<th class="bg-success text-white">%</th>
								<th class="bg-success text-white">Status</th>
							</tr>
						</thead>
						<tbody id="order-details-body">
							<tr>
								<td colspan="20" class="text-center text-muted" style="padding: 40px;">
									<i class="fa fa-info-circle fa-2x"></i><br>
									Select filters and click "Load Dashboard" to view data
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</div>
	`);
	
	$(wrapper).append($container);
	
	// Initialize link fields
	setTimeout(function() {
		setupLinkFields();
	}, 100);
}

function setupLinkFields() {
	// Clear dependent fields when parent changes
	$('#filter_customer').on('change', function() {
		$('#filter_sales_order').val('');
		$('#filter_order_sheet').val('');
	});
	
	$('#filter_sales_order').on('change', function() {
		$('#filter_order_sheet').val('');
	});
}

function selectCustomer() {
	frappe.prompt([
		{
			fieldtype: 'Link',
			fieldname: 'customer',
			label: 'Customer',
			options: 'Customer',
			reqd: 0
		}
	], function(values) {
		if (values.customer) {
			$('#filter_customer').val(values.customer);
		}
	}, 'Select Customer');
}

function selectSalesOrder() {
	let customer = $('#filter_customer').val();
	let filters = { docstatus: ['!=', 2] };
	if (customer) {
		filters.customer = customer;
	}
	
	frappe.prompt([
		{
			fieldtype: 'Link',
			fieldname: 'sales_order',
			label: 'Sales Order',
			options: 'Sales Order',
			get_query: function() {
				return {
					filters: filters
				};
			},
			reqd: 0
		}
	], function(values) {
		if (values.sales_order) {
			$('#filter_sales_order').val(values.sales_order);
		}
	}, 'Select Sales Order');
}

function selectOrderSheet() {
	let salesOrder = $('#filter_sales_order').val();
	let filters = {};
	if (salesOrder) {
		filters.sales_order = salesOrder;
	}
	
	frappe.prompt([
		{
			fieldtype: 'Link',
			fieldname: 'order_sheet',
			label: 'Order Sheet',
			options: 'Order Sheet',
			get_query: function() {
				return {
					filters: filters
				};
			},
			reqd: 0
		}
	], function(values) {
		if (values.order_sheet) {
			$('#filter_order_sheet').val(values.order_sheet);
		}
	}, 'Select Order Sheet');
}

function loadDashboardData() {
	let customer = $('#filter_customer').val();
	let salesOrder = $('#filter_sales_order').val();
	let orderSheet = $('#filter_order_sheet').val();
	
	if (!customer && !salesOrder && !orderSheet) {
		frappe.msgprint({
			message: __('Please select at least one filter (Customer, Sales Order, or Order Sheet)'),
			indicator: 'orange',
			title: __('Filter Required')
		});
		return;
	}
	
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
		<div class="col-md-3 mb-3">
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
		<div class="col-md-3 mb-3">
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
		<div class="col-md-3 mb-3">
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
		<div class="col-md-3 mb-3">
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

function renderDetailedTable(details) {
	const tbody = $('#order-details-body');
	tbody.empty();
	
	if (details.length === 0) {
		tbody.append(`
			<tr>
				<td colspan="20" class="text-center text-muted" style="padding: 40px;">
					<i class="fa fa-info-circle fa-2x"></i><br>
					No data found for the selected filters
				</td>
			</tr>
		`);
		return;
	}
	
	details.forEach(function(row) {
		// Calculate percentages based on actual qty vs finished qty (not planned)
		// If qty > 0, percentage = (finished / qty) * 100
		// If qty == 0, check if there's planned qty to show progress
		const cuttingPercent = row.cutting_qty > 0 ? (row.cutting_finished / row.cutting_qty * 100) : (row.cutting_planned > 0 ? (row.cutting_finished / row.cutting_planned * 100) : 0);
		const stitchingPercent = row.stitching_qty > 0 ? (row.stitching_finished / row.stitching_qty * 100) : (row.stitching_planned > 0 ? (row.stitching_finished / row.stitching_planned * 100) : 0);
		const packingPercent = row.packing_qty > 0 ? (row.packing_finished / row.packing_qty * 100) : (row.packing_planned > 0 ? (row.packing_finished / row.packing_planned * 100) : 0);
		
		const cuttingStatus = getStatusBadge(cuttingPercent);
		const stitchingStatus = getStatusBadge(stitchingPercent);
		const packingStatus = getStatusBadge(packingPercent);
		
		// Determine if this is a parent row (finished item) or child row (bundle item)
		const isParent = row.is_parent === true;
		const isBundleItem = row.bundle_item && row.bundle_item !== null;
		
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
		if (isBundleItem) {
			displayItem = `  └─ ${row.bundle_item || ''}`;
		}
		
		const tr = $(`
			<tr class="${rowClass}" style="${rowStyle}">
				<td>${isBundleItem ? '' : (row.order_sheet || '')}</td>
				<td>${displayItem}</td>
				<td>${isBundleItem ? '' : (row.size || '')}</td>
				<td>${isBundleItem ? '' : (row.color || '')}</td>
				<td class="text-right">${isBundleItem ? '' : formatNumber(row.order_qty || 0)}</td>
				<td class="text-right">${isBundleItem ? '' : formatNumber(row.planned_qty || 0)}</td>
				<td class="text-right">${formatNumber(row.pcs || 0)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-info text-white'}">${formatNumber(row.cutting_qty || 0)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-info text-white'}">${formatNumber(row.cutting_finished || 0)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-info text-white'}">${formatPercentage(cuttingPercent)}%</td>
				<td class="text-center ${isBundleItem ? '' : 'bg-info text-white'}">${cuttingStatus}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-warning text-white'}">${formatNumber(row.stitching_qty || 0)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-warning text-white'}">${formatNumber(row.stitching_finished || 0)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-warning text-white'}">${formatPercentage(stitchingPercent)}%</td>
				<td class="text-center ${isBundleItem ? '' : 'bg-warning text-white'}">${stitchingStatus}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-success text-white'}">${isBundleItem ? '-' : formatNumber(row.packing_qty || 0)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-success text-white'}">${isBundleItem ? '-' : formatNumber(row.packing_finished || 0)}</td>
				<td class="text-right ${isBundleItem ? '' : 'bg-success text-white'}">${isBundleItem ? '-' : formatPercentage(packingPercent) + '%'}</td>
				<td class="text-center ${isBundleItem ? '' : 'bg-success text-white'}">${isBundleItem ? '-' : packingStatus}</td>
			</tr>
		`);
		tbody.append(tr);
	});
}

function getStatusBadge(percent) {
	if (percent >= 100) {
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
