frappe.ui.form.on("Production Plan", {
	setup(frm) {
		console.log("[PP Custom] production_plan.js loaded for", frm.doc && frm.doc.name);
	},

	refresh(frm) {
		console.log("[PP Custom] refresh for", frm.doc && frm.doc.name, {
			docstatus: frm.doc && frm.doc.docstatus,
			status: frm.doc && frm.doc.status,
			po_items: frm.doc && frm.doc.po_items && frm.doc.po_items.length,
		});

		// Replace core button with custom button that asks for PO series
		setTimeout(() => {
			frm.page.remove_inner_button(__("Work Order / Subcontract PO"), __("Create"));
			// Avoid duplicate custom buttons on repeated refresh
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
});
