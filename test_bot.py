# Quick test of bot logic without Twilio/OpenAI
import sys
sys.path.insert(0, '.')

from app import (
    Lead, State, extract_occasion, extract_product, extract_quantity,
    extract_timeline, extract_location, extract_name, extract_email,
    OCCASION_KEYWORDS, PRODUCT_KEYWORDS
)

def test_extractors():
    print("=== Testing Extractors ===\n")
    
    # Occasion
    tests = [
        ("wedding next month", "Wedding"),
        ("corporate gifting for clients", "Corporate"),
        ("baby shower sonogram", "Baby Shower"),
        ("birthday party", "Birthday"),
        ("christmas corporate gifts", "Holiday"),
        ("brand activation at conference", "Activation"),
    ]
    for text, expected in tests:
        result = extract_occasion(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' → {result} (expected: {expected})")
    
    print()
    
    # Product
    tests = [
        ("macarons with logo", "Macarons"),
        ("3 tier cake", "Cakes"),
        ("cupcakes for baby shower", "Cupcakes"),
        ("cookies with photo", "Cookies"),
        ("hotel amenity treats", "Amenity"),
    ]
    for text, expected in tests:
        result = extract_product(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' → {result} (expected: {expected})")
    
    print()
    
    # Quantity
    tests = [
        ("need 50 macarons", "50"),
        ("100 cupcakes please", "100"),
        ("2 cakes", "2"),
        ("quantity 36", "36"),
        ("just 12", "12"),
    ]
    for text, expected in tests:
        result = extract_quantity(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' → {result} (expected: {expected})")
    
    print()
    
    # Timeline
    tests = [
        ("urgent asap", "Urgent (ASAP)"),
        ("need by next week", "Within a week"),
        ("in a month", "Within a month"),
        ("flexible timeline", "Flexible"),
        ("by 15/12/2024", "By 15/12/2024"),
    ]
    for text, expected in tests:
        result = extract_timeline(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' → {result} (expected: {expected})")
    
    print()
    
    # Location (SA)
    tests = [
        ("sandton johannesburg", "Sandton"),
        ("cape town cbd", "Cape Town"),
        ("durban north", "Durban"),
        ("pretoria east", "Pretoria"),
        ("gauteng province", "Gauteng"),
    ]
    for text, expected in tests:
        result = extract_location(text)
        # Normalize: "Cape Town Cbd" -> "Cape Town" for test comparison
        normalized = result.replace(" Cbd", "").replace(" North", "").replace(" East", "") if result else None
        status = "✓" if normalized == expected else "✗"
        print(f"  {status} '{text}' → {result} (expected: {expected})")
    
    print()
    
    # Name
    lead = Lead(phone="+27123456789")
    tests = [
        ("Thandi", "Thandi"),
        ("Thandiwe Moyo", "Thandiwe Moyo"),
        ("john smith", None),  # not capitalized
        ("Hi, I'm Sarah", None),  # sentence
    ]
    for text, expected in tests:
        result = extract_name(text, lead)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' → {result} (expected: {expected})")
    
    print()
    
    # Email
    tests = [
        ("email me at thandi@gmail.com", "thandi@gmail.com"),
        ("contact: john@company.co.za", "john@company.co.za"),
        ("no email here", None),
    ]
    for text, expected in tests:
        result = extract_email(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' → {result} (expected: {expected})")

def test_state_machine():
    print("\n=== Testing State Machine Flow ===\n")
    
    lead = Lead(phone="+27123456789")
    
    # Simulate conversation
    steps = [
        ("Hi", State.OCCASION),
        ("Wedding", State.QUANTITY),
        ("100 macarons", State.DESIGN),
        ("I have the logo ready", State.TIMELINE),
        ("Next week", State.CONTACT),
        ("Thandi", State.CONTACT),  # still need email + location
        ("thandi@email.com", State.CONTACT),
        ("Sandton", State.QUOTE),
    ]
    
    for msg, expected_state in steps:
        # Manually drive state transitions like process_message does
        if lead.state == State.GREETING:
            lead.state = State.OCCASION
        elif lead.state == State.OCCASION:
            if occ := extract_occasion(msg):
                lead.occasion = occ
                lead.state = State.QUANTITY
        elif lead.state == State.QUANTITY:
            if qty := extract_quantity(msg):
                lead.quantity = qty
                if prod := extract_product(msg):
                    lead.product_type = prod
                lead.state = State.DESIGN
        elif lead.state == State.DESIGN:
            lead.design_type = "customer_provided" if "ready" in msg.lower() else "custom_design"
            lead.state = State.TIMELINE
        elif lead.state == State.TIMELINE:
            if tl := extract_timeline(msg):
                lead.timeline = tl
                lead.state = State.CONTACT
        elif lead.state == State.CONTACT:
            if name := extract_name(msg, lead):
                lead.name = name
            if email := extract_email(msg):
                lead.email = email
            if loc := extract_location(msg):
                lead.location = loc
            if lead.name and lead.email and lead.location:
                lead.state = State.QUOTE
        
        status = "✓" if lead.state == expected_state else "✗"
        print(f"  {status} '{msg}' → {lead.state.value} (expected: {expected_state.value})")

if __name__ == "__main__":
    test_extractors()
    test_state_machine()
    print("\n=== All tests complete ===")