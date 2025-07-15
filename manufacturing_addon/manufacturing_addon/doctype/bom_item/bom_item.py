# Copyright (c) 2025, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BOMItem(Document):
    def validate(self):
        # Prevent modification of frozen items
        if self.custom_frozen_from_template:
            # Check if any critical fields are being modified
            if self.has_value_changed('item_code') or self.has_value_changed('qty') or self.has_value_changed('uom') or self.has_value_changed('rate'):
                frappe.throw(_("Cannot modify frozen item from template. This item is locked and cannot be changed.")) 