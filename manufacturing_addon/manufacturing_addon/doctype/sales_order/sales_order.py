import frappe
import json
from frappe import _
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder as ERPNextSalesOrder
from frappe.utils import flt
from pathlib import Path


class CustomSalesOrder(ERPNextSalesOrder):
	def validate_update_after_submit(self):
		if self.can_update_submitted_sales_order():
			self.flags.ignore_validate_update_after_submit = True

		super().validate_update_after_submit()

	def can_update_submitted_sales_order(self):
		if self.docstatus != 1:
			return False

		return not has_linked_delivery_note(self.name)

def validate_sales_order(doc, method):
    for item in doc.items:
        item_doc = frappe.get_doc("Item", item.item_code)

        # Skip global items
        if item_doc.custom_global_item == 1:
            continue

        allowed_customers = item_doc.custom_allowed_customers or []
        if not any(c.customer == doc.customer for c in allowed_customers):
            frappe.throw(_(
                f"🚫 Restricted Item!\n\n❌ The item <b>{item.item_code}</b> cannot be sold to <b>{doc.customer}</b>.\n🔒 Please select another item or contact the administrator."
            ))

        item.custom_cost_of_product = get_cost_of_product(
            item_code=item.item_code,
            bom_no=item.bom_no,
            company=doc.company,
            currency=doc.currency,
            conversion_rate=doc.conversion_rate,
        )

def close_cost_center_when_sales_order_is_closed(doc, method):
    if doc.status == "Closed" and doc.cost_center:
        frappe.msgprint("Closing cost center")
        try:
            cost_center = frappe.get_doc("Cost Center", doc.cost_center)
            if not cost_center.disabled:
                cost_center.disabled = 1
                cost_center.save()
                frappe.msgprint(f"Cost Center {doc.cost_center} has been closed.")
        except frappe.DoesNotExistError:
            frappe.msgprint(f"Cost Center {doc.cost_center} not found.")
        except Exception as e:
            frappe.msgprint(f"Error closing cost center: {str(e)}")
    else:
        frappe.msgprint("Cost Center is not closed.")

@frappe.whitelist()
def close_sales_order_and_cost_center(sales_order_name):
    """Close Sales Order and disable its cost center"""
    try:
        # Get the Sales Order document
        sales_order = frappe.get_doc("Sales Order", sales_order_name)
        
        # Check if already closed
        if sales_order.status == "Closed":
            frappe.msgprint("Sales Order is already closed.")
            return {"status": "already_closed"}
        
        # Use the proper ERPNext method to update status to Closed
        sales_order.update_status("Closed")
        
        # Disable cost center if it exists
        if sales_order.cost_center:
            try:
                cost_center = frappe.get_doc("Cost Center", sales_order.cost_center)
                if not cost_center.disabled:
                    cost_center.disabled = 1
                    cost_center.save()
                    frappe.msgprint(f"Sales Order closed and Cost Center {sales_order.cost_center} has been disabled.")
                else:
                    frappe.msgprint("Sales Order closed. Cost Center was already disabled.")
            except frappe.DoesNotExistError:
                frappe.msgprint("Sales Order closed. Cost Center not found.")
        else:
            frappe.msgprint("Sales Order closed. No cost center to disable.")
        
        return {"status": "success", "message": "Sales Order closed successfully"}
        
    except Exception as e:
        frappe.msgprint(f"Error closing Sales Order: {str(e)}")
        return {"status": "error", "message": str(e)}


def has_linked_delivery_note(sales_order_name):
	return bool(
		frappe.db.sql(
			"""
			select dni.parent
			from `tabDelivery Note Item` dni
			inner join `tabDelivery Note` dn on dn.name = dni.parent
			where dni.against_sales_order = %s
				and dn.docstatus != 2
			limit 1
			""",
			(sales_order_name,),
		)
	)


@frappe.whitelist()
def can_update_submitted_sales_order(sales_order_name):
	doc = frappe.get_doc("Sales Order", sales_order_name)
	doc.check_permission("write")

	return {
		"allowed": doc.docstatus == 1 and not has_linked_delivery_note(sales_order_name),
		"has_delivery_note": has_linked_delivery_note(sales_order_name),
	}


def get_cost_of_product(item_code=None, bom_no=None, company=None, currency=None, conversion_rate=None):
	bom_name = bom_no
	if not bom_name and item_code:
		bom_name = frappe.db.get_value("Item", item_code, "default_bom")

	if not bom_name:
		return 0

	bom = frappe.db.get_value(
		"BOM",
		bom_name,
		["total_cost", "quantity"],
		as_dict=True,
	)
	if not bom:
		return 0

	divisor = 0
	if item_code:
		item_values = frappe.db.get_value(
			"Item",
			item_code,
			["custom_item_quantity", "custom_qty_ctn", "custom_qty__ctn"],
			as_dict=True,
		) or {}
		divisor = (
			flt(item_values.get("custom_item_quantity"))
			or flt(item_values.get("custom_qty_ctn"))
			or flt(item_values.get("custom_qty__ctn"))
		)

	if not divisor:
		divisor = flt(bom.quantity)

	if not divisor:
		return 0

	cost_of_product = flt(bom.total_cost) / divisor
	company_currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	if (
		company_currency
		and currency
		and company_currency != currency
		and flt(conversion_rate)
	):
		cost_of_product = cost_of_product / flt(conversion_rate)

	return cost_of_product


@frappe.whitelist()
def get_sales_order_item_cost_of_product(
	item_code=None,
	bom_no=None,
	company=None,
	currency=None,
	conversion_rate=None,
):
	return {
		"cost_of_product": get_cost_of_product(
			item_code=item_code,
			bom_no=bom_no,
			company=company,
			currency=currency,
			conversion_rate=conversion_rate,
		),
	}


@frappe.whitelist()
def sync_sales_order_item_cost_of_product_field():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	create_custom_fields(
		{
			"Sales Order Item": [
				{
					"fieldname": "custom_cost_of_product",
					"label": "Cost of Product",
					"fieldtype": "Currency",
					"insert_after": "rate",
					"read_only": 1,
					"allow_on_submit": 1,
					"in_list_view": 1,
					"options": "currency",
					"default": "0",
					"precision": "6",
				}
			]
		},
		update=True,
	)

	customization_path = Path(__file__).resolve().parents[2] / "custom" / "sales_order_item.json"
	field_order = []
	if customization_path.exists():
		customization = json.loads(customization_path.read_text())
		for property_setter in customization.get("property_setters", []):
			if property_setter.get("name") == "Sales Order Item-main-field_order":
				field_order = json.loads(property_setter.get("value") or "[]")
				break

	field_order = [field for field in field_order if field != "custom_cost_of_product"]
	if "rate" in field_order:
		field_order.insert(field_order.index("rate") + 1, "custom_cost_of_product")
	else:
		field_order.append("custom_cost_of_product")

	if frappe.db.exists("Property Setter", "Sales Order Item-main-field_order"):
		frappe.db.set_value(
			"Property Setter",
			"Sales Order Item-main-field_order",
			"value",
			frappe.as_json(field_order),
			update_modified=False,
		)
	else:
		make_property_setter(
			"Sales Order Item",
			None,
			"field_order",
			frappe.as_json(field_order),
			"Data",
		)

	frappe.clear_cache(doctype="Sales Order Item")
	frappe.db.commit()
	return {"field_order": field_order}
