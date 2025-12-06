# Copyright (c) 2024, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StitchingSize(Document):
	def validate(self):
		"""Validate that required fields are present"""
		if not self.lenght:
			frappe.throw("Lenght is required")
		if not self.width:
			frappe.throw("Width is required")
	
	def autoname(self):
		"""Custom autoname - use size field if available, otherwise build from lenght/width"""
		# If size field is set, use it directly as the name
		if self.size:
			self.name = self.size
			return
		
		# Otherwise, build name from lenght/width/standard_size/flap
		# Format numbers without .0 for integers
		def format_num(n):
			if n is None:
				return ""
			if isinstance(n, float) and n.is_integer():
				return str(int(n))
			return str(n)
		
		# Build name: {lenght}X{width},{standard_size}+{flap}
		lenght_str = format_num(self.lenght)
		width_str = format_num(self.width)
		name_parts = [f"{lenght_str}X{width_str}"]
		
		# Add standard_size if exists
		if self.standard_size:
			std_part = self.standard_size
		else:
			std_part = ""
		
		# Add flap if exists
		if self.flap is not None:
			flap_str = format_num(self.flap)
			flap_part = f"+{flap_str}"
		else:
			flap_part = ""
		
		# Build final name
		if std_part:
			name = f"{name_parts[0]},{std_part}{flap_part}"
		else:
			# If no standard_size, just use lenghtXwidth+flap or lenghtXwidth
			if flap_part:
				name = f"{name_parts[0]}{flap_part}"
			else:
				name = name_parts[0]
		
		self.name = name
