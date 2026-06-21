// Copyright (c) 2026, Manufacturing Addon and contributors

frappe.ui.form.on("Subcontracting Order", {
	refresh(frm) {
		if (!frm.doc.name) return;

		frm.add_custom_button(
			__("Complete History"),
			() => {
				frappe.route_options = { subcontracting_order: frm.doc.name };
				frappe.set_route("subcontracting-order-history");
			},
			__("View")
		);
	},
});
