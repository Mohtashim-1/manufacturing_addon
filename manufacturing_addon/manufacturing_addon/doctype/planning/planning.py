# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Planning(Document):
	def validate(self):
		self.data()
		self.add_percentage()
	
	def data(self):
		for i in self.planning_ct:
			fabric_set = i.fabric_set 
			set_data = frappe.get_doc("Fabric Set",fabric_set)
			i.consumption_per_set = set_data.total_consumption
			i.expected_consumption = i.consumption_per_set * i.total_qty
	
	def add_percentage(self):
		for i in self.planning_ct:
			initial = i.expected_consumption
			percentage = i.percentage
			final = initial + (initial * (percentage/100))
			i.final_consumption_copy = final

		
