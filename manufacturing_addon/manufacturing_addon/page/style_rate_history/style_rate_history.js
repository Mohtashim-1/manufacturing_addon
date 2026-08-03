// Copyright (c) 2026, Manufacturing Addon and contributors
// Style Rate History — Desk page (System Manager only)

frappe.pages["style-rate-history"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Style Rate History"),
		single_column: true,
	});

	wrapper.page = page;
	wrapper.style_rate_history = new StyleRateHistoryPage(page, wrapper);
};

frappe.pages["style-rate-history"].on_page_show = function (wrapper) {
	if (wrapper.style_rate_history) {
		wrapper.style_rate_history.apply_route_options();
		wrapper.style_rate_history.load();
	}
};

class StyleRateHistoryPage {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = $(wrapper).find(".layout-main-section");
		this.fields = {};
		this.setup();
	}

	setup() {
		if (!frappe.user.has_role("System Manager")) {
			this.wrapper.html(
				`<div class="text-muted" style="padding:40px;">${__(
					"Only System Manager can view Style Rate History."
				)}</div>`
			);
			return;
		}

		this.wrapper.html(`
			<div class="srh-page">
				<div class="srh-filters" style="display:flex; gap:12px; flex-wrap:wrap; align-items:flex-end; margin-bottom:16px;">
					<div style="min-width:200px;"><div class="srh-style"></div></div>
					<div style="min-width:200px;"><div class="srh-item"></div></div>
					<div style="min-width:220px;"><div class="srh-os"></div></div>
					<button class="btn btn-primary btn-sm" id="srh-refresh">${__("Refresh")}</button>
					<button class="btn btn-default btn-sm" id="srh-clear">${__("Clear")}</button>
				</div>
				<div id="srh-content" class="frappe-card" style="padding:16px;">
					<div class="text-muted">${__("Loading…")}</div>
				</div>
			</div>
		`);

		this.fields.style = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "Style",
				label: __("Style"),
				fieldname: "style",
				change: () => this.load(),
			},
			parent: this.wrapper.find(".srh-style"),
			render_input: true,
		});
		this.fields.item = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "Item",
				label: __("Item"),
				fieldname: "item",
				change: () => this.load(),
			},
			parent: this.wrapper.find(".srh-item"),
			render_input: true,
		});
		this.fields.order_sheet = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "Order Sheet",
				label: __("Order Sheet"),
				fieldname: "order_sheet",
				change: () => this.load(),
			},
			parent: this.wrapper.find(".srh-os"),
			render_input: true,
		});

		this.wrapper.find("#srh-refresh").on("click", () => this.load());
		this.wrapper.find("#srh-clear").on("click", () => {
			this.fields.style.set_value("");
			this.fields.item.set_value("");
			this.fields.order_sheet.set_value("");
			this.load();
		});

		this.apply_route_options();
		this.load();
	}

	apply_route_options() {
		const opts = frappe.route_options || {};
		if (opts.style && this.fields.style) {
			this.fields.style.set_value(opts.style);
		}
		if (opts.item && this.fields.item) {
			this.fields.item.set_value(opts.item);
		}
		if (opts.order_sheet && this.fields.order_sheet) {
			this.fields.order_sheet.set_value(opts.order_sheet);
		}
		frappe.route_options = null;
	}

	load() {
		if (!frappe.user.has_role("System Manager") || !this.fields.style) {
			return;
		}
		const $content = this.wrapper.find("#srh-content");
		$content.html(`<div class="text-muted">${__("Loading…")}</div>`);

		frappe.call({
			method:
				"manufacturing_addon.manufacturing_addon.page.style_rate_history.style_rate_history.get_history",
			args: {
				style: this.fields.style.get_value() || "",
				item: this.fields.item.get_value() || "",
				order_sheet: this.fields.order_sheet.get_value() || "",
				limit: 500,
			},
			callback: (r) => {
				const html = r.message?.html || `<div class="text-muted">${__("No data")}</div>`;
				$content.html(html);
			},
			error: () => {
				$content.html(
					`<div class="text-danger">${__("Failed to load Style Rate History.")}</div>`
				);
			},
		});
	}
}
