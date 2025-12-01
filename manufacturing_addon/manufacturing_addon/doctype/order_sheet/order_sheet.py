# Copyright (c) 2024, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OrderSheet(Document):
	def validate(self):
		self.qty_per_cartoon()
		self.total()
		self.consumption()
		# self.total_qty()
	
	def qty_per_cartoon(self):
		for row in self.order_sheet_ct:
			# total_cartoons = row.total_cartoons or 0  
			quantity = row.quantity or 0  # Ensure it's not None
			qty_ctn = row.qty_ctn or 0 

			if qty_ctn > 0:  # Prevent division by zero
				row.total_cartoons = quantity / qty_ctn  # 230 / 22 = 10 
				# frappe.msgprint(f"Total Cartoons: {row.total_cartoons}")
				# frappe.errprint(f"Total Cartoons: {row.total_cartoons}")
			else:
				row.total_cartoons = 0  # Set to 0 if total_cartoons is invalid
			# 	frappe.msgprint('Total Cartoons set to 0')




	def total(self):
		quantity = 0
		total_cartoons = 0
		total_quantity_per_cartoon = 0
		for i in self.order_sheet_ct:
			quantity += i.quantity or 0
			total_cartoons += i.total_cartoons or 0
			total_quantity_per_cartoon += i.qty_ctn or 0
		self.total_quantity = quantity
		self.total_cartoon = total_cartoons
		self.total_quantity_per_cartoon = total_quantity_per_cartoon

	def consumption(self):
		total_consumption = 0
		for i in self.order_sheet_ct:
			# total_consumption += i.total_consumption
			total_consumption += i.total_consumption if i.total_consumption else 0
			if i.consumption and i.quantity:
				i.total_consumption = i.consumption * i.quantity
		self.total_consumption = total_consumption


def find_or_create_design(design_value):
	"""Find or create Stitching Design record"""
	if not design_value:
		return None
	
	# Search by design field
	existing = frappe.get_all(
		"Stitching Design",
		filters={"design": design_value},
		limit=1
	)
	
	if existing:
		return existing[0].name
	
	# Create new record
	try:
		doc = frappe.get_doc({
			"doctype": "Stitching Design",
			"design": design_value
		})
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception as e:
		frappe.log_error(f"Error creating Stitching Design: {str(e)}")
		return None


def find_or_create_colour(colour_value):
	"""Find or create Stitching Colour record"""
	if not colour_value:
		return None
	
	# Search by name (since autoname is format:{colour})
	existing = frappe.get_all(
		"Stitching Colour",
		filters={"name": colour_value},
		limit=1
	)
	
	if existing:
		return existing[0].name
	
	# Search by colour field
	existing = frappe.get_all(
		"Stitching Colour",
		filters={"colour": colour_value},
		limit=1
	)
	
	if existing:
		return existing[0].name
	
	# Create new record
	try:
		doc = frappe.get_doc({
			"doctype": "Stitching Colour",
			"colour": colour_value
		})
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception as e:
		frappe.log_error(f"Error creating Stitching Colour: {str(e)}")
		return None


def find_or_create_ean(ean_value):
	"""Find or create Ean Code record"""
	if not ean_value:
		return None
	
	# Search by name (since autoname is format:{ean_code})
	existing = frappe.get_all(
		"Ean Code",
		filters={"name": ean_value},
		limit=1
	)
	
	if existing:
		return existing[0].name
	
	# Search by ean_code field
	existing = frappe.get_all(
		"Ean Code",
		filters={"ean_code": ean_value},
		limit=1
	)
	
	if existing:
		return existing[0].name
	
	# Create new record
	try:
		doc = frappe.get_doc({
			"doctype": "Ean Code",
			"ean_code": ean_value
		})
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception as e:
		frappe.log_error(f"Error creating Ean Code: {str(e)}")
		return None


def find_or_create_gsm(gsm_value):
	"""Find or create GSM record"""
	if not gsm_value:
		return None
	
	# Search by gsm field
	existing = frappe.get_all(
		"GSM",
		filters={"gsm": gsm_value},
		limit=1
	)
	
	if existing:
		return existing[0].name
	
	# Create new record
	try:
		doc = frappe.get_doc({
			"doctype": "GSM",
			"gsm": gsm_value
		})
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception as e:
		frappe.log_error(f"Error creating GSM: {str(e)}")
		return None


def find_or_create_article(article_value):
	"""Find or create Stitching Article No record"""
	if not article_value:
		return None
	
	# Search by name (since autoname is format:{article_no})
	existing = frappe.get_all(
		"Stitching Article No",
		filters={"name": article_value},
		limit=1
	)
	
	if existing:
		return existing[0].name
	
	# Search by article_no field
	existing = frappe.get_all(
		"Stitching Article No",
		filters={"article_no": article_value},
		limit=1
	)
	
	if existing:
		return existing[0].name
	
	# Create new record
	try:
		doc = frappe.get_doc({
			"doctype": "Stitching Article No",
			"article_no": article_value
		})
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception as e:
		frappe.log_error(f"Error creating Stitching Article No: {str(e)}")
		return None


def find_or_create_size(size_value):
	"""Find or create Stitching Size record by name"""
	if not size_value:
		return None
	
	# Search by name first (since autoname format might match)
	existing = frappe.get_all(
		"Stitching Size",
		filters={"name": size_value},
		limit=1
	)
	
	if existing:
		return existing[0].name
	
	# If not found by name, return None (Size parsing is complex)
	return None


@frappe.whitelist()
def get_items_from_sales_order(sales_order):
	"""
	Fetch items from Sales Order and return them in a format suitable for Order Sheet CT
	Includes variant attributes mapping with automatic record creation
	"""
	if not sales_order:
		frappe.throw("Sales Order is required")

	# Get Sales Order document
	so = frappe.get_doc("Sales Order", sales_order)
	
	items = []
	for item in so.items:
		item_data = {
			"item_code": item.item_code,
			"item_name": item.item_name,
			"qty": item.qty,
			"uom": item.uom,
			"description": item.description,
			"rate": item.rate,
			"amount": item.amount
		}
		
		# Fetch variant attributes from item
		attributes = {}
		
		# Get attributes from Item Variant Attribute child table
		# This works for both variant items and items with attributes
		variant_attributes = frappe.get_all(
			"Item Variant Attribute",
			filters={"parent": item.item_code},
			fields=["attribute", "attribute_value"]
		)
		
		# Convert to dictionary for easy lookup
		for attr in variant_attributes:
			attributes[attr.attribute.upper()] = attr.attribute_value
		
		# Map attributes to Order Sheet CT fields with find_or_create
		# DESIGN -> design (Link to Stitching Design)
		if attributes.get("DESIGN"):
			design_name = find_or_create_design(attributes.get("DESIGN"))
			if design_name:
				item_data["design"] = design_name
		
		# EAN -> ean (Link to Ean Code)
		if attributes.get("EAN"):
			ean_name = find_or_create_ean(attributes.get("EAN"))
			if ean_name:
				item_data["ean"] = ean_name
		
		# COLOR/COLOUR/DESIGN -> colour (Link to Stitching Colour)
		colour_value = None
		if attributes.get("COLOR"):
			colour_value = attributes.get("COLOR")
		elif attributes.get("COLOUR"):
			colour_value = attributes.get("COLOUR")
		elif attributes.get("DESIGN"):
			# If DESIGN is used for colour
			colour_value = attributes.get("DESIGN")
		
		if colour_value:
			colour_name = find_or_create_colour(colour_value)
			if colour_name:
				item_data["colour"] = colour_name
		
		# ARTICLE -> stitching_article_no (Link to Stitching Article No)
		if attributes.get("ARTICLE"):
			article_name = find_or_create_article(attributes.get("ARTICLE"))
			if article_name:
				item_data["stitching_article_no"] = article_name
		
		# SIZE -> size (Link to Stitching Size)
		if attributes.get("SIZE"):
			size_name = find_or_create_size(attributes.get("SIZE"))
			if size_name:
				item_data["size"] = size_name
		
		# GSM -> gsm (Link to GSM)
		if attributes.get("GSM"):
			gsm_name = find_or_create_gsm(attributes.get("GSM"))
			if gsm_name:
				item_data["gsm"] = gsm_name
		
		items.append(item_data)
	
	return items
	

