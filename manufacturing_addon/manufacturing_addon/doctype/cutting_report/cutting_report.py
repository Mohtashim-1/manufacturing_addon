# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class CuttingReport(Document):
    @frappe.whitelist()
    def get_data1(self):
        print(f"\n{'='*60}")
        print(f"[get_data1] Starting for Cutting Report: '{self.name}'")
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
        
        # Check if cutting_report_ct is empty or not
        existing_rows = len(self.cutting_report_ct) if self.cutting_report_ct else 0
        print(f"[get_data1] Existing cutting_report_ct rows: {existing_rows}")
        
        # Clear existing rows to allow re-fetch with new calculations
        if existing_rows > 0:
            print(f"[get_data1] Clearing {existing_rows} existing rows to re-fetch data...")
            self.cutting_report_ct = []
        
        if not self.cutting_report_ct or existing_rows == 0:
            print(f"[get_data1] cutting_report_ct is empty, will fetch data")
            if doc.is_or == 0:
                print(f"[get_data1] Order Sheet is_or = 0, fetching data...")
                rec = frappe.db.sql("""
                    SELECT * FROM `tabOrder Sheet` AS opr
                    LEFT JOIN `tabOrder Sheet CT` AS orct
                    ON orct.parent = opr.name
                    WHERE opr.name = %s AND opr.is_or = 0
                """, (self.order_sheet,), as_dict=True)
                
                print(f"[get_data1] Found {len(rec)} rows from Order Sheet")

                self.cutting_report_ct = []
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
                            # Add each combo item to cutting report
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
                                
                                self.append("cutting_report_ct", {
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
                                            
                                            self.append("cutting_report_ct", {
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
                        frappe.log_error(error_msg, "Cutting Report Item Processing")
                        continue
                
                print(f"\n{'='*60}")
                print(f"[get_data1] SUMMARY:")
                print(f"  - Total rows added to cutting_report_ct: {len(self.cutting_report_ct)}")
                print(f"[get_data1] Final cutting_report_ct data:")
                for idx, row in enumerate(self.cutting_report_ct):
                    print(f"  Row {idx+1}:")
                    print(f"    - so_item: {row.so_item}")
                    print(f"    - combo_item: {row.combo_item}")
                    print(f"    - order_qty: {row.order_qty}")
                    print(f"    - planned_qty: {row.planned_qty}")
                    print(f"    - pcs: {row.pcs}")
                    print(f"    - qty: {row.qty}")
                print(f"{'='*60}")
                print(f"[get_data1] Saving Cutting Report...")
                
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
            print(f"[get_data1] cutting_report_ct already has {existing_rows} rows, skipping fetch")
            print(f"{'='*60}\n")

    def validate(self):
        self.calculate_finished_cutting_qty()
        self.total_qty()
        self.total_percentage()
        self.total()
    
    def before_save(self):
        self.calculate_finished_cutting_qty()

    def calculate_finished_cutting_qty(self):
        """Calculate and update finished_cutting_qty in the child table based on user-entered cutting_qty values."""
        try:
            # Dictionary to store total cutting_qty for each (so_item, combo_item) combination
            cutting_totals = {}

            # Iterate through child table and fetch totals dynamically
            for row in self.cutting_report_ct:
                if not row.so_item:
                    continue  # Skip rows without valid so_item
                
                # Handle cases where combo_item is blank
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

                order_sheets = frappe.db.sql(query, params, as_dict=True)

                # Store the total in the dictionary
                cutting_totals[(row.so_item, row.combo_item or '')] = order_sheets[0].total_cutting if order_sheets else 0

            # Update finished_cutting_qty in child table
            for row in self.cutting_report_ct:
                row.finished_cutting_qty = cutting_totals.get((row.so_item, row.combo_item or ''), 0)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Cutting Quantity Calculation Failed")
            frappe.throw(f"Error in calculating finished cutting quantity: {str(e)}")

    def total_qty(self):
        for i in self.cutting_report_ct:
            i.total_copy1 = i.cutting_qty or 0

    def total_percentage(self):
        for i in self.cutting_report_ct:
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
            SELECT crct.customer, 
                crct.design, 
                crct.colour, 
                crct.article, 
                crct.ean, 
                crct.qty,
                SUM(crct.cutting_qty) AS cutting,
                crct.qty_ctn
            FROM `tabCutting Report` AS cr
            LEFT JOIN `tabCutting Report CT` AS crct ON crct.parent = cr.name
            WHERE cr.order_sheet = %s AND cr.docstatus = 1
            GROUP BY crct.customer, crct.design, crct.colour, crct.article, crct.ean, crct.qty, crct.qty_ctn
        """, (self.order_sheet,), as_dict=True)

        # Ensure `ready_qty` is not empty before accessing its fields
        if ready_qty:
            self.ready_qty = ready_qty[0].get("cutting", 0) if ready_qty else 0
        else:
            self.ready_qty = 0
        
        if self.ready_qty and self.ordered_qty:
            self.percentage = (self.ready_qty / self.ordered_qty) * 100
        else:
            self.percentage = 0
	
        for i in self.cutting_report_ct:
            total_qty += i.qty or 0
            self.ordered_qty = total_qty

