import frappe
from erpnext.manufacturing.doctype.production_plan.production_plan import ProductionPlan as ERPNextProductionPlan


def get_default_active_bom(item_code):
	"""
	Get the default active BOM for an item.
	Returns the default BOM from item master if it's active, 
	otherwise finds the active default BOM.
	"""
	if not item_code:
		return None
	
	# First, try to get default BOM from item master
	default_bom = frappe.db.get_value("Item", item_code, "default_bom")
	
	if default_bom:
		# Check if default BOM is active
		bom_status = frappe.db.get_value(
			"BOM",
			default_bom,
			["is_active", "docstatus"],
			as_dict=True
		)
		
		if bom_status and bom_status.is_active == 1 and bom_status.docstatus == 1:
			return default_bom
	
	# If default BOM is not active or doesn't exist, find active default BOM
	bom = frappe.qb.DocType("BOM")
	active_default_bom = (
		frappe.qb.from_(bom)
		.select(bom.name)
		.where(
			(bom.item == item_code)
			& (bom.is_active == 1)
			& (bom.is_default == 1)
			& (bom.docstatus == 1)
		)
		.orderby(bom.modified, order=frappe.qb.Order.desc)
		.limit(1)
	).run()
	
	if active_default_bom:
		return active_default_bom[0][0]
	
	# If no default BOM found, get any active BOM
	active_bom = (
		frappe.qb.from_(bom)
		.select(bom.name)
		.where(
			(bom.item == item_code)
			& (bom.is_active == 1)
			& (bom.docstatus == 1)
		)
		.orderby(bom.modified, order=frappe.qb.Order.desc)
		.limit(1)
	).run()
	
	if active_bom:
		return active_bom[0][0]
	
	return None


class ProductionPlan(ERPNextProductionPlan):
	"""
	Override ProductionPlan to update BOMs to use default active BOM
	instead of the BOM from sales order if it's inactive.
	"""
	
	def add_items(self, items):
		"""
		Override add_items to update BOM to default active before adding items.
		"""
		# Update BOM in items data before processing
		for data in items:
			if data.get("bom_no") and data.get("item_code"):
				# Check if BOM from sales order is active and default
				bom_status = frappe.db.get_value(
					"BOM",
					data.bom_no,
					["is_active", "is_default", "docstatus"],
					as_dict=True
				)
				
				# If BOM is not active or not default, get the default active BOM
				if not bom_status or not (bom_status.is_active == 1 and bom_status.docstatus == 1):
					default_active_bom = get_default_active_bom(data.item_code)
					if default_active_bom:
						data.bom_no = default_active_bom
				elif bom_status.is_default != 1:
					# BOM is active but not default, check if there's a default active BOM
					default_active_bom = get_default_active_bom(data.item_code)
					if default_active_bom:
						data.bom_no = default_active_bom
		
		# Call parent method to add items
		super().add_items(items)

