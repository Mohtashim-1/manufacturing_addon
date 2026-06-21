// Copyright (c) 2026, Manufacturing Addon and contributors

frappe.pages["subcontracting-order-history"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Subcontracting Order History"),
		single_column: true,
	});

	const $container = $(`
		<div class="sco-history-page" style="padding: 16px;">
			<div class="sco-filter-card" style="background:#f8f9fa;padding:16px;border-radius:8px;margin-bottom:16px;">
				<div class="row align-items-end">
					<div class="col-md-5">
						<div id="sco_history_filter"></div>
					</div>
					<div class="col-md-3">
						<button class="btn btn-primary btn-block" id="sco_history_load_btn">
							${__("Load History")}
						</button>
					</div>
					<div class="col-md-4 text-right">
						<button class="btn btn-default" id="sco_history_open_form_btn" style="display:none;">
							${__("Open Subcontracting Order")}
						</button>
						<button class="btn btn-default" id="sco_history_report_btn" style="display:none;">
							${__("Open Report")}
						</button>
					</div>
				</div>
			</div>
			<div id="sco_history_content">
				<div class="text-muted text-center" style="padding:60px;">
					${__("Select a Subcontracting Order to view complete history.")}
				</div>
			</div>
		</div>
	`);

	$(wrapper).append($container);

	const sco_field = frappe.ui.form.make_control({
		df: {
			fieldtype: "Link",
			fieldname: "subcontracting_order",
			options: "Subcontracting Order",
			label: __("Subcontracting Order"),
			reqd: 1,
			change() {
				load_history();
			},
		},
		parent: $("#sco_history_filter"),
		render_input: true,
	});
	sco_field.make_input();
	window.sco_history_field = sco_field;

	$("#sco_history_load_btn").on("click", load_history);
	$("#sco_history_open_form_btn").on("click", () => {
		const sco = sco_field.get_value();
		if (sco) frappe.set_route("Form", "Subcontracting Order", sco);
	});
	$("#sco_history_report_btn").on("click", () => {
		const sco = sco_field.get_value();
		if (!sco) return;
		frappe.route_options = { subcontracting_order: sco };
		frappe.set_route("query-report", "Subcontracting Order History");
	});

	if (frappe.route_options?.subcontracting_order) {
		sco_field.set_value(frappe.route_options.subcontracting_order);
		frappe.route_options = null;
		setTimeout(load_history, 200);
	}
};

function load_history() {
	const subcontracting_order = window.sco_history_field?.get_value?.();

	if (!subcontracting_order) {
		frappe.msgprint(__("Please select a Subcontracting Order"));
		return;
	}

	frappe.call({
		method:
			"manufacturing_addon.manufacturing_addon.page.subcontracting_order_history.subcontracting_order_history.get_subcontracting_order_history",
		args: { subcontracting_order },
		freeze: true,
		freeze_message: __("Loading complete history..."),
		callback(r) {
			if (r.message) {
				render_history(r.message);
				$("#sco_history_open_form_btn, #sco_history_report_btn").show();
			}
		},
	});
}

function render_history(data) {
	const $content = $("#sco_history_content");
	const h = data.header || {};
	const s = data.summary || {};

	$content.html(`
		<div class="sco-summary row" style="margin-bottom:16px;">
			${summary_card(__("Order Qty"), format_qty(s.total_ordered_qty), "blue")}
			${summary_card(__("Received Qty"), format_qty(s.total_received_qty), "green")}
			${summary_card(__("Pending FG Qty"), format_qty(s.pending_fg_qty), "orange")}
			${summary_card(__("% Received"), `${flt(s.per_received, 2)}%`, "purple")}
			${summary_card(__("Material Transfers"), s.material_transfer_count || 0, "teal")}
			${summary_card(__("Receipts"), s.receipt_count || 0, "indigo")}
		</div>

		<div class="sco-header-card" style="background:#fff;border:1px solid #d1d8dd;border-radius:8px;padding:16px;margin-bottom:16px;">
			<h5 style="margin:0 0 12px 0;">${escape_html(h.name)}</h5>
			<div class="row" style="font-size:13px;">
				<div class="col-md-3"><b>${__("Supplier")}:</b> ${doc_link("Supplier", h.supplier, h.supplier_name)}</div>
				<div class="col-md-3"><b>${__("Purchase Order")}:</b> ${doc_link("Purchase Order", h.purchase_order)}</div>
				<div class="col-md-2"><b>${__("Date")}:</b> ${frappe.datetime.str_to_user(h.transaction_date)}</div>
				<div class="col-md-2"><b>${__("Status")}:</b> ${status_badge(h.status)}</div>
				<div class="col-md-2"><b>${__("Received")}:</b> ${flt(h.per_received, 2)}%</div>
			</div>
		</div>

		${section_table(__("Complete Timeline"), timeline_columns(), data.timeline || [], true)}
		${section_table(__("Finished Goods Items"), order_item_columns(), data.order_items || [])}
		${section_table(__("Service Items"), service_item_columns(), data.service_items || [])}
		${section_table(__("Raw Materials Supplied"), supplied_item_columns(), data.supplied_items || [])}
		${render_stock_entries(data.stock_entries || [])}
		${render_receipts(data.receipts || [])}
		${section_table(__("Purchase Invoices"), invoice_columns(), flatten_invoices(data.purchase_invoices || []))}
	`);
}

function summary_card(label, value, color) {
	const colors = {
		blue: "#4facfe",
		green: "#43e97b",
		orange: "#fda085",
		purple: "#764ba2",
		teal: "#38f9d7",
		indigo: "#667eea",
	};
	return `
		<div class="col-md-2 col-sm-4 mb-3">
			<div style="background:linear-gradient(135deg, ${colors[color]} 0%, #fff 180%);border-radius:8px;padding:12px;border:1px solid #e9ecef;">
				<div style="font-size:12px;color:#495057;">${label}</div>
				<div style="font-size:20px;font-weight:700;">${value}</div>
			</div>
		</div>
	`;
}

function section_table(title, columns, rows, is_timeline = false) {
	if (!rows.length) {
		return `
			<div class="sco-section" style="margin-bottom:16px;">
				<h5>${title}</h5>
				<div class="text-muted" style="padding:12px;border:1px dashed #d1d8dd;border-radius:6px;">${__("No records found")}</div>
			</div>
		`;
	}

	const head = columns.map((c) => `<th>${c.label}</th>`).join("");
	const body = rows
		.map((row) => {
			const cells = columns
				.map((c) => {
					let val = row[c.fieldname];
					if (c.format === "link" && val) {
						const doctype = c.options || row.document_type;
						return `<td>${doc_link(doctype, val)}</td>`;
					}
					if (c.format === "qty") {
						return `<td class="text-right">${format_qty(val)}</td>`;
					}
					if (c.format === "amount") {
						return `<td class="text-right">${format_amount(val)}</td>`;
					}
					if (c.format === "badge") {
						return `<td>${status_badge(val)}</td>`;
					}
					if (c.format === "date" && val) {
						return `<td>${frappe.datetime.str_to_user(val)}</td>`;
					}
					return `<td>${escape_html(val || "")}</td>`;
				})
				.join("");
			return `<tr${is_timeline ? ' style="cursor:pointer;" data-doctype="' + escape_attr(row.document_type) + '" data-docname="' + escape_attr(row.document) + '"' : ""}>${cells}</tr>`;
		})
		.join("");

	const html = `
		<div class="sco-section" style="margin-bottom:16px;">
			<h5 style="margin-bottom:10px;">${title}</h5>
			<div class="table-responsive">
				<table class="table table-bordered table-sm" style="font-size:12px;background:#fff;">
					<thead style="background:#f8f9fa;"><tr>${head}</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		</div>
	`;

	setTimeout(() => {
		if (is_timeline) {
			$(".sco-section table tbody tr[data-doctype]").off("click").on("click", function () {
				const doctype = $(this).data("doctype");
				const docname = $(this).data("docname");
				if (doctype && docname) frappe.set_route("Form", doctype, docname);
			});
		}
	}, 0);

	return html;
}

function render_stock_entries(entries) {
	if (!entries.length) return section_table(__("Material Transfers (Stock Entry)"), [], []);

	let html = `<div class="sco-section" style="margin-bottom:16px;"><h5>${__("Material Transfers (Stock Entry)")}</h5>`;
	entries.forEach((entry) => {
		html += `
			<div style="border:1px solid #d1d8dd;border-radius:6px;margin-bottom:10px;overflow:hidden;">
				<div style="background:#eef2ff;padding:10px 12px;font-size:13px;">
					<a href="/app/stock-entry/${encodeURIComponent(entry.name)}">${escape_html(entry.name)}</a>
					&nbsp;|&nbsp; ${escape_html(entry.purpose || entry.stock_entry_type)}
					&nbsp;|&nbsp; ${frappe.datetime.str_to_user(entry.posting_date)}
					&nbsp;|&nbsp; ${escape_html(entry.docstatus_label || "")}
					&nbsp;|&nbsp; ${__("Total Qty")}: ${format_qty(entry.total_qty)}
				</div>
				<table class="table table-sm" style="margin:0;font-size:12px;">
					<thead><tr>
						<th>${__("RM Item")}</th><th>${__("FG Item")}</th>
						<th class="text-right">${__("Qty")}</th><th>${__("From")}</th><th>${__("To")}</th>
					</tr></thead>
					<tbody>
						${(entry.items || [])
							.map(
								(item) => `<tr>
							<td>${escape_html(item.item_code)}</td>
							<td>${escape_html(item.subcontracted_item || "")}</td>
							<td class="text-right">${format_qty(item.qty)}</td>
							<td>${escape_html(item.s_warehouse || "")}</td>
							<td>${escape_html(item.t_warehouse || "")}</td>
						</tr>`
							)
							.join("")}
					</tbody>
				</table>
			</div>
		`;
	});
	html += `</div>`;
	return html;
}

function render_receipts(receipts) {
	if (!receipts.length) return section_table(__("Subcontracting Receipts"), [], []);

	let html = `<div class="sco-section" style="margin-bottom:16px;"><h5>${__("Subcontracting Receipts")}</h5>`;
	receipts.forEach((receipt) => {
		html += `
			<div style="border:1px solid #d1d8dd;border-radius:6px;margin-bottom:10px;overflow:hidden;">
				<div style="background:#ecfdf5;padding:10px 12px;font-size:13px;">
					<a href="/app/subcontracting-receipt/${encodeURIComponent(receipt.name)}">${escape_html(receipt.name)}</a>
					&nbsp;|&nbsp; ${frappe.datetime.str_to_user(receipt.posting_date)}
					&nbsp;|&nbsp; ${escape_html(receipt.docstatus_label || "")}
					&nbsp;|&nbsp; ${__("Qty")}: ${format_qty(receipt.total_qty)}
					&nbsp;|&nbsp; ${__("Amount")}: ${format_amount(receipt.total)}
				</div>
				<table class="table table-sm" style="margin:0;font-size:12px;">
					<thead><tr>
						<th>${__("FG Item")}</th><th class="text-right">${__("Qty")}</th>
						<th class="text-right">${__("Received")}</th><th class="text-right">${__("Rate")}</th>
						<th class="text-right">${__("Amount")}</th>
					</tr></thead>
					<tbody>
						${(receipt.items || [])
							.map(
								(item) => `<tr>
							<td>${escape_html(item.item_code)}</td>
							<td class="text-right">${format_qty(item.qty)}</td>
							<td class="text-right">${format_qty(item.received_qty)}</td>
							<td class="text-right">${format_amount(item.rate)}</td>
							<td class="text-right">${format_amount(item.amount)}</td>
						</tr>`
							)
							.join("")}
					</tbody>
				</table>
			</div>
		`;
	});
	html += `</div>`;
	return html;
}

function timeline_columns() {
	return [
		{ label: __("#"), fieldname: "idx" },
		{ label: __("Date"), fieldname: "date", format: "date" },
		{ label: __("Document Type"), fieldname: "document_type" },
		{ label: __("Document"), fieldname: "document", format: "link" },
		{ label: __("Description"), fieldname: "description" },
		{ label: __("Qty"), fieldname: "qty", format: "qty" },
		{ label: __("Amount"), fieldname: "amount", format: "amount" },
		{ label: __("Status"), fieldname: "status", format: "badge" },
	];
}

function order_item_columns() {
	return [
		{ label: __("Item"), fieldname: "item_code" },
		{ label: __("Ordered Qty"), fieldname: "qty", format: "qty" },
		{ label: __("Received Qty"), fieldname: "received_qty", format: "qty" },
		{ label: __("Pending Qty"), fieldname: "pending_qty", format: "qty" },
		{ label: __("UOM"), fieldname: "uom" },
		{ label: __("Rate"), fieldname: "rate", format: "amount" },
		{ label: __("Amount"), fieldname: "amount", format: "amount" },
		{ label: __("BOM"), fieldname: "bom" },
	];
}

function service_item_columns() {
	return [
		{ label: __("Service Item"), fieldname: "item_code" },
		{ label: __("Qty"), fieldname: "qty", format: "qty" },
		{ label: __("FG Qty"), fieldname: "fg_item_qty", format: "qty" },
		{ label: __("UOM"), fieldname: "uom" },
		{ label: __("Rate"), fieldname: "rate", format: "amount" },
		{ label: __("Amount"), fieldname: "amount", format: "amount" },
	];
}

function supplied_item_columns() {
	return [
		{ label: __("FG Item"), fieldname: "main_item_code" },
		{ label: __("RM Item"), fieldname: "rm_item_code" },
		{ label: __("Required"), fieldname: "required_qty", format: "qty" },
		{ label: __("Supplied"), fieldname: "supplied_qty", format: "qty" },
		{ label: __("Consumed"), fieldname: "consumed_qty", format: "qty" },
		{ label: __("Returned"), fieldname: "returned_qty", format: "qty" },
		{ label: __("Pending"), fieldname: "pending_qty", format: "qty" },
		{ label: __("UOM"), fieldname: "stock_uom" },
	];
}

function invoice_columns() {
	return [
		{ label: __("Invoice"), fieldname: "name", format: "link", options: "Purchase Invoice" },
		{ label: __("Date"), fieldname: "posting_date", format: "date" },
		{ label: __("Item"), fieldname: "item_code" },
		{ label: __("Qty"), fieldname: "qty", format: "qty" },
		{ label: __("Amount"), fieldname: "amount", format: "amount" },
		{ label: __("Status"), fieldname: "status", format: "badge" },
	];
}

function flatten_invoices(invoices) {
	const rows = [];
	invoices.forEach((inv) => {
		(inv.items || []).forEach((item) => {
			rows.push({
				name: inv.name,
				posting_date: inv.posting_date,
				item_code: item.item_code,
				qty: item.qty,
				amount: item.amount,
				status: inv.status || inv.docstatus_label,
			});
		});
		if (!(inv.items || []).length) {
			rows.push({
				name: inv.name,
				posting_date: inv.posting_date,
				status: inv.status || inv.docstatus_label,
			});
		}
	});
	return rows;
}

function doc_link(doctype, name, label) {
	if (!name) return "";
	const text = label || name;
	return `<a href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}">${escape_html(text)}</a>`;
}

function status_badge(status) {
	if (!status) return "";
	const cls =
		(status || "").toLowerCase().includes("complete") ||
		(status || "").toLowerCase().includes("submit")
			? "success"
			: (status || "").toLowerCase().includes("partial")
			? "warning"
			: "secondary";
	return `<span class="badge badge-${cls}">${escape_html(status)}</span>`;
}

function format_qty(val) {
	return val == null || val === "" ? "-" : flt(val, 2);
}

function format_amount(val) {
	return val == null || val === "" ? "-" : format_currency(flt(val, 2));
}

function escape_html(value) {
	return frappe.utils.escape_html(String(value ?? ""));
}

function escape_attr(value) {
	return String(value ?? "").replace(/"/g, "&quot;");
}
