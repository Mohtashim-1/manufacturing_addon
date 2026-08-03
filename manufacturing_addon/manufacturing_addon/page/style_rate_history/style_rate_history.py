# Copyright (c) 2026, Manufacturing Addon and contributors
# License: MIT

import frappe
from frappe import _

from manufacturing_addon.manufacturing_addon.utils.style_rate_history import get_style_rate_history


@frappe.whitelist()
def get_history(style=None, item=None, order_sheet=None, limit=500):
	"""Page API — System Manager only (enforced in get_style_rate_history)."""
	if "System Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("Only System Manager can open Style Rate History."), frappe.PermissionError)
	return get_style_rate_history(style=style, item=item, order_sheet=order_sheet, limit=limit)
