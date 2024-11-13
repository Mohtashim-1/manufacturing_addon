# Copyright (c) 2024, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OrderSheet(Document):
	def validate(self):
		self.qty_per_cartoon()
		self.total()
	
	def qty_per_cartoon(self):
		qty_per_cartoon = 0
		for row in self.order_sheet_ct:
			total_cartoons = row.total_cartoons
			quantity = row.quantity
			qty_per_cartoon = quantity / total_cartoons
			row.qty_ctn = qty_per_cartoon

	def total(self):
		quantity = 0
		total_cartoons = 0
		total_quantity_per_cartoon = 0
		for i in self.order_sheet_ct:
			quantity += i.quantity
			total_cartoons += i.total_cartoons
			total_quantity_per_cartoon += i.qty_ctn
		self.total_quantity = quantity
		self.total_cartoon = total_cartoons
		self.total_quantity_per_cartoon = total_quantity_per_cartoon

