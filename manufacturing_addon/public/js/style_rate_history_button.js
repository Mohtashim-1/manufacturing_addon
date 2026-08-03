// Copyright (c) 2026, Manufacturing Addon and contributors
// Style Rate History button — System Manager only

(function () {
	function open_style_rate_history(opts) {
		if (!frappe.user.has_role("System Manager")) {
			frappe.msgprint(__("Only System Manager can view Style Rate History."));
			return;
		}
		frappe.route_options = opts || {};
		frappe.set_route("style-rate-history");
	}

	frappe.ui.form.on("Style", {
		refresh(frm) {
			if (!frappe.user.has_role("System Manager") || frm.is_new()) {
				return;
			}
			frm.add_custom_button(__("Style Rate History"), () => {
				open_style_rate_history({ style: frm.doc.name });
			});
		},
	});

	frappe.ui.form.on("Item", {
		refresh(frm) {
			if (!frappe.user.has_role("System Manager") || frm.is_new()) {
				return;
			}
			frm.add_custom_button(
				__("Style Rate History"),
				() => open_style_rate_history({ item: frm.doc.name }),
				__("History")
			);
		},
	});

	frappe.ui.form.on("Order Sheet", {
		refresh(frm) {
			if (!frappe.user.has_role("System Manager") || frm.is_new()) {
				return;
			}
			frm.add_custom_button(__("Style Rate History"), () => {
				open_style_rate_history({ order_sheet: frm.doc.name });
			});
		},
	});
})();
