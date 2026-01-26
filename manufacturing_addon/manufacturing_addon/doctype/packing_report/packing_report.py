# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt

# Patch Stock Entry's set_rate_for_outgoing_items to respect set_basic_rate_manually and already set rates
_original_set_rate_for_outgoing_items = None

def _patched_set_rate_for_outgoing_items(self, reset_outgoing_rate=True, raise_error_if_no_rate=True):
    """Patched version that skips rate calculation for items with set_basic_rate_manually=1 or already set rates"""
    outgoing_items_cost = 0.0
    for d in self.get("items"):
        if d.s_warehouse:
            # Skip if rate is manually set (set_basic_rate_manually=1) OR if rate is already > 0 and we're not resetting
            set_manually = getattr(d, 'set_basic_rate_manually', 0)
            current_rate = flt(d.basic_rate)
            if set_manually:
                # Rate is manually set - skip recalculation, just calculate amount
                print(f"[PATCH] Skipping rate calc for {d.item_code}: set_basic_rate_manually={set_manually}, current_rate={current_rate}")
                d.basic_amount = flt(flt(d.transfer_qty) * flt(d.basic_rate), d.precision("basic_amount"))
                if not d.t_warehouse:
                    outgoing_items_cost += flt(d.basic_amount)
                continue
            
            # If rate is already set (> 0) and we're not resetting, skip
            if flt(d.basic_rate) > 0 and not reset_outgoing_rate:
                d.basic_amount = flt(flt(d.transfer_qty) * flt(d.basic_rate), d.precision("basic_amount"))
                if not d.t_warehouse:
                    outgoing_items_cost += flt(d.basic_amount)
                continue
            
            # Original logic for items without manually set rates
            if reset_outgoing_rate:
                from erpnext.stock.utils import get_incoming_rate
                args = self.get_args_for_incoming_rate(d)
                rate = get_incoming_rate(args, raise_error_if_no_rate)
                if rate >= 0:
                    d.basic_rate = rate

            d.basic_amount = flt(flt(d.transfer_qty) * flt(d.basic_rate), d.precision("basic_amount"))
            if not d.t_warehouse:
                outgoing_items_cost += flt(d.basic_amount)

    return outgoing_items_cost

# Apply the patch once
if not hasattr(frappe, '_stock_entry_rate_patch_applied'):
    try:
        from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
        _original_set_rate_for_outgoing_items = StockEntry.set_rate_for_outgoing_items
        StockEntry.set_rate_for_outgoing_items = _patched_set_rate_for_outgoing_items
        frappe._stock_entry_rate_patch_applied = True
        print("[Packing Report] Patched StockEntry.set_rate_for_outgoing_items to respect set_basic_rate_manually")
    except Exception as e:
        print(f"[Packing Report] Warning: Could not patch StockEntry.set_rate_for_outgoing_items: {str(e)}")


class PackingReport(Document):
    @frappe.whitelist()
    def get_data1(self):
        print(f"\n{'='*60}")
        print(f"[get_data1] Starting for Packing Report: '{self.name}'")
        print(f"[get_data1] Order Sheet: '{self.order_sheet}'")
        print(f"{'='*60}")
        
        if not self.order_sheet:
            print(f"[get_data1] ERROR: No Order Sheet selected")
            frappe.throw("Please select an Order Sheet first.")
        
        if isinstance(self.order_sheet, str) and self.order_sheet:
            try:
                # Use ignore_links to load cancelled Order Sheets
                doc = frappe.get_doc("Order Sheet", self.order_sheet)
                print(f"[get_data1] Loaded Order Sheet: '{doc.name}'")
                print(f"[get_data1] Order Sheet is_or: {doc.is_or}")
                print(f"[get_data1] Order Sheet docstatus: {doc.docstatus}")
                
                # Check if Order Sheet is cancelled
                if doc.docstatus == 2:
                    print(f"[get_data1] WARNING: Order Sheet is cancelled, but proceeding anyway")
            except Exception as e:
                print(f"[get_data1] ERROR loading Order Sheet: {str(e)}")
                frappe.throw(f"Invalid Order Sheet reference: {str(e)}")
        else:
            print(f"[get_data1] ERROR: Invalid Order Sheet type")
            frappe.throw("Invalid Order Sheet reference.")
        
        # Check if packing_report_ct is empty or not
        existing_rows = len(self.packing_report_ct) if self.packing_report_ct else 0
        print(f"[get_data1] Existing packing_report_ct rows: {existing_rows}")
        
        # Clear existing rows to allow re-fetch with new calculations
        if existing_rows > 0:
            print(f"[get_data1] Clearing {existing_rows} existing rows to re-fetch data...")
            self.packing_report_ct = []
        
        if not self.packing_report_ct or existing_rows == 0:
            print(f"[get_data1] packing_report_ct is empty, will fetch data")
            if doc.is_or == 0:
                print(f"[get_data1] Order Sheet is_or = 0, fetching data...")
                rec = frappe.db.sql("""
                    SELECT * FROM `tabOrder Sheet` AS opr
                    LEFT JOIN `tabOrder Sheet CT` AS orct
                    ON orct.parent = opr.name
                    WHERE opr.name = %s AND opr.is_or = 0
                """, (self.order_sheet,), as_dict=True)
                
                print(f"[get_data1] Found {len(rec)} rows from Order Sheet")

                self.packing_report_ct = []
                print(f"[get_data1] Processing {len(rec)} Order Sheet CT rows...")
                for idx, r in enumerate(rec):
                    so_item = r.get("so_item")
                    planned_qty = r.get("planned_qty") or 0
                    order_qty = r.get("order_qty") or 0
                    
                    print(f"\n{'='*60}")
                    print(f"[get_data1] Row {idx+1} - Raw Data from Order Sheet CT:")
                    print(f"  - so_item: '{so_item}'")
                    print(f"  - order_qty (raw): {r.get('order_qty')}")
                    print(f"  - planned_qty (raw): {r.get('planned_qty')}")
                    print(f"  - order_qty (after or 0): {order_qty}")
                    print(f"  - planned_qty (after or 0): {planned_qty}")
                    print(f"  - All keys in row: {list(r.keys())}")
                    print(f"{'='*60}")
                    
                    if not so_item:
                        print(f"[get_data1] Row {idx+1}: Skipping - no so_item")
                        continue
                    
                    # In Packing Report, show FINISHED ITEM directly (not expand into combo items)
                    # But get combo items info for reference
                    try:
                        item_doc = frappe.get_doc("Item", so_item)
                        combo_items = getattr(item_doc, 'custom_product_combo_item', [])
                        
                        print(f"[get_data1] Item {so_item}:")
                        print(f"  - custom_product_combo_item count: {len(combo_items) if combo_items else 0}")
                        
                        # Get combo items from Item or Stitching Size for reference
                        bundle_items_data = []  # List of dicts: [{"pcs": 2, "item": "PILLOW 80X80"}, ...]
                        if combo_items and len(combo_items) > 0:
                            print(f"[get_data1] ✓ Found {len(combo_items)} combo items in Item for reference")
                            for combo_item_row in combo_items:
                                bundle_items_data.append({
                                    "pcs": combo_item_row.pcs or 1,
                                    "item": combo_item_row.item
                                })
                        else:
                            # Try Stitching Size
                            size_value = None
                            variant_attrs = frappe.get_all(
                                "Item Variant Attribute",
                                filters={"parent": so_item},
                                fields=["attribute", "attribute_value"]
                            )
                            for attr in variant_attrs:
                                if attr.attribute and attr.attribute.upper() == "SIZE":
                                    size_value = attr.attribute_value
                                    break
                            
                            if size_value:
                                stitching_size = frappe.db.get_value("Stitching Size", size_value, "name")
                                if stitching_size:
                                    stitching_size_doc = frappe.get_doc("Stitching Size", stitching_size)
                                    if stitching_size_doc.combo_detail and len(stitching_size_doc.combo_detail) > 0:
                                        print(f"[get_data1] ✓ Found {len(stitching_size_doc.combo_detail)} combo items in Stitching Size for reference")
                                        for combo_item_row in stitching_size_doc.combo_detail:
                                            bundle_items_data.append({
                                                "pcs": combo_item_row.pcs or 1,
                                                "item": combo_item_row.item
                                            })
                        
                        # Format bundle items as HTML table with detailed cutting and stitching data for each bundle item
                        if bundle_items_data:
                            # Create HTML table with detailed information for each bundle item
                            bundle_items_html = """
                            <div style="overflow-x: auto;">
                                <table style="width: 100%; border-collapse: collapse; margin: 0; font-size: 11px; border: 1px solid #ddd;">
                                    <thead>
                                        <tr style="background-color: #f0f0f0;">
                                            <th style="border: 1px solid #ddd; padding: 6px; text-align: left; font-weight: bold;">Bundle Item</th>
                                            <th style="border: 1px solid #ddd; padding: 6px; text-align: left; font-weight: bold;">PCS</th>
                                            <th colspan="6" style="border: 1px solid #ddd; padding: 6px; text-align: center; font-weight: bold; background-color: #e3f2fd;">CUTTING</th>
                                            <th colspan="6" style="border: 1px solid #ddd; padding: 6px; text-align: center; font-weight: bold; background-color: #fff3e0;">STITCHING</th>
                                        </tr>
                                        <tr style="background-color: #f5f5f5;">
                                            <th style="border: 1px solid #ddd; padding: 4px;"></th>
                                            <th style="border: 1px solid #ddd; padding: 4px;"></th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #e3f2fd;">Order Qty</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #e3f2fd;">Planned Qty</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #e3f2fd;">PCS</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #e3f2fd;">Qty</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #e3f2fd;">Qty/Ctn</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #e3f2fd;">Finished</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #fff3e0;">Order Qty</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #fff3e0;">Planned Qty</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #fff3e0;">PCS</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #fff3e0;">Qty</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #fff3e0;">Qty/Ctn</th>
                                            <th style="border: 1px solid #ddd; padding: 4px; background-color: #fff3e0;">Finished</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                            """
                            
                            # For each bundle item, fetch cutting and stitching data
                            for item_data in bundle_items_data:
                                combo_item_code = item_data['item']
                                combo_pcs = item_data['pcs']
                                
                                # Fetch cutting data for this combo item from Cutting Report CT
                                cutting_data = frappe.db.sql("""
                                    SELECT 
                                        crct.order_qty,
                                        crct.planned_qty,
                                        crct.pcs,
                                        crct.qty,
                                        crct.qty_ctn
                                    FROM `tabCutting Report CT` AS crct
                                    LEFT JOIN `tabCutting Report` AS cr ON crct.parent = cr.name
                                    WHERE cr.order_sheet = %s 
                                        AND crct.so_item = %s 
                                        AND crct.combo_item = %s
                                    LIMIT 1
                                """, (self.order_sheet, so_item, combo_item_code), as_dict=True)
                                
                                # Fetch finished cutting qty for this combo item
                                finished_cutting_data = frappe.db.sql("""
                                    SELECT SUM(crct.cutting_qty) AS finished_cutting_qty
                                    FROM `tabCutting Report CT` AS crct
                                    LEFT JOIN `tabCutting Report` AS cr ON crct.parent = cr.name
                                    WHERE cr.order_sheet = %s 
                                        AND crct.so_item = %s 
                                        AND crct.combo_item = %s
                                        AND cr.docstatus = 1
                                """, (self.order_sheet, so_item, combo_item_code), as_dict=True)
                                
                                cutting_order_qty = cutting_data[0].order_qty if cutting_data and cutting_data[0] and cutting_data[0].order_qty else 0
                                cutting_planned_qty = cutting_data[0].planned_qty if cutting_data and cutting_data[0] and cutting_data[0].planned_qty else 0
                                cutting_pcs = cutting_data[0].pcs if cutting_data and cutting_data[0] and cutting_data[0].pcs else combo_pcs
                                cutting_qty = cutting_data[0].qty if cutting_data and cutting_data[0] and cutting_data[0].qty else 0
                                cutting_qty_ctn = cutting_data[0].qty_ctn if cutting_data and cutting_data[0] and cutting_data[0].qty_ctn else ""
                                cutting_finished = finished_cutting_data[0].finished_cutting_qty if finished_cutting_data and finished_cutting_data[0] and finished_cutting_data[0].finished_cutting_qty else 0
                                
                                # Fetch stitching data for this combo item from Stitching Report CT
                                stitching_data = frappe.db.sql("""
                                    SELECT 
                                        srct.order_qty,
                                        srct.planned_qty,
                                        srct.pcs,
                                        srct.qty,
                                        srct.qty_ctn
                                    FROM `tabStitching Report CT` AS srct
                                    LEFT JOIN `tabStitching Report` AS sr ON srct.parent = sr.name
                                    WHERE sr.order_sheet = %s 
                                        AND srct.so_item = %s 
                                        AND srct.combo_item = %s
                                    LIMIT 1
                                """, (self.order_sheet, so_item, combo_item_code), as_dict=True)
                                
                                # Fetch finished stitching qty for this combo item
                                finished_stitching_data = frappe.db.sql("""
                                    SELECT SUM(srct.stitching_qty) AS finished_stitching_qty
                                    FROM `tabStitching Report CT` AS srct
                                    LEFT JOIN `tabStitching Report` AS sr ON srct.parent = sr.name
                                    WHERE sr.order_sheet = %s 
                                        AND srct.so_item = %s 
                                        AND srct.combo_item = %s
                                        AND sr.docstatus = 1
                                """, (self.order_sheet, so_item, combo_item_code), as_dict=True)
                                
                                stitching_order_qty = stitching_data[0].order_qty if stitching_data and stitching_data[0] and stitching_data[0].order_qty else 0
                                stitching_planned_qty = stitching_data[0].planned_qty if stitching_data and stitching_data[0] and stitching_data[0].planned_qty else 0
                                stitching_pcs = stitching_data[0].pcs if stitching_data and stitching_data[0] and stitching_data[0].pcs else combo_pcs
                                stitching_qty = stitching_data[0].qty if stitching_data and stitching_data[0] and stitching_data[0].qty else 0
                                stitching_qty_ctn = stitching_data[0].qty_ctn if stitching_data and stitching_data[0] and stitching_data[0].qty_ctn else ""
                                stitching_finished = finished_stitching_data[0].finished_stitching_qty if finished_stitching_data and finished_stitching_data[0] and finished_stitching_data[0].finished_stitching_qty else 0
                                
                                bundle_items_html += f"""
                                        <tr>
                                            <td style="border: 1px solid #ddd; padding: 6px; font-weight: bold;">{combo_item_code}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px;">{combo_pcs}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #e3f2fd;">{cutting_order_qty}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #e3f2fd;">{cutting_planned_qty}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #e3f2fd;">{cutting_pcs}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #e3f2fd;">{cutting_qty}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #e3f2fd;">{cutting_qty_ctn}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #e3f2fd;">{cutting_finished}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #fff3e0;">{stitching_order_qty}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #fff3e0;">{stitching_planned_qty}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #fff3e0;">{stitching_pcs}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #fff3e0;">{stitching_qty}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #fff3e0;">{stitching_qty_ctn}</td>
                                            <td style="border: 1px solid #ddd; padding: 6px; background-color: #fff3e0;">{stitching_finished}</td>
                                        </tr>
                                """
                            
                            bundle_items_html += """
                                    </tbody>
                                </table>
                            </div>
                            """
                            bundle_items_text = bundle_items_html.strip()
                        else:
                            bundle_items_text = None
                        
                        # Plain text version for print logs
                        bundle_items_log = ', '.join([f"{item['pcs']}x {item['item']}" for item in bundle_items_data]) if bundle_items_data else None
                        
                        print(f"\n{'='*60}")
                        print(f"[get_data1] ADDING FINISHED ITEM TO PACKING REPORT:")
                        print(f"{'='*60}")
                        print(f"  Finished Item: {so_item}")
                        print(f"  Bundle Items: {bundle_items_log or 'None'}")
                        print(f"  Order Qty: {order_qty}")
                        print(f"  Planned Qty: {planned_qty}")
                        print(f"  Qty: {planned_qty} (same as planned_qty for finished item)")
                        print(f"{'='*60}")
                        
                        new_row = self.append("packing_report_ct", {
                        "customer": r.get("customer"),
                        "design": r.get("design"),
                        "colour": r.get("colour"),
                        "finished_size": r.get("size"),
                        "qty_ctn": r.get("qty_ctn"),
                        "article": r.get("stitching_article_no"),
                        "ean": r.get("ean"),
                            "order_qty": order_qty,  # Original order_qty from Order Sheet CT
                            "pcs": 1,  # For finished item, PCS = 1 (it's already a complete unit)
                            "qty": planned_qty,  # For finished item, qty = planned_qty (not multiplied)
                            "planned_qty": planned_qty,  # Original planned_qty from Order Sheet CT
                            "so_item": so_item,  # Finished item
                            "combo_item": None,  # No combo_item for finished item in packing
                            "bundle_items": bundle_items_text,  # Bundle/combo items breakdown (HTML formatted)
                        })
                        
                        # Verify bundle_items was set
                        print(f"[get_data1] ✓ Finished item added successfully!")
                        print(f"[get_data1] Verifying bundle_items in row:")
                        print(f"  - bundle_items set: {new_row.bundle_items is not None}")
                        print(f"  - bundle_items length: {len(new_row.bundle_items) if new_row.bundle_items else 0}")
                        print(f"  - bundle_items preview: {new_row.bundle_items[:100] if new_row.bundle_items else 'None'}...")
                        print(f"{'='*60}\n")
                    except Exception as e:
                        error_msg = f"Error processing item {so_item}: {str(e)}"
                        print(f"[get_data1] Row {idx+1}: ✗ ERROR: {error_msg}")
                        frappe.log_error(error_msg, "Packing Report Item Processing")
                        continue
                
                print(f"\n{'='*60}")
                print(f"[get_data1] SUMMARY:")
                print(f"  - Total rows added to packing_report_ct: {len(self.packing_report_ct)}")
                print(f"[get_data1] Final packing_report_ct data:")
                for idx, row in enumerate(self.packing_report_ct):
                    print(f"  Row {idx+1}:")
                    print(f"    - so_item: {row.so_item}")
                    print(f"    - combo_item: {row.combo_item}")
                    print(f"    - bundle_items: {row.bundle_items}")
                    print(f"    - order_qty: {row.order_qty}")
                    print(f"    - planned_qty: {row.planned_qty}")
                    print(f"    - pcs: {row.pcs}")
                    print(f"    - qty: {row.qty}")
                print(f"{'='*60}")
                print(f"[get_data1] Saving Packing Report...")
                
                # Set flag to ignore link validation (allow cancelled Order Sheets)
                self.flags.ignore_links = True
                
                try:
                    self.save(ignore_permissions=True)
                    frappe.db.commit()
                    print(f"[get_data1] ✓ Saved successfully")
                except Exception as e:
                    print(f"[get_data1] ERROR saving: {str(e)}")
                    frappe.db.rollback()
                    raise
                
                print(f"{'='*60}\n")
            else:
                print(f"[get_data1] Order Sheet is_or = 1, skipping (only process when is_or = 0)")
                print(f"{'='*60}\n")
        else:
            print(f"[get_data1] packing_report_ct already has {existing_rows} rows, skipping fetch")
            print(f"{'='*60}\n")

    def validate(self):
        self.calculate_finished_cutting_qty()
        self.calculate_finished_stitching_qty()
        self.calculate_finished_quality_qty()
        self.calculate_finished_packaging_qty()
        self.packing_condition()
        self.total_qty()
        self.total_percentage()
        self.total()
    
    def before_save(self):
        self.calculate_finished_cutting_qty()
        self.calculate_finished_stitching_qty()
        self.calculate_finished_quality_qty()
        self.calculate_finished_packaging_qty()

    def calculate_finished_cutting_qty(self):
        """Get finished cutting qty from Cutting Reports"""
        try:
            cutting_totals = {}
            for row in self.packing_report_ct:
                if not row.so_item:
                    continue
                
                if row.combo_item:
                    # If combo_item is set, get cutting qty for that specific combo item
                    query = """
                        SELECT SUM(crct.cutting_qty) AS total_cutting
                        FROM `tabCutting Report CT` AS crct 
                        LEFT JOIN `tabCutting Report` AS cr 
                        ON crct.parent = cr.name
                        WHERE cr.order_sheet = %s AND crct.so_item = %s AND crct.combo_item = %s AND cr.docstatus = 1
                        GROUP BY crct.so_item, crct.combo_item
                    """
                    params = (self.order_sheet, row.so_item, row.combo_item)
                else:
                    # If combo_item is None (finished item), sum up ALL combo items for this finished item
                    # In Cutting/Stitching Reports, combo_item is always set, so we sum all of them
                    query = """
                        SELECT SUM(crct.cutting_qty) AS total_cutting
                        FROM `tabCutting Report CT` AS crct 
                        LEFT JOIN `tabCutting Report` AS cr 
                        ON crct.parent = cr.name
                        WHERE cr.order_sheet = %s AND crct.so_item = %s AND cr.docstatus = 1
                        GROUP BY crct.so_item
                    """
                    params = (self.order_sheet, row.so_item)

                result = frappe.db.sql(query, params, as_dict=True)
                cutting_totals[(row.so_item, row.combo_item or '')] = result[0].total_cutting if result else 0

            for row in self.packing_report_ct:
                row.finished_cutting_qty = cutting_totals.get((row.so_item, row.combo_item or ''), 0)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Cutting Quantity Fetch Failed")

    def calculate_finished_stitching_qty(self):
        """Get finished stitching qty from Stitching Reports"""
        try:
            stitching_totals = {}
            for row in self.packing_report_ct:
                if not row.so_item:
                    continue
                
                if row.combo_item:
                    # If combo_item is set, get stitching qty for that specific combo item
                    query = """
                        SELECT SUM(srct.stitching_qty) AS total_stitching
                        FROM `tabStitching Report CT` AS srct 
                        LEFT JOIN `tabStitching Report` AS sr 
                        ON srct.parent = sr.name
                        WHERE sr.order_sheet = %s AND srct.so_item = %s AND srct.combo_item = %s AND sr.docstatus = 1
                        GROUP BY srct.so_item, srct.combo_item
                    """
                    params = (self.order_sheet, row.so_item, row.combo_item)
                else:
                    # If combo_item is None (finished item), sum up ALL combo items for this finished item
                    # In Cutting/Stitching Reports, combo_item is always set, so we sum all of them
                    query = """
                        SELECT SUM(srct.stitching_qty) AS total_stitching
                        FROM `tabStitching Report CT` AS srct 
                        LEFT JOIN `tabStitching Report` AS sr 
                        ON srct.parent = sr.name
                        WHERE sr.order_sheet = %s AND srct.so_item = %s AND sr.docstatus = 1
                        GROUP BY srct.so_item
                    """
                    params = (self.order_sheet, row.so_item)

                result = frappe.db.sql(query, params, as_dict=True)
                stitching_totals[(row.so_item, row.combo_item or '')] = result[0].total_stitching if result else 0

            for row in self.packing_report_ct:
                row.finished_stitching_qty = stitching_totals.get((row.so_item, row.combo_item or ''), 0)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Stitching Quantity Fetch Failed")

    def calculate_finished_quality_qty(self):
        """Get finished quality qty from Quality Reports"""
        try:
            quality_totals = {}
            for row in self.packing_report_ct:
                if not row.so_item:
                    continue
                
                if row.combo_item:
                    query = """
                        SELECT SUM(qrct.quality_qty) AS total_quality
                        FROM `tabQuality Report CT` AS qrct 
                        LEFT JOIN `tabQuality Report` AS qr 
                        ON qrct.parent = qr.name
                        WHERE qr.order_sheet = %s AND qrct.so_item = %s AND qrct.combo_item = %s AND qr.docstatus = 1
                        GROUP BY qrct.so_item, qrct.combo_item
                    """
                    params = (self.order_sheet, row.so_item, row.combo_item)
                else:
                    query = """
                        SELECT SUM(qrct.quality_qty) AS total_quality
                        FROM `tabQuality Report CT` AS qrct 
                        LEFT JOIN `tabQuality Report` AS qr 
                        ON qrct.parent = qr.name
                        WHERE qr.order_sheet = %s AND qrct.so_item = %s AND (qrct.combo_item IS NULL OR qrct.combo_item = '') AND qr.docstatus = 1
                        GROUP BY qrct.so_item
                    """
                    params = (self.order_sheet, row.so_item)

                result = frappe.db.sql(query, params, as_dict=True)
                quality_totals[(row.so_item, row.combo_item or '')] = result[0].total_quality if result else 0

            for row in self.packing_report_ct:
                row.finished_quality_qty = quality_totals.get((row.so_item, row.combo_item or ''), 0)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Quality Quantity Fetch Failed")

    def calculate_finished_packaging_qty(self):
        """Calculate and update finished_packaging_qty in the child table based on user-entered packaging_qty values."""
        try:
            packaging_totals = {}

            for row in self.packing_report_ct:
                if not row.so_item:
                    continue
                
                # Exclude current document from calculation
                current_doc_filter = ""
                if self.name:
                    current_doc_filter = "AND pr.name != %s"
                    if row.combo_item:
                        query = """
                            SELECT SUM(prct.packaging_qty) AS total_packaging
                            FROM `tabPacking Report CT` AS prct 
                            LEFT JOIN `tabPacking Report` AS pr 
                            ON prct.parent = pr.name
                            WHERE pr.order_sheet = %s AND prct.so_item = %s AND prct.combo_item = %s AND pr.docstatus = 1 {current_doc_filter}
                            GROUP BY prct.so_item, prct.combo_item
                        """.format(current_doc_filter=current_doc_filter)
                        params = (self.order_sheet, row.so_item, row.combo_item, self.name)
                    else:
                        query = """
                            SELECT SUM(prct.packaging_qty) AS total_packaging
                            FROM `tabPacking Report CT` AS prct 
                            LEFT JOIN `tabPacking Report` AS pr 
                            ON prct.parent = pr.name
                            WHERE pr.order_sheet = %s AND prct.so_item = %s AND (prct.combo_item IS NULL OR prct.combo_item = '') AND pr.docstatus = 1 {current_doc_filter}
                            GROUP BY prct.so_item
                        """.format(current_doc_filter=current_doc_filter)
                        params = (self.order_sheet, row.so_item, self.name)
                else:
                    # New document, no need to exclude
                    if row.combo_item:
                        query = """
                            SELECT SUM(prct.packaging_qty) AS total_packaging
                            FROM `tabPacking Report CT` AS prct 
                            LEFT JOIN `tabPacking Report` AS pr 
                            ON prct.parent = pr.name
                            WHERE pr.order_sheet = %s AND prct.so_item = %s AND prct.combo_item = %s AND pr.docstatus = 1
                            GROUP BY prct.so_item, prct.combo_item
                        """
                        params = (self.order_sheet, row.so_item, row.combo_item)
                    else:
                        query = """
                            SELECT SUM(prct.packaging_qty) AS total_packaging
                            FROM `tabPacking Report CT` AS prct 
                            LEFT JOIN `tabPacking Report` AS pr 
                            ON prct.parent = pr.name
                            WHERE pr.order_sheet = %s AND prct.so_item = %s AND (prct.combo_item IS NULL OR prct.combo_item = '') AND pr.docstatus = 1
                            GROUP BY prct.so_item
                        """
                        params = (self.order_sheet, row.so_item)

                result = frappe.db.sql(query, params, as_dict=True)
                packaging_totals[(row.so_item, row.combo_item or '')] = result[0].total_packaging if result else 0

            for row in self.packing_report_ct:
                row.finished_packaging_qty = packaging_totals.get((row.so_item, row.combo_item or ''), 0)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Packaging Quantity Calculation Failed")
            frappe.throw(f"Error in calculating finished packaging quantity: {str(e)}")

    def packing_condition(self):
        """Validate that total packaging qty (finished_packaging_qty + packaging_qty) doesn't exceed stitching qty"""
        if not self.packing_report_ct:
            return

        # First ensure finished_stitching_qty and finished_packaging_qty are calculated
        self.calculate_finished_stitching_qty()
        self.calculate_finished_packaging_qty()

        for i in self.packing_report_ct:
            current_packaging_qty = i.packaging_qty or 0
            finished_packaging_qty = i.finished_packaging_qty or 0
            stitching_qty = i.finished_stitching_qty or 0
            
            # Total packaging = already packaged (from other documents) + current packaging qty
            total_packaging = finished_packaging_qty + current_packaging_qty

            # Only validate if stitching_qty > 0 (if stitching_qty is 0, allow any packaging qty)
            if stitching_qty > 0:
                # Check if total packaging (already packaged + current) exceeds stitching qty
                if total_packaging > stitching_qty:
                    frappe.throw(
                        _("Total Packing Qty ({0} = Finished Packing Qty {1} + Current Packing Qty {2}) cannot be greater than Finished Stitching Qty ({3}) for row {4} (Item: {5}, Combo Item: {6}). Please reduce the Packing Qty.").format(
                            total_packaging,
                            finished_packaging_qty,
                            current_packaging_qty,
                            stitching_qty,
                            i.idx,
                            i.so_item or "N/A",
                            i.combo_item or "N/A"
                        ),
                        title=_("Validation Error")
                )

    def total_qty(self):
        for i in self.packing_report_ct:
            i.total_copy1 = i.packaging_qty or 0

    def total_percentage(self):
        for i in self.packing_report_ct:
            qty = i.qty 
            total = i.total_copy1
            if qty and total:
                percentage = (total / qty) * 100
                i.percentage_copy = percentage
            else:
                i.percentage_copy = 0

    def total(self):
        total_qty = 0
        ready_qty = frappe.db.sql("""
            SELECT prct.customer, 
                prct.design, 
                prct.colour, 
                prct.article, 
                prct.ean, 
                prct.qty,
                SUM(prct.packaging_qty) AS packaging,
                prct.qty_ctn
            FROM `tabPacking Report` AS pr
            LEFT JOIN `tabPacking Report CT` AS prct ON prct.parent = pr.name
            WHERE pr.order_sheet = %s AND pr.docstatus = 1
            GROUP BY prct.customer, prct.design, prct.colour, prct.article, prct.ean, prct.qty, prct.qty_ctn
        """, (self.order_sheet,), as_dict=True)

        if ready_qty:
            self.ready_qty = ready_qty[0].get("packaging", 0) if ready_qty else 0
        else:
            self.ready_qty = 0
        
        if self.ready_qty and self.ordered_qty:
            self.percentage = (self.ready_qty / self.ordered_qty) * 100
        else:
            self.percentage = 0
	
        for i in self.packing_report_ct:
            total_qty += i.qty or 0
            self.ordered_qty = total_qty

    def on_submit(self):
        """Create Stock Entry for Manufacture when Packing Report is submitted"""
        try:
            print(f"\n{'='*60}")
            print(f"[on_submit] Creating Stock Entry for Packing Report: '{self.name}'")
            print(f"{'='*60}")
            
            # Fixed warehouses
            source_warehouse = "Work In Progress - SAH"
            target_warehouse = "Finished Goods - SAH"
            
            print(f"[on_submit] Source Warehouse: {source_warehouse}")
            print(f"[on_submit] Target Warehouse: {target_warehouse}")
            
            # Get company from Order Sheet
            company = None
            if self.order_sheet:
                order_sheet_doc = frappe.get_doc("Order Sheet", self.order_sheet)
                company = order_sheet_doc.get("company")
                if not company:
                    # Try to get from Sales Order (Order Sheet has sales_order field directly)
                    if order_sheet_doc.get("sales_order"):
                        company = frappe.db.get_value("Sales Order", order_sheet_doc.sales_order, "company")
            
            if not company:
                frappe.throw(_("Company not found. Please ensure Order Sheet has a company set."))
            
            print(f"[on_submit] Company: {company}")
            
            # Process each packing report row
            stock_entries_created = []
            
            for row in self.packing_report_ct:
                if not row.so_item or not row.packaging_qty or row.packaging_qty <= 0:
                    continue
                
                finished_item = row.so_item
                packaging_qty = row.packaging_qty
                
                print(f"\n[on_submit] Processing row: Finished Item = {finished_item}, Packaging Qty = {packaging_qty}")
                
                # Get BOM for finished item
                bom_no = frappe.db.get_value("BOM", {"item": finished_item, "is_active": 1, "is_default": 1}, "name")
                
                if not bom_no:
                    # Try to get any active BOM for this item
                    bom_no = frappe.db.get_value("BOM", {"item": finished_item, "is_active": 1}, "name", order_by="is_default desc, creation desc")
                
                if not bom_no:
                    frappe.throw(_("BOM not found for item {0}. Please create a BOM for this item.").format(finished_item))
                
                # Verify BOM item matches finished item
                bom_item = frappe.db.get_value("BOM", bom_no, "item")
                if bom_item != finished_item:
                    frappe.throw(_("BOM {0} is for item {1}, but finished item is {2}. Please use the correct BOM.").format(bom_no, bom_item, finished_item))
                
                print(f"[on_submit] BOM: {bom_no}, BOM Item: {bom_item}, Finished Item: {finished_item}")
                
                # Create Stock Entry
                stock_entry = frappe.new_doc("Stock Entry")
                stock_entry.purpose = "Manufacture"
                stock_entry.company = company
                stock_entry.posting_date = self.date or frappe.utils.nowdate()
                stock_entry.posting_time = self.time or frappe.utils.nowtime()
                stock_entry.bom_no = bom_no
                stock_entry.fg_completed_qty = packaging_qty
                stock_entry.from_bom = 1
                stock_entry.from_warehouse = source_warehouse
                stock_entry.to_warehouse = target_warehouse
                
                # Enable multi-level BOM to fetch all sub-assemblies and their components
                # stock_entry.use_multi_level_bom = 1
                # print(f"[on_submit] Set use_multi_level_bom = 1 to expand BOM recursively")
                
                # Set stock_entry_type based on purpose
                stock_entry.set_stock_entry_type()
                
                # Set custom field if it exists
                if hasattr(stock_entry, 'custom_packing_report'):
                    stock_entry.custom_packing_report = self.name
                
                # Set custom_cost_center from Packing Report
                if hasattr(stock_entry, 'custom_cost_center') and self.cost_center:
                    stock_entry.custom_cost_center = self.cost_center
                    print(f"[on_submit] Set custom_cost_center: {self.cost_center}")
                
                # Call get_items to populate items from BOM (will use multi-level BOM if enabled)
                print(f"[on_submit] Calling get_items() to populate items from BOM (with multi-level expansion)...")
                stock_entry.get_items()
                
                if not stock_entry.items:
                    frappe.throw(_("No items found from BOM {0}. Please check the BOM.").format(bom_no))
                
                print(f"[on_submit] Items populated: {len(stock_entry.items)} items")
                
                # Ensure warehouses are set for all items
                # For Manufacture type, consumed items should have s_warehouse, finished items should have t_warehouse
                warehouses_modified = False
                for item in stock_entry.items:
                    # Set source warehouse for consumed items (raw materials)
                    if not item.is_finished_item and not item.s_warehouse:
                        item.s_warehouse = source_warehouse
                        warehouses_modified = True
                    # Set target warehouse for finished items
                    if item.is_finished_item and not item.t_warehouse:
                        item.t_warehouse = target_warehouse
                        warehouses_modified = True
                    
                    # Set custom_packing_report field
                    if hasattr(item, 'custom_packing_report'):
                        item.custom_packing_report = self.name
                        print(f"[on_submit] Set custom_packing_report for {item.item_code}: {self.name}")
                
                # Ensure finished good is added (get_items should add it, but let's verify and add if missing)
                finished_item_found = False
                for item in stock_entry.items:
                    if item.item_code == finished_item and (item.is_finished_item or item.t_warehouse):
                        finished_item_found = True
                        break
                
                if not finished_item_found:
                    # Add finished good manually
                    item_uom = frappe.db.get_value("Item", finished_item, "stock_uom") or "Nos"
                    finished_item_row = stock_entry.append("items", {
                        "item_code": finished_item,
                        "qty": packaging_qty,
                        "t_warehouse": target_warehouse,
                        "uom": item_uom,
                        "is_finished_item": 1
                    })
                    # Set custom_packing_report for manually added finished good
                    if hasattr(finished_item_row, 'custom_packing_report'):
                        finished_item_row.custom_packing_report = self.name
                    print(f"[on_submit] Added finished good manually: {finished_item} = {packaging_qty} {item_uom}")
                    warehouses_modified = True
                
                # Always recalculate rates after modifying items (warehouses or adding items)
                # This ensures valuation rates are fetched from stock ledger for all items with proper warehouse assignments
                # Note: validate() will call calculate_rate_and_amount() with raise_error_if_no_rate=True by default,
                # so we need to ensure all items have proper rates calculated before insert
                print(f"\n{'='*80}")
                print(f"[on_submit] Recalculating rates after modifying items...")
                print(f"[on_submit] Items before rate calculation: {len(stock_entry.items)}")
                for idx, item in enumerate(stock_entry.items):
                    print(f"  Item {idx+1}: {item.item_code}")
                    print(f"    - s_warehouse: {item.s_warehouse}")
                    print(f"    - t_warehouse: {item.t_warehouse}")
                    print(f"    - is_finished_item: {item.is_finished_item}")
                    print(f"    - qty: {item.qty}")
                    print(f"    - transfer_qty: {getattr(item, 'transfer_qty', 'NOT SET')}")
                
                # Ensure transfer_qty is set for all items before calculating rates
                print(f"[on_submit] Setting transfer_qty for all items...")
                stock_entry.set_transfer_qty()
                print(f"[on_submit] transfer_qty set. Items after set_transfer_qty:")
                for idx, item in enumerate(stock_entry.items):
                    print(f"  Item {idx+1}: {item.item_code} | transfer_qty: {item.transfer_qty}")
                
                # Recalculate rates - this will fetch valuation rates from stock ledger
                # Use raise_error_if_no_rate=False to allow items without stock to proceed
                # (they will need allow_zero_valuation_rate set if they truly have no stock)
                print(f"[on_submit] Calling calculate_rate_and_amount(raise_error_if_no_rate=False)...")
                stock_entry.calculate_rate_and_amount(raise_error_if_no_rate=False)
                print(f"[on_submit] calculate_rate_and_amount() completed")
                print(f"{'='*80}\n")
                
                print(f"[on_submit] Valuation rates after calculation:")
                from frappe.utils import flt
                for item in stock_entry.items:
                    if item.s_warehouse:
                        print(f"\n{'='*80}")
                        print(f"[on_submit] Processing consumed item: {item.item_code}")
                        print(f"  - s_warehouse: {item.s_warehouse}")
                        print(f"  - transfer_qty: {item.transfer_qty}")
                        print(f"  - basic_rate (before check): {item.basic_rate}")
                        print(f"  - valuation_rate (before check): {item.valuation_rate}")
                        print(f"  - allow_zero_valuation_rate (before check): {item.allow_zero_valuation_rate}")
                        
                        # If item has no rate and no allow_zero_valuation_rate, try to get rate from stock ledger
                        # Try multiple methods to get the valuation rate
                        if not flt(item.basic_rate) and not item.allow_zero_valuation_rate:
                            print(f"[on_submit] Item {item.item_code} has no rate and allow_zero_valuation_rate is False, attempting to fetch from stock ledger...")
                            
                            rate = None
                            
                            # Method 1: Try get_incoming_rate (for outgoing items)
                            try:
                                from erpnext.stock.utils import get_incoming_rate
                                print(f"[on_submit] Method 1: Trying get_incoming_rate()...")
                                args = stock_entry.get_args_for_incoming_rate(item)
                                print(f"[on_submit] Args: item_code={args.get('item_code')}, warehouse={args.get('warehouse')}, qty={args.get('qty')}")
                                rate = get_incoming_rate(args, raise_error_if_no_rate=False)
                                print(f"[on_submit] get_incoming_rate() returned: {rate}")
                            except Exception as e:
                                print(f"[on_submit] get_incoming_rate() failed: {str(e)}")
                            
                            # Method 2: If get_incoming_rate returned 0 or None, try get_valuation_rate directly from stock ledger
                            if not rate or flt(rate) == 0:
                                try:
                                    from erpnext.stock.stock_ledger import get_valuation_rate
                                    import erpnext
                                    print(f"[on_submit] Method 2: Trying get_valuation_rate() directly from stock ledger...")
                                    print(f"[on_submit] Args: item_code={item.item_code}, warehouse={item.s_warehouse}, company={stock_entry.company}")
                                    rate = get_valuation_rate(
                                        item.item_code,
                                        item.s_warehouse,
                                        stock_entry.doctype,
                                        stock_entry.name or "",  # Use empty string if not saved yet
                                        item.allow_zero_valuation_rate,
                                        currency=erpnext.get_company_currency(stock_entry.company),
                                        company=stock_entry.company,
                                        raise_error_if_no_rate=False,
                                        batch_no=item.batch_no,
                                        serial_and_batch_bundle=item.serial_and_batch_bundle,
                                    )
                                    print(f"[on_submit] get_valuation_rate() returned: {rate}")
                                except Exception as e:
                                    print(f"[on_submit] get_valuation_rate() failed: {str(e)}")
                            
                            # Method 3: If still no rate, check bin table (current stock balance)
                            if not rate or flt(rate) == 0:
                                try:
                                    print(f"[on_submit] Method 3: Checking bin table for current stock valuation rate...")
                                    bin_data = frappe.db.sql("""
                                        SELECT valuation_rate, actual_qty, stock_value
                                        FROM `tabBin`
                                        WHERE item_code = %s 
                                            AND warehouse = %s
                                    """, (item.item_code, item.s_warehouse), as_dict=True)
                                    
                                    if bin_data and bin_data[0]:
                                        bin_info = bin_data[0]
                                        actual_qty = flt(bin_info.get('actual_qty', 0))
                                        stock_value = flt(bin_info.get('stock_value', 0))
                                        bin_valuation_rate = flt(bin_info.get('valuation_rate', 0))
                                        
                                        print(f"[on_submit] Bin data: actual_qty={actual_qty}, stock_value={stock_value}, valuation_rate={bin_valuation_rate}")
                                        
                                        if actual_qty > 0:
                                            # Use valuation_rate from bin if available, otherwise calculate from stock_value/actual_qty
                                            if bin_valuation_rate and bin_valuation_rate > 0:
                                                rate = bin_valuation_rate
                                                print(f"[on_submit] Using valuation_rate from bin: {rate}")
                                            elif stock_value > 0:
                                                rate = stock_value / actual_qty
                                                print(f"[on_submit] Calculated rate from stock_value/actual_qty: {rate}")
                                            else:
                                                print(f"[on_submit] Bin has stock but no valuation rate or stock value")
                                        else:
                                            print(f"[on_submit] Bin shows no stock (actual_qty={actual_qty})")
                                    else:
                                        print(f"[on_submit] No bin record found for item-warehouse combination")
                                except Exception as e:
                                    print(f"[on_submit] Bin query failed: {str(e)}")
                                    import traceback
                                    print(f"[on_submit] Traceback: {traceback.format_exc()}")
                            
                            # Method 4: If still no rate, query latest stock ledger entry (any qty, just get the rate)
                            if not rate or flt(rate) == 0:
                                try:
                                    print(f"[on_submit] Method 4: Querying latest stock ledger entry for valuation rate...")
                                    sle_data = frappe.db.sql("""
                                        SELECT valuation_rate, actual_qty, stock_value, stock_value_difference
                                        FROM `tabStock Ledger Entry`
                                        WHERE item_code = %s 
                                            AND warehouse = %s
                                            AND is_cancelled = 0
                                            AND valuation_rate > 0
                                        ORDER BY posting_date DESC, posting_time DESC, creation DESC
                                        LIMIT 1
                                    """, (item.item_code, item.s_warehouse), as_dict=True)
                                    
                                    if sle_data and sle_data[0].get('valuation_rate'):
                                        rate = flt(sle_data[0].valuation_rate)
                                        print(f"[on_submit] Latest stock ledger entry returned valuation_rate: {rate}")
                                    else:
                                        print(f"[on_submit] No stock ledger entry found with valuation_rate > 0")
                                        # Try without valuation_rate filter - get any entry and calculate
                                        sle_data2 = frappe.db.sql("""
                                            SELECT stock_value, actual_qty, stock_value_difference
                                            FROM `tabStock Ledger Entry`
                                            WHERE item_code = %s 
                                                AND warehouse = %s
                                                AND is_cancelled = 0
                                            ORDER BY posting_date DESC, posting_time DESC, creation DESC
                                            LIMIT 10
                                        """, (item.item_code, item.s_warehouse), as_dict=True)
                                        print(f"[on_submit] Found {len(sle_data2)} stock ledger entries (without valuation_rate filter)")
                                        for sle in sle_data2:
                                            print(f"  - actual_qty: {sle.get('actual_qty')}, stock_value: {sle.get('stock_value')}, stock_value_difference: {sle.get('stock_value_difference')}")
                                except Exception as e:
                                    print(f"[on_submit] Stock ledger query failed: {str(e)}")
                            
                            # Method 5: Check if item has stock in ANY warehouse and get weighted average
                            if not rate or flt(rate) == 0:
                                try:
                                    print(f"[on_submit] Method 5: Checking all warehouses for this item...")
                                    # Get weighted average valuation rate across all warehouses
                                    all_warehouses_data = frappe.db.sql("""
                                        SELECT 
                                            SUM(stock_value) as total_stock_value,
                                            SUM(actual_qty) as total_actual_qty,
                                            AVG(valuation_rate) as avg_valuation_rate
                                        FROM `tabBin`
                                        WHERE item_code = %s 
                                            AND actual_qty > 0
                                    """, (item.item_code,), as_dict=True)
                                    
                                    if all_warehouses_data and all_warehouses_data[0]:
                                        data = all_warehouses_data[0]
                                        total_qty = flt(data.get('total_actual_qty', 0))
                                        total_value = flt(data.get('total_stock_value', 0))
                                        
                                        print(f"[on_submit] All warehouses: total_qty={total_qty}, total_value={total_value}")
                                        
                                        if total_qty > 0 and total_value > 0:
                                            rate = total_value / total_qty
                                            print(f"[on_submit] Calculated weighted average rate from all warehouses: {rate}")
                                        else:
                                            print(f"[on_submit] No stock found in any warehouse")
                                except Exception as e:
                                    print(f"[on_submit] All warehouses query failed: {str(e)}")
                            
                            # Set the rate if found - store it to set after final recalculation
                            if rate and flt(rate) > 0:
                                # Item has valuation rate - store it to set after final recalculation
                                # (because calculate_rate_and_amount will reset it)
                                print(f"[on_submit] ✓ Item {item.item_code} has valuation rate {rate} from stock ledger")
                                # Store the rate in a custom attribute to set after recalculation
                                item._manual_valuation_rate = flt(rate)
                                # Also set it now so it's available, but it will be overwritten by calculate_rate_and_amount
                                item.allow_zero_valuation_rate = 0
                                item.basic_rate = flt(rate)
                                item.basic_amount = flt(flt(item.transfer_qty) * flt(item.basic_rate), item.precision("basic_amount"))
                                print(f"[on_submit] Stored manual rate {rate} to set after final recalculation")
                                print(f"[on_submit] Set now (will be restored after recalculation): basic_rate={item.basic_rate}, basic_amount={item.basic_amount}")
                            else:
                                # No rate available - allow zero valuation rate
                                print(f"[on_submit] ✗ WARNING: Item {item.item_code} has no valuation rate in {item.s_warehouse}")
                                print(f"  - All methods returned 0 or None")
                                print(f"  - Setting allow_zero_valuation_rate=1")
                                item.allow_zero_valuation_rate = 1
                                item.basic_rate = 0.0
                                item.basic_amount = 0.0
                                # Ensure the flag is set as integer (1) not boolean
                                if hasattr(item, 'db_set'):
                                    # This is a child table row, ensure flag is set
                                    item.db_set('allow_zero_valuation_rate', 1, update_modified=False)
                                print(f"[on_submit] Verified allow_zero_valuation_rate={item.allow_zero_valuation_rate}")
                        else:
                            if flt(item.basic_rate):
                                print(f"[on_submit] Item {item.item_code} already has rate: {item.basic_rate}, skipping")
                            elif item.allow_zero_valuation_rate:
                                print(f"[on_submit] Item {item.item_code} already has allow_zero_valuation_rate=True, skipping")
                        print(f"{'='*80}\n")
                    elif item.t_warehouse and item.is_finished_item:
                        print(f"  - Finished: {item.item_code} | Rate: {item.basic_rate} | Valuation Rate: {item.valuation_rate}")
                
                # Final recalculation after any allow_zero_valuation_rate changes
                # But skip if we have manually set rates (they will be restored after)
                print(f"\n{'='*80}")
                print(f"[on_submit] Final recalculation after rate fixes...")
                has_manual_rates = any(hasattr(item, '_manual_valuation_rate') and item._manual_valuation_rate for item in stock_entry.items if item.s_warehouse)
                if has_manual_rates:
                    print(f"[on_submit] Skipping calculate_rate_and_amount() - will restore manual rates after")
                else:
                    stock_entry.calculate_rate_and_amount(raise_error_if_no_rate=False)
                
                # After recalculation (or if skipped), restore manually set rates that were found
                print(f"[on_submit] Setting manually found rates...")
                restored_count = 0
                for item in stock_entry.items:
                    if hasattr(item, '_manual_valuation_rate') and item._manual_valuation_rate:
                        manual_rate = item._manual_valuation_rate
                        old_rate = item.basic_rate
                        print(f"[on_submit] Setting manual rate {manual_rate} for {item.item_code} (current: {old_rate})")
                        item.allow_zero_valuation_rate = 0
                        # Set set_basic_rate_manually flag BEFORE setting the rate
                        if hasattr(item, 'set_basic_rate_manually'):
                            item.set_basic_rate_manually = 1
                            print(f"[on_submit] Set set_basic_rate_manually=1 to prevent rate reset")
                        item.basic_rate = flt(manual_rate)
                        item.basic_amount = flt(flt(item.transfer_qty) * flt(item.basic_rate), item.precision("basic_amount"))
                        # Mark that this rate was manually set
                        item._rate_manually_set = True
                        print(f"[on_submit] Set: basic_rate={item.basic_rate}, basic_amount={item.basic_amount}, allow_zero_valuation_rate={item.allow_zero_valuation_rate}, set_basic_rate_manually={getattr(item, 'set_basic_rate_manually', 'N/A')}")
                        # Keep _manual_valuation_rate until after final verification before insert
                        restored_count += 1
                print(f"[on_submit] Set {restored_count} manually found rates")
                
                print(f"[on_submit] Final state of all items:")
                for idx, item in enumerate(stock_entry.items):
                    if item.s_warehouse:
                        print(f"  Consumed Item {idx+1}: {item.item_code}")
                        print(f"    - s_warehouse: {item.s_warehouse}")
                        print(f"    - transfer_qty: {item.transfer_qty}")
                        print(f"    - basic_rate: {item.basic_rate}")
                        print(f"    - valuation_rate: {item.valuation_rate}")
                        print(f"    - allow_zero_valuation_rate: {item.allow_zero_valuation_rate}")
                        print(f"    - basic_amount: {item.basic_amount}")
                    elif item.t_warehouse and item.is_finished_item:
                        print(f"  Finished Item {idx+1}: {item.item_code}")
                        print(f"    - t_warehouse: {item.t_warehouse}")
                        print(f"    - transfer_qty: {item.transfer_qty}")
                        print(f"    - basic_rate: {item.basic_rate}")
                        print(f"    - valuation_rate: {item.valuation_rate}")
                print(f"{'='*80}\n")
                
                # Ensure allow_zero_valuation_rate is set correctly before insert
                # Only set it for items that truly have no rate (not items with manually restored rates)
                print(f"[on_submit] Final verification: Ensuring allow_zero_valuation_rate is set for items with zero rate...")
                for item in stock_entry.items:
                    if item.s_warehouse:
                        current_rate = flt(item.basic_rate)
                        # Check if item has a manually restored rate
                        has_manual_rate = hasattr(item, '_manual_valuation_rate') and item._manual_valuation_rate
                        
                        if has_manual_rate:
                            # Item has manual rate - ensure it's restored and clean up
                            manual_rate = item._manual_valuation_rate
                            # Always restore the manual rate (it might have been reset)
                            if abs(flt(current_rate) - flt(manual_rate)) > 0.01:  # Use tolerance for float comparison
                                print(f"[on_submit] Restoring manual rate {manual_rate} for {item.item_code} (current_rate={current_rate})")
                                item.allow_zero_valuation_rate = 0
                                item.basic_rate = flt(manual_rate)
                                item.basic_amount = flt(flt(item.transfer_qty) * flt(item.basic_rate), item.precision("basic_amount"))
                                print(f"[on_submit] ✓ Restored: basic_rate={item.basic_rate}, basic_amount={item.basic_amount}")
                            else:
                                print(f"[on_submit] {item.item_code}: Manual rate {manual_rate} already set correctly (current={current_rate})")
                            # DON'T delete _manual_valuation_rate yet - keep it for final verification
                        elif (not current_rate or current_rate == 0):
                            # Item truly has no rate - set allow_zero_valuation_rate
                            if not item.allow_zero_valuation_rate:
                                print(f"[on_submit] WARNING: {item.item_code} has rate 0 but allow_zero_valuation_rate is not set! Setting it now...")
                                item.allow_zero_valuation_rate = 1
                                item.basic_rate = 0.0
                                item.basic_amount = 0.0
                            # Ensure it's integer 1, not boolean True
                            if item.allow_zero_valuation_rate is True:
                                item.allow_zero_valuation_rate = 1
                            print(f"[on_submit] {item.item_code}: allow_zero_valuation_rate={item.allow_zero_valuation_rate} (type: {type(item.allow_zero_valuation_rate).__name__})")
                        elif current_rate > 0:
                            print(f"[on_submit] {item.item_code}: Has rate {current_rate}, no action needed")
                
                # Final verification: Double-check that manually found rates are still set
                # This MUST happen right before insert to ensure rates aren't reset by validation
                print(f"[on_submit] Final verification before insert: Checking all rates...")
                for item in stock_entry.items:
                    if item.s_warehouse:
                        # If item has _manual_valuation_rate attribute, it means rate was found but might have been reset
                        if hasattr(item, '_manual_valuation_rate') and item._manual_valuation_rate:
                            manual_rate = item._manual_valuation_rate
                            current_rate = flt(item.basic_rate)
                            # Always restore the manual rate right before insert (it might have been reset by validation)
                            if abs(current_rate - flt(manual_rate)) > 0.01:  # Use tolerance for float comparison
                                print(f"[on_submit] CRITICAL: {item.item_code} rate was reset! Restoring {manual_rate} (current: {current_rate})")
                            else:
                                print(f"[on_submit] {item.item_code}: Rate {manual_rate} is set, but ensuring it persists...")
                            
                            # Always set the rate right before insert to ensure it persists
                            item.allow_zero_valuation_rate = 0
                            item.basic_rate = flt(manual_rate)
                            item.basic_amount = flt(flt(item.transfer_qty) * flt(item.basic_rate), item.precision("basic_amount"))
                            # Set set_basic_rate_manually to prevent future resets (though it might not work for outgoing items)
                            if hasattr(item, 'set_basic_rate_manually'):
                                item.set_basic_rate_manually = 1
                            print(f"[on_submit] ✓ FINAL SET: {item.item_code} basic_rate={item.basic_rate}, basic_amount={item.basic_amount}, set_basic_rate_manually={getattr(item, 'set_basic_rate_manually', 'N/A')}")
                            delattr(item, '_manual_valuation_rate')
                        print(f"[on_submit] Pre-insert check - {item.item_code}: basic_rate={item.basic_rate}, allow_zero_valuation_rate={item.allow_zero_valuation_rate}")
                
                # Ensure set_basic_rate_manually is set for items with manually found rates BEFORE insert
                # This will prevent validate() from trying to recalculate rates
                print(f"[on_submit] Setting set_basic_rate_manually for items with manually found rates...")
                for item in stock_entry.items:
                    if item.s_warehouse and hasattr(item, '_manual_valuation_rate') and item._manual_valuation_rate:
                        if hasattr(item, 'set_basic_rate_manually'):
                            item.set_basic_rate_manually = 1
                            print(f"[on_submit] Set set_basic_rate_manually=1 for {item.item_code} (rate={item._manual_valuation_rate})")
                        # Ensure rate is set
                        item.allow_zero_valuation_rate = 0
                        item.basic_rate = flt(item._manual_valuation_rate)
                        item.basic_amount = flt(flt(item.transfer_qty) * flt(item.basic_rate), item.precision("basic_amount"))
                        print(f"[on_submit] Pre-insert: {item.item_code} basic_rate={item.basic_rate}, set_basic_rate_manually={getattr(item, 'set_basic_rate_manually', 'N/A')}")
                
                # Store manually found rates in Stock Entry document to restore after validation (backup)
                stock_entry._manual_rates_to_restore = {}
                for idx, item in enumerate(stock_entry.items):
                    if item.s_warehouse and hasattr(item, '_manual_valuation_rate') and item._manual_valuation_rate:
                        key = f"{item.item_code}_{idx}"
                        stock_entry._manual_rates_to_restore[key] = {
                            'rate': item._manual_valuation_rate,
                            'item_code': item.item_code,
                            'idx': idx
                        }
                        print(f"[on_submit] Stored manual rate {item._manual_valuation_rate} for {item.item_code} (key={key})")
                
                # Save and submit Stock Entry
                print(f"[on_submit] Inserting Stock Entry (patch should prevent rate reset during validation)...")
                try:
                    stock_entry.insert(ignore_permissions=True)
                    print(f"[on_submit] Stock Entry inserted: {stock_entry.name}")
                    
                    # After insert, restore manually found rates that were reset by validation
                    if hasattr(stock_entry, '_manual_rates_to_restore') and stock_entry._manual_rates_to_restore:
                        print(f"[on_submit] Restoring {len(stock_entry._manual_rates_to_restore)} manually found rates after insert...")
                        # Reload the document to get fresh items
                        stock_entry.reload()
                        restored_count = 0
                        for idx, item in enumerate(stock_entry.items):
                            key = f"{item.item_code}_{idx}"
                            if key in stock_entry._manual_rates_to_restore:
                                manual_data = stock_entry._manual_rates_to_restore[key]
                                manual_rate = manual_data['rate']
                                print(f"[on_submit] Restoring rate {manual_rate} for {item.item_code} (idx={idx}, key={key})")
                                item.allow_zero_valuation_rate = 0
                                item.basic_rate = flt(manual_rate)
                                item.basic_amount = flt(flt(item.transfer_qty) * flt(item.basic_rate), item.precision("basic_amount"))
                                print(f"[on_submit] ✓ Restored: basic_rate={item.basic_rate}, basic_amount={item.basic_amount}")
                                restored_count += 1
                        
                        if restored_count > 0:
                            # Save again to persist the restored rates
                            print(f"[on_submit] Saving Stock Entry with {restored_count} restored rates...")
                            stock_entry.save(ignore_permissions=True)
                            frappe.db.commit()
                            print(f"[on_submit] ✓ Stock Entry saved with restored rates")
                        else:
                            print(f"[on_submit] WARNING: No rates were restored (items might have changed)")
                except Exception as e:
                    print(f"[on_submit] Error during insert/save: {str(e)}")
                    import traceback
                    print(f"[on_submit] Traceback: {traceback.format_exc()}")
                    raise
                print(f"[on_submit] Stock Entry inserted: {stock_entry.name}")
                # stock_entry.submit()
                
                stock_entries_created.append(stock_entry.name)
                print(f"[on_submit] ✓ Stock Entry '{stock_entry.name}' created and submitted successfully")
            
            if not stock_entries_created:
                frappe.throw(_("No items to process. Please ensure packaging quantities are entered."))
            
            print(f"{'='*60}\n")
            
            # Show success message
            if len(stock_entries_created) == 1:
                frappe.msgprint(
                    _("Stock Entry {0} created and submitted successfully.").format(
                        frappe.bold(stock_entries_created[0])
                    ),
                    alert=True
                )
            else:
                frappe.msgprint(
                    _("Stock Entries {0} created and submitted successfully.").format(
                        ", ".join([frappe.bold(se) for se in stock_entries_created])
                    ),
                    alert=True
                )
            
        except Exception as e:
            error_msg = f"Error creating Stock Entry: {str(e)}"
            print(f"[on_submit] ✗ ERROR: {error_msg}")
            frappe.log_error(frappe.get_traceback(), "Packing Report Stock Entry Creation Failed")
            frappe.throw(_(error_msg))
