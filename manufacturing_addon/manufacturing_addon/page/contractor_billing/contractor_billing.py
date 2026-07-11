# Copyright (c) 2026, Manufacturing Addon contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from manufacturing_addon.manufacturing_addon.utils.report_style_contractor import (
	billing_amount_for_work,
	_style_row_matches_report_line,
)
from manufacturing_addon.manufacturing_addon.utils.subassembly_bom import resolve_subassembly_unit_qty
from manufacturing_addon.manufacturing_addon.utils.style_contractor_split import (
	billable_amount_for_split,
	resolve_style_splits,
)

# Cutting / Stitching / Packing / Quality production reports
REPORT_SOURCES = (
	("Cutting Report", "Cutting Report CT", "Cutting", "cutting_qty"),
	("Stitching Report", "Stitching Report CT", "Stitching", "stitching_qty"),
	("Packing Report", "Packing Report CT", "Packing", "packaging_qty"),
	("Quality Report", "Quality Report CT", "Quality", "quality_qty"),
)

ITEM_STYLE_CHILD_DOCTYPES = (
	("custom_cutting_style", "Style CT"),
	("custom_stitching_style", "Stitching Style"),
	("custom_packing", "Packing Style"),
)

OPERATION_STYLE_FIELD = {
	"Cutting": "custom_cutting_style",
	"Stitching": "custom_stitching_style",
	"Packing": "custom_packing",
	"Quality": "custom_stitching_style",
}

SUBASSEMBLY_STYLE_DOCTYPES = ("Stitching Style", "Style CT", "Packing Style")


def _parse_filters(filters=None):
	if isinstance(filters, str):
		try:
			filters = frappe.parse_json(filters)
		except Exception:
			filters = {}
	filters = filters or {}
	if not filters.get("from_date"):
		filters["from_date"] = frappe.utils.add_months(nowdate(), -12)
	if not filters.get("to_date"):
		filters["to_date"] = nowdate()
	return filters


def _subassembly_row_names():
	names = set()
	for doctype in SUBASSEMBLY_STYLE_DOCTYPES:
		if not frappe.db.table_exists(doctype):
			continue
		if not frappe.db.has_column(doctype, "is_subassembly"):
			continue
		names.update(
			frappe.get_all(doctype, filters={"is_subassembly": 1}, pluck="name", limit=0) or []
		)
	return names


def _report_has_supplier(report_doctype):
	return bool(frappe.get_meta(report_doctype).has_field("supplier"))


def _fetch_report_ct_rows(filters):
	"""Load submitted report child rows with work quantity."""
	values = {
		"from_date": getdate(filters["from_date"]),
		"to_date": getdate(filters["to_date"]),
	}
	extra_order = ""
	extra_supplier = ""
	if filters.get("order_sheet"):
		extra_order = " AND r.order_sheet = %(order_sheet)s"
		values["order_sheet"] = filters["order_sheet"]
	if filters.get("contractor"):
		extra_supplier = " AND r.supplier = %(contractor)s"
		values["contractor"] = filters["contractor"]

	rows = []
	for report, ct, operation, qty_field in REPORT_SOURCES:
		if not frappe.db.table_exists(report) or not frappe.db.table_exists(ct):
			continue
		if not frappe.get_meta(ct).has_field(qty_field):
			continue

		supplier_col = "r.supplier" if _report_has_supplier(report) else "NULL"
		article_col = "ct.article" if frappe.get_meta(ct).has_field("article") else "NULL"

		part = f"""
			SELECT
				%(operation_{operation})s AS operation,
				%(report_{operation})s AS report_doctype,
				%(ct_{operation})s AS ct_doctype,
				r.name AS report_name,
				r.date AS report_date,
				r.order_sheet,
				{supplier_col} AS report_supplier,
				ct.name AS ct_row_name,
				ct.so_item,
				ct.combo_item,
				{article_col} AS article,
				COALESCE(ct.`{qty_field}`, 0) AS work_qty
			FROM `tab{ct}` ct
			INNER JOIN `tab{report}` r ON ct.parent = r.name
			WHERE r.docstatus = 1
				AND COALESCE(ct.`{qty_field}`, 0) > 0
				AND r.date BETWEEN %(from_date)s AND %(to_date)s
				{extra_order}
				{extra_supplier}
		"""
		values[f"operation_{operation}"] = operation
		values[f"report_{operation}"] = report
		values[f"ct_{operation}"] = ct
		rows.extend(frappe.db.sql(part, values, as_dict=True))

	return rows


def _bulk_variant_of(item_codes):
	"""Map item code → template (variant_of) when configured."""
	if not item_codes:
		return {}
	rows = frappe.get_all(
		"Item",
		filters={"name": ["in", item_codes]},
		fields=["name", "variant_of"],
	)
	return {r.name: r.variant_of for r in rows if r.variant_of}


def _bulk_style_cache(item_codes):
	"""Prefetch all Item style-tab child rows for many items."""
	lookup_codes = set(item_codes or [])
	variant_map = _bulk_variant_of(list(lookup_codes))
	lookup_codes.update(v for v in variant_map.values() if v)

	cache = {code: [] for code in lookup_codes}
	if not lookup_codes:
		return cache, variant_map
	for table_field, child_doctype in ITEM_STYLE_CHILD_DOCTYPES:
		if not frappe.db.table_exists(child_doctype):
			continue
		fields = ["name", "parent", "style", "rate", "qty", "amount", "combo_item", "stitching_component", "is_subassembly"]
		available = {f.fieldname for f in frappe.get_meta(child_doctype).fields}
		available.update({"name", "parent"})
		fields = [f for f in fields if f in available]
		for row in frappe.get_all(
			child_doctype,
			filters={"parent": ["in", item_codes]},
			fields=fields,
		):
			parent = row.get("parent")
			if not parent or parent not in cache:
				continue
			row["_table_field"] = table_field
			cache[parent].append(row)
	return cache, variant_map


def _resolve_item_styles(style_cache, variant_map, item_code, operation, combo_item=None, article=None):
	"""Match Item style-tab rows for a report line (same rules as report_style_contractor)."""
	own_field = OPERATION_STYLE_FIELD.get(operation)

	def _collect_from_item(code):
		if not code:
			return []
		seen = set()
		rows = []
		for style_row in style_cache.get(code, []):
			if not style_row.get("style"):
				continue
			row_key = style_row.get("name") or f"{style_row.get('_table_field')}:{style_row.get('style')}"
			if row_key in seen:
				continue

			is_subassembly = bool(style_row.get("is_subassembly"))
			is_own_table = style_row.get("_table_field") == own_field

			if is_own_table or is_subassembly:
				pass
			else:
				continue

			seen.add(row_key)
			rows.append(style_row)
		return rows

	def _filter_match(candidates, combo, article):
		matched = [
			r
			for r in candidates
			if _style_row_matches_report_line(r, item_code, combo, article)
		]
		return matched or candidates

	for code in (item_code, variant_map.get(item_code)):
		if not code:
			continue
		rows = _collect_from_item(code)
		if not rows:
			continue
		strict = _filter_match(rows, combo_item, article)
		if strict:
			return strict
		relaxed = _filter_match(rows, None, None)
		if relaxed:
			return relaxed

	# Combo item may be a component Item with its own style tab.
	if combo_item and frappe.db.exists("Item", combo_item):
		for code in (combo_item, variant_map.get(combo_item)):
			if not code:
				continue
			rows = _collect_from_item(code)
			if not rows:
				continue
			strict = _filter_match(rows, combo_item, article)
			if strict:
				return strict
			relaxed = _filter_match(rows, None, None)
			if relaxed:
				return relaxed

	return []


def _billing_operation(operation, style_row, subassembly_names):
	"""Use report process unless style is a cross-process subassembly row."""
	own_field = OPERATION_STYLE_FIELD.get(operation)
	row_name = style_row.get("name")
	is_sub = row_name in subassembly_names or bool(style_row.get("is_subassembly"))
	if is_sub and style_row.get("_table_field") != own_field:
		return "Sub-Assembly"
	return operation


def _load_style_contractor_maps(ct_rows):
	"""Bulk-load saved style contractor rows keyed by CT row name (lists per parent)."""
	if not ct_rows or not frappe.db.table_exists("Report Style Contractor"):
		return {}
	by_parenttype = {}
	for row in ct_rows:
		by_parenttype.setdefault(row.ct_doctype, []).append(row.ct_row_name)

	out = {}
	for parenttype, parents in by_parenttype.items():
		for entry in frappe.get_all(
			"Report Style Contractor",
			filters={"parent": ["in", parents], "parenttype": parenttype},
			fields=[
				"parent",
				"item_style_row",
				"contractor",
				"style",
				"rate",
				"qty",
				"split_qty",
				"amount",
				"is_subassembly",
			],
			order_by="idx asc",
		):
			out.setdefault(entry.parent, []).append(entry)
	return out


def _fetch_billing_lines(filters, ct_rows=None):
	"""Build billing lines from report qty × Item style tab rates."""
	subassembly_names = _subassembly_row_names()
	ct_rows = ct_rows or _fetch_report_ct_rows(filters)
	item_codes = list({r.so_item for r in ct_rows if r.so_item})
	combo_codes = list({r.combo_item for r in ct_rows if r.combo_item and frappe.db.exists("Item", r.combo_item)})
	style_cache, variant_map = _bulk_style_cache(item_codes + combo_codes)
	sc_maps = _load_style_contractor_maps(ct_rows)
	lines = []

	for ct_row in ct_rows:
		work_qty = flt(ct_row.work_qty)
		so_item = ct_row.so_item
		if not so_item or work_qty <= 0:
			continue

		operation = ct_row.operation
		style_rows = _resolve_item_styles(
			style_cache,
			variant_map,
			so_item,
			operation=operation,
			combo_item=ct_row.combo_item,
			article=ct_row.article,
		)
		if not style_rows:
			continue

		sc_list = sc_maps.get(ct_row.ct_row_name, [])
		default_contractor = ct_row.report_supplier or ""

		for style_row in style_rows:
			is_sub = style_row.name in subassembly_names or bool(style_row.get("is_subassembly"))
			style_qty = resolve_subassembly_unit_qty(so_item, style_row) if is_sub else (
				flt(style_row.get("qty") or 1) or 1
			)
			rate = flt(style_row.get("rate"))
			op = _billing_operation(operation, style_row, subassembly_names)

			splits = resolve_style_splits(style_row, sc_list, work_qty, default_contractor)
			if not splits:
				continue

			for contractor, split_work_qty, sc in splits:
				if is_sub:
					billable_qty = flt(split_work_qty) * style_qty
					amount = billable_qty * (flt((sc or {}).get("rate")) or rate)
				else:
					billable_qty, amount = billable_amount_for_split(
						so_item, style_row, split_work_qty, sc
					)

				if amount <= 0 and not rate and not flt(style_row.get("amount")):
					continue

				lines.append(
					{
						"contractor": contractor,
						"operation": op,
						"order_sheet": ct_row.order_sheet or "",
						"report_name": ct_row.report_name,
						"ct_row_name": ct_row.ct_row_name,
						"report_date": ct_row.report_date,
						"so_item": so_item,
						"combo_item": ct_row.combo_item,
						"article": ct_row.article,
						"style": style_row.style,
						"item_style_row": style_row.name,
						"work_qty": split_work_qty,
						"style_qty": style_qty,
						"rate": flt((sc or {}).get("rate")) or rate,
						"qty": billable_qty,
						"amount": amount,
						"is_subassembly": is_sub,
					}
				)

	return lines


def _aggregate_lines(lines, process_filter=None):
	grouped = {}
	for row in lines:
		op = row["operation"] or "Other"
		if process_filter and process_filter != "All":
			if process_filter == "Sub-Assembly":
				if not row["is_subassembly"]:
					continue
			elif op != process_filter:
				continue

		key = (row["contractor"], op, row["order_sheet"] or "")
		if key not in grouped:
			grouped[key] = {
				"contractor": row["contractor"],
				"process": op,
				"order_sheet": row["order_sheet"] or "",
				"total_bill": 0,
				"qty": 0,
				"is_subassembly": row["is_subassembly"],
				"report_names": set(),
				"details": [],
			}
		g = grouped[key]
		g["total_bill"] += flt(row["amount"])
		g["qty"] += flt(row["qty"])
		g["is_subassembly"] = g["is_subassembly"] or row["is_subassembly"]
		if row["report_name"]:
			g["report_names"].add(row["report_name"])
		g["details"].append(
			{
				"report_name": row["report_name"],
				"report_date": str(row["report_date"]) if row["report_date"] else "",
				"amount": flt(row["amount"]),
				"qty": flt(row["qty"]),
				"work_qty": flt(row["work_qty"]),
				"style": row.get("style"),
				"rate": flt(row.get("rate")),
				"so_item": row.get("so_item"),
			}
		)

	out = []
	for g in grouped.values():
		g["report_names"] = sorted(g["report_names"])
		out.append(g)
	out.sort(key=lambda r: (-r["total_bill"], r["contractor"] or "", r["process"] or ""))
	return out


def _fetch_settlement_payments(filters):
	if not frappe.db.table_exists("Contractor Settlement"):
		return {}, {"draft": 0, "paid": 0, "due": 0, "partial": 0}

	conditions = ["cs.docstatus = 1"]
	values = {
		"from_date": getdate(filters["from_date"]),
		"to_date": getdate(filters["to_date"]),
	}
	conditions.append("cs.to_date >= %(from_date)s")
	conditions.append("cs.from_date <= %(to_date)s")
	if filters.get("contractor"):
		conditions.append("cs.contractor = %(contractor)s")
		values["contractor"] = filters["contractor"]

	where = " AND ".join(conditions)
	rows = frappe.db.sql(
		f"""
		SELECT
			cs.contractor,
			cs.name AS settlement,
			COALESCE(cs.total_amount, 0) AS total_amount,
			cs.purchase_invoice,
			COALESCE(pi.grand_total, 0) - COALESCE(pi.outstanding_amount, 0) AS paid_amount,
			COALESCE(pi.outstanding_amount, 0) AS pi_outstanding
		FROM `tabContractor Settlement` cs
		LEFT JOIN `tabPurchase Invoice` pi
			ON pi.name = cs.purchase_invoice AND pi.docstatus = 1
		WHERE {where}
		""",
		values,
		as_dict=True,
	)

	by_contractor = {}
	bill_counts = {"draft": 0, "paid": 0, "due": 0, "partial": 0}

	draft_rows = frappe.db.sql("SELECT COUNT(*) FROM `tabContractor Settlement` WHERE docstatus = 0")
	bill_counts["draft"] = int(draft_rows[0][0] if draft_rows else 0)

	for row in rows:
		contractor = row.contractor
		if not contractor:
			continue
		entry = by_contractor.setdefault(contractor, {"billed": 0, "paid": 0, "outstanding": 0})
		billed = flt(row.total_amount)
		paid = flt(row.paid_amount) if row.purchase_invoice else 0
		outstanding = flt(row.pi_outstanding) if row.purchase_invoice else billed
		entry["billed"] += billed
		entry["paid"] += paid
		entry["outstanding"] += outstanding if row.purchase_invoice else max(billed - paid, 0)

		if row.purchase_invoice:
			if outstanding <= 0.01:
				bill_counts["paid"] += 1
			elif paid > 0:
				bill_counts["partial"] += 1
				bill_counts["due"] += 1
			else:
				bill_counts["due"] += 1
		else:
			bill_counts["due"] += 1

	return by_contractor, bill_counts


def _supplier_label(contractor):
	if not contractor or contractor == "Unassigned":
		return ""
	return frappe.db.get_value("Manufacturing Contractor", contractor, "supplier") or ""


def _apply_payment_split(rows, payment_map):
	contractor_totals = {}
	for row in rows:
		if row["contractor"] == "Unassigned":
			continue
		contractor_totals[row["contractor"]] = contractor_totals.get(row["contractor"], 0) + row["total_bill"]

	for row in rows:
		contractor = row["contractor"]
		if contractor == "Unassigned":
			row["paid"] = 0
			row["due"] = row["total_bill"]
			row["supplier"] = ""
			row["progress"] = 0
			row["status"] = "Due"
			continue

		total_work = contractor_totals.get(contractor, 0)
		pay = payment_map.get(contractor, {})
		contractor_paid = flt(pay.get("paid"))
		share = row["total_bill"] / total_work if total_work else 0
		# A settlement may include work outside the selected process or date range.
		# Never present more of that payment than this filtered billing row can clear.
		row["paid"] = min(round(contractor_paid * share, 2), row["total_bill"])
		row["due"] = max(row["total_bill"] - row["paid"], 0)
		row["supplier"] = _supplier_label(contractor)
		row["progress"] = min(round((row["paid"] / row["total_bill"]) * 100, 1), 100) if row["total_bill"] else 0

		if row["due"] <= 0.01 and row["total_bill"] > 0:
			row["status"] = "Paid"
		elif row["paid"] > 0:
			row["status"] = "Partial"
		else:
			row["status"] = "Due"

	return rows


def _filter_lines_by_process(lines, process_filter=None):
	if not process_filter or process_filter == "All":
		return lines
	filtered = []
	for row in lines:
		op = row.get("operation") or "Other"
		if process_filter == "Sub-Assembly":
			if row.get("is_subassembly"):
				filtered.append(row)
		elif op == process_filter and not row.get("is_subassembly"):
			filtered.append(row)
	return filtered


def _build_trend_chart(rows):
	by_month = {}
	for row in rows:
		total = flt(row.get("total_bill"))
		for detail in row.get("details") or []:
			month = str(detail.get("report_date"))[:7] if detail.get("report_date") else "Unknown"
			entry = by_month.setdefault(month, {"billed": 0, "paid": 0, "qty": 0})
			amount = flt(detail.get("amount"))
			entry["billed"] += amount
			entry["qty"] += flt(detail.get("qty"))
			entry["paid"] += flt(row.get("paid")) * (amount / total if total else 0)
	labels = sorted(by_month.keys())
	return {
		"labels": labels,
		"billed": [by_month[m]["billed"] for m in labels],
		"paid": [by_month[m]["paid"] for m in labels],
		"qty": [by_month[m]["qty"] for m in labels],
	}


def _build_status_summary(rows):
	counts = {"Paid": 0, "Partial": 0, "Due": 0}
	for row in rows:
		status = row.get("status") or "Due"
		counts[status] = counts.get(status, 0) + 1
	return {"counts": counts}


def _build_process_chart(rows):
	by_contractor = {}
	for row in rows:
		if row["contractor"] == "Unassigned":
			continue
		by_contractor[row["contractor"]] = by_contractor.get(row["contractor"], 0) + row["total_bill"]
	sorted_items = sorted(by_contractor.items(), key=lambda x: -x[1])[:12]
	return {
		"labels": [x[0] for x in sorted_items],
		"amounts": [x[1] for x in sorted_items],
	}


def _build_contractor_stacked_chart(rows):
	by_contractor = {}
	for row in rows:
		contractor = row.get("contractor")
		if not contractor or contractor == "Unassigned":
			continue
		entry = by_contractor.setdefault(contractor, {"paid": 0, "due": 0, "total": 0})
		entry["paid"] += flt(row.get("paid"))
		entry["due"] += flt(row.get("due"))
		entry["total"] += flt(row.get("total_bill"))
	sorted_items = sorted(by_contractor.items(), key=lambda x: -x[1]["total"])[:10]
	return {
		"labels": [x[0] for x in sorted_items],
		"paid": [x[1]["paid"] for x in sorted_items],
		"due": [x[1]["due"] for x in sorted_items],
		"totals": [x[1]["total"] for x in sorted_items],
	}


def _build_order_chart(rows):
	by_order = {}
	for row in rows:
		key = row.get("order_sheet") or _("No Order")
		by_order[key] = by_order.get(key, 0) + flt(row.get("total_bill"))
	sorted_items = sorted(by_order.items(), key=lambda x: -x[1])[:10]
	return {
		"labels": [x[0] for x in sorted_items],
		"amounts": [x[1] for x in sorted_items],
	}


def _build_report_volume_chart(ct_rows):
	by_op = {}
	for row in ct_rows:
		if flt(row.work_qty) <= 0 or not row.so_item:
			continue
		op = row.operation or "Other"
		by_op[op] = by_op.get(op, 0) + 1
	order = ["Cutting", "Stitching", "Packing", "Quality", "Sub-Assembly", "Other"]
	labels = [op for op in order if by_op.get(op)]
	labels += [op for op in sorted(by_op) if op not in labels]
	return {
		"labels": labels,
		"counts": [by_op.get(l, 0) for l in labels],
		"work_qty": [
			sum(flt(r.work_qty) for r in ct_rows if (r.operation or "Other") == l and r.so_item)
			for l in labels
		],
	}


def _build_process_qty_chart(lines):
	by_proc = {}
	for row in lines:
		proc = row.get("operation") or "Other"
		by_proc[proc] = by_proc.get(proc, 0) + flt(row.get("qty"))
	labels = sorted(by_proc.keys(), key=lambda k: -by_proc[k])
	return {"labels": labels, "qty": [by_proc[l] for l in labels]}


def _build_coverage_chart(ct_rows, billed_lines):
	# CT row names are unique. Using report/item/operation makes repeated Item rows in
	# one report appear rated when only one of them actually has a matching Style rate.
	billed_keys = {l.get("ct_row_name") for l in billed_lines if l.get("ct_row_name")}
	by_op = {}
	for row in ct_rows:
		if flt(row.work_qty) <= 0 or not row.so_item:
			continue
		op = row.operation or "Other"
		entry = by_op.setdefault(op, {"rated": 0, "missing": 0})
		if row.ct_row_name in billed_keys:
			entry["rated"] += 1
		else:
			entry["missing"] += 1
	order = ["Cutting", "Stitching", "Packing", "Quality", "Other"]
	labels = [op for op in order if op in by_op]
	labels += [op for op in sorted(by_op) if op not in labels]
	return {
		"labels": labels,
		"rated": [by_op.get(l, {}).get("rated", 0) for l in labels],
		"missing": [by_op.get(l, {}).get("missing", 0) for l in labels],
	}


def _build_unbilled_rows(ct_rows, billed_lines):
	"""Production rows which cannot be valued because no eligible Style rate matched."""
	billed_keys = {line.get("ct_row_name") for line in billed_lines if line.get("ct_row_name")}
	rows = []
	for row in ct_rows:
		if row.ct_row_name in billed_keys or flt(row.work_qty) <= 0 or not row.so_item:
			continue
		rows.append(
			{
				"report_doctype": row.report_doctype,
				"report_name": row.report_name,
				"report_date": str(row.report_date) if row.report_date else "",
				"process": row.operation or "Other",
				"order_sheet": row.order_sheet or "",
				"item_code": row.so_item,
				"combo_item": row.combo_item or "",
				"article": row.article or "",
				"work_qty": flt(row.work_qty),
				"reason": _("No matching Item Style rate"),
			}
		)
	rows.sort(key=lambda row: (row["process"], row["report_date"], row["report_name"]))
	return {"total": len(rows), "rows": rows[:500], "is_limited": len(rows) > 500}


@frappe.whitelist()
def get_contractor_billing_data(filters=None):
	filters = _parse_filters(filters)
	process_filter = (filters.get("process") or "All").strip()

	ct_rows = _fetch_report_ct_rows(filters)
	lines = _fetch_billing_lines(filters, ct_rows=ct_rows)
	filtered_lines = _filter_lines_by_process(lines, process_filter)
	if process_filter == "All":
		filtered_ct_rows = ct_rows
	elif process_filter == "Sub-Assembly":
		filtered_names = {line.get("ct_row_name") for line in filtered_lines}
		filtered_ct_rows = [row for row in ct_rows if row.ct_row_name in filtered_names]
	else:
		filtered_ct_rows = [row for row in ct_rows if row.operation == process_filter]
	report_qty_rows = sum(1 for r in filtered_ct_rows if flt(r.work_qty) > 0 and r.so_item)
	rated_report_rows = len({line.get("ct_row_name") for line in filtered_lines if line.get("ct_row_name")})
	rows = _aggregate_lines(filtered_lines, process_filter=None)
	payment_map, bill_counts = _fetch_settlement_payments(filters)
	rows = _apply_payment_split(rows, payment_map)

	search = (filters.get("search") or "").strip().lower()
	if search:
		rows = [
			r
			for r in rows
			if search in (r.get("contractor") or "").lower()
			or search in (r.get("order_sheet") or "").lower()
			or search in (r.get("supplier") or "").lower()
		]

	status_filter = (filters.get("status") or "All").strip()
	if status_filter and status_filter != "All":
		rows = [r for r in rows if r.get("status") == status_filter]

	total_billed = sum(flt(r["total_bill"]) for r in rows)
	total_paid = sum(flt(r["paid"]) for r in rows)
	total_due = sum(flt(r["total_due"]) if "total_due" in r else flt(r["due"]) for r in rows)
	contractor_count = len({r["contractor"] for r in rows if r.get("contractor") and r["contractor"] != "Unassigned"})

	kpis = {
		"total_billed": total_billed,
		"total_paid": total_paid,
		"total_due": total_due,
		"contractor_count": contractor_count,
		"cleared_pct": round((total_paid / total_billed) * 100, 1) if total_billed else 0,
		"bills_due": bill_counts.get("due", 0),
		"bills_paid": bill_counts.get("paid", 0),
		"bills_partial": bill_counts.get("partial", 0),
		"bills_draft": bill_counts.get("draft", 0),
		"line_count": len(filtered_lines),
		"rated_report_rows": rated_report_rows,
		"report_qty_rows": report_qty_rows,
	}

	process_totals = {}
	for row in rows:
		proc = row.get("process") or "Other"
		process_totals[proc] = process_totals.get(proc, 0) + flt(row["total_bill"])

	return {
		"kpis": kpis,
		"rows": rows,
		"process_chart": _build_process_chart(rows),
		"contractor_stacked": _build_contractor_stacked_chart(rows),
		"order_chart": _build_order_chart(rows),
		"report_volume": _build_report_volume_chart(filtered_ct_rows),
		"process_qty": _build_process_qty_chart(filtered_lines),
		"coverage_chart": _build_coverage_chart(filtered_ct_rows, filtered_lines),
		"unbilled": _build_unbilled_rows(filtered_ct_rows, filtered_lines),
		"process_totals": process_totals,
		"trend_chart": _build_trend_chart(rows),
		"status_summary": _build_status_summary(rows),
		"filters": filters,
	}
