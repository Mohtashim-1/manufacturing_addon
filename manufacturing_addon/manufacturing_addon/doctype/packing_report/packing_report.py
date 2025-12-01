# Copyright (c) 2025, Manufacturing Addon and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class PackingReport(Document):
    @frappe.whitelist()
    def get_data1(self):
        if isinstance(self.order_sheet, str) and self.order_sheet:
            doc = frappe.get_doc("Order Sheet", self.order_sheet)
        else:
            frappe.throw("Invalid Order Sheet reference.")
        if not self.packing_report_ct:
            if doc.is_or == 0:
                rec = frappe.db.sql("""
                    SELECT * FROM `tabOrder Sheet` AS opr
                    LEFT JOIN `tabOrder Sheet CT` AS orct
                    ON orct.parent = opr.name
                    WHERE opr.name = %s AND opr.is_or = 0
                """, (self.order_sheet,), as_dict=True)

                self.packing_report_ct = []
                for r in rec:  
                    self.append("packing_report_ct", {
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
        self.calculate_finished_quality_qty()
        self.calculate_finished_packaging_qty()
        self.packing_condition()
        self.total_qty()
        self.total_percentage()
        self.total()
    
    def before_save(self):
        self.calculate_finished_quality_qty()
        self.calculate_finished_packaging_qty()

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
        """Validate that packaging qty doesn't exceed quality qty"""
        if not self.packing_report_ct:
            return

        for i in self.packing_report_ct:
            packing_qty = i.packaging_qty or 0
            quality_qty = i.finished_quality_qty or 0

            if packing_qty > quality_qty:
                frappe.msgprint(
                    f"⚠️ Warning: Packing Qty ({packing_qty}) cannot be greater than Finished Quality Qty ({quality_qty}) for row {i.idx}.", 
                    indicator='orange', 
                    title="Warning"
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

