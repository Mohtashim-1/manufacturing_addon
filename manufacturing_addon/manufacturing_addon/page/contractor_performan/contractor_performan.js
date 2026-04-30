// Contractor Performance Dashboard — route /app/contractor-performan
// Tabs must NOT use href="#..." (Frappe router treats hash as a Page route).

(function () {
	function inject_cp_dashboard_styles() {
		if (document.getElementById("cp-dashboard-styles")) return;
		const css = `
			.contractor-performance-page {
				background: #f1f5f9;
				padding: 16px;
				border-radius: 10px;
				margin: -4px -4px 8px;
			}
			.contractor-performance-page .cp-filters {
				box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
				border-color: #e2e8f0 !important;
			}
			.contractor-performance-page .cp-filters .cp-filter-row {
				display: flex;
				flex-wrap: wrap;
				align-items: flex-end;
			}
			.contractor-performance-page .cp-filters .cp-filter-row > *:not(.ml-auto) {
				margin-right: 14px;
				margin-bottom: 8px;
			}
			.contractor-performance-page .cp-filters .cp-filter-row > .ml-auto {
				margin-left: auto;
				margin-right: 0;
				margin-bottom: 8px;
			}
			.contractor-performance-page .cp-tabs {
				border-bottom: 1px solid #e2e8f0;
				gap: 4px;
			}
			.contractor-performance-page .cp-tabs .nav-item { margin-bottom: -1px; }
			.contractor-performance-page .cp-tabs .cp-tab-btn {
				border: none;
				border-bottom: 2px solid transparent;
				background: transparent;
				color: #64748b;
				padding: 10px 14px;
				border-radius: 6px 6px 0 0;
				cursor: pointer;
				font-size: 13px;
			}
			.contractor-performance-page .cp-tabs .cp-tab-btn:hover { color: #0f172a; background: rgba(255,255,255,.6); }
			.contractor-performance-page .cp-tabs .cp-tab-btn.active {
				color: #0f172a;
				border-bottom-color: #0f172a;
				font-weight: 600;
				background: #fff;
			}
			.contractor-performance-page .cp-chip-wrap {
				display: flex;
				flex-wrap: wrap;
				gap: 8px;
				align-items: center;
				min-height: 28px;
			}
			.contractor-performance-page .cp-chip {
				display: inline-flex;
				align-items: center;
				gap: 8px;
				padding: 5px 12px;
				background: #fff;
				border: 1px solid #e2e8f0;
				border-radius: 999px;
				font-size: 12px;
				line-height: 1.35;
				box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
			}
			.contractor-performance-page .cp-chip-name {
				font-weight: 500;
				color: #334155;
				white-space: nowrap;
				overflow: hidden;
				text-overflow: ellipsis;
				max-width: min(240px, 28vw);
			}
			.contractor-performance-page .cp-chip-qty {
				font-variant-numeric: tabular-nums;
				font-weight: 700;
				color: #0f172a;
				flex-shrink: 0;
			}
			.contractor-performance-page .cp-empty-cell { color: #94a3b8; font-style: italic; font-size: 13px; }
			.contractor-performance-page table.cp-table {
				font-size: 13px;
				border-color: #e2e8f0 !important;
			}
			.contractor-performance-page table.cp-table thead th {
				background: #e2e8f0;
				color: #334155;
				font-weight: 600;
				border-color: #cbd5e1 !important;
				vertical-align: middle;
				padding: 10px 12px;
			}
			.contractor-performance-page table.cp-table td {
				vertical-align: top !important;
				border-color: #e2e8f0 !important;
				padding: 10px 12px;
			}
			.contractor-performance-page table.cp-table tbody tr:nth-child(even) { background: #f8fafc; }
			.contractor-performance-page .cp-item-cell { max-width: 340px; word-break: break-word; color: #1e293b; }
			.contractor-performance-page .cp-item-sub { font-size: 11px; color: #64748b; margin-top: 4px; line-height: 1.3; }
			.contractor-performance-page .cp-matrix-intro {
				padding: 10px 14px;
				background: #f8fafc;
				border: 1px solid #e2e8f0;
				border-radius: 8px;
				border-left: 4px solid #64748b;
				margin-bottom: 1rem !important;
			}
			.contractor-performance-page .cp-matrix-groups {
				display: flex;
				flex-direction: column;
				gap: 22px;
			}
			.contractor-performance-page .cp-so-block {
				border-radius: 10px;
				overflow: hidden;
				background: #fff;
				border: 1px solid #cbd5e1;
				box-shadow:
					0 1px 2px rgba(15, 23, 42, 0.06),
					0 4px 12px rgba(15, 23, 42, 0.06);
			}
			.contractor-performance-page .cp-so-block.cp-so-block--sales {
				border-left: 4px solid #2563eb;
			}
			.contractor-performance-page .cp-so-block.cp-so-block--other {
				border-left: 4px solid #d97706;
				box-shadow:
					0 1px 2px rgba(217, 119, 6, 0.12),
					0 4px 12px rgba(15, 23, 42, 0.06);
			}
			.contractor-performance-page .cp-so-head {
				padding: 14px 16px;
				border-bottom: 1px solid #e2e8f0;
				background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
			}
			.contractor-performance-page .cp-so-head.cp-so-head--warn {
				background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%);
			}
			.contractor-performance-page .cp-so-head-label {
				font-size: 10px;
				letter-spacing: 0.06em;
				text-transform: uppercase;
				color: #64748b;
				font-weight: 700;
				margin-bottom: 6px;
			}
			.contractor-performance-page .cp-so-head-title {
				font-size: 15px;
				font-weight: 600;
				color: #0f172a;
				line-height: 1.45;
				word-break: break-word;
			}
			.contractor-performance-page .cp-so-head-code {
				font-size: 12px;
				color: #475569;
				font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
				margin-top: 8px;
				padding: 6px 10px;
				background: rgba(241, 245, 249, 0.9);
				border-radius: 6px;
				display: inline-block;
				max-width: 100%;
				word-break: break-all;
			}
			.contractor-performance-page .cp-so-table-wrap {
				border-top: none;
			}
			.contractor-performance-page .cp-so-table-wrap table.cp-table.cp-table-grouped {
				font-size: 13px;
			}
			.contractor-performance-page .cp-so-table-wrap table.cp-table.cp-table-grouped thead th {
				background: #e2e8f0;
				color: #1e293b;
				font-size: 11px;
				text-transform: uppercase;
				letter-spacing: 0.04em;
				font-weight: 700;
				padding: 11px 14px;
				border-color: #cbd5e1 !important;
				border-bottom: 2px solid #94a3b8 !important;
				vertical-align: middle;
			}
			.contractor-performance-page .cp-so-table-wrap table.cp-table.cp-table-grouped thead th:first-child {
				min-width: 140px;
			}
			.contractor-performance-page .cp-so-table-wrap table.cp-table.cp-table-grouped tbody td {
				padding: 12px 14px;
				border-color: #e8edf3 !important;
			}
			.contractor-performance-page .cp-so-table-wrap table.cp-table.cp-table-grouped tbody tr:nth-child(even) {
				background: #fafbfc;
			}
			.contractor-performance-page .cp-so-table-wrap table.cp-table.cp-table-grouped tbody td.cp-stage-cell {
				background: #f4f7fb;
				border-left: 1px solid #e8edf3;
				vertical-align: middle !important;
			}
			.contractor-performance-page .cp-so-table-wrap table.cp-table.cp-table-grouped tbody tr:nth-child(even) td.cp-stage-cell {
				background: #eef2f8;
			}
			.contractor-performance-page .cp-component-compact .cp-component-name {
				font-weight: 600;
				font-size: 14px;
				color: #0f172a;
				line-height: 1.35;
			}
			.contractor-performance-page .tab-content.cp-tab-panel {
				box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
				border-color: #e2e8f0 !important;
			}
		`;
		$("<style/>", { id: "cp-dashboard-styles", text: css }).appendTo("head");
	}
	inject_cp_dashboard_styles();

	frappe.pages["contractor-performan"].on_page_load = function (wrapper) {
		try {
			if (window.location.hash || window.location.pathname.indexOf("%23") !== -1) {
				history.replaceState(null, "", "/app/contractor-performan");
			}
		} catch (e) {
			/* ignore */
		}

		frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Contractor Manufacturing Dashboard"),
			single_column: true,
		});

		const $main = $(`
			<div class="contractor-performance-page">
				<div class="cp-filters card border p-3 mb-3 bg-white rounded">
					<div class="cp-filter-row"></div>
				</div>
				<p class="text-muted small cp-meta mb-3"></p>
				<ul class="nav nav-tabs mb-0 cp-tabs" role="tablist">
					<li class="nav-item">
						<button type="button" class="nav-link cp-tab-btn active" data-cp-tab="cp-tab-matrix">${__("By item (all stages)")}</button>
					</li>
					<li class="nav-item">
						<button type="button" class="nav-link cp-tab-btn" data-cp-tab="cp-tab-cutting">${__("Cutting detail")}</button>
					</li>
					<li class="nav-item">
						<button type="button" class="nav-link cp-tab-btn" data-cp-tab="cp-tab-stitching">${__("Stitching detail")}</button>
					</li>
					<li class="nav-item">
						<button type="button" class="nav-link cp-tab-btn" data-cp-tab="cp-tab-packing">${__("Packing detail")}</button>
					</li>
				</ul>
				<div class="tab-content bg-white border border-top-0 rounded-bottom p-3 mb-3 cp-tab-panel" style="border-color:#e2e8f0!important;">
					<div class="tab-pane fade show active" id="cp-tab-matrix"></div>
					<div class="tab-pane fade" id="cp-tab-cutting"></div>
					<div class="tab-pane fade" id="cp-tab-stitching"></div>
					<div class="tab-pane fade" id="cp-tab-packing"></div>
				</div>
			</div>
		`);

		$(wrapper).find(".layout-main-section").empty().append($main);

		const $filters = $main.find(".cp-filter-row");

		const ctrls = {};
		ctrls.from_date = frappe.ui.form.make_control({
			parent: $filters,
			df: {
				fieldtype: "Date",
				fieldname: "from_date",
				label: __("From Date"),
				reqd: 1,
				default: frappe.datetime.month_start(),
			},
			render_input: true,
		});
		ctrls.to_date = frappe.ui.form.make_control({
			parent: $filters,
			df: {
				fieldtype: "Date",
				fieldname: "to_date",
				label: __("To Date"),
				reqd: 1,
				default: frappe.datetime.month_end(),
			},
			render_input: true,
		});
		ctrls.customer = frappe.ui.form.make_control({
			parent: $filters,
			df: {
				fieldtype: "Link",
				fieldname: "customer",
				label: __("Customer"),
				options: "Customer",
			},
			render_input: true,
		});
		ctrls.cp_so_item = frappe.ui.form.make_control({
			parent: $filters,
			df: {
				fieldtype: "Link",
				fieldname: "cp_so_item",
				label: __("SO item (main)"),
				options: "Item",
			},
			render_input: true,
		});
		ctrls.cp_combo_item = frappe.ui.form.make_control({
			parent: $filters,
			df: {
				fieldtype: "Link",
				fieldname: "cp_combo_item",
				label: __("Combo item"),
				options: "Item",
			},
			render_input: true,
		});
		ctrls.cp_supplier = frappe.ui.form.make_control({
			parent: $filters,
			df: {
				fieldtype: "Link",
				fieldname: "cp_supplier",
				label: __("Supplier"),
				options: "Manufacturing Contractor",
			},
			render_input: true,
		});

		$filters.append(
			$(`<div class="ml-auto">
				<button type="button" class="btn btn-dark btn-sm">${__("Refresh")}</button>
			</div>`).on("click", "button", () => load())
		);

		Object.values(ctrls).forEach((c) => c.refresh());

		ctrls.from_date.set_value(frappe.datetime.month_start());
		ctrls.to_date.set_value(frappe.datetime.month_end());

		$main.find(".cp-tabs .cp-tab-btn").on("click", function (e) {
			e.preventDefault();
			e.stopPropagation();
			const id = $(this).attr("data-cp-tab");
			if (!id) return;
			$main.find(".tab-pane").removeClass("show active");
			$main.find("#" + id).addClass("show active");
			$main.find(".cp-tabs .cp-tab-btn").removeClass("active");
			$(this).addClass("active");
		});

		const $meta = $main.find(".cp-meta");
		const $matrix = $main.find("#cp-tab-matrix");
		const $cut = $main.find("#cp-tab-cutting");
		const $st = $main.find("#cp-tab-stitching");
		const $pk = $main.find("#cp-tab-packing");

		function fmt_qty(v) {
			return frappe.format(v, { fieldtype: "Float" });
		}

		function cpRefCell(label, code) {
			const L = frappe.utils.escape_html(label || "");
			const C = frappe.utils.escape_html(code || "");
			if (!L && !C) {
				return `<span class="cp-empty-cell">—</span>`;
			}
			if (L && C && L !== C) {
				return `<div>${L}</div><div class="cp-item-sub text-monospace">${C}</div>`;
			}
			return `<div>${L || C}</div>`;
		}

		function cpDetailItemCell(r) {
			let html = `<div class="fw-medium">${frappe.utils.escape_html(r.item_label || "")}</div>`;
			if (r.combo_detail) {
				html += `<div class="cp-item-sub">${frappe.utils.escape_html(r.combo_detail)}</div>`;
			}
			html += `<div class="cp-item-sub text-truncate">${frappe.utils.escape_html(r.item_key || "")}</div>`;
			if (r.is_combo) {
				html += `<span class="badge badge-light border ml-0 mt-1" style="font-size:10px">${__("Combo")}</span>`;
			}
			return html;
		}

		function cpMatrixItemCell(m) {
			let html = `<div class="fw-medium">${frappe.utils.escape_html(m.item_label || "")}</div>`;
			if (m.combo_detail) {
				html += `<div class="cp-item-sub">${frappe.utils.escape_html(m.combo_detail)}</div>`;
			}
			if (m.is_combo) {
				html += `<span class="badge badge-light border mt-1" style="font-size:10px">${__("Combo bundle")}</span>`;
			}
			return html;
		}

		function cpMatrixComponentCell(m) {
			const title = m.component_title || m.item_label || m.item_key || "";
			let html = `<div class="fw-medium">${frappe.utils.escape_html(title)}</div>`;
			if (m.combo_detail) {
				html += `<div class="cp-item-sub">${frappe.utils.escape_html(m.combo_detail)}</div>`;
			}
			if (m.item_key) {
				html += `<div class="cp-item-sub text-monospace small">${frappe.utils.escape_html(m.item_key)}</div>`;
			}
			if (m.is_combo) {
				html += `<span class="badge badge-light border mt-1" style="font-size:10px">${__("Combo bundle")}</span>`;
			}
			return html;
		}

		function cpMatrixComponentCellGrouped(m) {
			const title = m.component_title || m.item_label || m.item_key || "";
			let html = `<div class="cp-component-compact">`;
			html += `<div class="cp-component-name">${frappe.utils.escape_html(title)}</div>`;
			if (m.is_combo) {
				html += `<span class="badge badge-secondary border-0 mt-2" style="font-size:10px;background:#e2e8f0;color:#475569;">${__(
					"Combo bundle"
				)}</span>`;
			}
			html += `</div>`;
			return html;
		}

		function fmtContractors(list) {
			if (!list || !list.length) {
				return `<span class="cp-empty-cell">—</span>`;
			}
			const chips = list
				.map((r) => {
					const name = frappe.utils.escape_html(r.contractor_name || r.contractor || "—");
					const q = fmt_qty(r.qty);
					return `<span class="cp-chip"><span class="cp-chip-name">${name}</span><span class="cp-chip-qty">${q}</span></span>`;
				})
				.join("");
			return `<div class="cp-chip-wrap">${chips}</div>`;
		}

		function renderDetailTableGeneric($container, rows, reportRoutePrefix) {
			if (!rows || !rows.length) {
				$container.html(`<p class="text-muted mb-0">${__("No submitted report lines in this period.")}</p>`);
				return;
			}
			const th = `
				<thead><tr>
					<th>${__("Item")}</th>
					<th>${__("SO item")}</th>
					<th>${__("Combo item")}</th>
					<th>${__("Contractor")}</th>
					<th class="text-end">${__("Qty")}</th>
					<th class="text-end">${__("Reports")}</th>
					<th>${__("Sample report IDs")}</th>
				</tr></thead>`;
			const tr = rows
				.map((r) => {
					const links = (r.reports || [])
						.map(
							(n) =>
								`<a href="/app/${reportRoutePrefix}/${encodeURIComponent(n)}" target="_blank" rel="noopener noreferrer">${frappe.utils.escape_html(
									n
								)}</a>`
						)
						.join(", ");
					const cname = frappe.utils.escape_html(r.contractor_name || r.contractor || "");
					return `<tr>
					<td class="cp-item-cell">${cpDetailItemCell(r)}</td>
					<td class="small">${cpRefCell(r.so_item_label, r.so_item)}</td>
					<td class="small">${cpRefCell(r.combo_item_label, r.combo_item)}</td>
					<td><div class="cp-chip-wrap"><span class="cp-chip"><span class="cp-chip-name">${cname}</span></span></div></td>
					<td class="text-end cp-chip-qty">${fmt_qty(r.qty)}</td>
					<td class="text-end">${r.report_count || 0}</td>
					<td class="small">${links}</td>
				</tr>`;
				})
				.join("");
			$container.html(
				`<div class="table-responsive rounded border" style="border-color:#e2e8f0!important;"><table class="table table-hover table-sm mb-0 cp-table">${th}<tbody>${tr}</tbody></table></div>`
			);
		}

		function renderMatrixGrouped($container, groups) {
			const intro = ``;

			const blocks = groups
				.map((g) => {
					const blockClass = g.so_item ? "cp-so-block cp-so-block--sales" : "cp-so-block cp-so-block--other";
					const soHead = g.so_item
						? `<div class="cp-so-head">
							<div class="cp-so-head-label">${__("Sales order line")}</div>
							<div class="cp-so-head-title">${frappe.utils.escape_html(g.so_item_label || "")}</div>
							<div class="cp-so-head-code">${frappe.utils.escape_html(g.so_item)}</div>
						</div>`
						: `<div class="cp-so-head cp-so-head--warn">
							<div class="cp-so-head-label">${__("Group")}</div>
							<div class="cp-so-head-title">${frappe.utils.escape_html(g.so_item_label || "")}</div>
						</div>`;

					const th = `<thead><tr>
						<th scope="col">${__("Component")}</th>
						<th scope="col">${__("Cutting")}</th>
						<th scope="col">${__("Stitching")}</th>
						<th scope="col">${__("Packing")}</th>
					</tr></thead>`;

					const tr = (g.lines || [])
						.map(
							(m) => `<tr>
							<td class="cp-item-cell">${cpMatrixComponentCellGrouped(m)}</td>
							<td class="cp-stage-cell">${fmtContractors(m.cutting)}</td>
							<td class="cp-stage-cell">${fmtContractors(m.stitching)}</td>
							<td class="cp-stage-cell">${fmtContractors(m.packing)}</td>
						</tr>`
						)
						.join("");

					return `<div class="${blockClass}">
						${soHead}
						<div class="table-responsive cp-so-table-wrap"><table class="table table-hover table-sm mb-0 cp-table cp-table-grouped">${th}<tbody>${tr}</tbody></table></div>
					</div>`;
				})
				.join("");

			$container.html(intro + `<div class="cp-matrix-groups">${blocks}</div>`);
		}

		function renderMatrix($container, data) {
			const groups = data.item_matrix_groups;
			const matrix = data.item_matrix;

			if (groups && groups.length) {
				renderMatrixGrouped($container, groups);
				return;
			}

			if (!matrix || !matrix.length) {
				$container.html(`<p class="text-muted mb-0">${__("No data in this period.")}</p>`);
				return;
			}
			const th = `<thead><tr>
				<th>${__("Item")}</th>
				<th>${__("SO item")}</th>
				<th>${__("Combo item")}</th>
				<th>${__("Cutting")}</th>
				<th>${__("Stitching")}</th>
				<th>${__("Packing")}</th>
			</tr></thead>`;
			const tr = matrix
				.map(
					(m) => `<tr>
					<td class="cp-item-cell">${cpMatrixItemCell(m)}</td>
					<td class="small">${cpRefCell(m.so_item_label, m.so_item)}</td>
					<td class="small">${cpRefCell(m.combo_item_label, m.combo_item)}</td>
					<td>${fmtContractors(m.cutting)}</td>
					<td>${fmtContractors(m.stitching)}</td>
					<td>${fmtContractors(m.packing)}</td>
				</tr>`
				)
				.join("");
			$container.html(
				`<p class="text-muted small mb-3">${__(
					"SO item = sales line product; Combo item = bundle component where applicable. Contractors and quantities from submitted reports."
				)}</p>
				<div class="table-responsive rounded border" style="border-color:#e2e8f0!important;"><table class="table table-hover table-sm mb-0 cp-table">${th}<tbody>${tr}</tbody></table></div>`
			);
		}

		function linkOrUndefined(ctrl) {
			const v = ctrl.get_value();
			return v && String(v).trim() ? v : undefined;
		}

		function load() {
			const args = {
				from_date: ctrls.from_date.get_value() || frappe.datetime.month_start(),
				to_date: ctrls.to_date.get_value() || frappe.datetime.month_end(),
				customer: linkOrUndefined(ctrls.customer),
				so_item: linkOrUndefined(ctrls.cp_so_item),
				combo_item: linkOrUndefined(ctrls.cp_combo_item),
				supplier: linkOrUndefined(ctrls.cp_supplier),
			};
			$meta.text(__("Loading…"));
			frappe
				.xcall(
					"manufacturing_addon.manufacturing_addon.page.contractor_performance.contractor_performance.get_contractor_performance_data",
					args
				)
				.then((data) => {
					$meta.text(
						``
					);
					renderMatrix($matrix, data);
					renderDetailTableGeneric($cut, data.cutting, "cutting-report");
					renderDetailTableGeneric($st, data.stitching, "stitching-report");
					renderDetailTableGeneric($pk, data.packing, "packing-report");
				})
				.catch((err) => {
					console.error(err);
					$meta.text(__("Failed to load. Check console and ensure Manufacturing Addon is installed."));
					frappe.show_alert({ message: __("Could not load contractor data"), indicator: "red" });
				});
		}

		load();
	};
})();