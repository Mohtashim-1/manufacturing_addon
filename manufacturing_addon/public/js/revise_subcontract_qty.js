// Copyright (c) 2026, Manufacturing Addon and contributors
// Revise submitted PO + SCO qty (System Manager) — does not touch Stock Entry

frappe.provide("manufacturing_addon.revise_subcontract_qty");

function _fmt_qty(v, digits) {
	const n = flt(v);
	if (typeof digits === "number") {
		return n.toFixed(digits);
	}
	try {
		return format_number(n);
	} catch (e) {
		return String(n);
	}
}

manufacturing_addon.revise_subcontract_qty.open = function (opts) {
	opts = opts || {};
	const args = {};
	if (opts.subcontracting_order) args.subcontracting_order = opts.subcontracting_order;
	if (opts.purchase_order) args.purchase_order = opts.purchase_order;

	if (!args.subcontracting_order && !args.purchase_order) {
		frappe.msgprint(__("Purchase Order or Subcontracting Order is required"));
		return;
	}

	frappe.call({
		method: "manufacturing_addon.manufacturing_addon.utils.revise_subcontract_qty.get_revise_rows",
		args,
		freeze: true,
		freeze_message: __("Loading lines..."),
		callback(r) {
			if (r.exc) {
				frappe.msgprint({
					title: __("Revise Qty"),
					message: __("Could not load lines. Check Error Log / permissions (System Manager)."),
					indicator: "red",
				});
				return;
			}
			if (!r.message || !(r.message.rows || []).length) {
				frappe.msgprint(__("No subcontract lines found to revise"));
				return;
			}
			try {
				manufacturing_addon.revise_subcontract_qty.show_dialog(r.message, opts.frm);
			} catch (e) {
				console.error("revise_subcontract_qty dialog error", e);
				frappe.msgprint({
					title: __("Revise Qty"),
					message: String(e && e.message ? e.message : e),
					indicator: "red",
				});
			}
		},
		error(r) {
			frappe.msgprint({
				title: __("Revise Qty failed"),
				message: (r && r.message) || __("Request failed"),
				indicator: "red",
			});
		},
	});
};

manufacturing_addon.revise_subcontract_qty.show_dialog = function (data, frm) {
	const fields = [
		{
			fieldtype: "HTML",
			fieldname: "intro",
			options: `<div class="text-muted" style="margin-bottom:8px">
				${__("Updates submitted Purchase Order + Subcontracting Order only.")}<br>
				${__("Stock Entry (raw material transfer) is not changed.")}<br>
				<strong>${__("PO")}:</strong> ${frappe.utils.escape_html(data.purchase_order || "")}
				&nbsp;·&nbsp;
				<strong>${__("SCO")}:</strong> ${frappe.utils.escape_html(data.subcontracting_order || "")}
			</div>`,
		},
	];

	(data.rows || []).forEach((row, idx) => {
		fields.push({ fieldtype: "Section Break", label: row.fg_item_name || row.fg_item });
		fields.push({
			fieldtype: "Float",
			fieldname: `fg_${idx}`,
			label: __("Finished Qty ({0})", [row.uom || "m"]),
			default: row.current_fg_qty,
			reqd: 1,
		});
		fields.push({ fieldtype: "Column Break" });
		fields.push({
			fieldtype: "Float",
			fieldname: `svc_${idx}`,
			label: __("Service Qty (Kg / charges)"),
			default: row.current_service_qty,
			reqd: 1,
		});
		fields.push({
			fieldtype: "HTML",
			fieldname: `meta_${idx}`,
			options: `<div class="text-muted small">
				${__("Current FG")}: ${_fmt_qty(row.current_fg_qty)}
				· ${__("Received")}: ${_fmt_qty(row.received_qty || 0)}
				· ${__("Service")}: ${_fmt_qty(row.current_service_qty)}
				${
					row.conversion_factor
						? ` · ${__("Factor")}: ${_fmt_qty(row.conversion_factor, 6)} svc/FG`
						: ""
				}
			</div>`,
		});
	});

	fields.push({ fieldtype: "Section Break", label: __("Remarks") });
	fields.push({
		fieldtype: "Small Text",
		fieldname: "remarks",
		label: __("Reason / note"),
		default: __("Yield variance — revise qty without amend"),
	});

	const d = new frappe.ui.Dialog({
		title: __("Revise Subcontract Qty"),
		size: "large",
		fields,
		primary_action_label: __("Update PO + SCO"),
		primary_action(values) {
			const payload = (data.rows || []).map((row, idx) => {
				const new_fg = flt(values[`fg_${idx}`]);
				let new_svc = flt(values[`svc_${idx}`]);
				if (
					Math.abs(new_fg - flt(row.current_fg_qty)) > 0.0001 &&
					Math.abs(new_svc - flt(row.current_service_qty)) < 0.0001 &&
					flt(row.conversion_factor)
				) {
					new_svc = flt(new_fg * row.conversion_factor, 3);
				}
				return {
					sco_item: row.sco_item,
					purchase_order_item: row.purchase_order_item,
					new_fg_qty: new_fg,
					new_service_qty: new_svc,
					current_service_qty: row.current_service_qty,
				};
			});

			d.hide();
			frappe.call({
				method: "manufacturing_addon.manufacturing_addon.utils.revise_subcontract_qty.apply_revise_qty",
				args: {
					subcontracting_order: data.subcontracting_order,
					purchase_order: data.purchase_order,
					rows: payload,
					remarks: values.remarks,
				},
				freeze: true,
				freeze_message: __("Updating quantities..."),
				callback(res) {
					if (!res.message) return;
					frappe.show_alert({
						message: res.message.message || __("Updated"),
						indicator: "green",
					});
					if (frm) {
						frm.reload_doc();
					}
				},
			});
		},
	});

	(data.rows || []).forEach((row, idx) => {
		const fg_field = d.fields_dict[`fg_${idx}`];
		const svc_field = d.fields_dict[`svc_${idx}`];
		if (!fg_field || !svc_field || !row.conversion_factor) return;
		fg_field.df.onchange = () => {
			const new_fg = flt(fg_field.get_value());
			svc_field.set_value(flt(new_fg * row.conversion_factor, 3));
		};
	});

	d.show();
};
