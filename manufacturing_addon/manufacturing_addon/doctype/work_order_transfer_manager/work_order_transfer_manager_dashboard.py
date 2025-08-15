# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	return {
		"fieldname": "work_order_transfer_manager",
		"non_standard_fieldnames": {
			"Raw Material Transfer": "work_order_transfer_manager",
		},
		"transactions": [
			{"label": _("Stock"), "items": ["Raw Material Transfer"]},
		],
	} 