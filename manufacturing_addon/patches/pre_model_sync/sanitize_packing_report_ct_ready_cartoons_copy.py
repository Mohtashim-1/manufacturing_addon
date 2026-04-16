import frappe


def execute():
	"""Normalize child-table values so schema change to Decimal does not fail."""
	if frappe.db.db_type != "mariadb":
		return

	if not frappe.db.has_table("Packing Report CT"):
		return

	columns = frappe.db.get_table_columns("Packing Report CT")
	if "ready_cartoons_copy" not in columns:
		return

	# Remove formatting artifacts and trim whitespace.
	frappe.db.sql(
		"""
		UPDATE `tabPacking Report CT`
		SET ready_cartoons_copy = NULLIF(TRIM(REPLACE(ready_cartoons_copy, ',', '')), '')
		WHERE ready_cartoons_copy IS NOT NULL
		"""
	)

	# Ensure only values compatible with Decimal(21,9) remain.
	frappe.db.sql(
		"""
		UPDATE `tabPacking Report CT`
		SET ready_cartoons_copy = '0'
		WHERE ready_cartoons_copy IS NULL
			OR ready_cartoons_copy NOT REGEXP '^-?[0-9]+(\\.[0-9]+)?$'
			OR CAST(ready_cartoons_copy AS DECIMAL(65,30)) > 999999999999.999999999
			OR CAST(ready_cartoons_copy AS DECIMAL(65,30)) < -999999999999.999999999
		"""
	)
