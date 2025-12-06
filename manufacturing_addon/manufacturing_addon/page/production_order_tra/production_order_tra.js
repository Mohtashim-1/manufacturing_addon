frappe.pages['production-order-tra'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Production Order Tracking Spreadsheet',
		single_column: true
	});
	
	// Get document name from route_options, route, or query parameters
	let docName = null;
	
	// First check route_options (set when navigating from form)
	if (frappe.route_options && frappe.route_options.docname) {
		docName = frappe.route_options.docname;
		frappe.route_options = null; // Clear after use
	}
	
	// Then check route
	if (!docName) {
		const route = frappe.get_route();
		if (route && route.length > 2) {
			docName = route[2];
		}
	}
	
	// Finally check query parameters
	if (!docName) {
		const urlParams = new URLSearchParams(window.location.search);
		docName = urlParams.get('docname') || urlParams.get('name') || null;
	}
	
	// Create and load spreadsheet - pass wrapper instead of page
	load_spreadsheet(wrapper, docName);
}

function load_spreadsheet(wrapper, docName) {
	// Create container
	let $container = $(`
		<div class="production-order-tracking-spreadsheet" style="padding: 20px;">
			<div class="spreadsheet-header" style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
				<div class="row mb-3">
					<div class="col-md-12">
						<h2>Production Order Tracking</h2>
					</div>
				</div>
				<div class="row mb-3">
					<div class="col-md-2">
						<label style="font-weight: bold; font-size: 12px;">Customer</label>
						<div class="input-group">
							<input type="text" id="customer" class="form-control" placeholder="Select Customer" />
							<div class="input-group-append">
								<button class="btn btn-sm btn-secondary" type="button" onclick="selectCustomer()" title="Select Customer">
									<i class="fa fa-search"></i>
								</button>
							</div>
						</div>
					</div>
					<div class="col-md-2">
						<label style="font-weight: bold; font-size: 12px;">Sales Order</label>
						<div class="input-group">
							<input type="text" id="sales_order" class="form-control" placeholder="Select Sales Order" />
							<div class="input-group-append">
								<button class="btn btn-sm btn-secondary" type="button" onclick="selectSalesOrder()" title="Select Sales Order">
									<i class="fa fa-search"></i>
								</button>
							</div>
						</div>
					</div>
					<div class="col-md-2">
						<label style="font-weight: bold; font-size: 12px;">PO #</label>
						<input type="text" id="po_number" class="form-control" />
					</div>
					<div class="col-md-2">
						<label style="font-weight: bold; font-size: 12px;">SHIP DATE</label>
						<input type="date" id="ship_date" class="form-control" />
					</div>
					<div class="col-md-2">
						<label style="font-weight: bold; font-size: 12px;">PORT OF DESTINATION</label>
						<input type="text" id="port_of_destination" class="form-control" />
					</div>
					<div class="col-md-2">
						<button class="btn btn-primary btn-sm mt-4" onclick="saveSpreadsheetData()">Save</button>
						<button class="btn btn-secondary btn-sm mt-4" onclick="loadSpreadsheetData()">Load</button>
					</div>
				</div>
			</div>
			<div class="spreadsheet-container" style="overflow-x: auto;">
				<div class="table-responsive">
					<table class="table table-bordered table-sm" id="spreadsheet-table" style="font-size: 12px; min-width: 1500px;">
						<thead>
							<tr>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">ITEM</th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">Dessin</th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">Size (CM)</th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">COLOR</th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">EANCODE</th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">QUANTITY</th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">QTY/CTN</th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">TOTAL CARTONS</th>
								<th colspan="4" class="text-center bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">CUTTING</th>
								<th colspan="3" class="text-center bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">STITCHING</th>
								<th colspan="3" class="text-center bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">PACKING</th>
							</tr>
							<tr>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;"></th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;"></th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;"></th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;"></th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;"></th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;"></th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;"></th>
								<th style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;"></th>
								<th class="bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">PLAN</th>
								<th class="bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">DUVET</th>
								<th class="bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">Fitted</th>
								<th class="bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">PILLOW</th>
								<th class="bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">DUVET</th>
								<th class="bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">Fitted</th>
								<th class="bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">PILLOW</th>
								<th class="bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">CTN</th>
								<th class="bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">PCS</th>
								<th class="bg-light" style="background-color: #f8f9fa; position: sticky; top: 0; z-index: 10; text-align: center; padding: 8px 4px;">Percentage</th>
							</tr>
						</thead>
						<tbody id="spreadsheet-body"></tbody>
						<tfoot>
							<tr class="font-weight-bold bg-light" style="background-color: #e9ecef !important;">
								<td colspan="5">TOTAL</td>
								<td id="total-quantity">0</td>
								<td></td>
								<td id="total-cartons">0</td>
								<td id="total-cutting-plan">0</td>
								<td id="total-cutting-duvet">0</td>
								<td id="total-cutting-fitted">0</td>
								<td id="total-cutting-pillow">0</td>
								<td id="total-stitching-duvet">0</td>
								<td id="total-stitching-fitted">0</td>
								<td id="total-stitching-pillow">0</td>
								<td id="total-packing-ctn">0</td>
								<td id="total-packing-pcs">0</td>
								<td></td>
							</tr>
						</tfoot>
					</table>
				</div>
				<div class="mt-2">
					<button class="btn btn-success btn-sm" onclick="addSpreadsheetRow()">Add Row</button>
					<button class="btn btn-danger btn-sm" onclick="deleteSelectedSpreadsheetRows()">Delete Selected</button>
				</div>
			</div>
		</div>
	`);
	
	// Append to wrapper instead of page
	$(wrapper).append($container);
	
	// Initialize Link fields for Customer and Sales Order after a short delay
	setTimeout(function() {
		setupLinkFields();
	}, 100);
	
	// Initialize spreadsheet
	window.spreadsheetDocName = docName;
	
	if (docName) {
		loadSpreadsheetData();
	} else {
		// Add initial rows
		addSpreadsheetRow();
		addSpreadsheetRow();
		addSpreadsheetRow();
	}
}

function setupLinkFields() {
	// Fields are set up with buttons to select
	// Clear sales order when customer changes
	$('#customer').on('change', function() {
		$('#sales_order').val('');
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
			$('#customer').val(values.customer);
		}
	}, 'Select Customer');
}

function selectSalesOrder() {
	let customer = $('#customer').val();
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
			$('#sales_order').val(values.sales_order);
		}
	}, 'Select Sales Order');
}

let spreadsheetRowCount = 0;

function addSpreadsheetRow() {
	const tbody = document.getElementById('spreadsheet-body');
	const row = document.createElement('tr');
	row.dataset.rowIndex = spreadsheetRowCount++;
	
	row.innerHTML = `
		<td><input type="text" class="item-input" data-field="item" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="text" class="item-input" data-field="dessin" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="text" class="item-input" data-field="size_cm" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="text" class="item-input" data-field="color" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="text" class="item-input" data-field="ean_code" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="quantity" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="qty_ctn" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="total_cartons" step="0.01" readonly style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="cutting_plan" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="cutting_duvet" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="cutting_fitted" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="cutting_pillow" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="stitching_duvet" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="stitching_fitted" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="stitching_pillow" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="packing_ctn" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="packing_pcs" step="0.01" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		<td><input type="number" class="item-input numeric" data-field="packing_percentage" step="0.01" readonly style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
	`;
	
	tbody.appendChild(row);
	
	// Add event listeners
	const inputs = row.querySelectorAll('input');
	inputs.forEach(input => {
		input.addEventListener('input', function() {
			calculateSpreadsheetRow(row);
			calculateSpreadsheetTotals();
		});
		
		if (input.dataset.field === 'quantity' || input.dataset.field === 'qty_ctn') {
			input.addEventListener('blur', function() {
				calculateSpreadsheetTotalCartons(row);
			});
		}
		
		if (input.dataset.field === 'quantity' || input.dataset.field === 'packing_pcs') {
			input.addEventListener('blur', function() {
				calculateSpreadsheetPackingPercentage(row);
			});
		}
	});
}

function calculateSpreadsheetRow(row) {
	calculateSpreadsheetTotalCartons(row);
	calculateSpreadsheetPackingPercentage(row);
}

function calculateSpreadsheetTotalCartons(row) {
	const quantity = parseFloat(row.querySelector('[data-field="quantity"]').value) || 0;
	const qtyCtn = parseFloat(row.querySelector('[data-field="qty_ctn"]').value) || 0;
	const totalCartonsInput = row.querySelector('[data-field="total_cartons"]');
	
	if (qtyCtn > 0) {
		totalCartonsInput.value = (quantity / qtyCtn).toFixed(2);
	} else {
		totalCartonsInput.value = '';
	}
}

function calculateSpreadsheetPackingPercentage(row) {
	const quantity = parseFloat(row.querySelector('[data-field="quantity"]').value) || 0;
	const packingPcs = parseFloat(row.querySelector('[data-field="packing_pcs"]').value) || 0;
	const packingPercentageInput = row.querySelector('[data-field="packing_percentage"]');
	
	if (quantity > 0) {
		packingPercentageInput.value = ((packingPcs / quantity) * 100).toFixed(2);
	} else {
		packingPercentageInput.value = '';
	}
}

function calculateSpreadsheetTotals() {
	const rows = document.querySelectorAll('#spreadsheet-body tr');
	let totalQuantity = 0;
	let totalCartons = 0;
	let totalCuttingPlan = 0;
	let totalCuttingDuvet = 0;
	let totalCuttingFitted = 0;
	let totalCuttingPillow = 0;
	let totalStitchingDuvet = 0;
	let totalStitchingFitted = 0;
	let totalStitchingPillow = 0;
	let totalPackingCtn = 0;
	let totalPackingPcs = 0;
	
	rows.forEach(row => {
		totalQuantity += parseFloat(row.querySelector('[data-field="quantity"]').value) || 0;
		totalCartons += parseFloat(row.querySelector('[data-field="total_cartons"]').value) || 0;
		totalCuttingPlan += parseFloat(row.querySelector('[data-field="cutting_plan"]').value) || 0;
		totalCuttingDuvet += parseFloat(row.querySelector('[data-field="cutting_duvet"]').value) || 0;
		totalCuttingFitted += parseFloat(row.querySelector('[data-field="cutting_fitted"]').value) || 0;
		totalCuttingPillow += parseFloat(row.querySelector('[data-field="cutting_pillow"]').value) || 0;
		totalStitchingDuvet += parseFloat(row.querySelector('[data-field="stitching_duvet"]').value) || 0;
		totalStitchingFitted += parseFloat(row.querySelector('[data-field="stitching_fitted"]').value) || 0;
		totalStitchingPillow += parseFloat(row.querySelector('[data-field="stitching_pillow"]').value) || 0;
		totalPackingCtn += parseFloat(row.querySelector('[data-field="packing_ctn"]').value) || 0;
		totalPackingPcs += parseFloat(row.querySelector('[data-field="packing_pcs"]').value) || 0;
	});
	
	document.getElementById('total-quantity').textContent = totalQuantity.toFixed(2);
	document.getElementById('total-cartons').textContent = totalCartons.toFixed(2);
	document.getElementById('total-cutting-plan').textContent = totalCuttingPlan.toFixed(2);
	document.getElementById('total-cutting-duvet').textContent = totalCuttingDuvet.toFixed(2);
	document.getElementById('total-cutting-fitted').textContent = totalCuttingFitted.toFixed(2);
	document.getElementById('total-cutting-pillow').textContent = totalCuttingPillow.toFixed(2);
	document.getElementById('total-stitching-duvet').textContent = totalStitchingDuvet.toFixed(2);
	document.getElementById('total-stitching-fitted').textContent = totalStitchingFitted.toFixed(2);
	document.getElementById('total-stitching-pillow').textContent = totalStitchingPillow.toFixed(2);
	document.getElementById('total-packing-ctn').textContent = totalPackingCtn.toFixed(2);
	document.getElementById('total-packing-pcs').textContent = totalPackingPcs.toFixed(2);
}

function deleteSelectedSpreadsheetRows() {
	const rows = document.querySelectorAll('#spreadsheet-body tr');
	const selectedRows = [];
	
	rows.forEach((row, index) => {
		const checkbox = row.querySelector('input[type="checkbox"]');
		if (checkbox && checkbox.checked) {
			selectedRows.push(row);
		}
	});
	
	selectedRows.forEach(row => row.remove());
	calculateSpreadsheetTotals();
}

function getSpreadsheetDataFromTable() {
	const rows = document.querySelectorAll('#spreadsheet-body tr');
	const items = [];
	
	rows.forEach(row => {
		const item = {};
		const inputs = row.querySelectorAll('input.item-input');
		inputs.forEach(input => {
			const field = input.dataset.field;
			if (field) {
				if (input.type === 'number') {
					item[field] = parseFloat(input.value) || 0;
				} else {
					item[field] = input.value || '';
				}
			}
		});
		
		if (Object.values(item).some(val => val !== '' && val !== 0)) {
			items.push(item);
		}
	});
	
	return items;
}

function populateSpreadsheetTable(items) {
	const tbody = document.getElementById('spreadsheet-body');
	tbody.innerHTML = '';
	spreadsheetRowCount = 0;
	
	items.forEach(item => {
		const row = document.createElement('tr');
		row.dataset.rowIndex = spreadsheetRowCount++;
		
		row.innerHTML = `
			<td><input type="text" class="item-input" data-field="item" value="${(item.item || '').replace(/"/g, '&quot;')}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="text" class="item-input" data-field="dessin" value="${(item.dessin || '').replace(/"/g, '&quot;')}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="text" class="item-input" data-field="size_cm" value="${(item.size_cm || '').replace(/"/g, '&quot;')}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="text" class="item-input" data-field="color" value="${(item.color || '').replace(/"/g, '&quot;')}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="text" class="item-input" data-field="ean_code" value="${(item.ean_code || '').replace(/"/g, '&quot;')}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="quantity" step="0.01" value="${item.quantity || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="qty_ctn" step="0.01" value="${item.qty_ctn || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="total_cartons" step="0.01" value="${item.total_cartons || ''}" readonly style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="cutting_plan" step="0.01" value="${item.cutting_plan || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="cutting_duvet" step="0.01" value="${item.cutting_duvet || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="cutting_fitted" step="0.01" value="${item.cutting_fitted || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="cutting_pillow" step="0.01" value="${item.cutting_pillow || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="stitching_duvet" step="0.01" value="${item.stitching_duvet || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="stitching_fitted" step="0.01" value="${item.stitching_fitted || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="stitching_pillow" step="0.01" value="${item.stitching_pillow || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="packing_ctn" step="0.01" value="${item.packing_ctn || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="packing_pcs" step="0.01" value="${item.packing_pcs || ''}" style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
			<td><input type="number" class="item-input numeric" data-field="packing_percentage" step="0.01" value="${item.packing_percentage || ''}" readonly style="border: none; width: 100%; padding: 4px; font-size: 12px;" /></td>
		`;
		
		tbody.appendChild(row);
		
		const inputs = row.querySelectorAll('input');
		inputs.forEach(input => {
			input.addEventListener('input', function() {
				calculateSpreadsheetRow(row);
				calculateSpreadsheetTotals();
			});
			
			if (input.dataset.field === 'quantity' || input.dataset.field === 'qty_ctn') {
				input.addEventListener('blur', function() {
					calculateSpreadsheetTotalCartons(row);
				});
			}
			
			if (input.dataset.field === 'quantity' || input.dataset.field === 'packing_pcs') {
				input.addEventListener('blur', function() {
					calculateSpreadsheetPackingPercentage(row);
				});
			}
		});
	});
	
	calculateSpreadsheetTotals();
}

function saveSpreadsheetData() {
	const customer = $('#customer').val();
	const salesOrder = $('#sales_order').val();
	const poNumber = document.getElementById('po_number').value;
	const shipDate = document.getElementById('ship_date').value;
	const portOfDestination = document.getElementById('port_of_destination').value;
	const items = getSpreadsheetDataFromTable();
	
	const docData = {
		doctype: 'Production Order Tracking',
		customer: customer || null,
		sales_order: salesOrder || null,
		po_number: poNumber || null,
		ship_date: shipDate || null,
		port_of_destination: portOfDestination || null,
		items_table: items
	};
	
	if (window.spreadsheetDocName) {
		docData.name = window.spreadsheetDocName;
	}
	
	frappe.call({
		method: 'frappe.client.save',
		args: {
			doc: docData
		},
		freeze: true,
		freeze_message: __('Saving...'),
		callback: function(r) {
			if (r.message) {
				window.spreadsheetDocName = r.message.name;
				frappe.show_alert({
					message: __('Saved successfully'),
					indicator: 'green'
				}, 3);
				
				// Update route_options for next navigation
				frappe.route_options = {
					docname: window.spreadsheetDocName
				};
			}
		},
		error: function(r) {
			frappe.msgprint({
				message: __('Error saving data'),
				indicator: 'red',
				title: __('Error')
			});
		}
	});
}

function loadSpreadsheetData() {
	if (!window.spreadsheetDocName) {
		frappe.msgprint({
			message: __('No document selected'),
			indicator: 'orange',
			title: __('Error')
		});
		return;
	}
	
	frappe.call({
		method: 'frappe.client.get',
		args: {
			doctype: 'Production Order Tracking',
			name: window.spreadsheetDocName
		},
		freeze: true,
		freeze_message: __('Loading...'),
		callback: function(r) {
			if (r.message) {
				const doc = r.message;
				
				// Set Customer and Sales Order
				$('#customer').val(doc.customer || '');
				$('#sales_order').val(doc.sales_order || '');
				
				// Set other fields
				document.getElementById('po_number').value = doc.po_number || '';
				document.getElementById('ship_date').value = doc.ship_date || '';
				document.getElementById('port_of_destination').value = doc.port_of_destination || '';
				
				if (doc.items_table && doc.items_table.length > 0) {
					populateSpreadsheetTable(doc.items_table);
				} else {
					addSpreadsheetRow();
					addSpreadsheetRow();
					addSpreadsheetRow();
				}
			}
		},
		error: function(r) {
			frappe.msgprint({
				message: __('Error loading data'),
				indicator: 'red',
				title: __('Error')
			});
		}
	});
}
