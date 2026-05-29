// Reusable contractor performance UI (same as /app/contractor-performan) for Order Sheet embed.
frappe.provide("manufacturing_addon.contractor_performance");

(function () {
	const CP = manufacturing_addon.contractor_performance;

	function cpFlt(v) {
		if (typeof flt === "function") {
			return flt(v);
		}
		const n = parseFloat(v);
		return Number.isFinite(n) ? n : 0;
	}

	function injectStyles() {
		if (document.getElementById("cp-dashboard-styles")) return;
		const css = `
			.contractor-performance-page,.contractor-performance-embed{background:#f1f5f9;padding:12px;border-radius:10px;}
			.contractor-performance-embed .cp-filters{box-shadow:0 1px 3px rgba(15,23,42,.06);border-color:#e2e8f0!important;}
			.contractor-performance-embed .cp-filter-row{display:flex;flex-wrap:wrap;align-items:flex-end;gap:10px;}
			.contractor-performance-embed .cp-tabs{border-bottom:1px solid #e2e8f0;gap:4px;}
			.contractor-performance-embed .cp-tab-btn{border:none;border-bottom:2px solid transparent;background:transparent;color:#64748b;padding:8px 12px;border-radius:6px 6px 0 0;cursor:pointer;font-size:12px;}
			.contractor-performance-embed .cp-tab-btn.active{color:#0f172a;border-bottom-color:#0f172a;font-weight:600;background:#fff;}
			.contractor-performance-embed .cp-chip-wrap{display:flex;flex-wrap:wrap;gap:8px;align-items:center;}
			.contractor-performance-embed .cp-chip{display:inline-flex;align-items:center;gap:8px;padding:5px 12px;background:#fff;border:1px solid #e2e8f0;border-radius:999px;font-size:12px;}
			.contractor-performance-embed .cp-chip-name{font-weight:500;color:#334155;max-width:min(240px,28vw);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
			.contractor-performance-embed .cp-chip-qty{font-weight:700;color:#0f172a;}
			.contractor-performance-embed .cp-empty-cell{color:#94a3b8;font-style:italic;font-size:13px;}
			.contractor-performance-embed table.cp-table{font-size:12px;border-color:#e2e8f0!important;}
			.contractor-performance-embed table.cp-table thead th{background:#e2e8f0;color:#334155;font-weight:600;padding:8px 10px;}
			.contractor-performance-embed table.cp-table td{padding:8px 10px;vertical-align:top!important;border-color:#e2e8f0!important;}
			.contractor-performance-embed .cp-item-sub{font-size:11px;color:#64748b;margin-top:4px;}
			.contractor-performance-embed .cp-matrix-groups{display:flex;flex-direction:column;gap:16px;}
			.contractor-performance-embed .cp-so-block{border-radius:10px;overflow:hidden;background:#fff;border:1px solid #cbd5e1;box-shadow:0 1px 2px rgba(15,23,42,.06);}
			.contractor-performance-embed .cp-so-block--sales{border-left:4px solid #2563eb;}
			.contractor-performance-embed .cp-so-head{padding:12px 14px;border-bottom:1px solid #e2e8f0;background:linear-gradient(180deg,#fff 0%,#f8fafc 100%);}
			.contractor-performance-embed .cp-so-head-label{font-size:10px;text-transform:uppercase;color:#64748b;font-weight:700;margin-bottom:4px;}
			.contractor-performance-embed .cp-so-head-title{font-size:14px;font-weight:600;color:#0f172a;}
			.contractor-performance-embed .cp-drill-toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px;}
			.contractor-performance-embed .cp-drill-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;}
			.contractor-performance-embed .cp-drill-card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px;cursor:pointer;}
			.contractor-performance-embed .cp-drill-card-title{font-size:13px;font-weight:600;color:#0f172a;}
			.contractor-performance-embed .cp-drill-card-qty{font-size:15px;font-weight:700;margin-top:8px;}
			.contractor-performance-embed .tab-content.cp-tab-panel{background:#fff;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;padding:12px;}
		`;
		$("<style/>", { id: "cp-dashboard-styles", text: css }).appendTo("head");
	}

	function fmtQty(v) {
		return frappe.format(v, { fieldtype: "Float" });
	}

	function cpRefCell(label, code) {
		const L = frappe.utils.escape_html(label || "");
		const C = frappe.utils.escape_html(code || "");
		if (!L && !C) return `<span class="cp-empty-cell">—</span>`;
		if (L && C && L !== C) return `<div>${L}</div><div class="cp-item-sub text-monospace">${C}</div>`;
		return `<div>${L || C}</div>`;
	}

	function cpDetailItemCell(r) {
		let html = `<div class="fw-medium">${frappe.utils.escape_html(r.item_label || "")}</div>`;
		if (r.combo_detail) html += `<div class="cp-item-sub">${frappe.utils.escape_html(r.combo_detail)}</div>`;
		if (r.is_combo) html += `<span class="badge badge-light border mt-1" style="font-size:10px">${__("Combo")}</span>`;
		return html;
	}

	function cpMatrixComponentCellGrouped(m) {
		const title = m.component_title || m.item_label || m.item_key || "";
		let html = `<div class="fw-medium">${frappe.utils.escape_html(title)}</div>`;
		if (m.is_combo) {
			html += `<span class="badge badge-secondary border-0 mt-1" style="font-size:10px;background:#e2e8f0;color:#475569;">${__("Combo bundle")}</span>`;
		}
		return html;
	}

	function articleLabel(row) {
		const parts = [row.article, row.design, row.colour].filter((v) => v && String(v).trim());
		return parts.length ? parts.join(" / ") : __("No article");
	}

	function itemDisplayLabel(row) {
		return row.item_label || row.combo_item_label || row.so_item_label || row.item_key || __("Unknown item");
	}

	function fmtContractors(list) {
		if (!list || !list.length) return `<span class="cp-empty-cell">—</span>`;
		const chips = list
			.map((r) => {
				const name = frappe.utils.escape_html(r.contractor_name || r.contractor || "—");
				return `<span class="cp-chip"><span class="cp-chip-name">${name}</span><span class="cp-chip-qty">${fmtQty(r.qty)}</span></span>`;
			})
			.join("");
		return `<div class="cp-chip-wrap">${chips}</div>`;
	}

	function groupAndSort(rows, keyFn, titleFn, qtyFn, extraFn) {
		const buckets = new Map();
		(rows || []).forEach((row) => {
			const key = keyFn(row);
			if (!key) return;
			if (!buckets.has(key)) {
				buckets.set(key, { key, title: titleFn(row), qty: 0, rows: [], extra: extraFn ? extraFn(row) : "" });
			}
			const bucket = buckets.get(key);
			bucket.qty += qtyFn(row);
			bucket.rows.push(row);
		});
		return Array.from(buckets.values()).sort((a, b) => {
			if (b.qty !== a.qty) return b.qty - a.qty;
			return String(a.title || "").localeCompare(String(b.title || ""));
		});
	}

	function drillCard(entry, nextLevelLabel) {
		const extra = entry.extra ? `<div class="cp-item-sub">${frappe.utils.escape_html(entry.extra)}</div>` : "";
		const btn = nextLevelLabel
			? `<button type="button" class="btn btn-xs btn-light border cp-drill-next">${frappe.utils.escape_html(nextLevelLabel)}</button>`
			: "";
		return `<div class="cp-drill-card" data-key="${frappe.utils.escape_html(entry.key)}">
			<div class="cp-drill-card-title">${frappe.utils.escape_html(entry.title)}</div>${extra}
			<div class="d-flex justify-content-between align-items-center mt-2">
				<div class="cp-drill-card-qty">${fmtQty(entry.qty)}</div>${btn}
			</div></div>`;
	}

	function renderContractorDrilldown($container, data) {
		const rows = [].concat(data.cutting || [], data.stitching || [], data.packing || []);
		if (!rows.length) {
			$container.html(`<p class="text-muted mb-0">${__("No contractor activity in this period.")}</p>`);
			return;
		}
		const state = { contractor: null, operation: null, item: null };

		function currentRows() {
			return rows.filter((row) => {
				if (state.contractor && row.contractor !== state.contractor) return false;
				if (state.operation && row.stage !== state.operation) return false;
				if (state.item && row.item_key !== state.item) return false;
				return true;
			});
		}

		function breadcrumbHtml() {
			const crumbs = [`<button type="button" class="btn btn-xs btn-light border cp-crumb" data-level="root">${__("Contractors")}</button>`];
			if (state.contractor) {
				const sample = rows.find((r) => r.contractor === state.contractor);
				crumbs.push(
					` / <button type="button" class="btn btn-xs btn-light border cp-crumb" data-level="contractor">${frappe.utils.escape_html(
						(sample && sample.contractor_name) || state.contractor
					)}</button>`
				);
			}
			if (state.operation) {
				crumbs.push(
					` / <button type="button" class="btn btn-xs btn-light border cp-crumb" data-level="operation">${frappe.utils.escape_html(state.operation)}</button>`
				);
			}
			if (state.item) {
				const sample = currentRows()[0] || rows.find((r) => r.item_key === state.item);
				crumbs.push(
					` / <button type="button" class="btn btn-xs btn-light border cp-crumb" data-level="item">${frappe.utils.escape_html(
						itemDisplayLabel(sample || {})
					)}</button>`
				);
			}
			return crumbs.join("");
		}

		function renderLevel() {
			let cards = [];
			let heading = "";
			let level = "contractor";

			if (!state.contractor) {
				heading = __("Click a contractor to drill into operations.");
				cards = groupAndSort(
					rows,
					(r) => r.contractor || r.contractor_name,
					(r) => r.contractor_name || r.contractor || __("Unknown contractor"),
					(r) => cpFlt(r.qty),
					() => __("Operations: Cutting, Stitching, Packing")
				);
				level = "contractor";
			} else if (!state.operation) {
				heading = __("Click an operation to see item-wise totals.");
				cards = groupAndSort(currentRows(), (r) => r.stage, (r) => r.stage, (r) => cpFlt(r.qty), null);
				level = "operation";
			} else if (!state.item) {
				heading = __("Click an item to see article-wise totals.");
				cards = groupAndSort(
					currentRows(),
					(r) => r.item_key,
					(r) => itemDisplayLabel(r),
					(r) => cpFlt(r.qty),
					(r) => r.combo_detail || articleLabel(r)
				);
				level = "item";
			} else {
				heading = __("Article-wise breakdown for the selected item.");
				cards = groupAndSort(
					currentRows(),
					(r) => [r.article || "", r.design || "", r.colour || ""].join("|"),
					(r) => articleLabel(r),
					(r) => cpFlt(r.qty),
					null
				);
				level = "article";
			}

			const toolbar = `<div class="cp-drill-toolbar"><div>${breadcrumbHtml()}</div><div class="text-muted small">${frappe.utils.escape_html(heading)}</div></div>`;
			if (!cards.length) {
				$container.html(toolbar + `<p class="text-muted mb-0">${__("No rows found for this selection.")}</p>`);
				return;
			}

			const html = cards
				.map((entry) => {
					if (level === "article") {
						return `<div class="cp-drill-card"><div class="cp-drill-card-title">${frappe.utils.escape_html(entry.title)}</div><div class="cp-drill-card-qty">${fmtQty(entry.qty)}</div></div>`;
					}
					const next =
						level === "contractor" ? __("View operations") : level === "operation" ? __("View items") : __("View articles");
					return drillCard(entry, next);
				})
				.join("");

			$container.html(toolbar + `<div class="cp-drill-grid">${html}</div>`);

			$container.find(".cp-crumb").on("click", function () {
				const target = $(this).data("level");
				if (target === "root") {
					state.contractor = state.operation = state.item = null;
				} else if (target === "contractor") {
					state.operation = state.item = null;
				} else if (target === "operation") {
					state.item = null;
				}
				renderLevel();
			});

			$container.find(".cp-drill-card").on("click", function () {
				if (level === "article") return;
				const key = $(this).data("key");
				if (level === "contractor") state.contractor = key;
				else if (level === "operation") state.operation = key;
				else if (level === "item") state.item = key;
				renderLevel();
			});
		}

		renderLevel();
	}

	function renderMatrixGrouped($container, groups) {
		const blocks = (groups || [])
			.map((g) => {
				const blockClass = g.so_item ? "cp-so-block cp-so-block--sales" : "cp-so-block";
				const soHead = g.so_item
					? `<div class="cp-so-head"><div class="cp-so-head-label">${__("Sales order line")}</div><div class="cp-so-head-title">${frappe.utils.escape_html(g.so_item_label || "")}</div><div class="cp-item-sub text-monospace">${frappe.utils.escape_html(g.so_item)}</div></div>`
					: `<div class="cp-so-head"><div class="cp-so-head-title">${frappe.utils.escape_html(g.so_item_label || "")}</div></div>`;
				const tr = (g.lines || [])
					.map(
						(m) => `<tr>
						<td>${cpMatrixComponentCellGrouped(m)}</td>
						<td>${fmtContractors(m.cutting)}</td>
						<td>${fmtContractors(m.stitching)}</td>
						<td>${fmtContractors(m.packing)}</td>
					</tr>`
					)
					.join("");
				return `<div class="${blockClass}">${soHead}<div class="table-responsive"><table class="table table-sm mb-0 cp-table"><thead><tr>
					<th>${__("Component")}</th><th>${__("Cutting")}</th><th>${__("Stitching")}</th><th>${__("Packing")}</th>
				</tr></thead><tbody>${tr}</tbody></table></div></div>`;
			})
			.join("");
		$container.html(`<div class="cp-matrix-groups">${blocks}</div>`);
	}

	function renderDetailTable($container, rows, reportRoutePrefix) {
		if (!rows || !rows.length) {
			$container.html(`<p class="text-muted mb-0">${__("No submitted report lines in this period.")}</p>`);
			return;
		}
		const tr = rows
			.map((r) => {
				const links = (r.reports || [])
					.map(
						(n) =>
							`<a href="/app/${reportRoutePrefix}/${encodeURIComponent(n)}" target="_blank">${frappe.utils.escape_html(n)}</a>`
					)
					.join(", ");
				return `<tr>
				<td>${cpDetailItemCell(r)}</td>
				<td class="small">${frappe.utils.escape_html(articleLabel(r))}</td>
				<td class="small">${cpRefCell(r.so_item_label, r.so_item)}</td>
				<td class="small">${cpRefCell(r.combo_item_label, r.combo_item)}</td>
				<td>${fmtContractors([{ contractor_name: r.contractor_name || r.contractor, qty: r.qty }])}</td>
				<td class="text-right">${fmtQty(r.qty)}</td>
				<td class="text-right">${r.report_count || 0}</td>
				<td class="small">${links}</td>
			</tr>`;
			})
			.join("");
		$container.html(
			`<div class="table-responsive"><table class="table table-sm cp-table mb-0"><thead><tr>
			<th>${__("Item")}</th><th>${__("Article")}</th><th>${__("SO item")}</th><th>${__("Combo item")}</th>
			<th>${__("Contractor")}</th><th class="text-right">${__("Qty")}</th><th class="text-right">${__("Reports")}</th><th>${__("Sample report IDs")}</th>
		</tr></thead><tbody>${tr}</tbody></table></div>`
		);
	}

	CP.render_panel = function ($container, options = {}) {
		injectStyles();
		const scopedToOrderSheet = !!(options.order_sheet && String(options.order_sheet).trim());
		const opts = {
			order_sheet: options.order_sheet || null,
			customer: options.customer || null,
			from_date: options.from_date || frappe.datetime.month_start(),
			to_date: options.to_date || frappe.datetime.month_end(),
			so_item: options.so_item || null,
			combo_item: options.combo_item || null,
			supplier: options.supplier || null,
			all_dates: scopedToOrderSheet ? true : !!options.all_dates,
			show_filters: scopedToOrderSheet ? false : options.show_filters !== false,
			title: options.title || null,
		};

		const uid = frappe.utils.get_random(8);
		const $root = $(`<div class="contractor-performance-embed contractor-performance-page" data-cp-uid="${uid}"></div>`);
		$container.empty().append($root);

		let filterHtml = "";
		if (opts.show_filters) {
			filterHtml = `
				<div class="cp-filters card border p-3 mb-3 bg-white rounded">
					<div class="cp-filter-row">
						<div class="cp-f-from"></div>
						<div class="cp-f-to"></div>
						${opts.order_sheet ? "" : `<div class="cp-f-customer"></div>`}
						<div class="ml-auto"><button type="button" class="btn btn-dark btn-sm cp-refresh">${__("Refresh")}</button></div>
					</div>
				</div>`;
		}

		const fullPageUrl = opts.order_sheet
			? `/app/contractor-performan?order_sheet=${encodeURIComponent(opts.order_sheet)}`
			: "/app/contractor-performan";
		const titleHtml = opts.title
			? `<div class="d-flex justify-content-between align-items-center mb-2">
				<h6 class="mb-0">${frappe.utils.escape_html(opts.title)}</h6>
				<a href="${fullPageUrl}" class="small">${__("Open full dashboard")}</a>
			</div>`
			: "";

		$root.html(`
			${titleHtml}
			${filterHtml}
			<p class="text-muted small cp-meta mb-2"></p>
			<ul class="nav cp-tabs mb-0" role="tablist">
				<li class="nav-item"><button type="button" class="nav-link cp-tab-btn active" data-cp-tab="cp-tab-contractor-${uid}">${__("By contractor")}</button></li>
				<li class="nav-item"><button type="button" class="nav-link cp-tab-btn" data-cp-tab="cp-tab-matrix-${uid}">${__("By item (all stages)")}</button></li>
				<li class="nav-item"><button type="button" class="nav-link cp-tab-btn" data-cp-tab="cp-tab-cutting-${uid}">${__("Cutting detail")}</button></li>
				<li class="nav-item"><button type="button" class="nav-link cp-tab-btn" data-cp-tab="cp-tab-stitching-${uid}">${__("Stitching detail")}</button></li>
				<li class="nav-item"><button type="button" class="nav-link cp-tab-btn" data-cp-tab="cp-tab-packing-${uid}">${__("Packing detail")}</button></li>
			</ul>
			<div class="tab-content cp-tab-panel">
				<div class="tab-pane fade show active" id="cp-tab-contractor-${uid}"></div>
				<div class="tab-pane fade" id="cp-tab-matrix-${uid}"></div>
				<div class="tab-pane fade" id="cp-tab-cutting-${uid}"></div>
				<div class="tab-pane fade" id="cp-tab-stitching-${uid}"></div>
				<div class="tab-pane fade" id="cp-tab-packing-${uid}"></div>
			</div>
		`);

		const ctrls = {};
		if (opts.show_filters) {
			ctrls.from_date = frappe.ui.form.make_control({
				parent: $root.find(".cp-f-from"),
				df: { fieldtype: "Date", label: __("From Date"), default: opts.from_date },
				render_input: true,
			});
			ctrls.to_date = frappe.ui.form.make_control({
				parent: $root.find(".cp-f-to"),
				df: { fieldtype: "Date", label: __("To Date"), default: opts.to_date },
				render_input: true,
			});
			if (!opts.order_sheet) {
				ctrls.customer = frappe.ui.form.make_control({
					parent: $root.find(".cp-f-customer"),
					df: { fieldtype: "Link", options: "Customer", label: __("Customer") },
					render_input: true,
				});
				if (opts.customer) ctrls.customer.set_value(opts.customer);
			}
			ctrls.from_date.set_value(opts.from_date);
			ctrls.to_date.set_value(opts.to_date);
			Object.values(ctrls).forEach((c) => c.refresh && c.refresh());
		}

		const $meta = $root.find(".cp-meta");
		const $contractor = $root.find(`#cp-tab-contractor-${uid}`);
		const $matrix = $root.find(`#cp-tab-matrix-${uid}`);
		const $cut = $root.find(`#cp-tab-cutting-${uid}`);
		const $st = $root.find(`#cp-tab-stitching-${uid}`);
		const $pk = $root.find(`#cp-tab-packing-${uid}`);

		$root.find(".cp-tabs .cp-tab-btn").on("click", function (e) {
			e.preventDefault();
			const id = $(this).attr("data-cp-tab");
			$root.find(".tab-pane").removeClass("show active");
			$root.find("#" + id).addClass("show active");
			$root.find(".cp-tab-btn").removeClass("active");
			$(this).addClass("active");
		});

		function load() {
			const args = {
				from_date: ctrls.from_date ? ctrls.from_date.get_value() : opts.from_date,
				to_date: ctrls.to_date ? ctrls.to_date.get_value() : opts.to_date,
				customer: ctrls.customer ? ctrls.customer.get_value() || undefined : opts.customer || undefined,
				order_sheet: opts.order_sheet || undefined,
				so_item: opts.so_item || undefined,
				combo_item: opts.combo_item || undefined,
				supplier: opts.supplier || undefined,
				all_dates: opts.all_dates ? 1 : 0,
			};
			console.log("[CP embed] load", args);
			$meta.text(__("Loading…"));
			frappe.call({
				method:
					"manufacturing_addon.manufacturing_addon.page.contractor_performance.contractor_performance.get_contractor_performance_data",
				args: args,
				callback: (r) => {
					try {
					const data = r.message || r || {};
					if (opts.order_sheet) {
						$meta.text(
							opts.all_dates
								? __("Order Sheet {0} — all submitted reports", [opts.order_sheet])
								: __("Order Sheet {0} · {1} to {2}", [
										opts.order_sheet,
										frappe.datetime.str_to_user(args.from_date),
										frappe.datetime.str_to_user(args.to_date),
								  ])
						);
					} else if (args.from_date && args.to_date) {
						$meta.text(
							__("{0} to {1}", [
								frappe.datetime.str_to_user(args.from_date),
								frappe.datetime.str_to_user(args.to_date),
							])
						);
					} else {
						$meta.text("");
					}
					renderContractorDrilldown($contractor, data);
					const groups = data.item_matrix_groups;
					if (groups && groups.length) {
						renderMatrixGrouped($matrix, groups);
					} else {
						$matrix.html(`<p class="text-muted mb-0">${__("No data in this period.")}</p>`);
					}
					renderDetailTable($cut, data.cutting, "cutting-report");
					renderDetailTable($st, data.stitching, "stitching-report");
					renderDetailTable($pk, data.packing, "packing-report");
					} catch (renderErr) {
						console.error("[CP embed] render failed", renderErr);
						$meta.html(`<span class="text-danger">${__("Failed to display contractor data.")}</span>`);
					}
				},
				error: (err) => {
					console.error("[CP embed] load failed", err);
					$meta.html(`<span class="text-danger">${__("Failed to load contractor data.")}</span>`);
				},
			});
		}

		$root.find(".cp-refresh").on("click", load);
		load();
		return { reload: load };
	};
})();
