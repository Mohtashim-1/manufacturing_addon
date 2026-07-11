/** Item Connections — Order Sheet / Cutting / Stitching / Packing via so_item child rows. */
const ITEM_PRODUCTION_CONNECTIONS = [
	"Order Sheet",
	"Cutting Report",
	"Stitching Report",
	"Checking Report",
	"Packing Report",
];
const ITEM_OPEN_COUNT_METHOD =
	"manufacturing_addon.manufacturing_addon.doctype.item.item_dashboard.get_open_count";

function ensure_item_production_connections(frm) {
	if (frm.is_new() || !frm.meta) return false;

	if (!frm.meta.__dashboard) {
		frm.meta.__dashboard = {
			fieldname: "item_code",
			transactions: [],
			internal_links: {},
			non_standard_fieldnames: {},
		};
	}

	const dash = frm.meta.__dashboard;
	dash.method = ITEM_OPEN_COUNT_METHOD;
	dash.fieldname = dash.fieldname || "item_code";
	dash.transactions = dash.transactions || [];

	let group = dash.transactions.find((g) => g.label === __("Production"));
	if (!group) {
		group = { label: __("Production"), items: [] };
		dash.transactions.push(group);
	}

	let changed = false;
	ITEM_PRODUCTION_CONNECTIONS.forEach((dt) => {
		if (!frappe.model.can_read(dt)) return;
		if (!group.items.includes(dt)) {
			group.items.push(dt);
			changed = true;
		}
	});

	if (changed && frm.dashboard) {
		frm.dashboard.data = null;
		frm.dashboard.data_rendered = false;
		frm.dashboard._fetched_counts = false;
	}

	return changed;
}

function sync_item_production_connection_links(frm) {
	const count = (frm.dashboard_data && frm.dashboard_data.count) || {};
	const internalLinks = count.internal_links_found || [];

	internalLinks.forEach((link) => {
		if (!link || !ITEM_PRODUCTION_CONNECTIONS.includes(link.doctype)) return;

		const $el = $(frm.dashboard.transactions_area).find(
			`.document-link[data-doctype="${link.doctype}"]`
		);
		if (!$el.length) return;

		const names = (link.names || []).filter(Boolean);
		if (names.length) {
			$el.attr("data-names", names.join(","));
			$el.find("a.badge-link").removeAttr("disabled");
			$el.find(".count")
				.removeClass("hidden")
				.text(cint(link.count) > 99 ? "99+" : cint(link.count || names.length));
		} else {
			$el.removeAttr("data-names");
			$el.find("a.badge-link").attr("disabled", true);
			$el.find(".count").addClass("hidden").text("");
		}
	});
}

frappe.ui.form.on("Item", {
	onload(frm) {
		ensure_item_production_connections(frm);
	},
	refresh(frm) {
		ensure_item_production_connections(frm);
	},
	dashboard_update(frm) {
		sync_item_production_connection_links(frm);
	},
});
