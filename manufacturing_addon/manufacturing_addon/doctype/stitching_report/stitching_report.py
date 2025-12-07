# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class StitchingReport(Document):
    @frappe.whitelist()
    def get_data1(self):
        print(f"\n{'='*60}")
        print(f"[get_data1] Starting for Stitching Report: '{self.name}'")
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
        
        # Check if stitching_report_ct is empty or not
        existing_rows = len(self.stitching_report_ct) if self.stitching_report_ct else 0
        print(f"[get_data1] Existing stitching_report_ct rows: {existing_rows}")
        
        # Clear existing rows to allow re-fetch with new calculations
        if existing_rows > 0:
            print(f"[get_data1] Clearing {existing_rows} existing rows to re-fetch data...")
            self.stitching_report_ct = []
        
        if not self.stitching_report_ct or existing_rows == 0:
            print(f"[get_data1] stitching_report_ct is empty, will fetch data")
            if doc.is_or == 0:
                print(f"[get_data1] Order Sheet is_or = 0, fetching data...")
                rec = frappe.db.sql("""
                    SELECT * FROM `tabOrder Sheet` AS opr
                    LEFT JOIN `tabOrder Sheet CT` AS orct
                    ON orct.parent = opr.name
                    WHERE opr.name = %s AND opr.is_or = 0
                """, (self.order_sheet,), as_dict=True)
                
                print(f"[get_data1] Found {len(rec)} rows from Order Sheet")

                self.stitching_report_ct = []
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
                    
                    # Check if item has combo items (either flag is set OR combo items exist)
                    try:
                        item_doc = frappe.get_doc("Item", so_item)
                        is_product_combo = getattr(item_doc, 'custom_is_product_combo', 0) == 1
                        combo_items = getattr(item_doc, 'custom_product_combo_item', [])
                        
                        print(f"[get_data1] Item {so_item}:")
                        print(f"  - custom_is_product_combo: {is_product_combo}")
                        print(f"  - custom_product_combo_item count: {len(combo_items) if combo_items else 0}")
                        
                        # Check if item has combo items (either flag is set OR combo items exist)
                        has_combo_items = (combo_items and len(combo_items) > 0)
                        
                        # First, try to get combo items from Item's custom_product_combo_item
                        if combo_items and len(combo_items) > 0:
                            print(f"[get_data1] ✓ Found {len(combo_items)} combo items in Item")
                            # Add each combo item to stitching report
                            for combo_item_row in combo_items:
                                combo_item_code = combo_item_row.item
                                combo_pcs = combo_item_row.pcs or 1
                                calculated_qty = combo_pcs * planned_qty
                                
                                print(f"\n{'='*60}")
                                print(f"[get_data1] PROCESSING COMBO ITEM:")
                                print(f"{'='*60}")
                                print(f"  Combo Item Code: {combo_item_code}")
                                print(f"  Source: Item's custom_product_combo_item table")
                                print(f"")
                                print(f"  STEP 1: Get PCS from combo_item_row.pcs")
                                print(f"    - combo_item_row.pcs (raw): {combo_item_row.pcs}")
                                print(f"    - combo_item_row.pcs (after 'or 1'): {combo_pcs}")
                                print(f"    → PCS = {combo_pcs}")
                                print(f"")
                                print(f"  STEP 2: Get Order Qty from Order Sheet CT")
                                print(f"    - Order Sheet CT order_qty (raw): {r.get('order_qty')}")
                                print(f"    - Order Sheet CT order_qty (after 'or 0'): {order_qty}")
                                print(f"    → Order Qty = {order_qty} (NOT multiplied by PCS)")
                                print(f"")
                                print(f"  STEP 3: Get Planned Qty from Order Sheet CT")
                                print(f"    - Order Sheet CT planned_qty (raw): {r.get('planned_qty')}")
                                print(f"    - Order Sheet CT planned_qty (after 'or 0'): {planned_qty}")
                                print(f"    → Planned Qty = {planned_qty}")
                                print(f"")
                                print(f"  STEP 4: Calculate Qty")
                                print(f"    - Formula: Qty = Planned Qty * PCS")
                                print(f"    - Calculation: {planned_qty} * {combo_pcs} = {calculated_qty}")
                                print(f"    → Qty = {calculated_qty}")
                                print(f"")
                                print(f"  STEP 5: Get Qty/Ctn from Order Sheet CT")
                                print(f"    - Order Sheet CT qty_ctn: {r.get('qty_ctn')}")
                                print(f"    → Qty/Ctn = {r.get('qty_ctn')}")
                                print(f"")
                                print(f"{'='*60}")
                                print(f"[get_data1] FINAL VALUES BEING SET:")
                                print(f"  - order_qty: {order_qty} (from Order Sheet CT, NOT multiplied)")
                                print(f"  - pcs: {combo_pcs} (from combo_item_row.pcs)")
                                print(f"  - planned_qty: {planned_qty} (from Order Sheet CT)")
                                print(f"  - qty: {calculated_qty} (calculated as: {planned_qty} * {combo_pcs})")
                                print(f"  - qty_ctn: {r.get('qty_ctn')} (from Order Sheet CT)")
                                print(f"{'='*60}")
                                
                                self.append("stitching_report_ct", {
                                    "customer": r.get("customer"),
                                    "design": r.get("design"),
                                    "colour": r.get("colour"),
                                    "finished_size": r.get("size"),
                                    "qty_ctn": r.get("qty_ctn"),
                                    "article": r.get("stitching_article_no"),
                                    "ean": r.get("ean"),
                                    "order_qty": order_qty,  # Original order_qty from Order Sheet CT (NOT multiplied by PCS)
                                    "pcs": combo_pcs,
                                    "qty": calculated_qty,  # planned_qty * pcs
                                    "planned_qty": planned_qty,  # Original planned_qty from Order Sheet CT
                                    "so_item": so_item,
                                    "combo_item": combo_item_code,
                                })
                                
                                print(f"[get_data1] ✓ Row added successfully!")
                                print(f"{'='*60}\n")
                        else:
                            # If no combo items in Item, try Stitching Size
                            print(f"[get_data1] Row {idx+1}: No combo items in Item, checking Stitching Size...")
                            
                            # Get SIZE from variant attributes
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
                                print(f"[get_data1] Found SIZE attribute: '{size_value}', checking Stitching Size...")
                                stitching_size = frappe.db.get_value("Stitching Size", size_value, "name")
                                if stitching_size:
                                    stitching_size_doc = frappe.get_doc("Stitching Size", stitching_size)
                                    if stitching_size_doc.combo_detail and len(stitching_size_doc.combo_detail) > 0:
                                        print(f"[get_data1] ✓ Found {len(stitching_size_doc.combo_detail)} combo items in Stitching Size")
                                        # Use combo items from Stitching Size
                                        for combo_item_row in stitching_size_doc.combo_detail:
                                            combo_item_code = combo_item_row.item
                                            combo_pcs = combo_item_row.pcs or 1
                                            calculated_qty = combo_pcs * planned_qty
                                            
                                            print(f"\n{'='*60}")
                                            print(f"[get_data1] PROCESSING COMBO ITEM FROM STITCHING SIZE:")
                                            print(f"{'='*60}")
                                            print(f"  Combo Item Code: {combo_item_code}")
                                            print(f"  Source: Stitching Size '{stitching_size}' combo_detail table")
                                            print(f"")
                                            print(f"  STEP 1: Get PCS from stitching_size_doc.combo_detail")
                                            print(f"    - combo_item_row.pcs (raw): {combo_item_row.pcs}")
                                            print(f"    - combo_item_row.pcs (after 'or 1'): {combo_pcs}")
                                            print(f"    → PCS = {combo_pcs}")
                                            print(f"")
                                            print(f"  STEP 2: Get Order Qty from Order Sheet CT")
                                            print(f"    - Order Sheet CT order_qty (raw): {r.get('order_qty')}")
                                            print(f"    - Order Sheet CT order_qty (after 'or 0'): {order_qty}")
                                            print(f"    → Order Qty = {order_qty} (NOT multiplied by PCS)")
                                            print(f"")
                                            print(f"  STEP 3: Get Planned Qty from Order Sheet CT")
                                            print(f"    - Order Sheet CT planned_qty (raw): {r.get('planned_qty')}")
                                            print(f"    - Order Sheet CT planned_qty (after 'or 0'): {planned_qty}")
                                            print(f"    → Planned Qty = {planned_qty}")
                                            print(f"")
                                            print(f"  STEP 4: Calculate Qty")
                                            print(f"    - Formula: Qty = Planned Qty * PCS")
                                            print(f"    - Calculation: {planned_qty} * {combo_pcs} = {calculated_qty}")
                                            print(f"    → Qty = {calculated_qty}")
                                            print(f"")
                                            print(f"  STEP 5: Get Qty/Ctn from Order Sheet CT")
                                            print(f"    - Order Sheet CT qty_ctn: {r.get('qty_ctn')}")
                                            print(f"    → Qty/Ctn = {r.get('qty_ctn')}")
                                            print(f"")
                                            print(f"{'='*60}")
                                            print(f"[get_data1] FINAL VALUES BEING SET:")
                                            print(f"  - order_qty: {order_qty} (from Order Sheet CT, NOT multiplied)")
                                            print(f"  - pcs: {combo_pcs} (from Stitching Size combo_detail)")
                                            print(f"  - planned_qty: {planned_qty} (from Order Sheet CT)")
                                            print(f"  - qty: {calculated_qty} (calculated as: {planned_qty} * {combo_pcs})")
                                            print(f"  - qty_ctn: {r.get('qty_ctn')} (from Order Sheet CT)")
                                            print(f"{'='*60}")
                                            
                                            self.append("stitching_report_ct", {
                                                "customer": r.get("customer"),
                                                "design": r.get("design"),
                                                "colour": r.get("colour"),
                                                "finished_size": r.get("size"),
                                                "qty_ctn": r.get("qty_ctn"),
                                                "article": r.get("stitching_article_no"),
                                                "ean": r.get("ean"),
                                                "order_qty": order_qty,  # Original order_qty from Order Sheet CT (NOT multiplied by PCS)
                                                "pcs": combo_pcs,
                                                "qty": calculated_qty,  # planned_qty * pcs
                                                "planned_qty": planned_qty,  # Original planned_qty from Order Sheet CT
                                                "so_item": so_item,
                                                "combo_item": combo_item_code,
                                            })
                                            
                                            print(f"[get_data1] ✓ Row added successfully!")
                                            print(f"{'='*60}\n")
                                        continue
                            
                            # If no combo items found anywhere, skip
                            print(f"[get_data1] Row {idx+1}: ✗ No combo items found (not in Item or Stitching Size), skipping")
                            continue
                    except Exception as e:
                        error_msg = f"Error processing item {so_item}: {str(e)}"
                        print(f"[get_data1] Row {idx+1}: ✗ ERROR: {error_msg}")
                        frappe.log_error(error_msg, "Stitching Report Item Processing")
                        continue
                
                print(f"\n{'='*60}")
                print(f"[get_data1] SUMMARY:")
                print(f"  - Total rows added to stitching_report_ct: {len(self.stitching_report_ct)}")
                print(f"[get_data1] Final stitching_report_ct data:")
                for idx, row in enumerate(self.stitching_report_ct):
                    print(f"  Row {idx+1}:")
                    print(f"    - so_item: {row.so_item}")
                    print(f"    - combo_item: {row.combo_item}")
                    print(f"    - order_qty: {row.order_qty}")
                    print(f"    - planned_qty: {row.planned_qty}")
                    print(f"    - pcs: {row.pcs}")
                    print(f"    - qty: {row.qty}")
                print(f"{'='*60}")
                print(f"[get_data1] Saving Stitching Report...")
                
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
            print(f"[get_data1] stitching_report_ct already has {existing_rows} rows, skipping fetch")
            print(f"{'='*60}\n")

    def validate(self):
        self.calculate_finished_cutting_qty()
        self.calculate_finished_stitching_qty()
        self.stitching_condition()
        self.total_qty()
        self.total_percentage()
        self.total()

    def before_save(self):
        self.calculate_finished_cutting_qty()
        self.calculate_finished_stitching_qty()

    def calculate_finished_cutting_qty(self):
        """Get finished cutting qty from Cutting Reports"""
        try:
            cutting_totals = {}
            for row in self.stitching_report_ct:
                if not row.so_item:
                    continue
                
                if row.combo_item:
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
                    query = """
                        SELECT SUM(crct.cutting_qty) AS total_cutting
                        FROM `tabCutting Report CT` AS crct 
                        LEFT JOIN `tabCutting Report` AS cr 
                        ON crct.parent = cr.name
                        WHERE cr.order_sheet = %s AND crct.so_item = %s AND (crct.combo_item IS NULL OR crct.combo_item = '') AND cr.docstatus = 1
                        GROUP BY crct.so_item
                    """
                    params = (self.order_sheet, row.so_item)

                result = frappe.db.sql(query, params, as_dict=True)
                cutting_totals[(row.so_item, row.combo_item or '')] = result[0].total_cutting if result else 0

            for row in self.stitching_report_ct:
                row.finished_cutting_qty = cutting_totals.get((row.so_item, row.combo_item or ''), 0)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Cutting Quantity Fetch Failed")

    def calculate_finished_stitching_qty(self):
        """Calculate and update finished_stitching_qty in the child table based on user-entered stitching_qty values."""
        try:
            stitching_totals = {}

            for row in self.stitching_report_ct:
                if not row.so_item:
                    continue
                
                # Exclude current document from calculation
                current_doc_filter = ""
                if self.name:
                    current_doc_filter = "AND sr.name != %s"
                    if row.combo_item:
                        query = """
                            SELECT SUM(srct.stitching_qty) AS total_stitching
                            FROM `tabStitching Report CT` AS srct 
                            LEFT JOIN `tabStitching Report` AS sr 
                            ON srct.parent = sr.name
                            WHERE sr.order_sheet = %s AND srct.so_item = %s AND srct.combo_item = %s AND sr.docstatus = 1 {current_doc_filter}
                            GROUP BY srct.so_item, srct.combo_item
                        """.format(current_doc_filter=current_doc_filter)
                        params = (self.order_sheet, row.so_item, row.combo_item, self.name)
                    else:
                        query = """
                            SELECT SUM(srct.stitching_qty) AS total_stitching
                            FROM `tabStitching Report CT` AS srct 
                            LEFT JOIN `tabStitching Report` AS sr 
                            ON srct.parent = sr.name
                            WHERE sr.order_sheet = %s AND srct.so_item = %s AND (srct.combo_item IS NULL OR srct.combo_item = '') AND sr.docstatus = 1 {current_doc_filter}
                            GROUP BY srct.so_item
                        """.format(current_doc_filter=current_doc_filter)
                        params = (self.order_sheet, row.so_item, self.name)
                else:
                    # New document, no need to exclude
                    if row.combo_item:
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
                        query = """
                            SELECT SUM(srct.stitching_qty) AS total_stitching
                            FROM `tabStitching Report CT` AS srct 
                            LEFT JOIN `tabStitching Report` AS sr 
                            ON srct.parent = sr.name
                            WHERE sr.order_sheet = %s AND srct.so_item = %s AND (srct.combo_item IS NULL OR srct.combo_item = '') AND sr.docstatus = 1
                            GROUP BY srct.so_item
                        """
                        params = (self.order_sheet, row.so_item)

                result = frappe.db.sql(query, params, as_dict=True)
                stitching_totals[(row.so_item, row.combo_item or '')] = result[0].total_stitching if result else 0

            for row in self.stitching_report_ct:
                row.finished_stitched_qty = stitching_totals.get((row.so_item, row.combo_item or ''), 0)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Stitching Quantity Calculation Failed")
            frappe.throw(f"Error in calculating finished stitching quantity: {str(e)}")

    def stitching_condition(self):
        """Validate that total stitching qty (finished_stitched_qty + stitching_qty) doesn't exceed cutting qty"""
        if not self.stitching_report_ct:
            return

        # First ensure finished_cutting_qty and finished_stitched_qty are calculated
        self.calculate_finished_cutting_qty()
        self.calculate_finished_stitching_qty()

        for i in self.stitching_report_ct:
            current_stitching_qty = i.stitching_qty or 0
            finished_stitched_qty = i.finished_stitched_qty or 0
            cutting_qty = i.finished_cutting_qty or 0

            # Total stitching = already stitched (from other documents) + current stitching qty
            total_stitching = finished_stitched_qty + current_stitching_qty

            if current_stitching_qty > 0 and cutting_qty == 0:
                frappe.throw(
                    _("Cannot enter Stitching Qty ({0}) for row {1} because Finished Cutting Qty is 0. Please ensure Cutting Report is submitted first (Item: {2}, Combo Item: {3}).").format(
                        current_stitching_qty,
                        i.idx,
                        i.so_item or "N/A",
                        i.combo_item or "N/A"
                    ),
                    title=_("Validation Error")
                )

            # Check if total stitching (already stitched + current) exceeds cutting qty
            if total_stitching > cutting_qty:
                frappe.throw(
                    _("Total Stitching Qty ({0} = Finished Stitched Qty {1} + Current Stitching Qty {2}) cannot be greater than Finished Cutting Qty ({3}) for row {4} (Item: {5}, Combo Item: {6}). Please reduce the Stitching Qty.").format(
                        total_stitching,
                        finished_stitched_qty,
                        current_stitching_qty,
                        cutting_qty,
                        i.idx,
                        i.so_item or "N/A",
                        i.combo_item or "N/A"
                    ),
                    title=_("Validation Error")
                )

    def total_qty(self):
        for i in self.stitching_report_ct:
            i.total_copy1 = i.stitching_qty or 0

    def total_percentage(self):
        for i in self.stitching_report_ct:
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
            SELECT srct.customer, 
                srct.design, 
                srct.colour, 
                srct.article, 
                srct.ean, 
                srct.qty,
                SUM(srct.stitching_qty) AS stitching,
                srct.qty_ctn
            FROM `tabStitching Report` AS sr
            LEFT JOIN `tabStitching Report CT` AS srct ON srct.parent = sr.name
            WHERE sr.order_sheet = %s AND sr.docstatus = 1
            GROUP BY srct.customer, srct.design, srct.colour, srct.article, srct.ean, srct.qty, srct.qty_ctn
        """, (self.order_sheet,), as_dict=True)

        if ready_qty:
            self.ready_qty = ready_qty[0].get("stitching", 0) if ready_qty else 0
        else:
            self.ready_qty = 0
        
        if self.ready_qty and self.ordered_qty:
            self.percentage = (self.ready_qty / self.ordered_qty) * 100
        else:
            self.percentage = 0

        for i in self.stitching_report_ct:
            total_qty += i.qty or 0
            self.ordered_qty = total_qty
