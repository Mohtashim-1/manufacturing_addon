import frappe
from frappe.model.document import Document
from frappe import _

class OperationReport(Document):
    @frappe.whitelist()
    def get_data1(self):
        if isinstance(self.order_sheet, str) and self.order_sheet:
            doc = frappe.get_doc("Order Sheet", self.order_sheet)
        else:
            frappe.throw("Invalid Order Sheet reference.")
        if not self.operation_report_ct:
            if doc.is_or == 0:
                rec = frappe.db.sql("""
                    SELECT * FROM `tabOrder Sheet` AS opr
                    LEFT JOIN `tabOrder Sheet CT` AS orct
                    ON orct.parent = opr.name
                    WHERE opr.name = %s AND opr.is_or = 0
                """, (self.order_sheet,), as_dict=True)

                self.operation_report_ct = []
                for r in rec:  
                    self.append("operation_report_ct", {
                        "customer": r.get("customer"),
                        "design": r.get("design"),
                        "colour": r.get("colour"),
                        "finished_size": r.get("size"),
                        "qty_ctn": r.get("qty_ctn"),
                        "article": r.get("stitching_article_no"),
                        "ean": r.get("ean"),
                        "qty":  r.get("planned_qty") or 0,
                        "so_item": r.get("so_item"),
                        "combo_item": r.get("combo_item"),
                    })
                    self.save()

    def validate(self):
        self.cutting_condition()
        self.stitching_condition()
        self.total_qty()
        self.total_percentage()
        self.total()
        # self.cutting_condition()
        # self.calculate_cutting_qty()
        # self.calculate_stitching_qty()
        # self.calculate_packaging_qty()
    
    def before_save(self):
        # self.cutting_condition()
        self.calculate_cutting_qty()
        self.calculate_stitching_qty()
        self.calculate_packaging_qty()

    def cutting_condition(self):

        if not self.operation_report_ct:
            frappe.logger().info("No child table records found. Skipping validation.")
            return

        for i in self.operation_report_ct:
            frappe.logger().info(f"Row {i.idx}: {i.finished_stitched_qty}, {i.finished_cutting_qty}")

            stitched_qty = i.finished_stitched_qty or 0
            cutting_qty = i.finished_cutting_qty or 0

            if stitched_qty > cutting_qty:
                frappe.msgprint(f"⚠️ Excess Qty Error: Finished Stitched Qty ({stitched_qty}) cannot be greater than Finished Cutting Qty ({cutting_qty}) for row {i.idx}.", 
                            indicator='orange', title="Warning")

    
    def stitching_condition(self):

        if not self.operation_report_ct:
            frappe.logger().info("No child table records found. Skipping validation.")
            return

        for i in self.operation_report_ct:
            frappe.logger().info(f"Row {i.idx}: {i.finished_stitched_qty}, {i.finished_packaging_qty}")

            stitched_qty = i.finished_stitched_qty or 0
            packing_qty = i.finished_packaging_qty or 0

            if packing_qty >  stitched_qty  :
                frappe.msgprint(f"❌ Excess Qty Error: Finished Packing Qty ({packing_qty}) cannot be greater than Finished Stitched Qty ({stitched_qty}) for row {i.idx}.",
                            title="Validation Error")

                # if packing_qty > stitched_qty :
                #     frappe.msgprint(f"⚠️ Excess Qty Error: Finished Stitched Qty ({stitched_qty}) cannot be greater than Finished Packing Qty ({packing_qty}) for row {i.idx}.", 
                #                 indicator='orange', title="Warning")

    def calculate_cutting_qty(self):
        """Calculate and update finished_cutting_qty in the child table based on user-entered cutting1 values."""
        try:
            # Dictionary to store total cutting1 for each (so_item, combo_item) combination
            cutting_totals = {}

            # Iterate through child table and fetch totals dynamically
            for row in self.operation_report_ct:
                if not row.so_item:
                    continue  # Skip rows without valid so_item
                
                # Handle cases where combo_item is blank
                if row.combo_item:
                    query = """
                        SELECT SUM(orct.cutting1) AS total_cutting1
                        FROM `tabOperation Report CT` AS orct 
                        LEFT JOIN `tabOperation Report` AS opr 
                        ON orct.parent = opr.name
                        WHERE opr.order_sheet = %s AND orct.so_item = %s AND orct.combo_item = %s and opr.docstatus = 1
                        GROUP BY orct.so_item, orct.combo_item
                    """
                    params = (self.order_sheet, row.so_item, row.combo_item)
                else:
                    query = """
                        SELECT SUM(orct.cutting1) AS total_cutting1
                        FROM `tabOperation Report CT` AS orct 
                        LEFT JOIN `tabOperation Report` AS opr 
                        ON orct.parent = opr.name
                        WHERE opr.order_sheet = %s AND orct.so_item = %s AND (orct.combo_item IS NULL OR orct.combo_item = '') and opr.docstatus = 1
                        GROUP BY orct.so_item
                    """
                    params = (self.order_sheet, row.so_item)

                order_sheets = frappe.db.sql(query, params, as_dict=True)

                # Store the total in the dictionary
                cutting_totals[(row.so_item, row.combo_item or '')] = order_sheets[0].total_cutting1 if order_sheets else 0

            # Update finished_cutting_qty in child table without modifying cutting1
            for row in self.operation_report_ct:
                row.finished_cutting_qty = cutting_totals.get((row.so_item, row.combo_item or ''), 0)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Cutting Quantity Calculation Failed")
            frappe.throw(f"Error in calculating finished cutting quantity: {str(e)}")


    def calculate_stitching_qty(self):
        """Calculate and update finished_stitching_qty in the child table based on user-entered stitching1 values."""
        try:
            # Dictionary to store total stitching1 for each (so_item, combo_item) combination
            stitching_totals = {}

            # Iterate through child table and fetch totals dynamically
            for row in self.operation_report_ct:
                if not row.so_item:
                    continue  # Skip rows without valid so_item
                
                # Handle cases where combo_item is blank
                if row.combo_item:
                    query = """
                        SELECT SUM(orct.stitching1) AS total_stitching
                        FROM `tabOperation Report CT` AS orct 
                        LEFT JOIN `tabOperation Report` AS opr 
                        ON orct.parent = opr.name
                        WHERE opr.order_sheet = %s AND orct.so_item = %s AND orct.combo_item = %s and opr.docstatus = 1
                        GROUP BY orct.so_item, orct.combo_item
                    """
                    params = (self.order_sheet, row.so_item, row.combo_item)
                else:
                    query = """
                        SELECT SUM(orct.stitching1) AS total_stitching
                        FROM `tabOperation Report CT` AS orct 
                        LEFT JOIN `tabOperation Report` AS opr 
                        ON orct.parent = opr.name
                        WHERE opr.order_sheet = %s AND orct.so_item = %s AND (orct.combo_item IS NULL OR orct.combo_item = '') and opr.docstatus = 1
                        GROUP BY orct.so_item
                    """
                    params = (self.order_sheet, row.so_item)

                order_sheets = frappe.db.sql(query, params, as_dict=True)

                # Store the total in the dictionary
                stitching_totals[(row.so_item, row.combo_item or '')] = order_sheets[0].total_stitching if order_sheets else 0
                # frappe.errprint(f"{order_sheets[0].total_stitching}")

            # Update finished_stitching_qty in child table without modifying stitching1
            for row in self.operation_report_ct:
                row.finished_stitched_qty = stitching_totals.get((row.so_item, row.combo_item or ''), 0)  # Correct field name
                # row.db_set("finished_stitching_qty", stitching_totals.get((row.so_item, row.combo_item or ''), 0))
                # frappe.errprint(f"finished stitching {row.finished_stitching_qty}")
                # self.save(ignore_permissions=True)
                # frappe.db.commit()

                # frappe.errprint(f"finished stitching {row.finished_stitching_qty}")
                

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Stitching Quantity Calculation Failed")  # Fixed error message
            frappe.throw(f"Error in calculating finished stitching quantity: {str(e)}")

    def calculate_packaging_qty(self):
        """Calculate and update finished_packaging_qty in the child table based on user-entered packaging1 values."""
        try:
            # Dictionary to store total packaging1 for each (so_item, combo_item) combination
            packaging_totals = {}

            # Iterate through child table and fetch totals dynamically
            for row in self.operation_report_ct:
                if not row.so_item:
                    continue  # Skip rows without valid so_item
                
                # Handle cases where combo_item is blank
                if row.combo_item:
                    query = """
                        SELECT SUM(orct.packaging1) AS total_packaging
                        FROM `tabOperation Report CT` AS orct 
                        LEFT JOIN `tabOperation Report` AS opr 
                        ON orct.parent = opr.name
                        WHERE opr.order_sheet = %s AND orct.so_item = %s AND orct.combo_item = %s  and opr.docstatus = 1
                        GROUP BY orct.so_item, orct.combo_item
                    """
                    params = (self.order_sheet, row.so_item, row.combo_item)
                else:
                    query = """
                        SELECT SUM(orct.packaging1) AS total_packaging
                        FROM `tabOperation Report CT` AS orct 
                        LEFT JOIN `tabOperation Report` AS opr 
                        ON orct.parent = opr.name
                        WHERE opr.order_sheet = %s AND orct.so_item = %s AND (orct.combo_item IS NULL OR orct.combo_item = '') and opr.docstatus = 1
                        GROUP BY orct.so_item
                    """
                    params = (self.order_sheet, row.so_item)

                order_sheets = frappe.db.sql(query, params, as_dict=True)

                # Store the total in the dictionary
                packaging_totals[(row.so_item, row.combo_item or '')] = order_sheets[0].total_packaging if order_sheets else 0

            # Update finished_packaging_qty in child table
            for row in self.operation_report_ct:
                # row.finished_packaging_qty = packaging_totals.get((row.so_item, row.combo_item or ''), 0)
                row.db_set("finished_packaging_qty", packaging_totals.get((row.so_item, row.combo_item or ''), 0))
                # frappe.errprint(f"finished packaging {row.finished_packaging_qty}")
                # self.save(ignore_permissions=True)
                # frappe.db.commit()


        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Finished Packaging Quantity Calculation Failed")
            frappe.throw(f"Error in calculating finished packaging quantity: {str(e)}")



    def total_qty(self):
        for i in self.operation_report_ct:
            i.total_copy1 = i.packaging1

    def total_percentage(self):
        for i in self.operation_report_ct:
            qty = i.qty 
            total = i.total_copy1
            if qty and total:
                percentage = (total / qty) * 100
                i.percentage_copy = percentage

    def on_submit(self):
        pass
        # Update the is_or field in `Order Sheet` on submit
        # frappe.db.sql("""
        #     UPDATE `tabOrder Sheet` 
        #     SET is_or = 1
        #     WHERE name = %s
        # """, (self.order_sheet,))
        # frappe.db.commit()
        
        # # Reload and save the `Order Sheet` document to apply changes
        # doc = frappe.get_doc("Order Sheet", self.order_sheet)
        # doc.save()

    def total(self):
        total_qty = 0
        ready_qty = frappe.db.sql("""
            SELECT oprct.customer, 
                oprct.design, 
                oprct.colour, 
                oprct.article, 
                oprct.ean, 
                oprct.qty,
                SUM(oprct.cutting1) AS cutting,
                SUM(oprct.stitching1) AS stitching,
                SUM(oprct.packaging1) AS packaging,
                oprct.qty_ctn
            FROM `tabOperation Report` AS oprr
            LEFT JOIN `tabOperation Report CT` AS oprct ON oprct.parent = oprr.name
            WHERE oprr.order_sheet = %s
            GROUP BY oprct.customer, oprct.design, oprct.colour, oprct.article, oprct.ean, oprct.qty, oprct.qty_ctn
        """, (self.order_sheet,), as_dict=True)

        # Ensure `ready_qty` is not empty before accessing its fields
        if ready_qty:
            # If you need a single value or total for `qty`, you can sum or select the appropriate entry
            self.ready_qty = ready_qty[0].get("packaging", 0)  # Assuming you want the first entry's qty
        else:
            self.ready_qty = 0  # Default to 0 if no results
        
        if self.ready_qty and  self.ordered_qty:
            self.percentage = (self.ready_qty / self.ordered_qty ) * 100
		
	
        for i in self.operation_report_ct:
            total_qty += i.qty
            self.ordered_qty = total_qty

