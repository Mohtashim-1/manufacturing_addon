frappe.listview_settings["Shipment Loading"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Open Loading Desk"), () => {
			frappe.set_route("page", "shipment-loading-desk");
		});
	},
};
