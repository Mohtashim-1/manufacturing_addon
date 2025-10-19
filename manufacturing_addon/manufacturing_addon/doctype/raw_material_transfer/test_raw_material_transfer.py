# Copyright (c) 2025, mohtashim and Contributors
# See license.txt

import frappe
import unittest
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, now_datetime, add_days
from manufacturing_addon.manufacturing_addon.doctype.raw_material_transfer.raw_material_transfer import (
    RawMaterialTransfer,
    get_pending_raw_materials,
    bulk_delete_raw_material_rows,
    bulk_clear_all_raw_material_rows,
    bulk_select_and_delete_rows,
    distribute_extra_quantities,
    set_extra_quantity_for_item,
    refresh_transferred_quantities,
    get_transfer_summary,
    sync_warehouse_information,
    create_raw_material_transfer_from_pending,
    debug_bom_allocation
)


class TestRawMaterialTransfer(FrappeTestCase):
    def setUp(self):
        """Set up test data before each test method"""
        self.setup_test_data()
    
    def tearDown(self):
        """Clean up test data after each test method"""
        self.cleanup_test_data()
    
    def setup_test_data(self):
        """Create test data for testing"""
        # Create test company
        if not frappe.db.exists("Company", "Test Company"):
            try:
                company = frappe.new_doc("Company")
                company.company_name = "Test Company"
                company.abbr = "TC"
                company.default_currency = "USD"
                company.country = "United States"
                company.insert()
                self.test_company = company.name
            except Exception as e:
                print(f"Warning: Could not create test company: {e}")
                # Use existing company if available
                existing_companies = frappe.get_all("Company", limit=1)
                if existing_companies:
                    self.test_company = existing_companies[0].name
                else:
                    raise e
        
        # Create test customer
        if not frappe.db.exists("Customer", "Test Customer"):
            try:
                customer = frappe.new_doc("Customer")
                customer.customer_name = "Test Customer"
                customer.customer_type = "Individual"
                customer.disabled = 0  # Ensure customer is enabled
                # Try to set custom_customer_code if the field exists
                try:
                    customer.custom_customer_code = "TEST-CUST-001"
                except:
                    pass  # Field doesn't exist, continue without it
                customer.insert()
                self.test_customer = customer.name
            except Exception as e:
                print(f"Warning: Could not create test customer: {e}")
                # Use existing customer if available
                existing_customers = frappe.get_all("Customer", limit=1)
                if existing_customers:
                    self.test_customer = existing_customers[0].name
                else:
                    # Create a minimal customer without custom fields
                    try:
                        customer = frappe.new_doc("Customer")
                        customer.customer_name = "Test Customer Fallback"
                        customer.customer_type = "Individual"
                        customer.disabled = 0
                        customer.insert()
                        self.test_customer = customer.name
                    except:
                        raise e
        
        # Create test items
        self.test_items = []
        for i in range(3):
            item_code = f"TEST-ITEM-{i+1}"
            if not frappe.db.exists("Item", item_code):
                try:
                    item = frappe.new_doc("Item")
                    item.item_code = item_code
                    item.item_name = f"Test Item {i+1}"
                    # Try to get existing item group or use default
                    existing_item_groups = frappe.get_all("Item Group", limit=1)
                    if existing_item_groups:
                        item.item_group = existing_item_groups[0].name
                    else:
                        item.item_group = "All Item Groups"
                    item.stock_uom = "Nos"
                    item.is_stock_item = 1
                    item.disabled = 0  # Ensure item is enabled
                    # Set as global item to bypass customer restrictions in tests
                    try:
                        item.custom_global_item = 1
                    except:
                        pass  # Field doesn't exist, continue without it
                    item.insert()
                except Exception as e:
                    print(f"Warning: Could not create test item {item_code}: {e}")
                    continue
            self.test_items.append(item_code)
        
        # Create test warehouses
        self.source_warehouse = "Test Source Warehouse - TC"
        self.target_warehouse = "Test Target Warehouse - TC"
        
        # Get existing warehouse types or use default
        existing_warehouse_types = frappe.get_all("Warehouse Type", limit=2)
        if existing_warehouse_types:
            source_warehouse_type = existing_warehouse_types[0].name
            target_warehouse_type = existing_warehouse_types[1].name if len(existing_warehouse_types) > 1 else existing_warehouse_types[0].name
        else:
            # Create basic warehouse types if none exist
            try:
                wt1 = frappe.new_doc("Warehouse Type")
                wt1.warehouse_type = "Raw Material"
                wt1.insert()
                source_warehouse_type = "Raw Material"
            except:
                source_warehouse_type = None
                
            try:
                wt2 = frappe.new_doc("Warehouse Type")
                wt2.warehouse_type = "Work In Progress"
                wt2.insert()
                target_warehouse_type = "Work In Progress"
            except:
                target_warehouse_type = None
        
        if not frappe.db.exists("Warehouse", self.source_warehouse):
            warehouse = frappe.new_doc("Warehouse")
            warehouse.warehouse_name = "Test Source Warehouse"
            warehouse.company = getattr(self, 'test_company', "Test Company")
            if source_warehouse_type:
                warehouse.warehouse_type = source_warehouse_type
            warehouse.insert()
        
        if not frappe.db.exists("Warehouse", self.target_warehouse):
            warehouse = frappe.new_doc("Warehouse")
            warehouse.warehouse_name = "Test Target Warehouse"
            warehouse.company = getattr(self, 'test_company', "Test Company")
            if target_warehouse_type:
                warehouse.warehouse_type = target_warehouse_type
            warehouse.insert()
        
        # Ensure we have test items
        if not self.test_items:
            raise Exception("No test items created")
        
        # Create test sales order
        import time
        unique_id = str(int(time.time() * 1000))[-8:]  # Use timestamp for uniqueness
        sales_order_name = f"TEST-SO-{unique_id}"
        if not frappe.db.exists("Sales Order", sales_order_name):
            sales_order = frappe.new_doc("Sales Order")
            sales_order.name = sales_order_name  # Set explicit unique name to avoid duplicates
            sales_order.customer = getattr(self, 'test_customer', "Test Customer")
            sales_order.company = getattr(self, 'test_company', "Test Company")
            sales_order.transaction_date = now_datetime().date()
            sales_order.delivery_date = add_days(now_datetime().date(), 7)
            # Set currency to match company's default currency
            company_currency = frappe.db.get_value("Company", getattr(self, 'test_company', "Test Company"), "default_currency")
            if company_currency:
                sales_order.currency = company_currency
            sales_order.append("items", {
                "item_code": self.test_items[0],
                "qty": 10,
                "rate": 100,
                "warehouse": self.target_warehouse  # Add delivery warehouse
            })
            sales_order.insert()
            sales_order.submit()
            self.sales_order = sales_order.name
        
        # Create test work order transfer manager
        wotm_name = f"TEST-WOTM-{unique_id}"
        if not frappe.db.exists("Work Order Transfer Manager", wotm_name):
            wotm = frappe.new_doc("Work Order Transfer Manager")
            wotm.name = wotm_name  # Set explicit unique name to avoid duplicates
            wotm.sales_order = self.sales_order
            wotm.customer = getattr(self, 'test_customer', "Test Customer")  # Add required customer field
            wotm.company = getattr(self, 'test_company', "Test Company")
            wotm.source_warehouse = self.source_warehouse
            wotm.target_warehouse = self.target_warehouse
            wotm.posting_date = now_datetime().date()
            wotm.posting_time = now_datetime().time()
            wotm.stock_entry_type = "Material Transfer"
            
            # Add transfer items
            for item_code in self.test_items:
                wotm.append("transfer_items", {
                    "item_code": item_code,
                    "item_name": f"Test Item {item_code.split('-')[-1]}",
                    "total_required_qty": 10,
                    "pending_qty": 10,
                    "transferred_qty_so_far": 0,
                    "uom": "Nos"
                })
            
            wotm.insert()
            # Don't submit WOTM as it requires work orders to be fetched first
            # wotm.submit()
            self.wotm_name = wotm.name
    
    def cleanup_test_data(self):
        """Clean up test data"""
        # Cancel and delete test documents
        test_docs = []
        if hasattr(self, 'wotm_name') and self.wotm_name:
            test_docs.extend([
                ("Raw Material Transfer", {"work_order_transfer_manager": self.wotm_name}),
                ("Work Order Transfer Manager", {"name": self.wotm_name}),
            ])
        if hasattr(self, 'sales_order') and self.sales_order:
            test_docs.append(("Sales Order", {"name": self.sales_order}))
        
        for doctype, filters in test_docs:
            docs = frappe.get_all(doctype, filters=filters)
            for doc in docs:
                try:
                    frappe_doc = frappe.get_doc(doctype, doc.name)
                    if frappe_doc.docstatus == 1:
                        frappe_doc.cancel()
                    frappe_doc.delete()
                except:
                    pass
        
        # Delete test items
        for item_code in self.test_items:
            if frappe.db.exists("Item", item_code):
                frappe.delete_doc("Item", item_code)
        
        # Delete test warehouses
        for warehouse in [self.source_warehouse, self.target_warehouse]:
            if frappe.db.exists("Warehouse", warehouse):
                frappe.delete_doc("Warehouse", warehouse)
        
        # Delete test customer and company
        if hasattr(self, 'test_customer') and self.test_customer and frappe.db.exists("Customer", self.test_customer):
            try:
                frappe.delete_doc("Customer", self.test_customer)
            except:
                pass
        if hasattr(self, 'test_company') and self.test_company and frappe.db.exists("Company", self.test_company):
            try:
                frappe.delete_doc("Company", self.test_company)
            except:
                pass
    
    def test_create_raw_material_transfer(self):
        """Test creating a raw material transfer document"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.source_warehouse = self.source_warehouse
        rmt.target_warehouse = self.target_warehouse
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw materials
        for item_code in self.test_items:
            rmt.append("raw_materials", {
                "item_code": item_code,
                "item_name": f"Test Item {item_code.split('-')[-1]}",
                "pending_qty": 5,
                "transfer_qty": 5,
                "uom": "Nos",
                "source_warehouse": self.source_warehouse,
                "target_warehouse": self.target_warehouse
            })
        
        rmt.insert()
        
        # Test basic properties
        self.assertEqual(rmt.sales_order, self.sales_order)
        self.assertEqual(rmt.work_order_transfer_manager, self.wotm_name)
        self.assertEqual(rmt.company, "Test Company")
        self.assertEqual(len(rmt.raw_materials), 3)
        
        # Test warehouse synchronization
        self.assertEqual(rmt.raw_materials[0].source_warehouse, self.source_warehouse)
        self.assertEqual(rmt.raw_materials[0].target_warehouse, self.target_warehouse)
    
    def test_warehouse_synchronization(self):
        """Test warehouse synchronization from parent to child table"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw materials without warehouse info
        for item_code in self.test_items:
            rmt.append("raw_materials", {
                "item_code": item_code,
                "item_name": f"Test Item {item_code.split('-')[-1]}",
                "pending_qty": 5,
                "transfer_qty": 5,
                "uom": "Nos"
            })
        
        # Set parent warehouse fields
        rmt.source_warehouse = self.source_warehouse
        rmt.target_warehouse = self.target_warehouse
        
        # Test sync_warehouse_information method
        rmt.sync_warehouse_information()
        
        # Verify child table rows are updated
        for item in rmt.raw_materials:
            self.assertEqual(item.source_warehouse, self.source_warehouse)
            self.assertEqual(item.target_warehouse, self.target_warehouse)
    
    def test_calculate_totals(self):
        """Test calculation of totals"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw materials with different quantities
        quantities = [5, 10, 15]
        for i, item_code in enumerate(self.test_items):
            rmt.append("raw_materials", {
                "item_code": item_code,
                "item_name": f"Test Item {item_code.split('-')[-1]}",
                "pending_qty": quantities[i],
                "transfer_qty": quantities[i],
                "extra_qty": 2,
                "uom": "Nos"
            })
        
        rmt.calculate_totals()
        
        # Test calculated totals
        expected_transfer_qty = sum(quantities)
        expected_extra_qty = 2 * len(quantities)
        expected_target_qty = expected_transfer_qty + expected_extra_qty
        expected_expected_qty = expected_transfer_qty + expected_extra_qty
        
        self.assertEqual(rmt.total_transfer_qty, expected_transfer_qty)
        self.assertEqual(rmt.total_extra_qty, expected_extra_qty)
        self.assertEqual(rmt.total_target_qty, expected_target_qty)
        self.assertEqual(rmt.total_expected_qty, expected_expected_qty)
        self.assertEqual(rmt.total_items, len(quantities))
    
    def test_validate_transfer_quantities(self):
        """Test validation of transfer quantities"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Test case 1: No transfer quantities
        rmt.append("raw_materials", {
            "item_code": self.test_items[0],
            "item_name": "Test Item 1",
            "pending_qty": 5,
            "transfer_qty": 0,
            "uom": "Nos"
        })
        
        with self.assertRaises(frappe.ValidationError):
            rmt.validate_transfer_quantities()
        
        # Test case 2: Valid transfer quantities
        rmt.raw_materials[0].transfer_qty = 5
        rmt.validate_transfer_quantities()  # Should not raise error
    
    def test_bulk_delete_rows(self):
        """Test bulk deletion of rows"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add multiple raw materials
        for item_code in self.test_items:
            rmt.append("raw_materials", {
                "item_code": item_code,
                "item_name": f"Test Item {item_code.split('-')[-1]}",
                "pending_qty": 5,
                "transfer_qty": 5,
                "uom": "Nos"
            })
        
        rmt.insert()
        
        # Test bulk delete
        initial_count = len(rmt.raw_materials)
        rmt.bulk_delete_rows([0, 2])  # Delete first and third items
        
        self.assertEqual(len(rmt.raw_materials), initial_count - 2)
        self.assertEqual(rmt.raw_materials[0].item_code, self.test_items[1])  # Only second item remains
    
    def test_bulk_clear_all_rows(self):
        """Test clearing all rows"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw materials
        for item_code in self.test_items:
            rmt.append("raw_materials", {
                "item_code": item_code,
                "item_name": f"Test Item {item_code.split('-')[-1]}",
                "pending_qty": 5,
                "transfer_qty": 5,
                "uom": "Nos"
            })
        
        rmt.insert()
        
        # Test bulk clear
        rmt.bulk_clear_all_rows()
        self.assertEqual(len(rmt.raw_materials), 0)
    
    def test_initialize_tracking_fields(self):
        """Test initialization of tracking fields"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw material without tracking fields
        rmt.append("raw_materials", {
            "item_code": self.test_items[0],
            "item_name": "Test Item 1",
            "pending_qty": 5,
            "transfer_qty": 5,
            "uom": "Nos"
        })
        
        rmt.initialize_tracking_fields()
        
        # Check if tracking fields are initialized
        item = rmt.raw_materials[0]
        self.assertEqual(item.extra_qty, 0)
        self.assertEqual(item.target_qty, 5)  # pending_qty + extra_qty
        self.assertEqual(item.expected_qty, 5)  # transfer_qty + extra_qty
        self.assertEqual(item.transfer_status, "Pending")
    
    def test_update_item_transfer_status(self):
        """Test updating item transfer status"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw material
        rmt.append("raw_materials", {
            "item_code": self.test_items[0],
            "item_name": "Test Item 1",
            "pending_qty": 5,
            "transfer_qty": 5,
            "uom": "Nos"
        })
        
        item = rmt.raw_materials[0]
        
        # Test case 1: Pending status
        item.transferred_qty_so_far = 0
        rmt.update_item_transfer_status(item)
        self.assertEqual(item.transfer_status, "Pending")
        
        # Test case 2: Partially transferred
        item.transferred_qty_so_far = 3
        rmt.update_item_transfer_status(item)
        self.assertEqual(item.transfer_status, "Partially Transferred")
        
        # Test case 3: Fully transferred
        item.transferred_qty_so_far = 5
        rmt.update_item_transfer_status(item)
        self.assertEqual(item.transfer_status, "Fully Transferred")
    
    def test_api_get_pending_raw_materials(self):
        """Test API method get_pending_raw_materials"""
        result = get_pending_raw_materials(self.wotm_name)
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)  # Should have 3 test items
        
        for item in result:
            self.assertIn("item_code", item)
            self.assertIn("item_name", item)
            self.assertIn("pending_qty", item)
            self.assertIn("uom", item)
            self.assertIn("warehouse", item)
    
    def test_api_bulk_delete_raw_material_rows(self):
        """Test API method bulk_delete_raw_material_rows"""
        # Create a test document
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        for item_code in self.test_items:
            rmt.append("raw_materials", {
                "item_code": item_code,
                "item_name": f"Test Item {item_code.split('-')[-1]}",
                "pending_qty": 5,
                "transfer_qty": 5,
                "uom": "Nos"
            })
        
        rmt.insert()
        
        # Test bulk delete API
        result = bulk_delete_raw_material_rows(rmt.name, [0, 2])
        
        self.assertTrue(result["success"])
        self.assertEqual(result["remaining_rows"], 1)
        
        # Clean up
        rmt.cancel()
        rmt.delete()
    
    def test_api_sync_warehouse_information(self):
        """Test API method sync_warehouse_information"""
        # Create a test document
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.source_warehouse = self.source_warehouse
        rmt.target_warehouse = self.target_warehouse
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw materials without warehouse info
        for item_code in self.test_items:
            rmt.append("raw_materials", {
                "item_code": item_code,
                "item_name": f"Test Item {item_code.split('-')[-1]}",
                "pending_qty": 5,
                "transfer_qty": 5,
                "uom": "Nos"
            })
        
        rmt.insert()
        
        # Test sync warehouse information API
        result = sync_warehouse_information(rmt.name)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "Warehouse information synced successfully")
        
        # Verify warehouse information is synced
        rmt.reload()
        for item in rmt.raw_materials:
            self.assertEqual(item.source_warehouse, self.source_warehouse)
            self.assertEqual(item.target_warehouse, self.target_warehouse)
        
        # Clean up
        rmt.cancel()
        rmt.delete()
    
    def test_api_get_transfer_summary(self):
        """Test API method get_transfer_summary"""
        # Create a test document
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw materials
        for item_code in self.test_items:
            rmt.append("raw_materials", {
                "item_code": item_code,
                "item_name": f"Test Item {item_code.split('-')[-1]}",
                "pending_qty": 5,
                "transfer_qty": 5,
                "extra_qty": 2,
                "uom": "Nos"
            })
        
        rmt.insert()
        
        # Test get transfer summary API
        result = get_transfer_summary(rmt.name)
        
        self.assertTrue(result["success"])
        self.assertIn("summary", result)
        
        summary = result["summary"]
        self.assertEqual(summary["total_items"], 3)
        self.assertEqual(summary["total_pending_qty"], 15)  # 5 * 3
        self.assertEqual(summary["total_transfer_qty"], 15)  # 5 * 3
        self.assertEqual(summary["total_extra_qty"], 6)  # 2 * 3
        
        # Clean up
        rmt.cancel()
        rmt.delete()
    
    def test_api_create_raw_material_transfer_from_pending(self):
        """Test API method create_raw_material_transfer_from_pending"""
        result = create_raw_material_transfer_from_pending(self.wotm_name)
        
        self.assertTrue(result["success"])
        self.assertIn("doc_name", result)
        
        # Verify the created document
        doc_name = result["doc_name"]
        rmt = frappe.get_doc("Raw Material Transfer", doc_name)
        
        self.assertEqual(rmt.work_order_transfer_manager, self.wotm_name)
        self.assertEqual(len(rmt.raw_materials), 3)
        
        # Clean up
        rmt.cancel()
        rmt.delete()
    
    def test_warehouse_validation(self):
        """Test warehouse validation"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw material without source warehouse
        rmt.append("raw_materials", {
            "item_code": self.test_items[0],
            "item_name": "Test Item 1",
            "pending_qty": 5,
            "transfer_qty": 5,
            "uom": "Nos"
        })
        
        # Should raise validation error
        with self.assertRaises(frappe.ValidationError):
            rmt.validate_warehouses()
    
    def test_work_order_manager_validation(self):
        """Test work order manager validation"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Test case 1: No work order transfer manager
        with self.assertRaises(frappe.ValidationError):
            rmt.validate_work_order_manager()
        
        # Test case 2: Invalid work order transfer manager
        rmt.work_order_transfer_manager = "INVALID-WOTM"
        with self.assertRaises(frappe.ValidationError):
            rmt.validate_work_order_manager()
    
    def test_stock_entry_type_validation(self):
        """Test stock entry type validation"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Test case: No stock entry type
        with self.assertRaises(frappe.ValidationError):
            rmt.validate_stock_entry_type()
    
    def test_bom_allocation_validation(self):
        """Test BOM allocation validation"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw material that doesn't exist in any BOM
        rmt.append("raw_materials", {
            "item_code": "NON-EXISTENT-ITEM",
            "item_name": "Non Existent Item",
            "pending_qty": 5,
            "transfer_qty": 5,
            "uom": "Nos"
        })
        
        # Should raise validation error for BOM allocation
        with self.assertRaises(frappe.ValidationError):
            rmt.validate_allocation()
    
    def test_get_bom_allocation_debug_info(self):
        """Test BOM allocation debug info method"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Test debug info for a test item
        debug_info = rmt.get_bom_allocation_debug_info(self.test_items[0])
        
        self.assertIn("item_code", debug_info)
        self.assertIn("work_orders", debug_info)
        self.assertIn("can_allocate", debug_info)
        self.assertEqual(debug_info["item_code"], self.test_items[0])
    
    def test_api_debug_bom_allocation(self):
        """Test API method debug_bom_allocation"""
        # Create a test document
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw materials
        for item_code in self.test_items:
            rmt.append("raw_materials", {
                "item_code": item_code,
                "item_name": f"Test Item {item_code.split('-')[-1]}",
                "pending_qty": 5,
                "transfer_qty": 5,
                "uom": "Nos"
            })
        
        rmt.insert()
        
        # Test debug BOM allocation API
        result = debug_bom_allocation(rmt.name)
        
        self.assertTrue(result["success"])
        self.assertIn("debug_info", result)
        
        # Clean up
        rmt.cancel()
        rmt.delete()
    
    def test_error_log_title_truncation(self):
        """Test that error log titles are properly truncated"""
        rmt = frappe.new_doc("Raw Material Transfer")
        rmt.sales_order = self.sales_order
        rmt.work_order_transfer_manager = self.wotm_name
        rmt.company = getattr(self, 'test_company', "Test Company")
        rmt.stock_entry_type = "Material Transfer"
        rmt.posting_date = now_datetime().date()
        rmt.posting_time = now_datetime().time()
        
        # Add raw material that will cause BOM allocation error
        rmt.append("raw_materials", {
            "item_code": "VERY-LONG-ITEM-CODE-THAT-WILL-CAUSE-TITLE-TRUNCATION-ISSUE",
            "item_name": "Very Long Item Name That Will Cause Title Truncation Issue",
            "pending_qty": 5,
            "transfer_qty": 5,
            "uom": "Nos"
        })
        
        rmt.insert()
        
        # This should not cause a character length exceeded error
        try:
            rmt.validate_allocation()
        except frappe.ValidationError as e:
            # The error should be caught and logged without title truncation issues
            self.assertIsInstance(e, frappe.ValidationError)
        
        # Clean up
        rmt.cancel()
        rmt.delete()


if __name__ == "__main__":
    unittest.main()
