from frappe import _


def get_data():
	return {
		"fieldname": "packing_report",
		"non_standard_fieldnames": {
			"Stock Entry": "custom_packing_report",
		},
		"dynamic_links": {"custom_packing_report": ["Packing Report", "custom_packing_report"]},
		"transactions": [
			{"label": _("Stock Entries"), "items": ["Stock Entry"]},
		],
	}
