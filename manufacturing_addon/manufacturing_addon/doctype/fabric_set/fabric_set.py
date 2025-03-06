# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FabricSet(Document):
	def validate(self):
		self.data()
		self.total()
	
	def total(self):
		total_qty = 0
		consumption = 0
		# frappe.msgprint(f"Total Qty Calculated: {total_qty}")
		if self.planning_ct:  # Ensure there are rows
			for k in self.planning_ct:
				total_qty += k.qty or 0  # Use 0 if qty is None
				consumption += k.consumption
		self.total_qty = total_qty
		self.total_consumption = consumption
		# frappe.msgprint(f"Total Qty Calculated: {total_qty}")

	def data(self):
		for i in self.planning_ct:
			# Fields from the current row in planning
			faced_type = i.faced_type
			gsm = i.gsm
			cutting_style = i.cutting_style
			width = i.width
			qty = i.qty

			# Fetch the matching Master Size document
			master_size = frappe.get_doc("Master Size", i.main_category)
			match_found = False

			for j in master_size.master_size_ct:
				# Check if all fields match
				if (
					j.faced_type == faced_type and
					j.gsm == gsm and
					j.cutting_style == cutting_style and
					j.width == width
				):
					# Calculate and set consumption
					i.consumption = j.consumption * qty
					match_found = True
					break  # Stop searching once a match is found

			if not match_found:
				frappe.throw(
					f"No matching data found in Master Size for: Faced Type = {faced_type}, GSM = {gsm}, Cutting Style = {cutting_style}, Width = {width}"
				)

