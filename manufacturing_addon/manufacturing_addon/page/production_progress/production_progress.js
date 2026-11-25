// Thin stub — real UI lives in public/js/production_progress_live_v3.js (app_include_js)
// so desk Page localStorage cannot keep a stale script.
try {
	localStorage.removeItem("_page:production-progress");
} catch (e) {
	/* ignore */
}

frappe.pages["production-progress"].on_page_load = function (wrapper) {
	if (window.__pp_live_on_page_load) {
		return window.__pp_live_on_page_load(wrapper);
	}
	$(wrapper)
		.find(".layout-main-section")
		.html(
			`<div style="padding:16px;">
				<p><b>${__("Production Progress failed to load the latest UI script.")}</b></p>
				<p>${__("Press Ctrl+Shift+R to hard-refresh Desk, then open this page again.")}</p>
			</div>`
		);
};
