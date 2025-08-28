# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	return {
		"fieldname": "custom_stock_entry_against_bom",
		"non_standard_fieldnames": {},
		"transactions": [
			{"label": _("Stock"), "items": ["Stock Entry"]},
			# {"label": _("Transfer"), "items": ["Transfer Form"]},
		],
	} 