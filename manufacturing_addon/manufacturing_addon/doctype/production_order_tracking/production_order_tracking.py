# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class ProductionOrderTracking(Document):
	def validate(self):
		self.calculate_totals()
		self.calculate_total_cartons()
		self.calculate_packing_percentage()
	
	def calculate_totals(self):
		"""Calculate all totals from child table"""
		total_quantity = 0
		total_cartons = 0
		total_cutting_plan = 0
		total_cutting_duvet = 0
		total_cutting_pillow = 0
		total_stitching_duvet = 0
		total_stitching_pillow = 0
		total_packing_ctn = 0
		total_packing_pcs = 0
		
		for row in self.items_table:
			total_quantity += row.quantity or 0
			total_cartons += row.total_cartons or 0
			total_cutting_plan += row.cutting_plan or 0
			total_cutting_duvet += row.cutting_duvet or 0
			total_cutting_pillow += row.cutting_pillow or 0
			total_stitching_duvet += row.stitching_duvet or 0
			total_stitching_pillow += row.stitching_pillow or 0
			total_packing_ctn += row.packing_ctn or 0
			total_packing_pcs += row.packing_pcs or 0
		
		self.total_quantity = total_quantity
		self.total_cartons = total_cartons
		self.total_cutting_plan = total_cutting_plan
		self.total_cutting_duvet = total_cutting_duvet
		self.total_cutting_pillow = total_cutting_pillow
		self.total_stitching_duvet = total_stitching_duvet
		self.total_stitching_pillow = total_stitching_pillow
		self.total_packing_ctn = total_packing_ctn
		self.total_packing_pcs = total_packing_pcs
	
	def calculate_total_cartons(self):
		"""Calculate total cartons for each row"""
		for row in self.items_table:
			if row.quantity and row.qty_ctn:
				if row.qty_ctn > 0:
					row.total_cartons = row.quantity / row.qty_ctn
				else:
					row.total_cartons = 0
			else:
				row.total_cartons = 0
	
	def calculate_packing_percentage(self):
		"""Calculate packing percentage for each row"""
		for row in self.items_table:
			if row.quantity and row.packing_pcs:
				if row.quantity > 0:
					row.packing_percentage = (row.packing_pcs / row.quantity) * 100
				else:
					row.packing_percentage = 0
			else:
				row.packing_percentage = 0


@frappe.whitelist()
def get_items_from_sales_order(sales_order):
	"""
	Fetch items from Sales Order and return them in a format suitable for Production Order Tracking CT
	"""
	if not sales_order:
		frappe.throw("Sales Order is required")

	# Get Sales Order document
	so = frappe.get_doc("Sales Order", sales_order)
	
	items = []
	for item in so.items:
		item_data = {
			"item": item.item_code or item.item_name,
			"quantity": item.qty or 0
		}
		
		# Fetch variant attributes from item
		attributes = {}
		
		# Get attributes from Item Variant Attribute child table
		variant_attributes = frappe.get_all(
			"Item Variant Attribute",
			filters={"parent": item.item_code},
			fields=["attribute", "attribute_value"]
		)
		
		# Convert to dictionary for easy lookup
		for attr in variant_attributes:
			attributes[attr.attribute.upper()] = attr.attribute_value
		
		# Map attributes to Production Order Tracking CT fields
		# DESIGN -> dessin
		if attributes.get("DESIGN"):
			item_data["dessin"] = attributes.get("DESIGN")
		
		# SIZE -> size_cm
		if attributes.get("SIZE"):
			item_data["size_cm"] = attributes.get("SIZE")
		
		# COLOR/COLOUR -> color
		if attributes.get("COLOR"):
			item_data["color"] = attributes.get("COLOR")
		elif attributes.get("COLOUR"):
			item_data["color"] = attributes.get("COLOUR")
		
		# EAN -> ean_code
		if attributes.get("EAN"):
			item_data["ean_code"] = attributes.get("EAN")
		
		items.append(item_data)
	
	return items

