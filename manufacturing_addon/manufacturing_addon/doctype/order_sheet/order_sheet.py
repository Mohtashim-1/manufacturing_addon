# Copyright (c) 2024, mohtashim and contributors
# For license information, please see license.txt

import frappe
import re
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


def find_or_create_standard_size(standard_size_str):
	"""Find or create Standard Size record from string like '60X70'"""
	if not standard_size_str:
		return None
	
	# Search by name first (autoname format: {lenght_in_cm}X{width_in_cm_copy})
	existing = frappe.get_all(
		"Standard Size",
		filters={"name": standard_size_str},
		limit=1
	)
	
	if existing:
		return existing[0].name
	
	# Try to parse and create
	# Format: {lenght_in_cm}X{width_in_cm_copy}
	# Example: "60X70"
	try:
		if 'X' in standard_size_str:
			parts = standard_size_str.split('X')
			if len(parts) == 2:
				lenght_in_cm = float(parts[0].strip())
				width_in_cm = float(parts[1].strip())
				
				# Create new Standard Size record
				doc = frappe.get_doc({
					"doctype": "Standard Size",
					"lenght_in_cm": lenght_in_cm,
					"width_in_cm_copy": width_in_cm
				})
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				frappe.logger().info(f"Successfully created Standard Size '{doc.name}' for '{standard_size_str}'")
				return doc.name
			else:
				frappe.log_error(f"Standard Size format invalid: '{standard_size_str}' - expected format: numberXnumber", "Standard Size Creation")
	except Exception as e:
		error_detail = str(e)[:100] if len(str(e)) > 100 else str(e)
		frappe.log_error(f"Error creating Standard Size '{standard_size_str}': {error_detail}", "Standard Size Creation")
		frappe.logger().error(f"Error creating Standard Size '{standard_size_str}': {error_detail}")
	
	return None


def find_or_create_size(size_value):
	"""
	Simple function: Item ka SIZE value se Stitching Size create karo
	Format: {lenght}X{width},{standard_size}+{flap}
	Example: "240X220,2X60X70+15"
	"""
	print(f"\n=== FIND_OR_CREATE_SIZE CALLED ===")
	print(f"SIZE Value from Item: '{size_value}'")
	
	if not size_value:
		print("ERROR: SIZE value is empty/None")
		return None
	
	# Step 1: Pehle check karo agar already exist karta hai
	existing = frappe.get_all(
		"Stitching Size",
		filters={"name": size_value},
		limit=1
	)
	
	if existing:
		print(f"✓ Found existing Stitching Size: '{existing[0].name}'")
		return existing[0].name
	
	print(f"✗ Not found, will create new Stitching Size")
	
	# Step 2: Parse karo SIZE value ko
	# Format: {lenght}X{width},{standard_size}+{flap}
	# Example: "240X220,2X60X70+15"
	try:
		print(f"\n--- Parsing SIZE: '{size_value}' ---")
		parts = size_value.split(',')
		print(f"Split by comma: {parts}")
		
		if len(parts) == 2:
			main_part = parts[0].strip()  # "240X220"
			standard_and_flap = parts[1].strip()  # "2X60X70+15"
			print(f"Main part: '{main_part}'")
			print(f"Standard and flap part: '{standard_and_flap}'")
			
			# Parse main part: lenghtXwidth (e.g., "240X220")
			lenght = None
			width = None
			if 'X' in main_part:
				length_width = main_part.split('X')
				print(f"Split main part by X: {length_width}")
				if len(length_width) == 2:
					try:
						lenght = float(length_width[0].strip())
						width = float(length_width[1].strip())
						print(f"✓ Extracted: lenght={lenght}, width={width}")
					except ValueError as e:
						print(f"✗ ERROR converting to float: {e}")
				else:
					print(f"✗ ERROR: Expected 2 parts after splitting by X, got {len(length_width)}")
			else:
				print(f"✗ ERROR: No 'X' found in main part '{main_part}'")
			
			if lenght is None or width is None:
				print(f"✗ Cannot continue - missing lenght or width")
				raise ValueError("Missing lenght or width")
			
			# Parse standard_size and flap (e.g., "2X60X70+15")
			flap = None
			standard_size = None
			
			if '+' in standard_and_flap:
				standard_flap_parts = standard_and_flap.split('+')
				print(f"Split by +: {standard_flap_parts}")
				if len(standard_flap_parts) == 2:
					standard_size_str = standard_flap_parts[0].strip()  # "2X60X70"
					print(f"Standard size string: '{standard_size_str}'")
					try:
						flap = float(standard_flap_parts[1].strip())  # "15"
						print(f"✓ Extracted flap: {flap}")
					except ValueError:
						print(f"✗ Could not convert flap to float: '{standard_flap_parts[1]}'")
					
					# Extract standard_size - simple approach: split by X and take last two parts
					# For "2X60X70", split -> ['2', '60', '70'], take last 2 -> "60X70"
					parts = standard_size_str.split('X')
					print(f"Split standard_size_str by X: {parts}")
					if len(parts) >= 2:
						# Take the last two parts
						last_two = parts[-2:]
						try:
							# Validate they are numbers
							float(last_two[0])
							float(last_two[1])
							standard_size_final = f"{last_two[0]}X{last_two[1]}"
							print(f"✓ Extracted standard_size: '{standard_size_final}' (from {len(parts)} parts)")
						except ValueError:
							print(f"✗ Last two parts are not valid numbers: {last_two}")
							standard_size_final = None
					else:
						print(f"✗ Not enough parts after splitting by X: {parts}")
						standard_size_final = None
					
					# Create/find Standard Size if we extracted one
					if standard_size_final:
						standard_size = find_or_create_standard_size(standard_size_final)
						if standard_size:
							print(f"✓ Standard Size: '{standard_size}'")
						else:
							print(f"✗ Could not create/find Standard Size '{standard_size_final}'")
					else:
						print(f"✗ No standard_size extracted from '{standard_size_str}'")
				else:
					# Only flap, no standard_size
					try:
						flap = float(standard_and_flap.strip())
					except ValueError:
						flap = None
			else:
				# No flap, might be just standard_size or nothing
				standard_size_str = standard_and_flap
				# Try to extract standard size pattern
				match = re.search(r'(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)$', standard_size_str)
				if match:
					standard_size_final = f"{match.group(1)}X{match.group(2)}"
					standard_size = find_or_create_standard_size(standard_size_final)
				else:
					# Try to find any {number}X{number} pattern
					matches = re.findall(r'(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)', standard_size_str)
					if matches:
						last_match = matches[-1]
						standard_size_final = f"{last_match[0]}X{last_match[1]}"
						standard_size = find_or_create_standard_size(standard_size_final)
			
			# Create Stitching Size record
			print(f"\n--- Creating Stitching Size ---")
			doc_data = {
				"doctype": "Stitching Size",
				"lenght": lenght,
				"width": width
			}
			print(f"Base fields: lenght={lenght}, width={width}")
			
			if flap is not None:
				doc_data["flap"] = flap
				print(f"Added flap: {flap}")
			
			if standard_size:
				doc_data["standard_size"] = standard_size
				print(f"Added standard_size: {standard_size}")
			else:
				print("No standard_size (optional field)")
			
			print(f"Final doc_data: {doc_data}")
			
			# Create the record
			try:
				doc = frappe.get_doc(doc_data)
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				print(f"✓✓✓ SUCCESS! Created Stitching Size: '{doc.name}'")
				print(f"=== END FIND_OR_CREATE_SIZE ===\n")
				return doc.name
			except (frappe.exceptions.DuplicateEntryError, Exception) as de:
				# If duplicate or any error, try to find existing record
				error_str = str(de)
				print(f"⚠ Error creating record: {error_str[:200]}")
				
				# Check if it's a duplicate error
				if "Duplicate" in error_str or "already exists" in error_str:
					print("Trying to find existing record...")
					try:
						# Search by the fields we tried to create
						filters = {
							"lenght": lenght,
							"width": width
						}
						if flap is not None:
							filters["flap"] = flap
						else:
							# If flap is None, search for records where flap is also None or not set
							filters["flap"] = ["in", [None, 0]]
						
						existing = frappe.get_all(
							"Stitching Size",
							filters=filters,
							limit=1
						)
						if existing:
							print(f"✓ Found existing duplicate: '{existing[0].name}'")
							print(f"=== END FIND_OR_CREATE_SIZE ===\n")
							return existing[0].name
						else:
							print(f"✗ Could not find existing record with filters: {filters}")
					except Exception as e2:
						print(f"✗ Error searching for existing: {str(e2)[:200]}")
				
				# If it's not a duplicate or we couldn't find it, continue to next attempt
				if not isinstance(de, frappe.exceptions.DuplicateEntryError):
					raise
			except frappe.exceptions.ValidationError as ve:
				print(f"✗ Validation Error: {str(ve)[:200]}")
				print("Trying again without standard_size...")
				# Try again without standard_size
				if "standard_size" in doc_data:
					del doc_data["standard_size"]
					print(f"Retry doc_data: {doc_data}")
				try:
					doc = frappe.get_doc(doc_data)
					doc.insert(ignore_permissions=True)
					frappe.db.commit()
					print(f"✓✓✓ SUCCESS! Created without standard_size: '{doc.name}'")
					print(f"=== END FIND_OR_CREATE_SIZE ===\n")
					return doc.name
				except Exception as e2:
					print(f"✗ Second attempt failed: {str(e2)[:200]}")
					print("Trying with minimal fields (lenght, width, flap only)...")
					# Try one more time with just lenght and width
					try:
						minimal_doc_data = {
							"doctype": "Stitching Size",
							"lenght": lenght,
							"width": width
						}
						if flap is not None:
							minimal_doc_data["flap"] = flap
						print(f"Minimal doc_data: {minimal_doc_data}")
						doc = frappe.get_doc(minimal_doc_data)
						doc.insert(ignore_permissions=True)
						frappe.db.commit()
						print(f"✓✓✓ SUCCESS! Created with minimal fields: '{doc.name}'")
						print(f"=== END FIND_OR_CREATE_SIZE ===\n")
						return doc.name
					except Exception as e3:
						print(f"✗✗✗ ALL ATTEMPTS FAILED: {str(e3)[:200]}")
						print(f"=== END FIND_OR_CREATE_SIZE (FAILED) ===\n")
						return None
			except Exception as e:
				print(f"✗✗✗ UNEXPECTED ERROR: {str(e)[:200]}")
				print(f"=== END FIND_OR_CREATE_SIZE (ERROR) ===\n")
				return None
			
	except ValueError as ve:
		# If it's a ValueError about missing lenght/width, continue to simple format parsing
		if "will try simple format" in str(ve):
			frappe.logger().info(f"Complex format parsing failed for '{size_value}', trying simple format")
			# Don't return None, continue to simple format parsing below
			pass
		else:
			# Other ValueError, log and continue to simple format
			frappe.logger().warning(f"ValueError parsing '{size_value}': {str(ve)[:100]}, trying simple format")
			pass
	except Exception as e:
		# Log with shorter message to avoid truncation
		error_detail = str(e)[:100] if len(str(e)) > 100 else str(e)
		error_msg = f"Error parsing complex format for SIZE '{size_value[:50]}': {error_detail}. Trying simple format."
		frappe.log_error(error_msg, "Stitching Size Creation")
		frappe.logger().warning(error_msg)
		# Don't return None yet, try simple format parsing below
		pass
	
	# If we get here, parsing didn't match the expected format (no comma found)
	# Try to parse as simple format: just "lenghtXwidth" or "lenghtXwidth+flap"
	if 'X' in size_value:
		try:
			# Try simple format: "240X220" or "240X220+15"
			if '+' in size_value:
				parts = size_value.split('+')
				if len(parts) == 2:
					main = parts[0].strip()
					try:
						flap_val = float(parts[1].strip())
					except:
						flap_val = None
				else:
					main = size_value
					flap_val = None
			else:
				main = size_value
				flap_val = None
			
			# Parse main part
			if 'X' in main:
				length_width = main.split('X')
				if len(length_width) == 2:
					try:
						lenght = float(length_width[0].strip())
						width = float(length_width[1].strip())
						
						# Try to create with just lenght and width
						doc_data = {
							"doctype": "Stitching Size",
							"lenght": lenght,
							"width": width
						}
						if flap_val is not None:
							doc_data["flap"] = flap_val
						
						doc = frappe.get_doc(doc_data)
						doc.insert(ignore_permissions=True)
						frappe.db.commit()
						frappe.logger().info(f"Successfully created Stitching Size '{doc.name}' from simple format '{size_value}'")
						return doc.name
					except Exception as e:
						frappe.log_error(f"Failed to create Stitching Size from simple format '{size_value}': {str(e)[:100]}", "Stitching Size Creation")
		except Exception as e:
			frappe.log_error(f"Error parsing simple format for '{size_value}': {str(e)[:100]}", "Stitching Size Creation")
	
	# Final fallback: If all parsing attempts fail, try to extract ANY numbers and create a basic record
	# This ensures we always try to create something rather than returning None
	frappe.logger().warning(f"All parsing attempts failed for SIZE '{size_value}'. Trying final fallback.")
	try:
		# Try to extract any two numbers separated by X
		numbers = re.findall(r'\d+(?:\.\d+)?', size_value)
		if len(numbers) >= 2:
			# Use first two numbers as lenght and width
			try:
				lenght = float(numbers[0])
				width = float(numbers[1])
				doc_data = {
					"doctype": "Stitching Size",
					"lenght": lenght,
					"width": width
				}
				doc = frappe.get_doc(doc_data)
				doc.insert(ignore_permissions=True)
				frappe.db.commit()
				frappe.logger().info(f"Successfully created Stitching Size '{doc.name}' using fallback extraction from '{size_value}'")
				return doc.name
			except Exception as e:
				frappe.log_error(f"Final fallback failed for SIZE '{size_value}': {str(e)[:100]}", "Stitching Size Creation")
	except Exception as e:
		frappe.log_error(f"Error in final fallback for SIZE '{size_value}': {str(e)[:100]}", "Stitching Size Creation")
	
	# If everything fails, log and return None
	frappe.log_error(f"Could not create Stitching Size for SIZE '{size_value[:50]}' - all methods failed", "Stitching Size Creation")
	frappe.logger().error(f"FAILED to create Stitching Size for SIZE '{size_value}' - returning None")
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
			size_value = attributes.get("SIZE")
			print(f"\n{'='*60}")
			print(f"PROCESSING SIZE for Item: {item.item_code}")
			print(f"SIZE Attribute Value: '{size_value}'")
			print(f"{'='*60}")
			
			try:
				size_name = find_or_create_size(size_value)
				if size_name:
					item_data["size"] = size_name
					print(f"✓✓✓ FINAL RESULT: SIZE '{size_value}' -> Stitching Size '{size_name}'")
					print(f"✓ Size field set in item_data for {item.item_code}\n")
				else:
					print(f"✗✗✗ FINAL RESULT: Failed to create/find Stitching Size for SIZE '{size_value}'")
					print(f"✗ Size field NOT set for {item.item_code}\n")
					item_code_short = item.item_code[:30] if len(item.item_code) > 30 else item.item_code
					error_msg = f"Failed to create/find Stitching Size for SIZE '{size_value[:30]}' in item {item_code_short}"
					frappe.log_error(error_msg, "Order Sheet Size Mapping")
			except Exception as e:
				print(f"✗✗✗ EXCEPTION: {str(e)[:200]}\n")
				error_detail = str(e)[:80] if len(str(e)) > 80 else str(e)
				item_code_short = item.item_code[:30] if len(item.item_code) > 30 else item.item_code
				error_msg = f"Exception processing SIZE '{size_value[:30]}' for item {item_code_short}: {error_detail}"
				frappe.log_error(error_msg, "Order Sheet Size Mapping")
		
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

