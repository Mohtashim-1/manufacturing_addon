import frappe
from frappe.model.document import Document

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
                        "qty": r.get("quantity")
                    })
                    self.save()
            # elif doc.is_or == 1:
            #     # Fetch previous totals from the child table if they exist
            #     previous_totals = frappe.db.sql("""
            #         SELECT SUM(cutting1) AS total_cutting,
            #                SUM(stitching1) AS total_stitching,
            #                SUM(packaging1) AS total_packaging
            #         FROM `tabOperation Report CT`
            #         WHERE parent = %s
            #     """, (self.name,), as_dict=True)

            #     # Ensure values are not None and default to 0 if None
            #     previous_cutting = previous_totals[0].get('total_cutting') or 0
            #     previous_stitching = previous_totals[0].get('total_stitching') or 0
            #     previous_packaging = previous_totals[0].get('total_packaging') or 0

            #     rec1 = frappe.db.sql("""
            #         SELECT oprct.customer, 
            #                oprct.design, 
            #                oprct.colour, 
            #                oprct.article, 
            #                oprct.ean, 
            #                oprct.qty,
            #                SUM(oprct.cutting1) AS cutting,
            #                SUM(oprct.stitching1) AS stitching,
            #                SUM(oprct.packaging1) AS packaging,
            #                 oprct.finished_size,
            #                oprct.qty_ctn
            #         FROM `tabOperation Report` AS oprr
            #         LEFT JOIN `tabOperation Report CT` AS oprct ON oprct.parent = oprr.name
            #         WHERE oprr.order_sheet = %s
            #         GROUP BY oprct.customer, oprct.design, oprct.colour, oprct.article, oprct.ean, oprct.qty, oprct.qty_ctn, oprct.finished_size
            #     """, (self.order_sheet,), as_dict=True)

            #     if rec1:
            #         # Clear any existing data in the child table before appending
            #         self.set("operation_report_ct", [])
            #         for r in rec1:
            #             # Add the previous totals to the new totals, ensuring None values are handled
            #             total_cutting = (r.get('cutting') or 0) + previous_cutting
            #             total_stitching = (r.get('stitching') or 0) + previous_stitching
            #             total_packaging = (r.get('packaging') or 0) + previous_packaging

            #             # Only append data if it's not empty
            #             if r.get("customer") and r.get("design"):
            #                 self.append("operation_report_ct", {
            #                     "customer": r.get("customer"),
            #                     "design": r.get("design"),
            #                     "colour": r.get("colour"),
            #                     "article": r.get("article"),
            #                     "ean": r.get("ean"),
            #                     "qty_ctn": r.get("qty_ctn"),
            #                     "finished_size": r.get("finished_size"),
            #                     "qty": r.get("qty"),
            #                     "cutting1": total_cutting,
            #                     "stitching1": total_stitching,
            #                     "packaging1": total_packaging
            #                 })
            #         self.save()

    





    def validate(self):
        self.total_qty()
        self.total_percentage()
        self.total()
    
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

