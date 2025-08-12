#!/usr/bin/env python3
"""
Test script for Bulk Work Order Manager - Stock Entry Process
This script tests the complete flow from Sales Order to Stock Entry
"""

import frappe
from frappe import _

def test_bulk_stock_entry_process():
    """Test the complete bulk stock entry process"""
    
    print("=== Testing Bulk Work Order Manager - Stock Entry Process ===")
    
    try:
        # Step 1: Create a test sales order
        print("\n1. Creating test sales order...")
        sales_order = create_test_sales_order()
        print(f"✓ Sales Order created: {sales_order}")
        
        # Step 2: Create work orders
        print("\n2. Creating work orders...")
        work_orders = create_test_work_orders(sales_order)
        print(f"✓ Work Orders created: {len(work_orders)} work orders")
        
        # Step 3: Create bulk work order manager
        print("\n3. Creating bulk work order manager...")
        bwom = create_bulk_work_order_manager(sales_order)
        print(f"✓ Bulk Work Order Manager created: {bwom}")
        
        # Step 4: Test bulk stock entry creation
        print("\n4. Testing bulk stock entry creation...")
        stock_entry = test_bulk_stock_entry_creation(sales_order)
        print(f"✓ Stock Entry created: {stock_entry}")
        
        # Step 5: Verify results
        print("\n5. Verifying results...")
        verify_results(sales_order, work_orders, stock_entry)
        print("✓ All tests passed!")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {str(e)}")
        frappe.log_error(f"Bulk Stock Entry Test Failed: {str(e)}")
        return False

def create_test_sales_order():
    """Create a test sales order"""
    try:
        # Get a test customer
        customer = frappe.db.get_value("Customer", {"customer_name": "Test Customer"})
        if not customer:
            customer = frappe.db.get_value("Customer", limit=1)
        
        if not customer:
            raise Exception("No customer found for testing")
        
        # Get a test item
        item = frappe.db.get_value("Item", {"is_stock_item": 1}, limit=1)
        if not item:
            raise Exception("No stock item found for testing")
        
        # Create sales order
        so = frappe.new_doc("Sales Order")
        so.customer = customer
        so.delivery_date = frappe.utils.add_days(frappe.utils.nowdate(), 7)
        so.company = frappe.defaults.get_global_default("company")
        
        # Add items
        so.append("items", {
            "item_code": item,
            "qty": 150,
            "rate": 100
        })
        
        so.save()
        so.submit()
        
        return so.name
        
    except Exception as e:
        raise Exception(f"Failed to create test sales order: {str(e)}")

def create_test_work_orders(sales_order):
    """Create test work orders for the sales order"""
    try:
        work_orders = []
        
        # Get the item from sales order
        so_item = frappe.db.get_value("Sales Order Item", {"parent": sales_order}, "item_code")
        
        # Create 3 work orders of 50 units each
        for i in range(3):
            wo = frappe.new_doc("Work Order")
            wo.sales_order = sales_order
            wo.item_code = so_item
            wo.qty = 50
            wo.company = frappe.defaults.get_global_default("company")
            wo.planned_start_date = frappe.utils.nowdate()
            wo.planned_end_date = frappe.utils.add_days(frappe.utils.nowdate(), 5)
            
            wo.save()
            wo.submit()
            work_orders.append(wo.name)
        
        return work_orders
        
    except Exception as e:
        raise Exception(f"Failed to create test work orders: {str(e)}")

def create_bulk_work_order_manager(sales_order):
    """Create bulk work order manager"""
    try:
        # Import the function
        from manufacturing_addon.manufacturing_addon.doctype.bulk_work_order_manager.bulk_work_order_manager import create_bulk_work_order_manager
        
        bwom_name = create_bulk_work_order_manager(sales_order)
        return bwom_name
        
    except Exception as e:
        raise Exception(f"Failed to create bulk work order manager: {str(e)}")

def test_bulk_stock_entry_creation(sales_order):
    """Test bulk stock entry creation"""
    try:
        # Get work order summary
        from manufacturing_addon.manufacturing_addon.api import get_bulk_work_order_summary
        
        summary = get_bulk_work_order_summary(sales_order)
        
        if not summary.get("success"):
            raise Exception("Failed to get work order summary")
        
        # Create delivery data
        delivery_data = []
        for item_summary in summary["item_summary"]:
            if item_summary["total_pending_qty"] > 0:
                delivery_data.append({
                    "item_code": item_summary["item_code"],
                    "delivery_qty": 50  # Deliver 50 units
                })
        
        # Test bulk allocation
        from manufacturing_addon.manufacturing_addon.api import bulk_allocate_delivery
        
        result = bulk_allocate_delivery(sales_order, delivery_data)
        
        if not result.get("success"):
            raise Exception("Failed to allocate delivery")
        
        # Create stock entry
        from manufacturing_addon.manufacturing_addon.api import create_bulk_stock_entry
        
        stock_entry_result = create_bulk_stock_entry(sales_order, delivery_data)
        
        if not stock_entry_result.get("success"):
            raise Exception("Failed to create stock entry")
        
        return stock_entry_result["stock_entry"]
        
    except Exception as e:
        raise Exception(f"Failed to test bulk stock entry creation: {str(e)}")

def verify_results(sales_order, work_orders, stock_entry):
    """Verify the results of the bulk stock entry process"""
    try:
        # Check work order produced quantities
        for wo_name in work_orders:
            wo = frappe.get_doc("Work Order", wo_name)
            if wo.produced_qty != 50:
                raise Exception(f"Work Order {wo_name} should have 50 produced_qty, got {wo.produced_qty}")
        
        # Check stock entry
        se = frappe.get_doc("Stock Entry", stock_entry)
        if se.stock_entry_type != "Material Transfer for Manufacture":
            raise Exception(f"Stock Entry type should be 'Material Transfer for Manufacture', got {se.stock_entry_type}")
        
        if len(se.items) == 0:
            raise Exception("Stock Entry should have items")
        
        print(f"✓ Work Orders updated correctly")
        print(f"✓ Stock Entry created: {stock_entry}")
        print(f"✓ Stock Entry type: {se.stock_entry_type}")
        print(f"✓ Items in Stock Entry: {len(se.items)}")
        
    except Exception as e:
        raise Exception(f"Verification failed: {str(e)}")

def cleanup_test_data():
    """Clean up test data"""
    try:
        # Delete test documents
        test_docs = [
            ("Bulk Work Order Manager", {"sales_order": ["like", "%TEST%"]}),
            ("Work Order", {"sales_order": ["like", "%TEST%"]}),
            ("Sales Order", {"name": ["like", "%TEST%"]}),
            ("Stock Entry", {"reference_doctype": "Bulk Work Order Manager"})
        ]
        
        for doctype, filters in test_docs:
            docs = frappe.get_all(doctype, filters=filters, pluck="name")
            for doc in docs:
                try:
                    frappe.delete_doc(doctype, doc, force=True)
                except:
                    pass
        
        print("✓ Test data cleaned up")
        
    except Exception as e:
        print(f"Warning: Failed to cleanup test data: {str(e)}")

if __name__ == "__main__":
    # Run the test
    success = test_bulk_stock_entry_process()
    
    if success:
        print("\n🎉 All tests passed! Bulk Stock Entry process is working correctly.")
    else:
        print("\n❌ Tests failed. Please check the logs for details.")
    
    # Cleanup
    cleanup_test_data() 