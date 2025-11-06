from frappe import _


def get_data(data=None):
	if data is None:
		data = {}

	if "transactions" not in data:
		data["transactions"] = []

	if "internal_links" not in data:
		data["internal_links"] = {}
    
    

	return {
		"fieldname": "custom_production_plan",
		"transactions": [
			# {"label": _("Transactions"), "items": ["Work Order", "Material Request"]},
			# {"label": _("Subcontract"), "items": ["Purchase Order"]},
			{"label": _("Raw Material Transfer Planning"), "items": ["Raw Material Transfer Planning"]},
		],
	}
