from frappe import _


def get_data(data=None):
	"""Extend Stock Entry dashboard with Raw Material Transfer Planning and Raw Material Issuance connections"""
	if data is None:
		data = {}
	
	# Initialize if not present
	if "internal_links" not in data:
		data["internal_links"] = {}
	
	if "transactions" not in data:
		data["transactions"] = []
	
	# Add custom internal links
	data["internal_links"].update({
		"Raw Material Transfer Planning": ["items", "custom_raw_material_transfer_planning"],
		"Raw Material Issuance": ["items", "custom_raw_material_transfer_issuance"],
		"Machine Parts Issuance": ["items", "custom_machine_parts_issuance"],
		"General Item Issuance": ["items", "custom_general_item_issuance"],
		"Packing Report": ["items", "custom_packing_report"],
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
	if "Raw Material Transfer Planning" not in reference_group["items"]:
		reference_group["items"].append("Raw Material Transfer Planning")
	if "Raw Material Issuance" not in reference_group["items"]:
		reference_group["items"].append("Raw Material Issuance")
	if "Machine Parts Issuance" not in reference_group["items"]:
		reference_group["items"].append("Machine Parts Issuance")
	if "General Item Issuance" not in reference_group["items"]:
		reference_group["items"].append("General Item Issuance")
	if "Packing Report" not in reference_group["items"]:
		reference_group["items"].append("Packing Report")

	
	return data

