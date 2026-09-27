// Copyright (c) 2026, Manufacturing Addon and contributors
const BRR_API =
	"manufacturing_addon.manufacturing_addon.page.bom_rm_replace.bom_rm_replace";

function brr_flt(v) {
	if (typeof flt === "function") {
		return flt(v);
	}
	const n = parseFloat(v);
	return isNaN(n) ? 0 : n;
}

frappe.pages["bom-rm-replace"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Replace BOM Material"),
		single_column: true,
	});

	const state = {
		page,
		search: "",
		items: [],
		selected_item: null,
		bom: null,
		selected_rm: null,
	};

	page.set_primary_action(__("Refresh List"), () => load_items(state));
	render_shell(page, state);
	load_items(state);
};

function render_shell(page, state) {
	$(page.body).html(`
		<div class="brr-portal" style="padding:12px 16px 28px; max-width:1100px;">
			<style>
				.brr-portal .brr-hero {
					background:#0f766e; color:#fff; border-radius:10px;
					padding:14px 16px; margin-bottom:14px;
				}
				.brr-portal .brr-hero h3 { margin:0; color:#fff; font-weight:700; }
				.brr-portal .brr-hero p { margin:6px 0 0; opacity:.95; font-size:13px; color:#fff; }
				.brr-portal .brr-bar {
					display:flex; gap:10px; flex-wrap:wrap; align-items:end;
					background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px;
					padding:12px; margin-bottom:12px;
				}
				.brr-portal .brr-bar label {
					font-size:11px; font-weight:700; color:#475569; display:block; margin-bottom:2px;
				}
				.brr-portal .brr-list, .brr-portal .brr-edit {
					background:#fff; border:1px solid #cbd5e1; border-radius:8px; overflow:hidden;
				}
				.brr-portal table { width:100%; border-collapse:collapse; font-size:13px; margin:0; }
				.brr-portal th {
					background:#f1f5f9; text-align:left; padding:10px 12px;
					border-bottom:1px solid #e2e8f0; font-weight:700;
				}
				.brr-portal td { padding:10px 12px; border-bottom:1px solid #f1f5f9; vertical-align:middle; }
				.brr-portal tr.brr-row:hover { background:#f8fafc; cursor:pointer; }
				.brr-portal tr.brr-rm-selected { background:#ecfeff; }
				.brr-portal .brr-muted { color:#64748b; font-size:12px; }
				.brr-portal .brr-empty { padding:24px; text-align:center; color:#64748b; }
				.brr-portal .brr-edit-head {
					display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;
					align-items:center; padding:12px 14px; border-bottom:1px solid #e2e8f0;
					background:#ecfeff; border-left:4px solid #0f766e;
				}
				.brr-portal .brr-actions { display:flex; gap:8px; flex-wrap:wrap; align-items:center; padding:12px 14px; }
				.brr-portal .brr-edit-wrap { margin-bottom:14px; }
			</style>

			<div class="brr-hero">
				<h3>${__("Replace BOM Material")}</h3>
				<p>${__(
					"1) Select a finished item → Edit. 2) Select one raw material. 3) Choose the new material and Apply. Creates a new default BOM version."
				)}</p>
			</div>

			<div class="brr-bar">
				<div style="flex:1; min-width:220px;">
					<label>${__("Search Item")}</label>
					<input type="text" class="form-control input-sm brr-search"
						placeholder="${__("Item code or name...")}" />
				</div>
				<button class="btn btn-default btn-sm brr-search-btn">${__("Search")}</button>
			</div>

			<div class="brr-edit-wrap"></div>
			<div class="brr-list-wrap"></div>
		</div>
	`);

	const $root = $(page.body).find(".brr-portal");
	$root.find(".brr-search-btn").on("click", () => {
		state.search = ($root.find(".brr-search").val() || "").trim();
		load_items(state);
	});
	$root.find(".brr-search").on("keydown", (e) => {
		if (e.key === "Enter") {
			state.search = ($root.find(".brr-search").val() || "").trim();
			load_items(state);
		}
	});
}

function load_items(state) {
	const $wrap = $(state.page.body).find(".brr-list-wrap");
	$wrap.html(`<div class="brr-empty">${__("Loading items...")}</div>`);
	$(state.page.body).find(".brr-edit-wrap").empty();
	state.selected_item = null;
	state.bom = null;
	state.selected_rm = null;

	frappe.call({
		method: `${BRR_API}.search_fg_items`,
		args: { txt: state.search, limit: 50 },
		freeze: true,
		callback: (r) => {
			state.items = r.message || [];
			render_item_list(state);
		},
		error: () => {
			$wrap.html(`<div class="brr-empty text-danger">${__("Failed to load items")}</div>`);
		},
	});
}

function render_item_list(state) {
	const $wrap = $(state.page.body).find(".brr-list-wrap");
	if (!state.items.length) {
		$wrap.html(`<div class="brr-empty">${__("No items with a default BOM found.")}</div>`);
		return;
	}

	const rows = state.items
		.map(
			(it, idx) => `
		<tr class="brr-row" data-idx="${idx}">
			<td>
				<strong>${frappe.utils.escape_html(it.item_code)}</strong>
				<div class="brr-muted">${frappe.utils.escape_html(it.item_name || "")}</div>
			</td>
			<td class="brr-muted">${frappe.utils.escape_html(it.variant_of || "—")}</td>
			<td><a href="/desk/bom/${encodeURIComponent(it.default_bom)}" class="brr-bom-link">${frappe.utils.escape_html(
				it.default_bom
			)}</a></td>
			<td style="text-align:right;">
				<button type="button" class="btn btn-primary btn-xs brr-edit-btn">${__("Edit")}</button>
			</td>
		</tr>`
		)
		.join("");

	$wrap.html(`
		<div class="brr-list">
			<table>
				<thead>
					<tr>
						<th>${__("Finished Item")}</th>
						<th>${__("Template")}</th>
						<th>${__("Default BOM")}</th>
						<th></th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		</div>
	`);

	$wrap.find(".brr-edit-btn").on("click", function (e) {
		e.preventDefault();
		e.stopPropagation();
		const idx = cint($(this).closest("tr").attr("data-idx"));
		const row = state.items[idx];
		if (!row || !row.item_code) {
			frappe.msgprint(__("Could not read item from this row"));
			return;
		}
		open_edit(state, row.item_code);
	});

	$wrap.find("tr.brr-row").on("click", function (e) {
		if ($(e.target).closest("a,button").length) {
			return;
		}
		const idx = cint($(this).attr("data-idx"));
		const row = state.items[idx];
		if (row && row.item_code) {
			open_edit(state, row.item_code);
		}
	});
}

function open_edit(state, item_code) {
	if (!item_code) {
		frappe.msgprint(__("No item selected"));
		return;
	}

	state.selected_item = item_code;
	state.selected_rm = null;
	const $edit = $(state.page.body).find(".brr-edit-wrap");
	$edit.html(`<div class="brr-empty">${__("Loading BOM materials for {0}...", [item_code])}</div>`);

	// Scroll editor into view immediately (it sits above the list)
	try {
		$edit[0].scrollIntoView({ behavior: "smooth", block: "start" });
	} catch (e) {
		/* ignore */
	}

	frappe.call({
		method: `${BRR_API}.get_item_bom_materials`,
		args: { item_code },
		freeze: true,
		freeze_message: __("Loading BOM..."),
		callback: (r) => {
			if (!r.message) {
				$edit.html(`<div class="brr-empty text-danger">${__("No BOM data returned")}</div>`);
				return;
			}
			state.bom = r.message;
			render_edit_panel(state);
			try {
				$edit[0].scrollIntoView({ behavior: "smooth", block: "start" });
			} catch (e) {
				/* ignore */
			}
		},
		error: () => {
			$edit.html(`<div class="brr-empty text-danger">${__("Failed to load BOM")}</div>`);
		},
	});
}

function render_edit_panel(state) {
	const bom = state.bom;
	const $edit = $(state.page.body).find(".brr-edit-wrap");
	if (!bom) {
		$edit.empty();
		return;
	}

	const rows = (bom.materials || [])
		.map((m, idx) => {
			const selected = state.selected_rm === m.item_code ? "brr-rm-selected" : "";
			return `
			<tr class="brr-row ${selected}" data-rm-idx="${idx}">
				<td style="width:36px;">
					<input type="radio" name="brr_rm" ${state.selected_rm === m.item_code ? "checked" : ""} />
				</td>
				<td>
					<strong>${frappe.utils.escape_html(m.item_code)}</strong>
					<div class="brr-muted">${frappe.utils.escape_html(m.item_name || "")}</div>
				</td>
				<td style="text-align:right;">${brr_flt(m.qty)}</td>
				<td>${frappe.utils.escape_html(m.uom || m.stock_uom || "")}</td>
			</tr>`;
		})
		.join("");

	$edit.html(`
		<div class="brr-edit">
			<div class="brr-edit-head">
				<div>
					<strong>${__("Editing")}:</strong> ${frappe.utils.escape_html(bom.item_code)}
					<span class="brr-muted"> — ${frappe.utils.escape_html(bom.item_name || "")}</span>
					<div class="brr-muted">
						${__("BOM")}: <a href="/desk/bom/${encodeURIComponent(bom.bom_no)}">${frappe.utils.escape_html(
							bom.bom_no
						)}</a>
						&nbsp;|&nbsp; ${__("BOM Qty")}: ${brr_flt(bom.bom_qty)} ${frappe.utils.escape_html(bom.bom_uom || "")}
					</div>
				</div>
				<button type="button" class="btn btn-default btn-sm brr-close-edit">${__("Back to List")}</button>
			</div>
			<table>
				<thead>
					<tr>
						<th></th>
						<th>${__("Raw Material")}</th>
						<th style="text-align:right;">${__("Qty")}</th>
						<th>${__("UOM")}</th>
					</tr>
				</thead>
				<tbody>${rows || `<tr><td colspan="4" class="brr-empty">${__("No materials")}</td></tr>`}</tbody>
			</table>
			<div class="brr-actions">
				<button type="button" class="btn btn-primary btn-sm brr-replace-btn" ${
					state.selected_rm ? "" : "disabled"
				}>
					${__("Replace Selected Material")}
				</button>
				<span class="brr-muted">${__("Select a row above, then replace. Creates a new default active BOM version.")}</span>
			</div>
		</div>
	`);

	$edit.find("tr.brr-row").on("click", function () {
		const idx = cint($(this).attr("data-rm-idx"));
		const m = (bom.materials || [])[idx];
		if (!m) {
			return;
		}
		state.selected_rm = m.item_code;
		render_edit_panel(state);
	});
	$edit.find(".brr-close-edit").on("click", () => {
		state.selected_item = null;
		state.bom = null;
		state.selected_rm = null;
		$edit.empty();
	});
	$edit.find(".brr-replace-btn").on("click", () => open_replace_dialog(state));
}

function open_replace_dialog(state) {
	if (!state.selected_item || !state.selected_rm || !state.bom) {
		frappe.msgprint(__("Select a raw material first"));
		return;
	}

	const current = (state.bom.materials || []).find((m) => m.item_code === state.selected_rm);
	const d = new frappe.ui.Dialog({
		title: __("Replace Raw Material"),
		fields: [
			{
				fieldtype: "Data",
				fieldname: "old_rm",
				label: __("Current Material"),
				default: state.selected_rm,
				read_only: 1,
			},
			{
				fieldtype: "Float",
				fieldname: "old_qty",
				label: __("Current Qty"),
				default: current ? brr_flt(current.qty) : 0,
				read_only: 1,
			},
			{
				fieldtype: "Link",
				fieldname: "new_rm",
				label: __("New Material"),
				options: "Item",
				reqd: 1,
				get_query: () => ({ filters: { disabled: 0 } }),
			},
			{
				fieldtype: "Float",
				fieldname: "new_qty",
				label: __("Qty (leave blank to keep same)"),
				default: current ? brr_flt(current.qty) : 0,
			},
			{
				fieldtype: "Check",
				fieldname: "deactivate_old",
				label: __("Deactivate old BOM"),
				default: 0,
			},
		],
		primary_action_label: __("Apply Replace"),
		primary_action(values) {
			d.disable_primary_action();
			frappe.call({
				method: `${BRR_API}.replace_bom_material`,
				args: {
					item_code: state.selected_item,
					old_rm_item: state.selected_rm,
					new_rm_item: values.new_rm,
					new_qty: values.new_qty,
					deactivate_old: values.deactivate_old ? 1 : 0,
				},
				freeze: true,
				freeze_message: __("Creating new BOM..."),
				callback: (r) => {
					d.hide();
					const msg = r.message || {};
					const item = state.selected_item;
					frappe.msgprint({
						title: __("BOM Updated"),
						indicator: "green",
						message: __(
							"Replaced {0} → {1}. New default BOM: {2}",
							[
								frappe.utils.escape_html(msg.old_rm_item || ""),
								frappe.utils.escape_html(msg.new_rm_item || ""),
								`<a href="/desk/bom/${encodeURIComponent(msg.new_bom)}">${frappe.utils.escape_html(
									msg.new_bom || ""
								)}</a>`,
							]
						),
					});
					open_edit(state, item);
				},
				error: () => d.enable_primary_action(),
			});
		},
	});
	d.show();
}
