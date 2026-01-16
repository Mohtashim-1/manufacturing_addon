"""
Diagnostic script to check why CHINDI is not showing in Delivery Note item list
Run this in Frappe console to diagnose the issue
"""
import frappe

def check_chindi_item():
    """Check CHINDI item properties"""
    customer = "ASIF BHAI SAH  LOCAL SALE"
    
    print("=" * 80)
    print("CHECKING CHINDI ITEM PROPERTIES")
    print("=" * 80)
    
    # Check if CHINDI exists
    if not frappe.db.exists("Item", "CHINDI"):
        print("❌ ERROR: Item 'CHINDI' does not exist!")
        return
    
    item = frappe.get_doc("Item", "CHINDI")
    
    print(f"\n📦 Item: {item.name}")
    print(f"   - Item Name: {item.item_name}")
    print(f"   - is_sales_item: {item.is_sales_item}")
    print(f"   - has_variants: {item.has_variants}")
    print(f"   - disabled: {item.disabled}")
    print(f"   - end_of_life: {item.end_of_life}")
    
    # Check custom fields
    if hasattr(item, 'allow_sales'):
        print(f"   - allow_sales (custom): {item.allow_sales}")
    
    print("\n" + "=" * 80)
    print("CHECKING PARTY SPECIFIC ITEM RULES")
    print("=" * 80)
    
    # Check Party Specific Item rules for this customer
    party_rules = frappe.get_all(
        "Party Specific Item",
        filters={"party": customer},
        fields=["restrict_based_on", "based_on_value"]
    )
    
    if party_rules:
        print(f"\n✅ Found {len(party_rules)} Party Specific Item rule(s) for customer '{customer}':")
        for rule in party_rules:
            print(f"   - Restrict based on: {rule.restrict_based_on}")
            print(f"     Based on value: {rule.based_on_value}")
            
            # Check if CHINDI matches this rule
            if rule.restrict_based_on == "Item":
                if rule.based_on_value == "CHINDI":
                    print(f"     ✅ CHINDI is explicitly allowed")
                else:
                    print(f"     ❌ CHINDI is NOT in the allowed items list")
            elif rule.restrict_based_on == "Item Group":
                item_group = frappe.db.get_value("Item", "CHINDI", "item_group")
                if rule.based_on_value == item_group:
                    print(f"     ✅ CHINDI's item group '{item_group}' matches")
                else:
                    print(f"     ❌ CHINDI's item group '{item_group}' does NOT match '{rule.based_on_value}'")
            elif rule.restrict_based_on == "Brand":
                brand = frappe.db.get_value("Item", "CHINDI", "brand")
                if rule.based_on_value == brand:
                    print(f"     ✅ CHINDI's brand '{brand}' matches")
                else:
                    print(f"     ❌ CHINDI's brand '{brand}' does NOT match '{rule.based_on_value}'")
    else:
        print(f"\n⚠️  No Party Specific Item rules found for customer '{customer}'")
        print("   Items should be filtered by standard ERPNext filters only")
    
    print("\n" + "=" * 80)
    print("CHECKING ALLOWED CUSTOMERS (Custom Field)")
    print("=" * 80)
    
    # Check if CHINDI has custom_allowed_customers field
    if hasattr(item, 'custom_allowed_customers') and item.custom_allowed_customers:
        allowed_customers = [c.customer for c in item.custom_allowed_customers]
        print(f"\n✅ CHINDI has custom_allowed_customers:")
        for cust in allowed_customers:
            if cust == customer:
                print(f"   ✅ {cust} - MATCHES!")
            else:
                print(f"   - {cust}")
        
        if customer not in allowed_customers:
            print(f"\n❌ PROBLEM FOUND: '{customer}' is NOT in CHINDI's allowed customers list!")
            print("   This is why CHINDI is not showing in the item list.")
    else:
        print(f"\n⚠️  CHINDI does not have custom_allowed_customers field or it's empty")
    
    print("\n" + "=" * 80)
    print("COMPARING WITH CHINDI 7X15")
    print("=" * 80)
    
    if frappe.db.exists("Item", "CHINDI 7X15"):
        item2 = frappe.get_doc("Item", "CHINDI 7X15")
        print(f"\n📦 Item: {item2.name}")
        print(f"   - Item Name: {item2.item_name}")
        print(f"   - is_sales_item: {item2.is_sales_item}")
        print(f"   - has_variants: {item2.has_variants}")
        print(f"   - disabled: {item2.disabled}")
        
        if hasattr(item2, 'custom_allowed_customers') and item2.custom_allowed_customers:
            allowed_customers2 = [c.customer for c in item2.custom_allowed_customers]
            print(f"   - custom_allowed_customers: {allowed_customers2}")
            if customer in allowed_customers2:
                print(f"     ✅ '{customer}' IS in the allowed list")
        else:
            print(f"   - custom_allowed_customers: Not set or empty")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    issues = []
    
    if not item.is_sales_item:
        issues.append("❌ is_sales_item = 0 (should be 1)")
    
    if item.has_variants:
        issues.append("❌ has_variants = 1 (should be 0)")
    
    if item.disabled:
        issues.append("❌ disabled = 1 (should be 0)")
    
    if hasattr(item, 'custom_allowed_customers') and item.custom_allowed_customers:
        allowed_customers = [c.customer for c in item.custom_allowed_customers]
        if customer not in allowed_customers:
            issues.append(f"❌ '{customer}' not in custom_allowed_customers")
    
    if issues:
        print("\n🚨 ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ No obvious issues found. Item should appear in the list.")
        print("   Check Party Specific Item rules or custom query filters.")

if __name__ == "__main__":
    check_chindi_item()















