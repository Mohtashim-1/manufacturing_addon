// Unreserve leftover qty when ERPNext's normal reserved-qty update blocks it.
frappe.ui.form.on("Stock Reservation Entry", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.is_new()) {
			return;
		}

		const remaining =
			flt(frm.doc.reserved_qty) -
			flt(frm.doc.delivered_qty) -
			flt(frm.doc.transferred_qty) -
			flt(frm.doc.consumed_qty);

		if (remaining <= 0) {
			return;
		}

		frm.add_custom_button(__("Unreserve Remaining"), () => {
			frappe.prompt(
				[
					{
						fieldname: "qty",
						label: __("Qty to Unreserve"),
						fieldtype: "Float",
						reqd: 1,
						default: remaining,
						description: __(
							"Max remaining on this entry: {0}. Use this when standard Update Reserved Qty fails because other stock is already reserved.",
							[remaining]
						),
					},
				],
				(values) => {
					frappe.call({
						method:
							"manufacturing_addon.manufacturing_addon.utils.rmi_stock_reservation.unreserve_remaining_qty",
						args: {
							name: frm.doc.name,
							qty: values.qty,
						},
						freeze: true,
						freeze_message: __("Unreserving..."),
						callback: () => frm.reload_doc(),
					});
				},
				__("Unreserve Remaining Qty"),
				__("Unreserve")
			);
		}, __("Actions"));
	},
});
