# Copyright (c) 2026, Manufacturing Addon and contributors
# For license information, please see license.txt

import math
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime


LOADING_TAG_OPTIONS = ("Manual", "Forklift", "Pallet Jack", "Crane", "Conveyor", "Bulk")

CONTAINER_SPECS = {
	"20ft FCL": {"rows": 3, "cols": 10, "capacity_cbm": 33.0, "height_cm": 239.0},
	"40ft FCL": {"rows": 3, "cols": 20, "capacity_cbm": 67.0, "height_cm": 239.0},
}


class ShipmentLoading(Document):
	def validate(self):
		self.update_totals()

	def update_totals(self):
		total = sum(cint(row.carton_count) or 1 for row in self.cartons or [])
		loaded = sum(cint(row.carton_count) or 1 for row in self.cartons or [] if row.is_loaded)
		pending = total - loaded
		total_cbm = sum(flt(row.cbm) for row in self.cartons or [])
		loaded_cbm = sum(flt(row.cbm) for row in self.cartons or [] if row.is_loaded)

		self.total_cartons = total
		self.loaded_cartons = loaded
		self.pending_cartons = pending
		self.total_cbm = total_cbm
		self.loaded_cbm = loaded_cbm

		if total == 0:
			self.status = "Pending"
		elif loaded == 0:
			self.status = "Pending"
		elif loaded < total:
			self.status = "In Progress"
		else:
			self.status = "Completed"


def parse_carton_dimension(dimension_text):
	if not dimension_text:
		return (0.0, 0.0, 0.0)
	match = re.search(
		r"(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)",
		str(dimension_text),
	)
	if not match:
		return (0.0, 0.0, 0.0)
	return (flt(match.group(1)), flt(match.group(2)), flt(match.group(3)))


def _carton_dimension_map(order_sheet):
	rows = frappe.get_all(
		"Order Sheet CT",
		filters={"parent": order_sheet},
		fields=["so_item", "combo_item", "carton_dimension", "qty_ctn"],
	)
	dimensions = {}
	qty_ctn_map = {}
	for row in rows:
		key = (row.so_item, row.combo_item or "")
		dimensions[key] = row.carton_dimension
		qty_ctn_map[key] = flt(row.qty_ctn)
		if row.so_item and (row.so_item, "") not in dimensions:
			dimensions[(row.so_item, "")] = row.carton_dimension
			qty_ctn_map[(row.so_item, "")] = flt(row.qty_ctn)
	return dimensions, qty_ctn_map


def _compute_ready_cartons(total_packed_qty, qty_ctn):
	qty_ctn = flt(qty_ctn)
	if not qty_ctn:
		return 0, []
	total_packed_qty = flt(total_packed_qty)
	if total_packed_qty <= 0:
		return 0, []

	full_cartons = int(total_packed_qty // qty_ctn)
	remainder = total_packed_qty - (full_cartons * qty_ctn)
	carton_qtys = [qty_ctn] * full_cartons
	if remainder > 0:
		carton_qtys.append(remainder)
	return len(carton_qtys), carton_qtys


def compute_packing_readiness(order_sheet):
	"""Pieces ready and expected cartons from submitted packing reports."""
	if not order_sheet:
		return {"pieces_ready": 0, "expected_cartons": 0, "ready_cbm": 0.0}

	_, qty_ctn_map = _carton_dimension_map(order_sheet)
	ct_rows = frappe.db.sql(
		"""
		SELECT
			prct.so_item,
			prct.combo_item,
			prct.qty_ctn,
			IFNULL(prct.packaging_qty, 0) + IFNULL(prct.finished_packaging_qty, 0) AS pieces_ready
		FROM `tabPacking Report` pr
		INNER JOIN `tabPacking Report CT` prct ON prct.parent = pr.name
		WHERE pr.order_sheet = %s AND pr.docstatus = 1
		""",
		order_sheet,
		as_dict=True,
	)

	pieces_ready = 0.0
	expected_cartons = 0
	ready_cbm = 0.0
	dimensions, _ = _carton_dimension_map(order_sheet)

	for row in ct_rows:
		pieces = flt(row.pieces_ready)
		if pieces <= 0:
			continue
		pieces_ready += pieces
		qty_ctn = flt(row.qty_ctn) or qty_ctn_map.get((row.so_item, row.combo_item or "")) or qty_ctn_map.get(
			(row.so_item, "")
		)
		_, carton_qtys = _compute_ready_cartons(pieces, qty_ctn)
		expected_cartons += len(carton_qtys)
		carton_dimension = dimensions.get((row.so_item, row.combo_item or "")) or dimensions.get(
			(row.so_item, "")
		)
		length_cm, width_cm, height_cm = parse_carton_dimension(carton_dimension)
		per_carton_cbm = (
			(length_cm * width_cm * height_cm) / 1000000.0 if (length_cm and width_cm and height_cm) else 0
		)
		ready_cbm += per_carton_cbm * len(carton_qtys)

	return {
		"pieces_ready": pieces_ready,
		"expected_cartons": expected_cartons,
		"ready_cbm": ready_cbm,
	}


def estimate_consignment_containers(total_cbm, container_type="20ft FCL"):
	"""Estimate how many containers are needed for the full consignment CBM."""
	total_cbm = flt(total_cbm)
	by_type = {}
	for ctype, spec in CONTAINER_SPECS.items():
		capacity = flt(spec.get("capacity_cbm"))
		if not capacity or total_cbm <= 0:
			needed = 0
		else:
			needed = int(math.ceil(total_cbm / capacity))
		by_type[ctype] = {
			"capacity_cbm": capacity,
			"containers_needed": needed,
			"slots_per_container": cint(spec.get("rows")) * cint(spec.get("cols")),
		}

	selected = container_type if container_type in CONTAINER_SPECS else "20ft FCL"
	selected_needed = by_type[selected]["containers_needed"]
	return {
		"total_cbm": total_cbm,
		"selected_type": selected,
		"containers_needed": selected_needed,
		"consignment_fits_one": selected_needed <= 1,
		"by_type": by_type,
	}


def estimate_cartons_per_container(per_carton_cbm, container_type="20ft FCL"):
	"""How many cartons fit in one container by CBM and by planner slots."""
	spec = CONTAINER_SPECS.get(container_type, CONTAINER_SPECS["20ft FCL"])
	capacity = flt(spec.get("capacity_cbm"))
	per_carton_cbm = flt(per_carton_cbm)
	slots = cint(spec.get("rows")) * cint(spec.get("cols"))
	by_cbm = int(capacity // per_carton_cbm) if capacity and per_carton_cbm else slots
	return {
		"by_cbm": max(by_cbm, 0),
		"by_slots": slots,
		"effective_max": min(by_cbm, slots) if by_cbm else slots,
	}



def _carton_batch_details(total_packed_qty, qty_ctn):
	"""Return carton_count, qty_per_carton, partial_qty, total_pieces for a packing line."""
	qty_ctn = flt(qty_ctn)
	total_packed_qty = flt(total_packed_qty)
	if not qty_ctn or total_packed_qty <= 0:
		return 0, 0, 0, 0

	carton_count, carton_qtys = _compute_ready_cartons(total_packed_qty, qty_ctn)
	if not carton_count:
		return 0, 0, 0, 0

	qty_per_carton = qty_ctn
	partial_qty = 0
	if len(carton_qtys) == 1 and flt(carton_qtys[0]) < qty_ctn:
		partial_qty = flt(carton_qtys[0])
	elif flt(carton_qtys[-1]) < qty_ctn:
		partial_qty = flt(carton_qtys[-1])

	return carton_count, qty_per_carton, partial_qty, total_packed_qty


def get_or_create_shipment_loading(order_sheet):
	name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")
	if name:
		return frappe.get_doc("Shipment Loading", name)

	doc = frappe.get_doc({"doctype": "Shipment Loading", "order_sheet": order_sheet})
	doc.insert(ignore_permissions=True)
	return doc


def sync_shipment_loading_for_order_sheet(order_sheet, packing_report=None):
	"""Build carton rows from submitted packing reports for an order sheet."""
	if not order_sheet:
		return None

	doc = get_or_create_shipment_loading(order_sheet)
	readiness = compute_packing_readiness(order_sheet)
	doc.total_pieces_ready = readiness["pieces_ready"]
	doc.expected_cartons = readiness["expected_cartons"]
	dimensions, qty_ctn_map = _carton_dimension_map(order_sheet)
	existing_by_key = {
		(row.packing_report, row.packing_report_row): row for row in (doc.cartons or [])
	}

	filters = {"order_sheet": order_sheet, "docstatus": 1}
	if packing_report:
		filters["name"] = packing_report

	packing_reports = frappe.get_all(
		"Packing Report",
		filters=filters,
		fields=["name"],
		order_by="modified desc",
	)

	added = 0
	updated = 0
	for pr in packing_reports:
		ct_rows = frappe.get_all(
			"Packing Report CT",
			filters={"parent": pr.name},
			fields=[
				"name",
				"so_item",
				"combo_item",
				"colour",
				"article",
				"finished_size",
				"design",
				"qty_ctn",
				"packaging_qty",
				"finished_packaging_qty",
			],
		)
		for row in ct_rows:
			qty_ctn = flt(row.qty_ctn) or qty_ctn_map.get((row.so_item, row.combo_item or "")) or qty_ctn_map.get(
				(row.so_item, "")
			)
			total_packed = flt(row.packaging_qty) + flt(row.finished_packaging_qty)
			carton_count, qty_per_carton, partial_qty, total_pieces = _carton_batch_details(
				total_packed, qty_ctn
			)
			if not carton_count:
				continue

			carton_dimension = dimensions.get((row.so_item, row.combo_item or "")) or dimensions.get(
				(row.so_item, "")
			)
			length_cm, width_cm, height_cm = parse_carton_dimension(carton_dimension)
			per_carton_cbm = (
				(length_cm * width_cm * height_cm) / 1000000.0 if (length_cm and width_cm and height_cm) else 0
			)
			total_cbm = per_carton_cbm * carton_count
			key = (pr.name, row.name)
			label = f"{pr.name} · {carton_count} ctns"
			payload = {
				"packing_report": pr.name,
				"packing_report_row": row.name,
				"so_item": row.so_item,
				"combo_item": row.combo_item,
				"colour": row.colour,
				"article": row.article,
				"finished_size": row.finished_size,
				"design": row.design,
				"carton_no": 1,
				"carton_label": label,
				"carton_count": carton_count,
				"qty_in_carton": qty_per_carton,
				"partial_qty": partial_qty,
				"total_pieces": total_pieces,
				"carton_dimension": carton_dimension,
				"per_carton_cbm": per_carton_cbm,
				"cbm": total_cbm,
			}

			existing = existing_by_key.get(key)
			if existing:
				if existing.is_loaded:
					continue
				if not flt(existing.per_carton_cbm) and flt(existing.cbm):
					existing.per_carton_cbm = flt(existing.cbm) / max(cint(existing.carton_count), 1)
				changed = False
				for field, value in payload.items():
					if getattr(existing, field, None) != value:
						setattr(existing, field, value)
						changed = True
				if changed:
					updated += 1
				continue

			payload["is_loaded"] = 0
			doc.append("cartons", payload)
			existing_by_key[key] = doc.cartons[-1]
			added += 1

	doc.update_totals()
	if added or updated or doc.total_pieces_ready != readiness["pieces_ready"] or doc.expected_cartons != readiness["expected_cartons"]:
		doc.save(ignore_permissions=True)
	return {
		"name": doc.name,
		"added_cartons": added,
		"updated_cartons": updated,
		"total_cartons": doc.total_cartons,
		"pieces_ready": doc.total_pieces_ready,
		"expected_cartons": doc.expected_cartons,
	}


def remove_unloaded_cartons_for_packing_report(packing_report):
	"""Remove pending cartons when a packing report is cancelled."""
	if not packing_report:
		return

	order_sheet = frappe.db.get_value("Packing Report", packing_report, "order_sheet")
	if not order_sheet:
		return

	loading_name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")
	if not loading_name:
		return

	doc = frappe.get_doc("Shipment Loading", loading_name)
	remaining = []
	removed = 0
	for row in doc.cartons or []:
		if row.packing_report == packing_report and not row.is_loaded:
			removed += 1
			continue
		remaining.append(row)

	doc.set("cartons", remaining)
	doc.update_totals()
	doc.save(ignore_permissions=True)
	return {"removed": removed, "name": doc.name}


def sync_shipment_loading_from_packing_report(doc, method=None):
	if doc.doctype != "Packing Report" or not doc.order_sheet:
		return
	if doc.docstatus == 1:
		sync_shipment_loading_for_order_sheet(doc.order_sheet, packing_report=doc.name)
	elif doc.docstatus == 2:
		remove_unloaded_cartons_for_packing_report(doc.name)


@frappe.whitelist()
def get_shipment_loading_board(filters=None):
	"""Return order-sheet wise shipment loading summary for the page."""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})

	conditions = ["pr.docstatus = 1", "pr.order_sheet IS NOT NULL", "pr.order_sheet != ''"]
	values = {}

	if filters.get("order_sheet"):
		conditions.append("pr.order_sheet = %(order_sheet)s")
		values["order_sheet"] = filters["order_sheet"]
	if filters.get("customer"):
		conditions.append("pr.customer = %(customer)s")
		values["customer"] = filters["customer"]

	where_sql = " AND ".join(conditions)
	rows = frappe.db.sql(
		f"""
		SELECT
			pr.order_sheet,
			MAX(pr.customer) AS customer,
			COUNT(DISTINCT pr.name) AS packing_report_count,
			MAX(pr.modified) AS last_packing_at,
			MAX(sl.name) AS shipment_loading,
			MAX(sl.status) AS status,
			IFNULL(MAX(sl.total_cartons), 0) AS total_cartons,
			IFNULL(MAX(sl.loaded_cartons), 0) AS loaded_cartons,
			IFNULL(MAX(sl.pending_cartons), 0) AS pending_cartons,
			IFNULL(MAX(sl.total_cbm), 0) AS total_cbm,
			IFNULL(MAX(sl.loaded_cbm), 0) AS loaded_cbm,
			IFNULL(MAX(sl.total_pieces_ready), 0) AS total_pieces_ready,
			IFNULL(MAX(sl.expected_cartons), 0) AS expected_cartons,
			MAX(sl.shipment_date) AS shipment_date,
			MAX(sl.sales_order) AS sales_order,
			MAX(sl.container_type) AS container_type
		FROM `tabPacking Report` pr
		LEFT JOIN `tabShipment Loading` sl ON sl.order_sheet = pr.order_sheet
		WHERE {where_sql}
		GROUP BY pr.order_sheet
		ORDER BY last_packing_at DESC
		LIMIT 200
		""",
		values,
		as_dict=True,
	)

	board = []
	for row in rows:
		status = row.status or "Pending"
		if filters.get("status") and status != filters["status"]:
			continue

		if not flt(row.total_pieces_ready):
			readiness = compute_packing_readiness(row.order_sheet)
			row.total_pieces_ready = readiness["pieces_ready"]
			row.expected_cartons = readiness["expected_cartons"]

		board.append(
			{
				"order_sheet": row.order_sheet,
				"customer": row.customer,
				"packing_report_count": row.packing_report_count,
				"last_packing_at": row.last_packing_at,
				"shipment_loading": row.shipment_loading,
				"status": status,
				"total_cartons": row.total_cartons,
				"loaded_cartons": row.loaded_cartons,
				"pending_cartons": row.pending_cartons,
				"total_cbm": row.total_cbm,
				"loaded_cbm": row.loaded_cbm,
				"total_pieces_ready": row.total_pieces_ready,
				"expected_cartons": row.expected_cartons,
				"shipment_date": row.shipment_date,
				"sales_order": row.sales_order,
				"container_type": row.container_type or "20ft FCL",
			}
		)

	return {"rows": board}


@frappe.whitelist()
def sync_order_sheet_cartons(order_sheet):
	"""Sync cartons from packing reports for one order sheet (on-demand)."""
	if not order_sheet:
		frappe.throw(_("Order Sheet is required"))
	return sync_shipment_loading_for_order_sheet(order_sheet)


@frappe.whitelist()
def get_order_sheet_cartons(order_sheet, packing_report=None, loaded_only=None, sync=1):
	if not order_sheet:
		frappe.throw(_("Order Sheet is required"))

	if cint(sync):
		sync_shipment_loading_for_order_sheet(order_sheet, packing_report=packing_report or None)

	loading_name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")
	if not loading_name:
		return {"cartons": [], "shipment_loading": None, "summary": {}}

	carton_filters = {"parent": loading_name, "parenttype": "Shipment Loading", "parentfield": "cartons"}
	if packing_report:
		carton_filters["packing_report"] = packing_report
	if loaded_only is not None:
		carton_filters["is_loaded"] = cint(loaded_only)

	carton_rows = frappe.get_all(
		"Shipment Loading Carton",
		filters=carton_filters,
		fields=[
			"name",
			"packing_report",
			"so_item",
			"combo_item",
			"colour",
			"article",
			"finished_size",
			"design",
			"carton_no",
			"carton_label",
			"carton_count",
			"qty_in_carton",
			"partial_qty",
			"total_pieces",
				"carton_dimension",
				"per_carton_cbm",
				"cbm",
			"loading_tag",
			"is_loaded",
			"loaded_by",
			"loaded_on",
			"container_no",
			"position_row",
			"position_col",
			"position_layer",
			"remarks",
		],
		order_by="packing_report desc, so_item asc, carton_no asc",
		limit=5000,
	)

	summary = frappe.db.get_value(
		"Shipment Loading",
		loading_name,
		[
			"total_cartons",
			"loaded_cartons",
			"pending_cartons",
			"status",
			"total_pieces_ready",
			"expected_cartons",
			"container_type",
			"container_no",
			"total_cbm",
			"loaded_cbm",
		],
		as_dict=True,
	)
	readiness = compute_packing_readiness(order_sheet)
	container_type = (summary and summary.container_type) or "20ft FCL"
	container_spec = CONTAINER_SPECS.get(container_type, CONTAINER_SPECS["20ft FCL"])
	consignment_cbm = flt(readiness.get("ready_cbm")) or flt((summary or {}).get("total_cbm"))
	container_estimate = estimate_consignment_containers(consignment_cbm, container_type)

	return {
		"shipment_loading": loading_name,
		"cartons": carton_rows,
		"summary": summary or {},
		"readiness": readiness,
		"container_type": container_type,
		"container_spec": container_spec,
		"container_estimate": container_estimate,
	}


@frappe.whitelist()
def load_cartons(order_sheet, carton_rows, loading_tag, container_no=None, remarks=None):
	"""Mark selected cartons as loaded with a loading tag."""
	if not order_sheet:
		frappe.throw(_("Order Sheet is required"))
	if not loading_tag:
		frappe.throw(_("Loading Tag is required"))
	if loading_tag not in LOADING_TAG_OPTIONS:
		frappe.throw(_("Invalid Loading Tag"))

	if isinstance(carton_rows, str):
		carton_rows = frappe.parse_json(carton_rows)
	if not carton_rows:
		frappe.throw(_("Select at least one carton"))

	loading_name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")
	if not loading_name:
		frappe.throw(_("Shipment Loading not found for this Order Sheet"))

	doc = frappe.get_doc("Shipment Loading", loading_name)
	selected = set(carton_rows)
	updated = 0
	now = now_datetime()
	user = frappe.session.user

	for row in doc.cartons or []:
		if row.name not in selected:
			continue
		row.is_loaded = 1
		row.loading_tag = loading_tag
		row.loaded_by = user
		row.loaded_on = now
		if container_no:
			row.container_no = container_no
		if remarks:
			row.remarks = remarks
		updated += 1

	if not updated:
		frappe.throw(_("No matching cartons found"))

	doc.update_totals()
	doc.save(ignore_permissions=True)
	return {
		"updated": updated,
		"shipment_loading": doc.name,
		"status": doc.status,
		"loaded_cartons": doc.loaded_cartons,
		"pending_cartons": doc.pending_cartons,
	}


@frappe.whitelist()
def unload_cartons(order_sheet, carton_rows):
	if not order_sheet:
		frappe.throw(_("Order Sheet is required"))

	if isinstance(carton_rows, str):
		carton_rows = frappe.parse_json(carton_rows)
	if not carton_rows:
		frappe.throw(_("Select at least one carton"))

	loading_name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")
	if not loading_name:
		frappe.throw(_("Shipment Loading not found"))

	doc = frappe.get_doc("Shipment Loading", loading_name)
	selected = set(carton_rows)
	updated = 0
	for row in doc.cartons or []:
		if row.name not in selected:
			continue
		row.is_loaded = 0
		row.loading_tag = None
		row.loaded_by = None
		row.loaded_on = None
		row.position_row = 0
		row.position_col = 0
		row.position_layer = 0
		updated += 1

	if not updated:
		frappe.throw(_("No matching cartons found"))

	doc.update_totals()
	doc.save(ignore_permissions=True)
	return {"updated": updated, "status": doc.status}


@frappe.whitelist()
def save_container_settings(order_sheet, container_type=None, container_no=None):
	if not order_sheet:
		frappe.throw(_("Order Sheet is required"))

	loading_name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")
	if not loading_name:
		sync_shipment_loading_for_order_sheet(order_sheet)
		loading_name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")

	values = {}
	if container_type:
		if container_type not in CONTAINER_SPECS:
			frappe.throw(_("Invalid container type"))
		values["container_type"] = container_type
	if container_no is not None:
		values["container_no"] = container_no
	if values:
		frappe.db.set_value("Shipment Loading", loading_name, values, update_modified=True)
	return {"shipment_loading": loading_name, **values}


@frappe.whitelist()
def place_carton_in_container(
	order_sheet, carton_name, position_row, position_col, position_layer=None, loading_tag=None, mark_loaded=0
):
	"""Place a carton on the container grid with vertical stacking (row, col, layer)."""
	if not order_sheet:
		frappe.throw(_("Order Sheet is required"))
	if not carton_name:
		frappe.throw(_("Carton is required"))

	position_row = cint(position_row)
	position_col = cint(position_col)
	if position_row < 1 or position_col < 1:
		frappe.throw(_("Invalid container position"))

	loading_name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")
	if not loading_name:
		frappe.throw(_("Shipment Loading not found"))

	doc = frappe.get_doc("Shipment Loading", loading_name)
	container_type = doc.container_type or "20ft FCL"
	spec = CONTAINER_SPECS.get(container_type, CONTAINER_SPECS["20ft FCL"])
	if position_row > spec["rows"] or position_col > spec["cols"]:
		frappe.throw(_("Position is outside the {0} layout").format(container_type))

	target = None
	for row in doc.cartons or []:
		if row.name == carton_name:
			target = row

	if not target:
		frappe.throw(_("Carton not found"))

	if not _can_stack_at(doc, spec, position_row, position_col, target.carton_dimension, exclude_name=carton_name):
		frappe.throw(
			_("Stack height exceeds container ceiling at R{0} C{1}. Try another cell.").format(
				position_row, position_col
			)
		)

	position_layer = cint(position_layer) or _next_layer_at(
		doc, position_row, position_col, exclude_name=carton_name
	)
	for row in doc.cartons or []:
		if row.name == carton_name:
			continue
		if (
			cint(row.position_row) == position_row
			and cint(row.position_col) == position_col
			and cint(row.position_layer) == position_layer
		):
			frappe.throw(_("Layer L{0} at R{1} C{2} is already occupied").format(position_layer, position_row, position_col))

	target.position_row = position_row
	target.position_col = position_col
	target.position_layer = position_layer
	if loading_tag:
		if loading_tag not in LOADING_TAG_OPTIONS:
			frappe.throw(_("Invalid Loading Tag"))
		target.loading_tag = loading_tag
	if cint(mark_loaded):
		target.is_loaded = 1
		target.loaded_by = frappe.session.user
		target.loaded_on = now_datetime()
		if doc.container_no:
			target.container_no = doc.container_no

	doc.update_totals()
	doc.save(ignore_permissions=True)
	return {
		"carton": carton_name,
		"position_row": position_row,
		"position_col": position_col,
		"position_layer": position_layer,
		"is_loaded": target.is_loaded,
		"loaded_cartons": doc.loaded_cartons,
		"pending_cartons": doc.pending_cartons,
	}


@frappe.whitelist()
def place_carton_in_next_slot(order_sheet, carton_name, loading_tag=None, mark_loaded=1):
	"""Place carton in the next available 3D slot (fills vertical stacks first)."""
	if not order_sheet:
		frappe.throw(_("Order Sheet is required"))
	if not carton_name:
		frappe.throw(_("Carton is required"))

	loading_name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")
	if not loading_name:
		frappe.throw(_("Shipment Loading not found"))

	doc = frappe.get_doc("Shipment Loading", loading_name)
	target = next((row for row in (doc.cartons or []) if row.name == carton_name), None)
	if not target:
		frappe.throw(_("Carton not found"))

	container_type = doc.container_type or "20ft FCL"
	spec = CONTAINER_SPECS.get(container_type, CONTAINER_SPECS["20ft FCL"])
	slot = _find_next_3d_slot(doc, spec, target.carton_dimension)
	if not slot:
		frappe.throw(_("Container is full (floor cells and stack height). Switch to 40ft FCL or unload cartons."))

	position_row, position_col, position_layer = slot
	return place_carton_in_container(
		order_sheet,
		carton_name,
		position_row,
		position_col,
		position_layer=position_layer,
		loading_tag=loading_tag,
		mark_loaded=mark_loaded,
	)


def _row_per_carton_cbm(row):
	if flt(row.per_carton_cbm):
		return flt(row.per_carton_cbm)
	return flt(row.cbm) / max(cint(row.carton_count), 1)


def _carton_height_cm(carton_dimension):
	_, _, height_cm = parse_carton_dimension(carton_dimension)
	return height_cm or 35.0


def _stack_at_cell(doc, row_no, col_no, exclude_name=None):
	stacks = [
		row
		for row in (doc.cartons or [])
		if cint(row.position_row) == row_no
		and cint(row.position_col) == col_no
		and (not exclude_name or row.name != exclude_name)
	]
	stacks.sort(key=lambda row: cint(row.position_layer) or 1)
	return stacks


def _stack_height_cm(stacks):
	return sum(_carton_height_cm(row.carton_dimension) for row in stacks)


def _max_stack_layers(spec, carton_dimension):
	container_h = flt(spec.get("height_cm", 239))
	carton_h = _carton_height_cm(carton_dimension)
	if not carton_h:
		return 1
	return max(1, int(container_h // carton_h))


def _can_stack_at(doc, spec, row_no, col_no, carton_dimension, exclude_name=None):
	container_h = flt(spec.get("height_cm", 239))
	stacks = _stack_at_cell(doc, row_no, col_no, exclude_name=exclude_name)
	new_h = _carton_height_cm(carton_dimension)
	return _stack_height_cm(stacks) + new_h <= container_h + 0.5


def _next_layer_at(doc, row_no, col_no, exclude_name=None):
	stacks = _stack_at_cell(doc, row_no, col_no, exclude_name=exclude_name)
	if not stacks:
		return 1
	return max(cint(row.position_layer) or 1 for row in stacks) + 1


def _find_next_3d_slot(doc, spec, carton_dimension):
	for row_no in range(1, spec["rows"] + 1):
		for col_no in range(1, spec["cols"] + 1):
			if _can_stack_at(doc, spec, row_no, col_no, carton_dimension):
				layer = _next_layer_at(doc, row_no, col_no)
				return row_no, col_no, layer
	return None


def _auto_fill_candidates(doc, carton_rows=None, so_item=None, finished_size=None):
	selected = set(carton_rows or [])
	candidates = []
	for row in doc.cartons or []:
		if cint(row.position_row) and cint(row.position_col):
			continue
		if selected and row.name not in selected:
			continue
		if so_item and row.so_item != so_item:
			continue
		if finished_size is not None and (row.finished_size or "") != finished_size:
			continue
		candidates.append(row)
	return candidates


def _parse_optional_json_list(val):
	if val is None:
		return None
	if isinstance(val, (list, tuple)):
		return list(val)
	if isinstance(val, str):
		val = val.strip()
		if not val or val.lower() in ("null", "undefined", "none"):
			return None
		return frappe.parse_json(val)
	return val


def _normalize_optional_text(val):
	if val is None:
		return None
	if isinstance(val, str):
		val = val.strip()
		if not val or val.lower() in ("null", "undefined", "none"):
			return None
	return val


@frappe.whitelist()
def auto_fill_container(
	order_sheet,
	carton_rows=None,
	so_item=None,
	finished_size=None,
	loading_tag=None,
	stop_at_capacity=1,
):
	"""Automatically place cartons into free container slots."""
	if not order_sheet:
		frappe.throw(_("Order Sheet is required"))

	carton_rows = _parse_optional_json_list(carton_rows)
	so_item = _normalize_optional_text(so_item)
	finished_size = _normalize_optional_text(finished_size)
	loading_tag = _normalize_optional_text(loading_tag)

	if carton_rows is not None and not carton_rows:
		frappe.throw(_("Select at least one carton batch"))

	loading_name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")
	if not loading_name:
		frappe.throw(_("Shipment Loading not found"))

	doc = frappe.get_doc("Shipment Loading", loading_name)
	container_type = doc.container_type or "20ft FCL"
	spec = CONTAINER_SPECS.get(container_type, CONTAINER_SPECS["20ft FCL"])
	candidates = _auto_fill_candidates(
		doc,
		carton_rows=carton_rows,
		so_item=so_item,
		finished_size=finished_size,
	)

	if not candidates:
		frappe.throw(_("No pending cartons available to place"))

	if loading_tag and loading_tag not in LOADING_TAG_OPTIONS:
		frappe.throw(_("Invalid Loading Tag"))

	used_cbm = sum(
		_row_per_carton_cbm(row)
		for row in doc.cartons or []
		if cint(row.position_row) and cint(row.position_col)
	)
	capacity = flt(spec.get("capacity_cbm"))
	now = now_datetime()
	user = frappe.session.user
	placed = 0

	for target in candidates:
		slot = _find_next_3d_slot(doc, spec, target.carton_dimension)
		if not slot:
			break
		position_row, position_col, position_layer = slot
		per_carton_cbm = _row_per_carton_cbm(target)
		if cint(stop_at_capacity) and capacity and used_cbm + per_carton_cbm > capacity + 0.0001:
			break

		target.position_row = position_row
		target.position_col = position_col
		target.position_layer = position_layer
		target.is_loaded = 1
		target.loaded_by = user
		target.loaded_on = now
		if loading_tag:
			target.loading_tag = loading_tag
		if doc.container_no:
			target.container_no = doc.container_no
		used_cbm += per_carton_cbm
		placed += 1

	if not placed:
		frappe.throw(_("Container is full (volume or stack height). Switch to 40ft FCL or unload cartons."))

	doc.update_totals()
	doc.save(ignore_permissions=True)
	remaining_slots = 0
	for row_no in range(1, spec["rows"] + 1):
		for col_no in range(1, spec["cols"] + 1):
			if _can_stack_at(doc, spec, row_no, col_no, "40x40x35"):
				remaining_slots += 1
	pct_cbm = round((used_cbm / capacity) * 100, 1) if capacity else 0

	return {
		"placed": placed,
		"remaining_stack_positions": remaining_slots,
		"used_cbm": used_cbm,
		"capacity_cbm": capacity,
		"cbm_percent": pct_cbm,
		"loaded_cartons": doc.loaded_cartons,
		"pending_cartons": doc.pending_cartons,
		"status": doc.status,
	}


@frappe.whitelist()
def clear_carton_position(order_sheet, carton_name):
	if not order_sheet or not carton_name:
		frappe.throw(_("Order Sheet and Carton are required"))

	loading_name = frappe.db.get_value("Shipment Loading", {"order_sheet": order_sheet}, "name")
	if not loading_name:
		frappe.throw(_("Shipment Loading not found"))

	doc = frappe.get_doc("Shipment Loading", loading_name)
	updated = False
	for row in doc.cartons or []:
		if row.name != carton_name:
			continue
		row.position_row = 0
		row.position_col = 0
		row.position_layer = 0
		updated = True
		break
	if not updated:
		frappe.throw(_("Carton not found"))
	doc.save(ignore_permissions=True)
	return {"cleared": carton_name}
