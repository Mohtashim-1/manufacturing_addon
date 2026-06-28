# Copyright (c) 2026, mohtashim and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_order_drill_down(order_sheet):
	"""Return item/combo-level production breakdown for one Order Sheet."""

	# ── Production by combo_item + colour (from production reports) ──
	def get_production_by_combo(report_dt, ct_dt, qty_col):
		rows = frappe.db.sql(
			f"""
			SELECT
				IFNULL(crct.combo_item, '')     AS combo_item,
				IFNULL(crct.colour, '')          AS colour,
				IFNULL(crct.article, '')         AS article,
				IFNULL(SUM(crct.{qty_col}), 0)  AS qty,
				COUNT(DISTINCT cr.date)          AS active_days
			FROM `tab{report_dt}` cr
			JOIN `tab{ct_dt}` crct ON crct.parent = cr.name
			WHERE cr.docstatus = 1
			  AND cr.order_sheet = %s
			GROUP BY crct.combo_item, crct.colour, crct.article
			ORDER BY crct.combo_item, crct.colour
			""",
			(order_sheet,),
			as_dict=True,
		)
		return {
			(r.combo_item, r.colour): {
				"qty":     flt(r.qty),
				"days":    max(int(r.active_days or 1), 1),
				"article": r.article,
			}
			for r in rows
		}, set(rows and [(r.combo_item, r.colour) for r in rows] or [])

	cut_map,    cut_keys    = get_production_by_combo("Cutting Report",   "Cutting Report CT",   "cutting_qty")
	stitch_map, stitch_keys = get_production_by_combo("Stitching Report", "Stitching Report CT", "stitching_qty")
	check_map,  check_keys  = get_production_by_combo("Checking Report",  "Checking Report CT",  "checking_qty")
	pack_map,   pack_keys   = get_production_by_combo("Packing Report",   "Packing Report CT",   "packaging_qty")

	# Union of all combo+colour keys seen across all stages
	all_keys = cut_keys | stitch_keys | check_keys | pack_keys

	# ── Order quantities per combo_item from Order Sheet CT ──────────
	os_items = frappe.db.sql(
		"""
		SELECT
			IFNULL(osct.combo_item, '')     AS combo_item,
			IFNULL(osct.colour, '')         AS colour,
			IFNULL(SUM(osct.order_qty), 0)  AS order_qty
		FROM `tabOrder Sheet CT` osct
		WHERE osct.parent = %s
		GROUP BY osct.combo_item, osct.colour
		""",
		(order_sheet,),
		as_dict=True,
	)
	order_map = {(r.combo_item, r.colour): flt(r.order_qty) for r in os_items}

	# Merge order_map keys too so items with no production appear
	all_keys |= set(order_map.keys())

	# ── Build result rows ─────────────────────────────────────────────
	def pct(done, total):
		return round(done / total * 100, 1) if total > 0 else 0

	result = []
	for key in sorted(all_keys):
		combo_item, colour = key
		oq = order_map.get(key, 0)

		cut_d    = cut_map.get(key,    {"qty": 0, "days": 1, "article": ""})
		stitch_d = stitch_map.get(key, {"qty": 0, "days": 1, "article": ""})
		check_d  = check_map.get(key,  {"qty": 0, "days": 1, "article": ""})
		pack_d   = pack_map.get(key,   {"qty": 0, "days": 1, "article": ""})

		article = (cut_d["article"] or stitch_d["article"] or check_d["article"] or pack_d["article"])

		tc  = cut_d["qty"]
		ts  = stitch_d["qty"]
		tch = check_d["qty"]
		tp  = pack_d["qty"]

		# Use max of all stage totals as reference if no order_qty
		ref_qty = oq if oq > 0 else max(tc, ts, tch, tp)

		result.append({
			"combo_item":  combo_item or "—",
			"colour":      colour or "—",
			"article":     article,
			"order_qty":   oq,
			# Cutting
			"cut_done":    tc,
			"cut_pending": max(ref_qty - tc, 0) if ref_qty > 0 else 0,
			"cut_pct":     pct(tc, ref_qty),
			"cut_avg_d":   round(tc / cut_d["days"], 1) if tc > 0 else 0,
			# Stitching
			"stitch_done":    ts,
			"stitch_pending": max(ref_qty - ts, 0) if ref_qty > 0 else 0,
			"stitch_pct":     pct(ts, ref_qty),
			"stitch_avg_d":   round(ts / stitch_d["days"], 1) if ts > 0 else 0,
			# Checking
			"check_done":    tch,
			"check_pending": max(ref_qty - tch, 0) if ref_qty > 0 else 0,
			"check_pct":     pct(tch, ref_qty),
			"check_avg_d":   round(tch / check_d["days"], 1) if tch > 0 else 0,
			# Packing
			"pack_done":    tp,
			"pack_pending": max(ref_qty - tp, 0) if ref_qty > 0 else 0,
			"pack_pct":     pct(tp, ref_qty),
			"pack_avg_d":   round(tp / pack_d["days"], 1) if tp > 0 else 0,
		})

	return {"items": result}
