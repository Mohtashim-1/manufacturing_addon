frappe.ui.form.on("Production Plan", {
	setup(frm) {
		console.log("[PP Custom] production_plan.js loaded for", frm.doc && frm.doc.name);
	},

	onload(frm) {
		frm.trigger("wrap_get_items_for_material_requests");
	},

	refresh(frm) {
		if (frm.doc.custom_order_sheet) {
			frm.add_custom_button(
				__("Order Sheet"),
				() => frappe.set_route("Form", "Order Sheet", frm.doc.custom_order_sheet),
				__("View")
			);
		}

		frm.trigger("wrap_get_items_for_material_requests");
		frm.trigger("render_excluded_mr_items");

		console.log("[PP Custom] refresh for", frm.doc && frm.doc.name, {
			docstatus: frm.doc && frm.doc.docstatus,
			status: frm.doc && frm.doc.status,
			po_items: frm.doc && frm.doc.po_items && frm.doc.po_items.length,
		});

		// Replace core button with custom button that asks for PO series
		setTimeout(() => {
			frm.page.remove_inner_button(__("Work Order / Subcontract PO"), __("Create"));
			frm.page.remove_inner_button(__("Work Order / Subcontract PO"), __("Create"));

			if (frm.doc.docstatus === 1 && frm.doc.po_items && frm.doc.status !== "Closed") {
				console.log("[PP Custom] adding custom Work Order / Subcontract PO button");
				frm.add_custom_button(
					__("Work Order / Subcontract PO"),
					() => {
						console.log("[PP Custom] make_work_order clicked for", frm.doc && frm.doc.name);
						frappe.model.with_doctype("Purchase Order", () => {
							console.log("[PP Custom] with_doctype callback entered");
							try {
								let meta = frappe.get_meta("Purchase Order");
								let docfield = null;
								if (meta && meta.get_field) {
									docfield = meta.get_field("naming_series");
								} else if (meta && meta.fields) {
									docfield = meta.fields.find((f) => f.fieldname === "naming_series");
								}
								console.log("[PP Custom] naming_series field:", docfield);
								let options = (docfield && docfield.options ? docfield.options.split("\n") : []).filter(Boolean);
								console.log("[PP Custom] options length:", options.length);

								if (!options.length) {
									console.log("[PP Custom] No PO naming series options found");
									frappe.msgprint(__("No naming series found for Purchase Order."));
									return;
								}

								console.log("[PP Custom] PO naming series options:", options);
								frappe.prompt(
									[
										{
											fieldname: "po_naming_series",
											label: __("Purchase Order Series"),
											fieldtype: "Select",
											options: options.join("\n"),
											reqd: 1,
										},
									],
									(values) => {
										console.log("[PP Custom] Selected PO series:", values && values.po_naming_series);
										frappe.call({
											method: "make_work_order",
											freeze: true,
											doc: frm.doc,
											args: { po_naming_series: values.po_naming_series },
											callback: function () {
												frm.reload_doc();
											},
										});
									},
									__("Select Purchase Order Series"),
									__("Create")
								);
								console.log("[PP Custom] Prompt opened");
							} catch (e) {
								console.error("[PP Custom] Error building prompt", e);
								frappe.msgprint(__("Error opening PO series prompt. Check console."));
							}
						});
					},
					__("Create")
				);
			} else {
				console.log("[PP Custom] conditions not met for custom button");
			}
		}, 0);
	},

	wrap_get_items_for_material_requests(frm) {
		if (frm._pp_mr_fetch_wrapped || !frm.events.get_items_for_material_requests) {
			return;
		}
		const original = frm.events.get_items_for_material_requests;
		frm.events.get_items_for_material_requests = function (frm, warehouses) {
			frappe.call({
				method:
					"erpnext.manufacturing.doctype.production_plan.production_plan.get_items_for_material_requests",
				freeze: true,
				args: {
					doc: frm.doc,
					warehouses: warehouses || [],
				},
				callback: function (r) {
					if (r.message) {
						const snapshot = (r.message || []).map((row) => ({
							item_code: row.item_code,
							item_name: row.item_name,
							quantity: row.quantity,
							uom: row.uom || row.stock_uom,
							warehouse: row.warehouse,
							material_request_type: row.material_request_type,
							description: row.description,
						}));
						frm.set_value("custom_mr_items_fetched_json", JSON.stringify(snapshot));
						frm.set_value("custom_excluded_mr_items_json", "[]");

						frm.set_value("mr_items", []);
						r.message.forEach((row) => {
							let d = frm.add_child("mr_items");
							for (let field in row) {
								if (field !== "name") {
									d[field] = row[field];
								}
							}
						});
					}
					refresh_field("mr_items");
					frm.trigger("render_excluded_mr_items");
				},
			});
		};
		// Keep a reference so we know we wrapped; original unused but intentional
		frm._pp_mr_fetch_original = original;
		frm._pp_mr_fetch_wrapped = true;
	},

	mr_items_remove(frm) {
		frm.trigger("render_excluded_mr_items");
	},

	mr_items_add(frm) {
		frm.trigger("render_excluded_mr_items");
	},

	render_excluded_mr_items(frm) {
		if (!frm.fields_dict.custom_excluded_mr_items_html) {
			return;
		}

		// Always show the section (including submitted / old plans)
		frm.set_df_property("custom_excluded_mr_items_html", "hidden", 0);
		frm.set_df_property("custom_excluded_mr_items_html", "depends_on", "");

		const wrapper = frm.fields_dict.custom_excluded_mr_items_html.$wrapper;
		wrapper.html(`<div class="text-muted" style="padding:8px 0;">${__("Loading removed purchase items...")}</div>`);

		frappe.call({
			method:
				"manufacturing_addon.manufacturing_addon.utils.production_plan_excluded_mr.get_excluded_mr_items_preview",
			args: { doc: frm.doc },
			callback: (r) => {
				if (!r.message) {
					wrapper.html(
						`<div class="text-muted">${__("Could not load removed purchase items.")}</div>`
					);
					return;
				}
				wrapper.html(r.message.html || "");
				if (r.message.used_live && r.message.fetched_count && !frm.doc.custom_mr_items_fetched_json) {
					// Keep client doc in sync after server persisted snapshot
					frm.refresh_field("custom_mr_items_fetched_json");
				}
				if (frm.fields_dict.custom_excluded_mr_items_json) {
					frm.doc.custom_excluded_mr_items_json = JSON.stringify(r.message.excluded || []);
				}
			},
			error: () => {
				wrapper.html(
					`<div class="text-danger">${__("Error loading removed purchase items.")}</div>`
				);
			},
		});
	},
});
