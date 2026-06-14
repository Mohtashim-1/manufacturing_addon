from frappe import _


def get_data():
	return {
		"fieldname": "order_sheet",
		"non_standard_fieldnames": {
			"Production Plan": "custom_order_sheet",
		},
		"transactions": [
			{
				"label": _("Production"),
				"items": [
					"Production Plan",
					"Cutting Report",
					"Stitching Report",
					"Checking Report",
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
