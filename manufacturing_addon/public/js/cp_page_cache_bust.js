// Clear stale desk Page localStorage so contractor-performan picks up MultiSelect filters.
(function () {
	try {
		const keys = ["_page:contractor-performan", "_page:contractor-performance"];
		keys.forEach((k) => {
			if (localStorage.getItem(k)) {
				localStorage.removeItem(k);
				console.log("[CP] busted desk page cache", k);
			}
		});
		console.log("[CP] cp_page_cache_bust.js active — build 2026-11-19-v5");
	} catch (e) {
		console.warn("[CP] cache bust failed", e);
	}
})();
