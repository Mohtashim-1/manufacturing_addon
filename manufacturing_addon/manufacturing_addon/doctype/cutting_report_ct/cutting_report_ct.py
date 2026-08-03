# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from manufacturing_addon.manufacturing_addon.utils.nested_style_contractors import (
	StyleContractorsChildMixin,
)


class CuttingReportCT(StyleContractorsChildMixin, Document):
	pass
