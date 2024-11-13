import frappe
from frappe.model.document import Document

class OperationReport(Document):
    @frappe.whitelist()
    def get_data1(self):
        # Ensure that `self.order_sheet` is a valid string
        if isinstance(self.order_sheet, str) and self.order_sheet:
            doc = frappe.get_doc("Order Sheet", self.order_sheet)
        else:
            frappe.throw("Invalid Order Sheet reference.")
        
        # Check if the child table is already populated to prevent duplication
        if not self.operation_report_ct:  # If child table is empty
            # Fetch data when `is_or` is 0
            if doc.is_or == 0:
                rec = frappe.db.sql("""
                    SELECT * FROM `tabOrder Sheet` AS opr
                    LEFT JOIN `tabOrder Sheet CT` AS orct
                    ON orct.parent = opr.name
                    WHERE opr.name = %s AND opr.is_or = 0
                """, (self.order_sheet,), as_dict=True)

                if rec or len(rec) > 1:
                    # Clear any existing data in the child table before appending
                    self.set("operation_report_ct", [])
                    for r in rec:
                        if r.get("customer"):  # Check if there's data before appending
                            self.append("operation_report_ct", {
                                "customer": r.get("customer"),
                                "design": r.get("design"),
                                "colour": r.get("colour"),
                                "qty_ctn": r.get("qty_ctn"),
                                "article": r.get("stitching_article_no"),
                                "ean": r.get("ean"),
                                "quantity": r.get("quantity")
                            })
                    self.save()

            # Fetch data when `is_or` is 1 (including sum of previous totals)
            elif doc.is_or == 1:
                # Fetch previous totals from the child table if they exist
                previous_totals = frappe.db.sql("""
                    SELECT SUM(cutting) AS total_cutting,
                           SUM(stitching) AS total_stitching,
                           SUM(packaging) AS total_packaging
                    FROM `tabOperation Report CT`
                    WHERE parent = %s
                """, (self.name,), as_dict=True)

                # Ensure values are not None and default to 0 if None
                previous_cutting = previous_totals[0].get('total_cutting') or 0
                previous_stitching = previous_totals[0].get('total_stitching') or 0
                previous_packaging = previous_totals[0].get('total_packaging') or 0

                rec1 = frappe.db.sql("""
                    SELECT oprct.customer, 
                           oprct.design, 
                           oprct.colour, 
                           oprct.article, 
                           oprct.ean, 
                           oprct.quantity,
                           SUM(oprct.cutting) AS cutting,
                           SUM(oprct.stitching) AS stitching,
                           SUM(oprct.packaging) AS packaging,
                           oprct.qty_ctn
                    FROM `tabOperation Report` AS oprr
                    LEFT JOIN `tabOperation Report CT` AS oprct ON oprct.parent = oprr.name
                    WHERE oprr.order_sheet = %s
                    GROUP BY oprct.customer, oprct.design, oprct.colour, oprct.article, oprct.ean, oprct.quantity, oprct.qty_ctn
                """, (self.order_sheet,), as_dict=True)

                if rec1:
                    # Clear any existing data in the child table before appending
                    self.set("operation_report_ct", [])
                    for r in rec1:
                        # Add the previous totals to the new totals, ensuring None values are handled
                        total_cutting = (r.get('cutting') or 0) + previous_cutting
                        total_stitching = (r.get('stitching') or 0) + previous_stitching
                        total_packaging = (r.get('packaging') or 0) + previous_packaging

                        # Only append data if it's not empty
                        if r.get("customer") and r.get("design"):  # You can check for other required fields too
                            self.append("operation_report_ct", {
                                "customer": r.get("customer"),
                                "design": r.get("design"),
                                "colour": r.get("colour"),
                                "article": r.get("article"),
                                "ean": r.get("ean"),
                                "qty_ctn": r.get("qty_ctn"),
                                "quantity": r.get("quantity"),
                                "cutting": total_cutting,
                                "stitching": total_stitching,
                                "packaging": total_packaging
                            })
                    self.save()
        else:
            frappe.msgprint("Data is already fetched and displayed.")
            
    def on_submit(self):
        # Update the is_or field in `Order Sheet` on submit
        frappe.db.sql("""
            UPDATE `tabOrder Sheet` 
            SET is_or = 1
            WHERE name = %s
        """, (self.order_sheet,))
        frappe.db.commit()
        
        # Reload and save the `Order Sheet` document to apply changes
        doc = frappe.get_doc("Order Sheet", self.order_sheet)
        doc.save()
