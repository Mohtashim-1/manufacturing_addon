// Clear stale Production Progress page script from desk localStorage.
// Without this, Frappe keeps serving an old Page script and combo date-wise never appears.
(function () {
	try {
		const key = "_page:production-progress";
		if (localStorage.getItem(key)) {
			localStorage.removeItem(key);
			console.log("[PP] busted desk page cache", key);
		}
		console.log("[PP] pp_page_cache_bust.js active — build 2026-11-19-v1");
	} catch (e) {
		console.warn("[PP] cache bust failed", e);
	}
})();
