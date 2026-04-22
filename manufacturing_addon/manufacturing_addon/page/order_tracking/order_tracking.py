# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def _get_bundle_items_for_so_item(so_item):
	"""Return bundle item definitions as [{'item': code, 'pcs': qty}, ...]."""
	if not so_item:
		return []

	bundle_items = []

	try:
		item_doc = frappe.get_doc("Item", so_item)
		combo_items = getattr(item_doc, "custom_product_combo_item", []) or []
		if combo_items:
			for row in combo_items:
				if row.item:
					bundle_items.append({"item": row.item, "pcs": row.pcs or 1})
			if bundle_items:
				return bundle_items
	except Exception:
		pass

	size_value = None
	variant_attrs = frappe.get_all(
		"Item Variant Attribute",
		filters={"parent": so_item},
		fields=["attribute", "attribute_value"],
	)
	for attr in variant_attrs:
		if attr.attribute and attr.attribute.upper() == "SIZE":
			size_value = attr.attribute_value
			break

	if not size_value:
		return []

	stitching_size = frappe.db.get_value("Stitching Size", size_value, "name")
	if not stitching_size:
		return []

	try:
		stitching_size_doc = frappe.get_doc("Stitching Size", stitching_size)
		for row in (stitching_size_doc.combo_detail or []):
			if row.item:
				bundle_items.append({"item": row.item, "pcs": row.pcs or 1})
	except Exception:
		return []

	return bundle_items


def _get_finished_item_stage_info(stage_data, order_sheet, so_item, bundle_items, default_planned_qty=0):
	"""
	Convert bundle-stage data back to finished-item equivalents.
	For finished-item rows, use the lowest normalized component qty/finished.
	A finished set is limited by the least-complete combo item.
	"""
	finished_key = f"{order_sheet}||{so_item}||"
	finished_info = stage_data.get(finished_key)

	if not bundle_items:
		return finished_info or {"qty": 0, "finished": 0, "planned": default_planned_qty or 0}

	normalized_rows = []
	for bundle_item in bundle_items:
		combo_item_code = bundle_item.get("item")
		pcs = bundle_item.get("pcs") or 1
		bundle_key = f"{order_sheet}||{so_item}||{combo_item_code}"
		info = stage_data.get(bundle_key)
		if not info:
			continue
		normalized_rows.append(
			{
				"item": combo_item_code,
				"qty": (info.get("qty") or 0) / pcs,
				"finished": (info.get("finished") or 0) / pcs,
				"planned": default_planned_qty or info.get("planned") or 0,
			}
		)

	if not normalized_rows:
		return finished_info or {"qty": 0, "finished": 0, "planned": default_planned_qty or 0}

	# When there are multiple bundle items, use DUVET qty as the primary metric
	if len(normalized_rows) > 1:
		duvet_row = next(
			(r for r in normalized_rows if (r["item"] or "").upper() == "DUVET"), None
		)
		if duvet_row:
			return {
				"qty": duvet_row["qty"],
				"finished": duvet_row["finished"],
				"planned": duvet_row["planned"],
			}

	return {
		"qty": min(row["qty"] for row in normalized_rows),
		"finished": min(row["finished"] for row in normalized_rows),
		"planned": default_planned_qty or min(row["planned"] for row in normalized_rows),
	}


@frappe.whitelist()
def get_stage_voucher_details(stage, order_sheet, so_item, bundle_item=None):
	stage = (stage or "").strip().lower()
	if stage not in {"cutting", "stitching", "packing"}:
		frappe.throw(_("Invalid stage"))

	order_sheet = (order_sheet or "").strip()
	so_item = (so_item or "").strip()
	bundle_item = (bundle_item or "").strip()

	if not order_sheet or not so_item:
		frappe.throw(_("Order Sheet and Item are required"))

	stage_config = {
		"cutting": {
			"parent_doctype": "Cutting Report",
			"child_doctype": "Cutting Report CT",
			"parent_alias": "p",
			"child_alias": "c",
			"date_field": "date",
			"qty_field": "cutting_qty",
			"total_label": "Total Cutting Till Now",
		},
		"stitching": {
			"parent_doctype": "Stitching Report",
			"child_doctype": "Stitching Report CT",
			"parent_alias": "p",
			"child_alias": "c",
			"date_field": "date",
			"qty_field": "stitching_qty",
			"total_label": "Total Stitching Till Now",
		},
		"packing": {
			"parent_doctype": "Packing Report",
			"child_doctype": "Packing Report CT",
			"parent_alias": "p",
			"child_alias": "c",
			"date_field": "date",
			"qty_field": "packaging_qty",
			"total_label": "Total Packing Till Now",
		},
	}[stage]

	combo_condition = ""
	query_values = {
		"order_sheet": order_sheet,
		"so_item": so_item,
	}

	if stage in {"cutting", "stitching"}:
		if bundle_item:
			combo_condition = "AND IFNULL(c.combo_item, '') = %(bundle_item)s"
			query_values["bundle_item"] = bundle_item
	else:
		combo_condition = ""

	rows = frappe.db.sql(
		f"""
		SELECT
			p.name AS voucher,
			p.{stage_config["date_field"]} AS voucher_date,
			c.name AS child_row_name,
			c.idx AS child_row_idx,
			c.parentfield,
			c.so_item,
			IFNULL(c.combo_item, '') AS combo_item,
			IFNULL(c.colour, '') AS colour,
			IFNULL(c.finished_size, '') AS finished_size,
			IFNULL(c.pcs, 0) AS pcs,
			IFNULL(c.order_qty, 0) AS order_qty,
			IFNULL(c.planned_qty, 0) AS planned_qty,
			IFNULL(c.{stage_config["qty_field"]}, 0) AS qty
		FROM `tab{stage_config["child_doctype"]}` c
		INNER JOIN `tab{stage_config["parent_doctype"]}` p ON c.parent = p.name
		WHERE p.docstatus = 1
			AND p.order_sheet = %(order_sheet)s
			AND c.so_item = %(so_item)s
			AND IFNULL(c.{stage_config["qty_field"]}, 0) > 0
			{combo_condition}
		ORDER BY p.{stage_config["date_field"]}, p.name, c.idx
		""",
		query_values,
		as_dict=True,
	)

	return {
		"stage": stage.title(),
		"order_sheet": order_sheet,
		"so_item": so_item,
		"bundle_item": bundle_item,
		"parent_doctype": stage_config["parent_doctype"],
		"child_doctype": stage_config["child_doctype"],
		"qty_field": stage_config["qty_field"],
		"total_label": stage_config["total_label"],
		"rows": rows,
	}


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
			print(f"\n{'='*80}")
			print(f"[Order Tracking] Fetching Cutting Report data...")
			print(f"  - Cutting Report Names: {cutting_report_names}")
			print(f"  - Order Sheet Names: {order_sheet_names}")
			print(f"{'='*80}\n")
			
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
			
			print(f"[Order Tracking] Cutting Report CT Query Results:")
			print(f"  - Total rows: {len(cutting_report_ct)}")
			for idx, row in enumerate(cutting_report_ct, 1):
				print(f"  - Row {idx}: order_sheet='{row.order_sheet}', so_item='{row.so_item}', combo_item='{row.combo_item or ''}', finished_qty={row.finished_qty}, planned_qty={row.planned_qty}")
			
			for row in cutting_report_ct:
				key = f"{row.order_sheet}||{row.so_item}||{row.combo_item or ''}"
				# Use finished_qty as the actual qty (what was actually cut)
				cutting_data[key] = {
					"qty": row.finished_qty or 0,  # Actual cutting_qty from reports
					"finished": row.finished_qty or 0,  # Same as qty (what was cut)
					"planned": row.planned_qty or 0
				}
				print(f"  - Stored cutting_data['{key}'] = {cutting_data[key]}")
			
			print(f"\n[Order Tracking] Final cutting_data keys: {list(cutting_data.keys())}")
			print(f"{'='*80}\n")
		
		# Get Stitching Report data
		stitching_reports = frappe.get_all(
			"Stitching Report",
			filters={"order_sheet": ["in", order_sheet_names], "docstatus": 1},
			fields=["name", "order_sheet"]
		)
		
		stitching_report_names = [sr.name for sr in stitching_reports]
		stitching_data = {}
		
		if stitching_report_names:
			print(f"\n{'='*80}")
			print(f"[Order Tracking] Fetching Stitching Report data...")
			print(f"  - Stitching Report Names: {stitching_report_names}")
			print(f"  - Order Sheet Names: {order_sheet_names}")
			print(f"{'='*80}\n")
			
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
			
			print(f"[Order Tracking] Stitching Report CT Query Results:")
			print(f"  - Total rows: {len(stitching_report_ct)}")
			for idx, row in enumerate(stitching_report_ct, 1):
				print(f"  - Row {idx}: order_sheet='{row.order_sheet}', so_item='{row.so_item}', combo_item='{row.combo_item or ''}', finished_qty={row.finished_qty}, planned_qty={row.planned_qty}")
			
			for row in stitching_report_ct:
				key = f"{row.order_sheet}||{row.so_item}||{row.combo_item or ''}"
				# Use finished_qty as the actual qty (what was actually stitched)
				stitching_data[key] = {
					"qty": row.finished_qty or 0,  # Actual stitching_qty from reports
					"finished": row.finished_qty or 0,  # Same as qty (what was stitched)
					"planned": row.planned_qty or 0
				}
				print(f"  - Stored stitching_data['{key}'] = {stitching_data[key]}")
			
			print(f"\n[Order Tracking] Final stitching_data keys: {list(stitching_data.keys())}")
			print(f"{'='*80}\n")
		
		# Get Packing Report data
		packing_reports = frappe.get_all(
			"Packing Report",
			filters={"order_sheet": ["in", order_sheet_names], "docstatus": 1},
			fields=["name", "order_sheet"]
		)
		
		packing_report_names = [pr.name for pr in packing_reports]
		packing_data = {}
		
		if packing_report_names:
			print(f"\n{'='*80}")
			print(f"[Order Tracking] Fetching Packing Report data...")
			print(f"  - Packing Report Names: {packing_report_names}")
			print(f"  - Order Sheet Names: {order_sheet_names}")
			print(f"{'='*80}\n")
			
			# Packing is done at finished item level, so we need to SUM all quantities
			# for a given order_sheet + so_item, regardless of combo_item
			packing_report_ct = frappe.db.sql("""
				SELECT 
					pr.order_sheet,
					prct.so_item,
					SUM(prct.packaging_qty) as finished_qty,
					SUM(prct.planned_qty) as planned_qty
				FROM `tabPacking Report CT` prct
				LEFT JOIN `tabPacking Report` pr ON prct.parent = pr.name
				WHERE pr.order_sheet IN %s AND pr.docstatus = 1
				GROUP BY pr.order_sheet, prct.so_item
			""", (order_sheet_names,), as_dict=True)
			
			print(f"[Order Tracking] Packing Report CT Query Results (Aggregated by finished item):")
			print(f"  - Total rows: {len(packing_report_ct)}")
			for idx, row in enumerate(packing_report_ct, 1):
				print(f"  - Row {idx}: order_sheet='{row.order_sheet}', so_item='{row.so_item}', finished_qty={row.finished_qty}, planned_qty={row.planned_qty}")
			
			for row in packing_report_ct:
				# For packing, we aggregate all bundle items into finished item
				# So combo_item is always empty string
				key = f"{row.order_sheet}||{row.so_item}||"
				# Use finished_qty as the actual qty (what was actually packed)
				packing_data[key] = {
					"qty": row.finished_qty or 0,  # Actual packaging_qty from reports (sum of all bundle items)
					"finished": row.finished_qty or 0,  # Same as qty (what was packed)
					"planned": row.planned_qty or 0  # Planned qty (sum of all bundle items)
				}
				print(f"  - Stored packing_data['{key}'] = {packing_data[key]}")
			
			print(f"\n[Order Tracking] Final packing_data keys: {list(packing_data.keys())}")
			print(f"{'='*80}\n")
		
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
			bundle_items = _get_bundle_items_for_so_item(so_item)
			
			# If no bundle items found, add finished item as main item
			if not bundle_items:
				bundle_items.append({
					"item": so_item,
					"pcs": 1
				})
			
			# Add finished item row (parent row)
			# For cutting and stitching, finished items don't have data (only bundle items do)
			# For packing, finished items DO have data (packing is done at finished item level)
			finished_key = f"{order_sheet}||{so_item}||"
			
			print(f"\n{'='*80}")
			print(f"[Order Tracking] Processing finished item row:")
			print(f"  - Order Sheet: {order_sheet}")
			print(f"  - SO Item: {so_item}")
			print(f"  - Finished Key: '{finished_key}'")
			print(f"  - Available packing_data keys: {list(packing_data.keys())}")
			
			cutting_info_finished = _get_finished_item_stage_info(
				cutting_data, order_sheet, so_item, bundle_items if bundle_items and bundle_items[0]["item"] != so_item else [], row.planned_qty or 0
			)
			stitching_info_finished = _get_finished_item_stage_info(
				stitching_data, order_sheet, so_item, bundle_items if bundle_items and bundle_items[0]["item"] != so_item else [], row.planned_qty or 0
			)
			# Packing is done at finished item level, so combo_item is always empty
			packing_info_finished = packing_data.get(finished_key, {"qty": 0, "finished": 0, "planned": 0})
			
			print(f"  - Cutting Info: {cutting_info_finished}")
			print(f"  - Stitching Info: {stitching_info_finished}")
			print(f"  - Packing Info: {packing_info_finished}")
			
			# Try alternative keys if main key doesn't match
			if packing_info_finished["qty"] == 0 and packing_info_finished["finished"] == 0:
				print(f"  - ⚠️ Packing data not found with key '{finished_key}', trying alternatives...")
				for alt_key in packing_data.keys():
					if order_sheet in alt_key and so_item in alt_key:
						print(f"  - Found matching key: '{alt_key}' -> {packing_data[alt_key]}")
						packing_info_finished = packing_data[alt_key]
						break
			
			print(f"  - Final Packing Info: {packing_info_finished}")
			print(f"{'='*80}\n")
			
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

			total_cutting_planned += cutting_info_finished["planned"]
			total_cutting_finished += cutting_info_finished["finished"]
			total_stitching_planned += stitching_info_finished["planned"]
			total_stitching_finished += stitching_info_finished["finished"]
			
			# Add bundle items as child rows
			# Get Order Sheet planned_qty for this finished item (to use as fallback)
			order_sheet_planned_qty = row.planned_qty or 0
			total_pcs = sum([bi["pcs"] for bi in bundle_items])
			
			for bundle_item in bundle_items:
				combo_item_code = bundle_item["item"]
				bundle_pcs = bundle_item["pcs"]
				
				# Get data for this specific bundle item
				bundle_key = f"{order_sheet}||{so_item}||{combo_item_code}"
				cutting_info = cutting_data.get(bundle_key, {"qty": 0, "finished": 0, "planned": 0})
				stitching_info = stitching_data.get(bundle_key, {"qty": 0, "finished": 0, "planned": 0})
				
				# Fix planned_qty: Use Order Sheet planned_qty if report's planned_qty seems wrong
				# For Cutting: If planned_qty is 0 or seems too high (more than Order Sheet planned_qty), use Order Sheet's planned_qty
				# The planned_qty should be the same for all bundle items (Order Sheet planned_qty)
				if cutting_info["planned"] == 0 or cutting_info["planned"] > order_sheet_planned_qty:
					# Use Order Sheet planned_qty as fallback (all bundle items share the same planned_qty)
					cutting_info["planned"] = order_sheet_planned_qty
					print(f"  - ⚠️ Fixed Cutting planned_qty for {combo_item_code}: {cutting_info['planned']} -> {order_sheet_planned_qty} (using Order Sheet planned_qty)")
				
				# For Stitching: if planned_qty is 0 or inflated by repeated voucher rows,
				# use the finished-item planned qty instead of the summed voucher planned qty.
				if stitching_info["planned"] == 0 or stitching_info["planned"] > order_sheet_planned_qty:
					if cutting_info["planned"] > 0:
						stitching_info["planned"] = cutting_info["planned"]
						print(f"  - ⚠️ Fixed Stitching planned_qty for {combo_item_code}: {stitching_info['planned']} -> {cutting_info['planned']} (using Cutting planned_qty)")
					elif order_sheet_planned_qty > 0:
						stitching_info["planned"] = order_sheet_planned_qty
						print(f"  - ⚠️ Fixed Stitching planned_qty for {combo_item_code}: {stitching_info['planned']} -> {order_sheet_planned_qty} (using Order Sheet planned_qty)")
				# Packing is done at finished item level, not bundle item level
				# So bundle items don't have packing data
				
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
					"packing_qty": 0,  # Packing is not done at bundle item level
					"packing_finished": 0,  # Packing is not done at bundle item level
					"packing_planned": 0,  # Packing is not done at bundle item level
					"is_parent": False
				})
				
			# Add packing totals from finished item (packing is done at finished item level)
			total_packing_planned += packing_info_finished["planned"]
			total_packing_finished += packing_info_finished["finished"]
			
			print(f"\n[Progress Calc] Finished Item Packing:")
			print(f"  - Packing: finished={packing_info_finished['finished']}, planned={packing_info_finished['planned']}")
			print(f"  - Total Packing Planned (so far): {total_packing_planned}")
			print(f"  - Total Packing Finished (so far): {total_packing_finished}")
			
			# Add order_qty (only once per finished item)
			total_order_qty += row.order_qty or 0
		
		# Calculate summary
		print(f"\n{'='*80}")
		print(f"[Progress Calc] FINAL SUMMARY CALCULATIONS:")
		print(f"{'='*80}")
		print(f"\n[Cutting Progress]")
		print(f"  - Total Order Qty: {total_order_qty}")
		print(f"  - Total Cutting Planned (qty): {total_cutting_planned}")
		print(f"  - Total Cutting Finished (qty): {total_cutting_finished}")
		
		# Cutting % = (Finished finished-item qty / order qty) × 100
		if total_order_qty > 0:
			cutting_progress = (total_cutting_finished / total_order_qty) * 100
			print(f"  - Calculation: ({total_cutting_finished:.2f} / {total_order_qty}) * 100 = {cutting_progress:.1f}%")
		else:
			cutting_progress = 0
			print(f"  - No order qty, progress = 0%")
		
		print(f"\n[Stitching Progress]")
		print(f"  - Total Order Qty: {total_order_qty}")
		print(f"  - Total Stitching Planned (qty): {total_stitching_planned}")
		print(f"  - Total Stitching Finished (qty): {total_stitching_finished}")
		
		# Stitching % = (Finished finished-item qty / order qty) × 100
		if total_order_qty > 0:
			stitching_progress = (total_stitching_finished / total_order_qty) * 100
			print(f"  - Calculation: ({total_stitching_finished:.2f} / {total_order_qty}) * 100 = {stitching_progress:.1f}%")
		else:
			stitching_progress = 0
			print(f"  - No order qty, progress = 0%")
		
		print(f"\n[Packing Progress]")
		print(f"  - Total Packing Finished: {total_packing_finished}")
		print(f"  - Total Order Qty: {total_order_qty}")
		print(f"  - Total Packing Planned: {total_packing_planned}")
		
		# Packing % = (Finished Packing Qty / order qty) × 100
		# Allow percentage above 100% if finished exceeds order qty
		if total_order_qty > 0:
			packing_progress = (total_packing_finished / total_order_qty) * 100
			print(f"  - Calculation: ({total_packing_finished} / {total_order_qty}) * 100 = {packing_progress:.1f}%")
		else:
			packing_progress = 0
			print(f"  - No order qty, progress = 0%")
		
		# Overall progress: For finished items, get packing data from finished item rows (not bundle items)
		# Sum up packing_finished from parent rows (finished items) only
		total_packing_finished_finished_items = 0
		for detail_row in details:
			if detail_row.get("is_parent") == True:
				# Only count finished items' packing, not bundle items
				total_packing_finished_finished_items += detail_row.get("packing_finished", 0)
		
		print(f"\n[Overall Progress]")
		print(f"  - Total Order Qty: {total_order_qty}")
		print(f"  - Total Packing Finished (finished items): {total_packing_finished_finished_items}")
		
		# Overall progress = (finished items packed / total order qty) * 100
		overall_progress = (total_packing_finished_finished_items / total_order_qty * 100) if total_order_qty > 0 else 0
		print(f"  - Overall Progress: ({total_packing_finished_finished_items} / {total_order_qty}) * 100 = {overall_progress:.1f}%")
		
		print(f"{'='*80}\n")
		
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
