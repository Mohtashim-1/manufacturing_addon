from frappe import _


def get_data():
	return {
		"fieldname": "order_sheet",
		"transactions": [
			{
				"label": _("Production"),
				"items": [
					"Cutting Report",
					"Stitching Report",
					"Packing Report",
				],
			},
			{
				"label": _("Quality"),
				"items": [
					"Daily Checking",
					"Inline Stitching",
					"Final Inspection",
				],
			},
		],
	}
