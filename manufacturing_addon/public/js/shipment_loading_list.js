frappe.listview_settings["Shipment Loading"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Container Loading"), () => {
			frappe.set_route("page", "shipment-loading-desk");
		});
	},
};
