# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe import _


@frappe.whitelist()
def get_dashboard_data(customer=None, sales_order=None, order_sheet=None):
	"""
	Get dashboard data for Order Tracking page
	"""
	try:
		# Build filters
		filters = {}
		if customer:
			filters['customer'] = customer
		if sales_order:
			filters['sales_order'] = sales_order
		if order_sheet:
			filters['name'] = order_sheet
		
		# Get Order Sheets
		order_sheets = frappe.get_all(
			"Order Sheet",
			filters=filters,
			fields=["name", "customer", "sales_order", "docstatus"]
		)
		
		order_sheet_names = [os.name for os in order_sheets]
		
		if not order_sheet_names:
			return {
				"summary": {},
				"details": []
			}
		
		# Get Order Sheet CT data
		order_sheet_ct = frappe.get_all(
			"Order Sheet CT",
			filters={"parent": ["in", order_sheet_names]},
			fields=["parent", "so_item", "size", "colour", "order_qty", "planned_qty", "qty_ctn"]
		)
		
		# Get Cutting Report data
		cutting_reports = frappe.get_all(
			"Cutting Report",
			filters={"order_sheet": ["in", order_sheet_names], "docstatus": 1},
			fields=["name", "order_sheet"]
		)
		
		cutting_report_names = [cr.name for cr in cutting_reports]
		cutting_data = {}
		
		if cutting_report_names:
			cutting_report_ct = frappe.db.sql("""
				SELECT 
					cr.order_sheet,
					crct.so_item,
					crct.combo_item,
					SUM(crct.cutting_qty) as finished_qty,
					SUM(crct.planned_qty) as planned_qty
				FROM `tabCutting Report CT` crct
				LEFT JOIN `tabCutting Report` cr ON crct.parent = cr.name
				WHERE cr.order_sheet IN %s AND cr.docstatus = 1
				GROUP BY cr.order_sheet, crct.so_item, crct.combo_item
			""", (order_sheet_names,), as_dict=True)
			
			for row in cutting_report_ct:
				key = f"{row.order_sheet}||{row.so_item}||{row.combo_item or ''}"
				# Use finished_qty as the actual qty (what was actually cut)
				cutting_data[key] = {
					"qty": row.finished_qty or 0,  # Actual cutting_qty from reports
					"finished": row.finished_qty or 0,  # Same as qty (what was cut)
					"planned": row.planned_qty or 0
				}
		
		# Get Stitching Report data
		stitching_reports = frappe.get_all(
			"Stitching Report",
			filters={"order_sheet": ["in", order_sheet_names], "docstatus": 1},
			fields=["name", "order_sheet"]
		)
		
		stitching_report_names = [sr.name for sr in stitching_reports]
		stitching_data = {}
		
		if stitching_report_names:
			stitching_report_ct = frappe.db.sql("""
				SELECT 
					sr.order_sheet,
					srct.so_item,
					srct.combo_item,
					SUM(srct.stitching_qty) as finished_qty,
					SUM(srct.planned_qty) as planned_qty
				FROM `tabStitching Report CT` srct
				LEFT JOIN `tabStitching Report` sr ON srct.parent = sr.name
				WHERE sr.order_sheet IN %s AND sr.docstatus = 1
				GROUP BY sr.order_sheet, srct.so_item, srct.combo_item
			""", (order_sheet_names,), as_dict=True)
			
			for row in stitching_report_ct:
				key = f"{row.order_sheet}||{row.so_item}||{row.combo_item or ''}"
				# Use finished_qty as the actual qty (what was actually stitched)
				stitching_data[key] = {
					"qty": row.finished_qty or 0,  # Actual stitching_qty from reports
					"finished": row.finished_qty or 0,  # Same as qty (what was stitched)
					"planned": row.planned_qty or 0
				}
		
		# Get Packing Report data
		packing_reports = frappe.get_all(
			"Packing Report",
			filters={"order_sheet": ["in", order_sheet_names], "docstatus": 1},
			fields=["name", "order_sheet"]
		)
		
		packing_report_names = [pr.name for pr in packing_reports]
		packing_data = {}
		
		if packing_report_names:
			packing_report_ct = frappe.db.sql("""
				SELECT 
					pr.order_sheet,
					prct.so_item,
					prct.combo_item,
					SUM(prct.packaging_qty) as finished_qty,
					SUM(prct.planned_qty) as planned_qty
				FROM `tabPacking Report CT` prct
				LEFT JOIN `tabPacking Report` pr ON prct.parent = pr.name
				WHERE pr.order_sheet IN %s AND pr.docstatus = 1
				GROUP BY pr.order_sheet, prct.so_item, prct.combo_item
			""", (order_sheet_names,), as_dict=True)
			
			for row in packing_report_ct:
				key = f"{row.order_sheet}||{row.so_item}||{row.combo_item or ''}"
				# Use finished_qty as the actual qty (what was actually packed)
				packing_data[key] = {
					"qty": row.finished_qty or 0,  # Actual packaging_qty from reports
					"finished": row.finished_qty or 0,  # Same as qty (what was packed)
					"planned": row.planned_qty or 0
				}
		
		# Build details array with bundle items breakdown
		details = []
		total_order_qty = 0
		total_cutting_planned = 0
		total_cutting_finished = 0
		total_stitching_planned = 0
		total_stitching_finished = 0
		total_packing_planned = 0
		total_packing_finished = 0
		
		for row in order_sheet_ct:
			so_item = row.so_item
			order_sheet = row.parent
			
			# Get bundle items for this finished item
			bundle_items = []
			try:
				item_doc = frappe.get_doc("Item", so_item)
				combo_items = getattr(item_doc, 'custom_product_combo_item', [])
				
				if combo_items and len(combo_items) > 0:
					for ci in combo_items:
						bundle_items.append({
							"item": ci.item,
							"pcs": ci.pcs or 1
						})
				else:
					# Try Stitching Size
					size_value = None
					variant_attrs = frappe.get_all(
						"Item Variant Attribute",
						filters={"parent": so_item},
						fields=["attribute", "attribute_value"]
					)
					for attr in variant_attrs:
						if attr.attribute and attr.attribute.upper() == "SIZE":
							size_value = attr.attribute_value
							break
					
					if size_value:
						stitching_size = frappe.db.get_value("Stitching Size", size_value, "name")
						if stitching_size:
							stitching_size_doc = frappe.get_doc("Stitching Size", stitching_size)
							if stitching_size_doc.combo_detail and len(stitching_size_doc.combo_detail) > 0:
								for ci in stitching_size_doc.combo_detail:
									bundle_items.append({
										"item": ci.item,
										"pcs": ci.pcs or 1
									})
			except Exception as e:
				frappe.log_error(f"Error getting bundle items for {so_item}: {str(e)}", "Order Tracking Bundle Items")
			
			# If no bundle items found, add finished item as main item
			if not bundle_items:
				bundle_items.append({
					"item": so_item,
					"pcs": 1
				})
			
			# Add finished item row (parent row)
			finished_key = f"{order_sheet}||{so_item}||"
			cutting_info_finished = cutting_data.get(finished_key, {"qty": 0, "finished": 0, "planned": 0})
			stitching_info_finished = stitching_data.get(finished_key, {"qty": 0, "finished": 0, "planned": 0})
			packing_info_finished = packing_data.get(finished_key, {"qty": 0, "finished": 0, "planned": 0})
			
			# Calculate total PCS
			total_pcs = sum([bi["pcs"] for bi in bundle_items])
			
			details.append({
				"order_sheet": order_sheet,
				"item": so_item,
				"bundle_item": None,  # None means this is the finished item
				"size": row.size or "",
				"color": row.colour or "",
				"order_qty": row.order_qty or 0,
				"planned_qty": row.planned_qty or 0,
				"pcs": total_pcs,
				"cutting_qty": cutting_info_finished["qty"],
				"cutting_finished": cutting_info_finished["finished"],
				"cutting_planned": cutting_info_finished["planned"],
				"stitching_qty": stitching_info_finished["qty"],
				"stitching_finished": stitching_info_finished["finished"],
				"stitching_planned": stitching_info_finished["planned"],
				"packing_qty": packing_info_finished["qty"],
				"packing_finished": packing_info_finished["finished"],
				"packing_planned": packing_info_finished["planned"],
				"is_parent": True
			})
			
			# Add bundle items as child rows
			for bundle_item in bundle_items:
				combo_item_code = bundle_item["item"]
				bundle_pcs = bundle_item["pcs"]
				
				# Get data for this specific bundle item
				bundle_key = f"{order_sheet}||{so_item}||{combo_item_code}"
				cutting_info = cutting_data.get(bundle_key, {"qty": 0, "finished": 0, "planned": 0})
				stitching_info = stitching_data.get(bundle_key, {"qty": 0, "finished": 0, "planned": 0})
				packing_info = packing_data.get(bundle_key, {"qty": 0, "finished": 0, "planned": 0})
				
				details.append({
					"order_sheet": order_sheet,
					"item": so_item,
					"bundle_item": combo_item_code,  # This is a bundle item
					"size": "",
					"color": "",
					"order_qty": 0,  # Bundle items don't have order qty
					"planned_qty": 0,  # Bundle items don't have planned qty
					"pcs": bundle_pcs,
					"cutting_qty": cutting_info["qty"],
					"cutting_finished": cutting_info["finished"],
					"cutting_planned": cutting_info["planned"],
					"stitching_qty": stitching_info["qty"],
					"stitching_finished": stitching_info["finished"],
					"stitching_planned": stitching_info["planned"],
					"packing_qty": packing_info["qty"],
					"packing_finished": packing_info["finished"],
					"packing_planned": packing_info["planned"],
					"is_parent": False
				})
				
				# Add bundle item totals (these are the actual quantities from reports)
				total_cutting_planned += cutting_info["planned"]
				total_cutting_finished += cutting_info["finished"]
				total_stitching_planned += stitching_info["planned"]
				total_stitching_finished += stitching_info["finished"]
				total_packing_planned += packing_info["planned"]
				total_packing_finished += packing_info["finished"]
			
			# Add order_qty (only once per finished item)
			total_order_qty += row.order_qty or 0
		
		# Calculate summary
		# For progress, use finished vs planned (not vs order_qty)
		cutting_progress = (total_cutting_finished / total_cutting_planned * 100) if total_cutting_planned > 0 else 0
		stitching_progress = (total_stitching_finished / total_stitching_planned * 100) if total_stitching_planned > 0 else 0
		packing_progress = (total_packing_finished / total_packing_planned * 100) if total_packing_planned > 0 else 0
		
		# Overall progress: For finished items, get packing data from finished item rows (not bundle items)
		# Sum up packing_finished from parent rows (finished items) only
		total_packing_finished_finished_items = 0
		for detail_row in details:
			if detail_row.get("is_parent") == True:
				# Only count finished items' packing, not bundle items
				total_packing_finished_finished_items += detail_row.get("packing_finished", 0)
		
		# Overall progress = (finished items packed / total order qty) * 100
		overall_progress = (total_packing_finished_finished_items / total_order_qty * 100) if total_order_qty > 0 else 0
		
		summary = {
			"total_orders": len(order_sheet_names),
			"total_order_qty": total_order_qty,
			"cutting_planned": total_cutting_planned,
			"cutting_finished": total_cutting_finished,
			"cutting_progress": cutting_progress,
			"stitching_planned": total_stitching_planned,
			"stitching_finished": total_stitching_finished,
			"stitching_progress": stitching_progress,
			"packing_planned": total_packing_planned,
			"packing_finished": total_packing_finished,
			"packing_progress": packing_progress,
			"packing_finished_finished_items": total_packing_finished_finished_items,  # For overall progress
			"overall_progress": overall_progress
		}
		
		return {
			"summary": summary,
			"details": details
		}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Order Tracking Dashboard Error")
		frappe.throw(_("Error loading dashboard data: {0}").format(str(e)))

