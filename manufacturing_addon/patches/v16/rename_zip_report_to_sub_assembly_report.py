# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

"""Remove legacy Zip Report DocTypes and rename contractor zip flag."""

from __future__ import annotations

import frappe
from frappe.model.utils.rename_field import rename_field


def _drop_table(table_name: str):
	if frappe.db.has_table(table_name):
		frappe.db.sql(f"DROP TABLE IF EXISTS `{table_name}`")


def _delete_doctype_record(doctype: str):
	"""Delete DocType metadata without loading removed Python controllers."""
	if not frappe.db.exists("DocType", doctype):
		return

	# Child rows first
	for child in (
		"DocField",
		"DocPerm",
		"DocType Action",
		"DocType Link",
		"DocType State",
	):
		if frappe.db.has_table(f"tab{child}"):
			frappe.db.sql(f"DELETE FROM `tab{child}` WHERE parent=%s", doctype)

	frappe.db.sql("DELETE FROM `tabDocType` WHERE name=%s", doctype)
	_drop_table(f"tab{doctype}")


def execute():
	# Clear Zip Report documents via SQL (controller module already removed)
	if frappe.db.has_table("tabZip Report CT"):
		frappe.db.sql("DELETE FROM `tabZip Report CT`")
	if frappe.db.has_table("tabZip Report"):
		frappe.db.sql("DELETE FROM `tabZip Report`")

	_delete_doctype_record("Zip Report")
	_delete_doctype_record("Zip Report CT")
	frappe.db.commit()

	# Rename Manufacturing Contractor.zip → sub_assembly if still old
	if frappe.db.exists("DocType", "Manufacturing Contractor"):
		has_zip_col = frappe.db.has_column("Manufacturing Contractor", "zip")
		has_sub_col = frappe.db.has_column("Manufacturing Contractor", "sub_assembly")
		has_zip_field = frappe.db.exists("DocField", {"parent": "Manufacturing Contractor", "fieldname": "zip"})
		has_sub_field = frappe.db.exists(
			"DocField", {"parent": "Manufacturing Contractor", "fieldname": "sub_assembly"}
		)

		if has_zip_field and not has_sub_field:
			rename_field("Manufacturing Contractor", "zip", "sub_assembly")
		elif has_zip_col and has_sub_col:
			frappe.db.sql(
				"""
				UPDATE `tabManufacturing Contractor`
				SET sub_assembly = IF(IFNULL(sub_assembly, 0) OR IFNULL(zip, 0), 1, 0)
				"""
			)
			frappe.db.sql("ALTER TABLE `tabManufacturing Contractor` DROP COLUMN `zip`")
			frappe.db.sql(
				"""
				DELETE FROM `tabDocField`
				WHERE parent='Manufacturing Contractor' AND fieldname='zip'
				"""
			)
		elif has_zip_col and not has_sub_col:
			frappe.db.sql(
				"ALTER TABLE `tabManufacturing Contractor` CHANGE `zip` `sub_assembly` int(1) NOT NULL DEFAULT 0"
			)
			frappe.db.sql(
				"""
				UPDATE `tabDocField`
				SET fieldname='sub_assembly', label='Sub Assembly'
				WHERE parent='Manufacturing Contractor' AND fieldname='zip'
				"""
			)

	# Workspace link cleanup
	if frappe.db.has_table("tabWorkspace Link"):
		frappe.db.sql(
			"""
			UPDATE `tabWorkspace Link`
			SET label = 'Sub Assembly Report', link_to = 'Sub Assembly Report'
			WHERE parent = 'Manufacturing Addon' AND link_to = 'Zip Report'
			"""
		)

	frappe.clear_cache()
