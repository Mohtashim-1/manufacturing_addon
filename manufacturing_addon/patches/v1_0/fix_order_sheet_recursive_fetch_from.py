import frappe


def execute():
	"""Fix self-referential fetch_from on Order Sheet custom fields.

	Frappe validates that `fetch_from` source field cannot be the same field itself:
		fieldname = "foo", fetch_from = "foo.bar"  -> invalid (recursive)

	This can exist in DB from older customizations and will break `bench migrate`
	during `sync_customizations()` when `validate_fields_for_doctype("Order Sheet")`
	is called.
	"""
	rows = frappe.db.sql(
		"""
		SELECT name, fieldname, fetch_from, fetch_if_empty
		FROM `tabCustom Field`
		WHERE dt=%s
		  AND IFNULL(fetch_from, '') != ''
		  AND INSTR(fetch_from, '.') > 0
		""",
		("Order Sheet",),
		as_dict=True,
	)

	for r in rows:
		fetch_from = (r.get("fetch_from") or "").strip()
		fieldname = (r.get("fieldname") or "").strip()
		if not fetch_from or not fieldname:
			continue

		source_field = fetch_from.split(".", 1)[0].strip()
		if source_field != fieldname:
			continue

		# Clear invalid fetch_from and related fetch behavior.
		frappe.db.set_value(
			"Custom Field",
			r["name"],
			{"fetch_from": "", "fetch_if_empty": 0},
			update_modified=False,
		)

