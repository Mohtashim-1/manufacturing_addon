import frappe
from frappe import _
from frappe.utils import getdate, nowdate
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

	@frappe.whitelist()
	def make_work_order(self, po_naming_series=None):
		frappe.logger().info(
			"[PP Custom] make_work_order called: name=%s, po_naming_series=%s",
			self.name,
			po_naming_series,
		)
		from erpnext.manufacturing.doctype.work_order.work_order import get_default_warehouse

		if po_naming_series:
			self._validate_po_naming_series(po_naming_series)

		wo_list, po_list = [], []
		subcontracted_po = {}
		default_warehouses = get_default_warehouse()

		self.make_work_order_for_finished_goods(wo_list, default_warehouses)
		self.make_work_order_for_subassembly_items(wo_list, subcontracted_po, default_warehouses)
		self.make_subcontracted_purchase_order(
			subcontracted_po,
			po_list,
			po_naming_series=po_naming_series,
		)
		self.show_list_created_message("Work Order", wo_list)
		self.show_list_created_message("Purchase Order", po_list)

		if not wo_list:
			frappe.msgprint(_("No Work Orders were created"))

	def make_subcontracted_purchase_order(self, subcontracted_po, purchase_orders, po_naming_series=None):
		if not subcontracted_po:
			frappe.logger().info("[PP Custom] No subcontracted PO to create for %s", self.name)
			return

		for supplier, po_list in subcontracted_po.items():
			po = frappe.new_doc("Purchase Order")
			if po_naming_series:
				po.naming_series = po_naming_series
			po.company = self.company
			po.supplier = supplier
			po.schedule_date = getdate(po_list[0].schedule_date) if po_list[0].schedule_date else nowdate()
			po.is_subcontracted = 1
			for row in po_list:
				po_data = {
					"fg_item": row.production_item,
					"warehouse": row.fg_warehouse,
					"production_plan_sub_assembly_item": row.name,
					"bom": row.bom_no,
					"production_plan": self.name,
					"fg_item_qty": row.qty,
				}

				for field in [
					"schedule_date",
					"qty",
					"description",
					"production_plan_item",
				]:
					po_data[field] = row.get(field)

				po.append("items", po_data)

			po.set_service_items_for_finished_goods()
			po.set_missing_values()
			po.flags.ignore_mandatory = True
			po.flags.ignore_validate = True
			po.insert()
			frappe.logger().info(
				"[PP Custom] Subcontract PO created: %s (series=%s) for supplier=%s",
				po.name,
				po.naming_series,
				supplier,
			)
			purchase_orders.append(po.name)

	def _validate_po_naming_series(self, po_naming_series):
		field = frappe.get_meta("Purchase Order").get_field("naming_series")
		if not field or not field.options:
			frappe.throw(_("No Purchase Order naming series configured."))

		valid = [opt.strip() for opt in field.options.split("\n") if opt.strip()]
		if po_naming_series not in valid:
			frappe.throw(_("Invalid Purchase Order naming series: {0}").format(po_naming_series))
