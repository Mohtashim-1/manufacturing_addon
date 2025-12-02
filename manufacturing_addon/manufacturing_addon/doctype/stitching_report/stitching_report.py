# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class StitchingReport(Document):
    @frappe.whitelist()
    def get_data1(self):
        if isinstance(self.order_sheet, str) and self.order_sheet:
            doc = frappe.get_doc("Order Sheet", self.order_sheet)
        else:
            frappe.throw("Invalid Order Sheet reference.")
        if not self.stitching_report_ct:
            if doc.is_or == 0:
                rec = frappe.db.sql("""
                    SELECT * FROM `tabOrder Sheet` AS opr
                    LEFT JOIN `tabOrder Sheet CT` AS orct
                    ON orct.parent = opr.name
                    WHERE opr.name = %s AND opr.is_or = 0
                """, (self.order_sheet,), as_dict=True)

                self.stitching_report_ct = []
                for r in rec:  
                    self.append("stitching_report_ct", {
                        "customer": r.get("customer"),
                        "design": r.get("design"),
                        "colour": r.get("colour"),
                        "finished_size": r.get("size"),
                        "qty_ctn": r.get("qty_ctn"),
                        "article": r.get("stitching_article_no"),
                        "ean": r.get("ean"),
                        "qty": r.get("quantity"),
                        "so_item": r.get("so_item"),
                        "combo_item": r.get("combo_item"),
                    })
                    self.save()

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
        """Validate that stitching qty doesn't exceed cutting qty"""
        if not self.stitching_report_ct:
            return

        for i in self.stitching_report_ct:
            stitched_qty = i.stitching_qty or 0
            cutting_qty = i.finished_cutting_qty or 0

            if stitched_qty > cutting_qty:
                frappe.msgprint(
                    f"⚠️ Warning: Stitching Qty ({stitched_qty}) cannot be greater than Finished Cutting Qty ({cutting_qty}) for row {i.idx}.", 
                    indicator='orange', 
                    title="Warning"
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
