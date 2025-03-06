# Copyright (c) 2024, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OrderSheet(Document):
	def validate(self):
		self.qty_per_cartoon()
		self.total()
		self.consumption()
		# self.total_qty()
	
	def qty_per_cartoon(self):
		for row in self.order_sheet_ct:
			# total_cartoons = row.total_cartoons or 0  
			quantity = row.quantity or 0  # Ensure it's not None
			qty_ctn = row.qty_ctn or 0 

			if qty_ctn > 0:  # Prevent division by zero
				row.total_cartoons = quantity / qty_ctn  # 230 / 22 = 10 
				# frappe.msgprint(f"Total Cartoons: {row.total_cartoons}")
				# frappe.errprint(f"Total Cartoons: {row.total_cartoons}")
			else:
				row.total_cartoons = 0  # Set to 0 if total_cartoons is invalid
			# 	frappe.msgprint('Total Cartoons set to 0')




	def total(self):
		quantity = 0
		total_cartoons = 0
		total_quantity_per_cartoon = 0
		for i in self.order_sheet_ct:
			quantity += i.quantity or 0
			total_cartoons += i.total_cartoons or 0
			total_quantity_per_cartoon += i.qty_ctn or 0
		self.total_quantity = quantity
		self.total_cartoon = total_cartoons
		self.total_quantity_per_cartoon = total_quantity_per_cartoon

	def consumption(self):
		total_consumption = 0
		for i in self.order_sheet_ct:
			# total_consumption += i.total_consumption
			total_consumption += i.total_consumption if i.total_consumption else 0
			if i.consumption and i.quantity:
				i.total_consumption = i.consumption * i.quantity
		self.total_consumption = total_consumption
	
	

