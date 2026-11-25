// Clear stale Contractor Performance page script from desk localStorage.
(function () {
	try {
		["_page:contractor-performan", "_page:contractor-performance"].forEach((k) => {
			if (localStorage.getItem(k)) {
				localStorage.removeItem(k);
				console.log("[CP] busted desk page cache", k);
			}
		});
		console.log("[CP] cp_page_cache_bust.js active — build 2026-11-19-no-cust-sync");
	} catch (e) {
		console.warn("[CP] cache bust failed", e);
	}
})();
