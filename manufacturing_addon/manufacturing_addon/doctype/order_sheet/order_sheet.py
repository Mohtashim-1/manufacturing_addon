# Copyright (c) 2024, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OrderSheet(Document):
	def validate(self):
		self.total_cartoon()
	
	def total_cartoon(self):
		total_cartoon = 0
		for row in self.order_sheet_ct:
			qty_ctn = row.qty_ctn
			quantity = row.quantity
			total_cartoons = qty_ctn / quantity
			row.total_cartoons = total_cartoons
