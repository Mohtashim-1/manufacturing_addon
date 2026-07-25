// Copyright (c) 2026, Manufacturing Addon and contributors
// Show actual Stock Entry transfers on Subcontracting Receipt,
// allow editing RM on draft, and fix supplied_items footer alignment.

frappe.ui.form.on("Subcontracting Receipt", {
	setup(frm) {
		frm.trigger("setup_supplied_items_editing");
	},

	refresh(frm) {
		frm.trigger("patch_supplied_items_footer");
		frm.trigger("setup_supplied_items_editing");
		frm.trigger("add_rm_transfer_buttons");
		frm.trigger("load_transferred_rm_summary");
		frm.trigger("align_supplied_items_totals");
	},

	onload_post_render(frm) {
		frm.trigger("patch_supplied_items_footer");
		frm.trigger("align_supplied_items_totals");
	},

	patch_supplied_items_footer(frm) {
		const grid = frm.fields_dict.supplied_items?.grid;
		if (!grid || grid.__mfa_footer_patched) return;

		const render_total_row = grid.render_total_row?.bind(grid);
		if (!render_total_row) return;

		grid.__mfa_footer_patched = true;

		// scrollable_table draws the footer before it scales column widths to the
		// container, and it adds a trailing placeholder for both the edit icon and
		// the heading gear, so the footer ends up one column too wide.
		grid.render_total_row = () => {
			grid.update_form_grid_width?.();
			render_total_row();

			const $footer = grid.wrapper.find(".grid-total-row .data-row").first();
			if (!$footer.length) return;

			if ($footer.children(".edit-icon").length) {
				$footer.children(".grid-static-col.fixed-width-column").not("[data-fieldname]").remove();
			}

			const $data_row = grid.wrapper.find(".grid-body .rows .grid-row .data-row").first();
			const width = $data_row.outerWidth();
			if (width) {
				$footer.css({ width: `${width}px`, "min-width": `${width}px` });
			}
		};
	},

	setup_supplied_items_editing(frm) {
		const grid = frm.fields_dict.supplied_items?.grid;
		if (!grid) return;

		const is_draft = frm.doc.docstatus === 0;

		// Keep ERPNext "no add rows" — use Load from Stock Transfers / edit RM instead.
		// Unlock grid editing on draft so RM item + qty can be changed when SE ≠ BOM.
		grid.static_rows = !is_draft;
		grid.sortable_status = true;

		grid.update_docfield_property("rm_item_code", "read_only", is_draft ? 0 : 1);
		grid.update_docfield_property(
			"consumed_qty",
			"read_only",
			frm.doc.__onload && frm.doc.__onload.backflush_based_on === "BOM" ? 1 : 0
		);

		if (is_draft) {
			frm.set_query("rm_item_code", "supplied_items", () => ({
				filters: { is_stock_item: 1, disabled: 0 },
			}));
		}
	},

	add_rm_transfer_buttons(frm) {
		frm.remove_custom_button(__("Show Transferred Materials"));
		frm.remove_custom_button(__("Load from Stock Transfers"));
		frm.remove_custom_button(__("Fix Consumed Qty from Transfers"));

		if (!frappe.user.has_role("System Manager")) return;
		if (!frm.doc.items?.length) return;

		// Standalone toolbar buttons (not buried in a dropdown)
		frm.add_custom_button(__("Show Transferred Materials"), () => {
			frm.trigger("show_transferred_materials_dialog");
		});

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Fix Consumed Qty from Transfers"), () => {
				frappe.confirm(
					__(
						"Rebuild Consumed Items from Stock Entries (Send to Subcontractor)? This sets the correct consumed qty for the FG received on this receipt (not the full transferred qty)."
					),
					() => frm.trigger("load_supplied_from_transfers")
				);
			}).addClass("btn-primary");
		}

		frm.trigger("inject_rm_action_button");
	},

	inject_rm_action_button(frm) {
		const $section = frm.fields_dict.reset_raw_materials_table?.$wrapper;
		if (!$section || !$section.length) return;

		$section.find(".scr-fix-from-transfers-btn").remove();
		if (!frappe.user.has_role("System Manager")) return;
		if (frm.doc.docstatus !== 0) return;

		const $btn = $(`
			<button type="button" class="btn btn-primary btn-sm scr-fix-from-transfers-btn"
				style="margin-left: 8px;">
				${__("Fix Consumed Qty from Transfers")}
			</button>
		`);
		$btn.on("click", () => {
			frappe.confirm(
				__(
					"Rebuild Consumed Items from Stock Entries (Send to Subcontractor)? This sets the correct consumed qty for the FG received on this receipt (not the full transferred qty)."
				),
				() => frm.trigger("load_supplied_from_transfers")
			);
		});

		// Place next to the standard Reset Raw Materials Table button
		const $reset = $section.find("button").first();
		if ($reset.length) {
			$reset.after($btn);
		} else {
			$section.append($btn);
		}
	},

	load_supplied_from_transfers(frm) {
		// Close open row editor first so the grid rebuilds cleanly
		frappe.ui.form.close_grid_form?.();

		frm.clear_table("supplied_items");
		frm.doc.__unsaved = true;
		if (!frm.doc.set_posting_time) {
			frm.set_value("posting_time", frappe.datetime.now_time());
		}

		// Same engine as "Reset Raw Materials Table" — proportional qty from
		// actual Stock Entry transfers (not full transferred qty).
		frm.call({
			method: "reset_raw_materials",
			doc: frm.doc,
			freeze: true,
			freeze_message: __("Loading transferred raw materials..."),
			callback(r) {
				if (r.exc) return;
				frm.trigger("stamp_transferred_qty_on_rows");
				frm.save().then(() => {
					frappe.show_alert({
						message: __(
							"Consumed Items rebuilt from Stock Transfers with correct qty for this receipt"
						),
						indicator: "green",
					});
					frm.trigger("inject_rm_action_button");
					frm.trigger("load_transferred_rm_summary");
				});
			},
		});
	},

	show_transferred_materials_dialog(frm) {
		const orders = [
			...new Set((frm.doc.items || []).map((r) => r.subcontracting_order).filter(Boolean)),
		];
		if (!orders.length) {
			frappe.msgprint(__("No Subcontracting Order on Items"));
			return;
		}

		frappe.call({
			method:
				"manufacturing_addon.manufacturing_addon.utils.subcontracting_receipt_rm.get_transferred_raw_materials",
			args: { subcontracting_orders: orders },
			freeze: true,
			callback(r) {
				const aggregated = r.message?.aggregated || [];
				if (!aggregated.length) {
					frappe.msgprint(__("No Stock Entries (Send to Subcontractor) found for linked order(s)."));
					return;
				}

				const columns = [
					{ label: __("Finished Good"), fieldname: "main_item_code", fieldtype: "Link", options: "Item", width: 220 },
					{ label: __("Raw Material"), fieldname: "rm_item_code", fieldtype: "Link", options: "Item", width: 220 },
					{ label: __("Transferred Qty"), fieldname: "qty", fieldtype: "Float", width: 120 },
					{ label: __("UOM"), fieldname: "stock_uom", fieldtype: "Data", width: 80 },
					{ label: __("Stock Entries"), fieldname: "stock_entries", fieldtype: "Data", width: 200 },
				];

				const data = aggregated.map((row) => ({
					...row,
					stock_entries: (row.stock_entries || []).join(", "),
				}));

				const d = new frappe.ui.Dialog({
					title: __("Raw Materials Transferred to Supplier"),
					size: "extra-large",
					fields: [
						{
							fieldtype: "HTML",
							fieldname: "help",
							options: `<p class="text-muted">${__(
								"These are the actual items and quantities transferred via Stock Entry for the linked Subcontracting Order(s). Use Load from Stock Transfers to put them into Consumed Items."
							)}</p>`,
						},
						{
							fieldtype: "Table",
							fieldname: "transfers",
							label: __("Transferred Materials"),
							cannot_add_rows: true,
							in_place_edit: false,
							fields: columns.map((c) => ({ ...c, in_list_view: 1, read_only: 1 })),
							data,
						},
					],
				});
				d.show();
			},
		});
	},

	load_transferred_rm_summary(frm) {
		const $wrap = frm.fields_dict.supplied_items?.$wrapper;
		if (!$wrap) return;

		$wrap.find(".scr-transferred-rm-summary").remove();

		const orders = [
			...new Set((frm.doc.items || []).map((r) => r.subcontracting_order).filter(Boolean)),
		];
		if (!orders.length || frm.is_new()) return;

		frappe.call({
			method:
				"manufacturing_addon.manufacturing_addon.utils.subcontracting_receipt_rm.get_transferred_raw_materials",
			args: { subcontracting_orders: orders },
			callback(r) {
				const aggregated = r.message?.aggregated || [];
				if (!aggregated.length) return;

				const rows_html = aggregated
					.map(
						(row) => `<tr>
							<td>${frappe.utils.escape_html(row.main_item_code || "")}</td>
							<td><strong>${frappe.utils.escape_html(row.rm_item_code || "")}</strong></td>
							<td class="text-right">${frappe.format(row.qty, { fieldtype: "Float" })}</td>
							<td>${frappe.utils.escape_html(row.stock_uom || "")}</td>
						</tr>`
					)
					.join("");

				const html = `
					<div class="scr-transferred-rm-summary" style="margin: 8px 0 12px;">
						<div class="text-muted" style="margin-bottom: 4px;">
							${__("Actually transferred (from Stock Entry)")}
						</div>
						<table class="table table-bordered table-condensed" style="margin:0;">
							<thead>
								<tr>
									<th>${__("Finished Good")}</th>
									<th>${__("Raw Material")}</th>
									<th class="text-right">${__("Transferred Qty")}</th>
									<th>${__("UOM")}</th>
								</tr>
							</thead>
							<tbody>${rows_html}</tbody>
						</table>
					</div>`;

				$wrap.find(".form-grid-container").before(html);
				frm.trigger("stamp_transferred_qty_on_rows");
			},
		});
	},

	stamp_transferred_qty_on_rows(frm) {
		const orders = [
			...new Set((frm.doc.items || []).map((r) => r.subcontracting_order).filter(Boolean)),
		];
		if (!orders.length) return;

		frappe.call({
			method:
				"manufacturing_addon.manufacturing_addon.utils.subcontracting_receipt_rm.get_transferred_qty_map",
			args: { subcontracting_orders: orders },
			callback(r) {
				const qty_map = r.message || {};
				let changed = false;
				(frm.doc.supplied_items || []).forEach((row) => {
					const key = `${row.main_item_code}::${row.rm_item_code}`;
					const qty = flt(qty_map[key] || 0);
					if (flt(row.custom_transferred_qty) !== qty) {
						row.custom_transferred_qty = qty;
						changed = true;
					}
				});
				if (changed) {
					frm.refresh_field("supplied_items");
					frm.trigger("align_supplied_items_totals");
				}
			},
		});
	},

	align_supplied_items_totals(frm) {
		const grid = frm.fields_dict.supplied_items?.grid;
		if (!grid?.wrapper) return;

		const sync = () => {
			grid.update_form_grid_width?.();
			grid.render_total_row?.();
		};

		setTimeout(sync, 100);
		setTimeout(sync, 500);
	},
});

frappe.ui.form.on("Subcontracting Receipt Supplied Item", {
	rm_item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.rm_item_code) return;

		frappe.db.get_value(
			"Item",
			row.rm_item_code,
			["item_name", "description", "stock_uom"],
			(r) => {
				if (!r) return;
				frappe.model.set_value(cdt, cdn, {
					item_name: r.item_name,
					description: r.description,
					stock_uom: r.stock_uom,
				});
			}
		);

		frm.trigger("stamp_transferred_qty_on_rows");
	},

	consumed_qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const amount = flt(row.consumed_qty) * flt(row.rate);
		frappe.model.set_value(cdt, cdn, "amount", amount);
		frm.trigger("align_supplied_items_totals");
	},

	rate(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(row.consumed_qty) * flt(row.rate));
		frm.trigger("align_supplied_items_totals");
	},
});
