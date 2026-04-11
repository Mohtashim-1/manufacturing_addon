from frappe import _


def get_data():
	return {
		"fieldname": "order_sheet",
		"transactions": [
			{
				"label": _("Production Reports"),
				"items": ["Cutting Report", "Stitching Report", "Packing Report"],
			},
		],
	}
