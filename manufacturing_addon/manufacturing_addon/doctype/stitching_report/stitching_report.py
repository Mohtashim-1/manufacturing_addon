# Copyright (c) 2024, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StitchingReport(Document):
	def validate(self):
		self.calculate_dovet_line()
		self.calculate_pillow_line()
		self.sum_total_operators()
	
	def calculate_dovet_line(self):
		total = 0 
		for i in self.dovet_line:
			total += i.no_of_operator
		self.dovet_operators = total
	
	def calculate_pillow_line(self):
		total1 = 0 
		for j in self.pillow_line:
			total1 += j.no_of_operator
		self.pillow_operators = total1
	
	def sum_total_operators(self):
		dovet = self.dovet_operators
		pillow = self.pillow_operators
		total_operator = dovet + pillow
		self.total_operators = total_operator

