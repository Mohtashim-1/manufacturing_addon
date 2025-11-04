from frappe import _


def get_data(data=None):
	"""Dashboard data for Raw Material Issuance with connections to Stock Entry and Raw Material Transfer Planning"""
	import frappe
	frappe.log_error("Dashboard get_data called", "Dashboard Debug")
	
	if data is None:
		data = {}
	
	# Initialize if not present
	if "internal_links" not in data:
		data["internal_links"] = {}
	
	if "transactions" not in data:
		data["transactions"] = []
	
	# For direct parent document fields, use string format (not list)
	# These are direct fields on Raw Material Issuance pointing to other documents
	# Stock Entry: Raw Material Issuance has stock_entry field (direct link)
	# Raw Material Transfer Planning: Raw Material Issuance has planning field (direct link)
	data["internal_links"].update({
		# "Stock Entry": "stock_entry",
		"Raw Material Transfer Planning": "planning",
		# Sales Order excluded - may have invalid comma-separated values
		# "Sales Order": "sales_order",
	})
	
	# Add to transactions (Reference section)
	# Find or create Reference transaction group
	reference_group = None
	for transaction in data.get("transactions", []):
		if transaction.get("label") == _("Reference"):
			reference_group = transaction
			break
	
	if not reference_group:
		reference_group = {
			"label": _("Reference"),
			"items": []
		}
		data["transactions"].append(reference_group)
	
	# Add our doctypes if not already present
	# if "Stock Entry" not in reference_group["items"]:
	# 	reference_group["items"].append("Stock Entry")
	if "Raw Material Transfer Planning" not in reference_group["items"]:
		reference_group["items"].append("Raw Material Transfer Planning")
	# Sales Order removed from transactions since it's not in internal_links
	# if "Sales Order" not in reference_group["items"]:
	# 	reference_group["items"].append("Sales Order")
	
	return data
