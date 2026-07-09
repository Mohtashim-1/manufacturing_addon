# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt

from manufacturing_addon.manufacturing_addon.utils.report_style_contractor import (
    append_style_contractors,
    validate_mandatory_contractors,
)
from manufacturing_addon.manufacturing_addon.utils.subassembly_bom import (
    apply_subassembly_contractor_qty,
    validate_subassembly_qty_caps,
)
from manufacturing_addon.manufacturing_addon.utils.nested_style_contractors import (
    load_nested_style_contractors,
    save_nested_style_contractors,
)


@frappe.whitelist()
def get_style_contractors_for_line(
    so_item, combo_item=None, article=None, operation="Checking", work_qty=0
):
    """Return style contractor rows for one report line (client-side populate)."""
    from manufacturing_addon.manufacturing_addon.utils.report_style_contractor import (
        build_style_contractor_rows,
    )

    return build_style_contractor_rows(
        so_item,
        operation=operation,
        combo_item=combo_item,
        article=article,
        work_qty=work_qty,
    )


class CheckingReport(Document):
    def load_from_db(self):
        super().load_from_db()
        load_nested_style_contractors(self, "checking_report_ct", "Checking Report CT")
        return self

    def update_children(self):
        super().update_children()
        save_nested_style_contractors(self, "checking_report_ct", "Checking Report CT")
        load_nested_style_contractors(self, "checking_report_ct", "Checking Report CT")

    def _append_checking_ct_row(self, row_data):
        self.append("checking_report_ct", row_data)
        ct_row = self.checking_report_ct[-1]
        append_style_contractors(
            ct_row,
            row_data.get("so_item"),
            operation="Checking",
            combo_item=row_data.get("combo_item"),
            article=row_data.get("article"),
            work_qty_field="checking_qty",
        )

    def _apply_subassembly_style_qty(self):
        for row in self.checking_report_ct or []:
            apply_subassembly_contractor_qty(row, "checking_qty")

    @frappe.whitelist()
    def load_style_contractors(self):
        """Refresh nested style_contractors from Item master for all CT rows."""
        for row in self.checking_report_ct or []:
            if not row.so_item:
                continue
            append_style_contractors(
                row,
                row.so_item,
                operation="Checking",
                combo_item=row.combo_item,
                article=row.article,
                work_qty_field="checking_qty",
            )
        return len(self.checking_report_ct or [])

    @frappe.whitelist()
    def get_data1(self):
        print(f"\n{'='*60}")
        print(f"[get_data1] Starting for Checking Report: '{self.name}'")
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
        
        # Check if checking_report_ct is empty or not
        existing_rows = len(self.checking_report_ct) if self.checking_report_ct else 0
        print(f"[get_data1] Existing checking_report_ct rows: {existing_rows}")
        
        # Clear existing rows to allow re-fetch with new calculations
        if existing_rows > 0:
            print(f"[get_data1] Clearing {existing_rows} existing rows to re-fetch data...")
            self.checking_report_ct = []
        
        if not self.checking_report_ct or existing_rows == 0:
            print(f"[get_data1] checking_report_ct is empty, will fetch data")
            if doc.is_or == 0:
                print(f"[get_data1] Order Sheet is_or = 0, fetching data...")
                rec = frappe.db.sql("""
                    SELECT * FROM `tabOrder Sheet` AS opr
                    LEFT JOIN `tabOrder Sheet CT` AS orct
                    ON orct.parent = opr.name
                    WHERE opr.name = %s AND opr.is_or = 0
                """, (self.order_sheet,), as_dict=True)
                
                print(f"[get_data1] Found {len(rec)} rows from Order Sheet")

                self.checking_report_ct = []
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
                                
                                self._append_checking_ct_row({
                                    "customer": r.get("customer"),
                                    "design": r.get("design"),
                                    "colour": r.get("colour"),
                                    "finished_size": r.get("size"),
                                    "qty_ctn": r.get("qty_ctn"),
                                    "article": r.get("checking_article_no"),
                                    "ean": r.get("ean"),
                                    "order_qty": order_qty,  # Finished-item order qty (not multiplied by PCS)
                                    "pcs": combo_pcs,
                                    "qty": calculated_qty,  # component qty = planned_qty * pcs
                                    "planned_qty": planned_qty,  # Finished-item planned qty (same for duvet/pillow)
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
                                            
                                            self._append_checking_ct_row({
                                                "customer": r.get("customer"),
                                                "design": r.get("design"),
                                                "colour": r.get("colour"),
                                                "finished_size": r.get("size"),
                                                "qty_ctn": r.get("qty_ctn"),
                                                "article": r.get("checking_article_no"),
                                                "ean": r.get("ean"),
                                                "order_qty": order_qty,  # Original order_qty from Order Sheet CT (NOT multiplied by PCS)
                                                "pcs": combo_pcs,
                                                "qty": calculated_qty,  # component qty = planned_qty * pcs
                                                "planned_qty": planned_qty,  # Finished-item planned qty (same for duvet/pillow)
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
                        frappe.log_error(error_msg, "Checking Report Item Processing")
                        continue
                
                print(f"\n{'='*60}")
                print(f"[get_data1] SUMMARY:")
                print(f"  - Total rows added to checking_report_ct: {len(self.checking_report_ct)}")
                print(f"[get_data1] Final checking_report_ct data:")
                for idx, row in enumerate(self.checking_report_ct):
                    print(f"  Row {idx+1}:")
                    print(f"    - so_item: {row.so_item}")
                    print(f"    - combo_item: {row.combo_item}")
                    print(f"    - order_qty: {row.order_qty}")
                    print(f"    - planned_qty: {row.planned_qty}")
                    print(f"    - pcs: {row.pcs}")
                    print(f"    - qty: {row.qty}")
                print(f"{'='*60}")
                print(f"[get_data1] Saving Checking Report...")
                
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
            print(f"[get_data1] checking_report_ct already has {existing_rows} rows, skipping fetch")
            print(f"{'='*60}\n")

    def validate(self):
        self.calculate_finished_stitched_qty()
        self.calculate_finished_checked_qty()
        self._apply_subassembly_style_qty()
        validate_mandatory_contractors(
            self.checking_report_ct,
            qty_field="checking_qty",
            report_label="Checking Report",
        )
        validate_subassembly_qty_caps(
            self, "checking_report_ct", "checking_qty", "Checking Report"
        )
        self.checking_condition()
        self.total_qty()
        self.total_percentage()
        self.total()

    def before_save(self):
        self.calculate_finished_stitched_qty()
        self.calculate_finished_checked_qty()
        self._apply_subassembly_style_qty()

    def _qty_query(self, row, report_doctype, child_doctype, qty_field, exclude_self=False):
        if row.combo_item:
            query = f"""
                SELECT SUM(ct.{qty_field}) AS total_qty
                FROM `tab{child_doctype}` AS ct
                LEFT JOIN `tab{report_doctype}` AS r ON ct.parent = r.name
                WHERE r.order_sheet = %s AND ct.so_item = %s AND ct.combo_item = %s AND r.docstatus = 1
                {{exclude}}
                GROUP BY ct.so_item, ct.combo_item
            """
            params = [self.order_sheet, row.so_item, row.combo_item]
        else:
            query = f"""
                SELECT SUM(ct.{qty_field}) AS total_qty
                FROM `tab{child_doctype}` AS ct
                LEFT JOIN `tab{report_doctype}` AS r ON ct.parent = r.name
                WHERE r.order_sheet = %s AND ct.so_item = %s
                    AND (ct.combo_item IS NULL OR ct.combo_item = '') AND r.docstatus = 1
                {{exclude}}
                GROUP BY ct.so_item
            """
            params = [self.order_sheet, row.so_item]

        exclude = ""
        if exclude_self and self.name:
            exclude = "AND r.name != %s"
            params.append(self.name)

        return frappe.db.sql(query.format(exclude=exclude), tuple(params), as_dict=True)

    def calculate_finished_stitched_qty(self):
        """Available stitched qty from submitted Stitching Reports."""
        try:
            totals = {}
            for row in self.checking_report_ct:
                if not row.so_item:
                    continue
                result = self._qty_query(
                    row,
                    "Stitching Report",
                    "Stitching Report CT",
                    "stitching_qty",
                    exclude_self=False,
                )
                totals[(row.so_item, row.combo_item or "")] = flt(result[0].total_qty) if result else 0

            for row in self.checking_report_ct:
                row.finished_stitched_qty = totals.get((row.so_item, row.combo_item or ""), 0)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Finished Stitched Quantity Fetch Failed")

    def calculate_finished_checked_qty(self):
        """Already checked qty from other submitted Checking Reports."""
        try:
            totals = {}
            for row in self.checking_report_ct:
                if not row.so_item:
                    continue
                result = self._qty_query(
                    row,
                    "Checking Report",
                    "Checking Report CT",
                    "checking_qty",
                    exclude_self=True,
                )
                totals[(row.so_item, row.combo_item or "")] = flt(result[0].total_qty) if result else 0

            for row in self.checking_report_ct:
                row.finished_checked_qty = totals.get((row.so_item, row.combo_item or ""), 0)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Checking Quantity Calculation Failed")
            frappe.throw(_("Error calculating already checked quantity: {0}").format(str(e)))

    def checking_condition(self):
        """Total checked qty cannot exceed available stitched qty."""
        if not self.checking_report_ct:
            return

        self.calculate_finished_stitched_qty()
        self.calculate_finished_checked_qty()

        for row in self.checking_report_ct:
            current_qty = flt(row.checking_qty)
            already_checked = flt(row.finished_checked_qty)
            stitched_qty = flt(row.finished_stitched_qty)
            total_checked = already_checked + current_qty

            if current_qty > 0 and stitched_qty == 0:
                frappe.throw(
                    _(
                        "Cannot enter Checking Qty ({0}) for row {1} because Available Stitched Qty is 0. Submit Stitching Report first (Item: {2}, Combo Item: {3})."
                    ).format(current_qty, row.idx, row.so_item or "N/A", row.combo_item or "N/A"),
                    title=_("Validation Error"),
                )

            if current_qty > 0 and total_checked > stitched_qty:
                frappe.throw(
                    _(
                        "Total Checking Qty ({0} = Already Checked {1} + New Checking {2}) cannot exceed Available Stitched Qty ({3}) for row {4} (Item: {5}, Combo Item: {6})."
                    ).format(
                        total_checked,
                        already_checked,
                        current_qty,
                        stitched_qty,
                        row.idx,
                        row.so_item or "N/A",
                        row.combo_item or "N/A",
                    ),
                    title=_("Validation Error"),
                )

    def total_qty(self):
        for row in self.checking_report_ct:
            row.total_copy1 = flt(row.checking_qty) + flt(row.finished_checked_qty)

    def total_percentage(self):
        for row in self.checking_report_ct:
            entry_qty = flt(row.total_copy1)
            planned_qty = flt(row.planned_qty)
            order_qty = flt(row.order_qty)

            row.planned_percentage_copy = (entry_qty / planned_qty) * 100 if planned_qty else 0
            row.qty_percentage_copy = (entry_qty / order_qty) * 100 if order_qty else 0
            row.percentage_copy = row.qty_percentage_copy

    def total(self):
        total_qty = 0
        ready_qty = frappe.db.sql(
            """
            SELECT SUM(crct.checking_qty) AS checking
            FROM `tabChecking Report` AS cr
            LEFT JOIN `tabChecking Report CT` AS crct ON crct.parent = cr.name
            WHERE cr.order_sheet = %s AND cr.docstatus = 1
            """,
            (self.order_sheet,),
            as_dict=True,
        )

        self.ready_qty = flt(ready_qty[0].checking) if ready_qty else 0
        self.percentage = (self.ready_qty / self.ordered_qty) * 100 if self.ready_qty and self.ordered_qty else 0

        for row in self.checking_report_ct:
            total_qty += row.qty or 0
            self.ordered_qty = total_qty
