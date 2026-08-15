# Copyright (c) 2026, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt

from manufacturing_addon.manufacturing_addon.doctype.shipment_loading.shipment_loading import (
	_carton_batch_details,
	_carton_dimension_map,
	parse_carton_dimension,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Order Sheet"),
			"fieldname": "order_sheet",
			"fieldtype": "Link",
			"options": "Order Sheet",
			"width": 180,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 140,
		},
		{
			"label": _("Packing Report"),
			"fieldname": "packing_report",
			"fieldtype": "Link",
			"options": "Packing Report",
			"width": 150,
		},
		{
			"label": _("Item"),
			"fieldname": "so_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 220,
		},
		{
			"label": _("Article"),
			"fieldname": "article",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Colour"),
			"fieldname": "colour",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Size"),
			"fieldname": "finished_size",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Qty/Ctn"),
			"fieldname": "qty_ctn",
			"fieldtype": "Float",
			"width": 80,
		},
		{
			"label": _("Ready Pcs"),
			"fieldname": "ready_pieces",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": _("Ready Ctn"),
			"fieldname": "ready_cartons",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Loaded Ctn"),
			"fieldname": "loaded_cartons",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Pending Ctn"),
			"fieldname": "pending_cartons",
			"fieldtype": "Int",
			"width": 95,
		},
		{
			"label": _("Ready CBM"),
			"fieldname": "ready_cbm",
			"fieldtype": "Float",
			"width": 90,
			"precision": 4,
		},
		{
			"label": _("Carton Dim"),
			"fieldname": "carton_dimension",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Container No"),
			"fieldname": "container_no",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Status"),
			"fieldname": "load_status",
			"fieldtype": "Data",
			"width": 90,
		},
	]


def get_data(filters):
	conditions = ["pr.docstatus = 1"]
	values = {}

	if filters.get("order_sheet"):
		conditions.append("pr.order_sheet = %(order_sheet)s")
		values["order_sheet"] = filters.order_sheet
	if filters.get("customer"):
		conditions.append("IFNULL(pr.customer, os.customer) = %(customer)s")
		values["customer"] = filters.customer
	if filters.get("packing_report"):
		conditions.append("pr.name = %(packing_report)s")
		values["packing_report"] = filters.packing_report
	if filters.get("from_date"):
		conditions.append("IFNULL(pr.date, DATE(pr.creation)) >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("IFNULL(pr.date, DATE(pr.creation)) <= %(to_date)s")
		values["to_date"] = filters.to_date

	where_sql = " AND ".join(conditions)
	rows = frappe.db.sql(
		f"""
		SELECT
			pr.name AS packing_report,
			pr.order_sheet,
			IFNULL(pr.customer, os.customer) AS customer,
			prct.name AS packing_report_row,
			prct.so_item,
			prct.combo_item,
			prct.article,
			prct.colour,
			prct.finished_size,
			prct.design,
			prct.qty_ctn,
			IFNULL(prct.packaging_qty, 0) AS packaging_qty,
			IFNULL(prct.finished_packaging_qty, 0) AS finished_packaging_qty
		FROM `tabPacking Report` pr
		INNER JOIN `tabPacking Report CT` prct ON prct.parent = pr.name
		LEFT JOIN `tabOrder Sheet` os ON os.name = pr.order_sheet
		WHERE {where_sql}
		ORDER BY pr.order_sheet, pr.name, prct.idx
		""",
		values,
		as_dict=True,
	)

	# Loaded cartons from Shipment Loading by packing report row
	loaded_map = {}
	container_map = {}
	if rows:
		keys = [(r.packing_report, r.packing_report_row) for r in rows]
		# Fetch all shipment loading cartons for involved order sheets
		order_sheets = list({r.order_sheet for r in rows if r.order_sheet})
		if order_sheets:
			loaded_rows = frappe.db.sql(
				"""
				SELECT
					slc.packing_report,
					slc.packing_report_row,
					slc.carton_count,
					slc.is_loaded,
					slc.container_no,
					sl.container_no AS header_container_no
				FROM `tabShipment Loading Carton` slc
				INNER JOIN `tabShipment Loading` sl ON sl.name = slc.parent
				WHERE sl.order_sheet IN %(order_sheets)s
				""",
				{"order_sheets": order_sheets},
				as_dict=True,
			)
			for lr in loaded_rows:
				key = (lr.packing_report, lr.packing_report_row)
				if cint(lr.is_loaded):
					loaded_map[key] = loaded_map.get(key, 0) + cint(lr.carton_count)
				container_map[key] = lr.container_no or lr.header_container_no or container_map.get(key)

	dim_cache = {}
	data = []
	for row in rows:
		order_sheet = row.order_sheet
		if order_sheet not in dim_cache:
			dim_cache[order_sheet] = _carton_dimension_map(order_sheet)
		dimensions, qty_ctn_map = dim_cache[order_sheet]

		qty_ctn = (
			flt(row.qty_ctn)
			or qty_ctn_map.get((row.so_item, row.combo_item or ""))
			or qty_ctn_map.get((row.so_item, ""))
		)
		total_packed = flt(row.packaging_qty) + flt(row.finished_packaging_qty)
		ready_cartons, qty_per_carton, _partial, ready_pieces = _carton_batch_details(total_packed, qty_ctn)
		if not ready_cartons:
			continue

		carton_dimension = dimensions.get((row.so_item, row.combo_item or "")) or dimensions.get(
			(row.so_item, "")
		)
		length_cm, width_cm, height_cm = parse_carton_dimension(carton_dimension)
		per_cbm = (
			(length_cm * width_cm * height_cm) / 1000000.0 if (length_cm and width_cm and height_cm) else 0
		)
		ready_cbm = per_cbm * ready_cartons

		key = (row.packing_report, row.packing_report_row)
		loaded_cartons = cint(loaded_map.get(key, 0))
		pending_cartons = max(ready_cartons - loaded_cartons, 0)

		if filters.get("only_pending") and pending_cartons <= 0:
			continue

		if loaded_cartons <= 0:
			load_status = "Pending"
		elif pending_cartons <= 0:
			load_status = "Loaded"
		else:
			load_status = "Partial"

		data.append(
			{
				"order_sheet": row.order_sheet,
				"customer": row.customer,
				"packing_report": row.packing_report,
				"so_item": row.so_item,
				"article": row.article,
				"colour": row.colour,
				"finished_size": row.finished_size,
				"qty_ctn": qty_per_carton or qty_ctn,
				"ready_pieces": ready_pieces,
				"ready_cartons": ready_cartons,
				"loaded_cartons": loaded_cartons,
				"pending_cartons": pending_cartons,
				"ready_cbm": ready_cbm,
				"carton_dimension": carton_dimension,
				"container_no": container_map.get(key) or "",
				"load_status": load_status,
			}
		)

	return data
