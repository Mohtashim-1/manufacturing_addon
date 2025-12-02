# Copyright (c) 2024, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, now_datetime


class OrderSheet(Document):
	def validate(self):
		self.qty_per_cartoon()
		self.total()
		self.consumption()
		# self.total_qty()
	
	def qty_per_cartoon(self):
		for row in self.order_sheet_ct:
			# Use planned_qty for calculations, fallback to order_qty if planned_qty is not set
			planned_qty = row.planned_qty if row.planned_qty else (row.order_qty or 0)
			qty_ctn = row.qty_ctn or 0 

			if qty_ctn > 0:  # Prevent division by zero
				row.total_cartoons = planned_qty / qty_ctn
			else:
				row.total_cartoons = 0  # Set to 0 if total_cartoons is invalid




	def total(self):
		order_quantity = 0
		planned_quantity = 0
		total_cartoons = 0
		total_quantity_per_cartoon = 0
		for i in self.order_sheet_ct:
			order_quantity += i.order_qty or 0
			planned_quantity += i.planned_qty or 0
			total_cartoons += i.total_cartoons or 0
			total_quantity_per_cartoon += i.qty_ctn or 0
		# Use planned_qty for total if available, otherwise use order_qty
		self.total_quantity = planned_quantity if planned_quantity > 0 else order_quantity
		self.total_cartoon = total_cartoons
		self.total_quantity_per_cartoon = total_quantity_per_cartoon

	def consumption(self):
		total_consumption = 0
		for i in self.order_sheet_ct:
			# Use planned_qty for consumption calculation, fallback to order_qty
			qty_for_calc = i.planned_qty if i.planned_qty else (i.order_qty or 0)
			if i.consumption and qty_for_calc:
				i.total_consumption = i.consumption * qty_for_calc
			total_consumption += i.total_consumption if i.total_consumption else 0
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


@frappe.whitelist()
def create_production_plan_from_order_sheet(order_sheet):
	"""
	Create a Production Plan from Order Sheet
	"""
	if not order_sheet:
		frappe.throw("Order Sheet is required")

	# Get Order Sheet document
	os_doc = frappe.get_doc("Order Sheet", order_sheet)
	
	if not os_doc.order_sheet_ct or len(os_doc.order_sheet_ct) == 0:
		frappe.throw("Order Sheet must have items to create Production Plan")

	# Get company from Order Sheet or default company
	company = frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw("Please set default Company in User Settings")

	# Create Production Plan
	production_plan = frappe.get_doc({
		"doctype": "Production Plan",
		"company": company,
		"customer": os_doc.customer,
		"posting_date": os_doc.posting_date_and_time.date() if os_doc.posting_date_and_time else today(),
		"get_items_from": "Sales Order" if os_doc.sales_order else "",
		"for_warehouse": "Stores - SAH",
		"po_items": []
	})

	# Add Sales Order reference if available
	if os_doc.sales_order:
		production_plan.append("sales_orders", {
			"sales_order": os_doc.sales_order
		})

	# Add items from Order Sheet CT
	for row in os_doc.order_sheet_ct:
		if not row.so_item:
			continue

		# Get item details
		item_doc = frappe.get_doc("Item", row.so_item)
		
		# Get default BOM for the item
		bom_no = None
		if item_doc.default_bom:
			bom_no = item_doc.default_bom
		else:
			# Try to find active BOM
			bom_list = frappe.get_all(
				"BOM",
				filters={
					"item": row.so_item,
					"is_active": 1,
					"is_default": 1
				},
				limit=1
			)
			if bom_list:
				bom_no = bom_list[0].name
			else:
				# Get any active BOM
				bom_list = frappe.get_all(
					"BOM",
					filters={
						"item": row.so_item,
						"is_active": 1
					},
					limit=1
				)
				if bom_list:
					bom_no = bom_list[0].name

		if not bom_no:
			frappe.msgprint(
				f"No BOM found for item {row.so_item}. Skipping this item.",
				indicator="orange",
				title="BOM Not Found"
			)
			continue

		# Get warehouse from item defaults or company defaults
		warehouse = None
		
		# Try to get warehouse from item defaults (per company)
		item_defaults = frappe.db.get_value(
			"Item Default",
			{"parent": row.so_item, "company": company},
			"default_warehouse"
		)
		if item_defaults:
			warehouse = item_defaults
		else:
			# Get default finished goods warehouse from company
			warehouse = frappe.db.get_value("Company", company, "default_warehouse")
			if not warehouse:
				# Get any warehouse for the company
				warehouse_list = frappe.get_all(
					"Warehouse",
					filters={"company": company},
					limit=1
				)
				if warehouse_list:
					warehouse = warehouse_list[0].name

		# Use planned_qty if available, otherwise use order_qty
		planned_qty = row.planned_qty if row.planned_qty else (row.order_qty or 0)

		if planned_qty <= 0:
			continue

		# Get stock UOM from item
		stock_uom = item_doc.stock_uom
		if not stock_uom:
			stock_uom = item_doc.stock_uom or "Nos"  # Default to Nos if not set

		# Add item to Production Plan
		production_plan.append("po_items", {
			"item_code": row.so_item,
			"bom_no": bom_no,
			"planned_qty": planned_qty,
			"stock_uom": stock_uom,
			"warehouse": warehouse,
			"planned_start_date": os_doc.posting_date_and_time if os_doc.posting_date_and_time else now_datetime(),
			"sales_order": os_doc.sales_order if os_doc.sales_order else None,
			"description": item_doc.description or item_doc.item_name
		})

	if not production_plan.po_items or len(production_plan.po_items) == 0:
		frappe.throw("No valid items found to create Production Plan. Please ensure items have BOMs.")

	# Save Production Plan
	production_plan.insert(ignore_permissions=True)
	
	# Get items for Material Request
	from erpnext.manufacturing.doctype.production_plan.production_plan import get_items_for_material_requests
	
	try:
		# Reload to get fresh document
		production_plan.reload()
		
		# Call get_items_for_material_requests to populate MR items
		mr_items = get_items_for_material_requests(
			production_plan.as_dict(),
			warehouses=[{"warehouse": "Stores - SAH"}]
		)
		
		# Update Production Plan with MR items
		if mr_items and len(mr_items) > 0:
			production_plan.reload()
			production_plan.set("mr_items", [])
			for item in mr_items:
				# Convert dict to proper format for append
				production_plan.append("mr_items", item)
			production_plan.save(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(f"Error getting items for MR: {str(e)}", "Production Plan MR Items Error")
		# Continue even if MR items fail to populate
	
	return {
		"name": production_plan.name,
		"message": f"Production Plan {production_plan.name} created successfully"
	}

