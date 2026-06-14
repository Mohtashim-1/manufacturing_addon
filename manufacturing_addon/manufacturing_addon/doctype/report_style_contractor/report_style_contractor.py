# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

from frappe.model.document import Document
from frappe.utils import flt


class ReportStyleContractor(Document):
	def validate(self):
		qty = flt(self.qty or 1) or 1
		self.amount = flt(self.rate) * qty
