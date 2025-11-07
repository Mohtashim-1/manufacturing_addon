from frappe import _


def get_data(data=None):
	if data is None:
		data = {}

	if "transactions" not in data:
		data["transactions"] = []

	if "internal_links" not in data:
		data["internal_links"] = {}
    
	# Return transactions for both production_plan and custom_production_plan fields
	return {
		"fieldname": "production_plan",  # Default fieldname for Work Order, Material Request, Purchase Order
		"non_standard_fieldnames": {
			"Raw Material Transfer Planning": "custom_production_plan"  # Use custom_production_plan for Raw Material Transfer Planning
		},
		"transactions": [
			{"label": _("Transactions"), "items": ["Work Order", "Material Request"]},
			{"label": _("Subcontract"), "items": ["Purchase Order"]},
			{"label": _("Raw Material Transfer Planning"), "items": ["Raw Material Transfer Planning"]},
		],
	}
