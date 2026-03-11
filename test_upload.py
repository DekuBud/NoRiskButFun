#!/usr/bin/env python3
"""Quick test script for the manual supplier name upload flow."""
from io import BytesIO

import requests
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

BASE_URL = "http://localhost:8000"


def create_simple_pdf() -> bytes:
    """Create a minimal PDF with some financial text."""
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    c.drawString(100, 750, "Annual Report 2024/25")
    c.drawString(100, 730, "Umsatzerlöse: 4.126,3 Mio EUR")
    c.drawString(100, 710, "EBITDA: 850,5 Mio EUR")
    c.drawString(100, 690, "Employees: 5000")
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


def test_upload_with_manual_name():
    """Test uploading a PDF with a manual supplier name."""
    pdf_bytes = create_simple_pdf()

    files = {
        "file": ("test_report.pdf", pdf_bytes, "application/pdf"),
    }
    data = {
        "supplier_name": "Test Supplier Inc.",
    }

    print("Testing upload endpoint with manual supplier name...")
    print(f"  Supplier: {data['supplier_name']}")
    print(f"  PDF size: {len(pdf_bytes)} bytes")

    response = requests.post(f"{BASE_URL}/upload", files=files, data=data)

    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ Upload successful!")
        print(f"  Message: {result.get('message')}")
        print(f"  Supplier ID: {result['supplier']['id']}")
        print(f"  Supplier Name: {result['supplier']['name']}")
        print(f"  Year: {result['year_data'].get('year')}")
        print(f"  Extracted KPIs: {result['extraction']['kpis']}")
        return True
    else:
        print(f"\n✗ Upload failed with status {response.status_code}")
        print(f"  Details: {response.text}")
        return False


def test_missing_supplier_name():
    """Test that upload fails gracefully when supplier name is missing."""
    pdf_bytes = create_simple_pdf()

    files = {
        "file": ("test_report.pdf", pdf_bytes, "application/pdf"),
    }

    print("\nTesting endpoint with missing supplier name (should fail)...")
    response = requests.post(f"{BASE_URL}/upload", files=files, data={})

    if response.status_code == 400:
        print(f"✓ Correctly rejected: {response.json()['detail']}")
        return True
    else:
        print(f"✗ Unexpected status {response.status_code}: {response.text}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("NoRiskButFun Upload Flow Test")
    print("=" * 60)
    print("\nMake sure the app is running: uvicorn app.main:app --reload\n")

    try:
        # Test valid upload
        success1 = test_upload_with_manual_name()

        # Test validation
        success2 = test_missing_supplier_name()

        print("\n" + "=" * 60)
        if success1 and success2:
            print("✓ All tests passed!")
        else:
            print("✗ Some tests failed")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n✗ Could not connect to localhost:8000")
        print("  Make sure to run: uvicorn app.main:app --reload")
