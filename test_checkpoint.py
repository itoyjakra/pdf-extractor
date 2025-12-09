#!/usr/bin/env python3
"""Test script to verify checkpoint functionality."""

import json
from pathlib import Path
import sys

def test_checkpoint_exists():
    """Test 1: Check if checkpoint file is created."""
    checkpoint_path = Path("./output/.checkpoint.json")

    if not checkpoint_path.exists():
        print("❌ FAIL: Checkpoint file not found")
        return False

    print("✓ PASS: Checkpoint file exists")
    return True


def test_checkpoint_structure():
    """Test 2: Validate checkpoint structure."""
    checkpoint_path = Path("./output/.checkpoint.json")

    with open(checkpoint_path) as f:
        data = json.load(f)

    required_fields = [
        "pdf_path",
        "total_pages",
        "last_processed_page",
        "timestamp",
        "resolve_references",
        "previous_page_context",
        "all_extractions"
    ]

    for field in required_fields:
        if field not in data:
            print(f"❌ FAIL: Missing field '{field}' in checkpoint")
            return False

    print("✓ PASS: Checkpoint has all required fields")
    return True


def test_checkpoint_content():
    """Test 3: Verify checkpoint contains extraction data."""
    checkpoint_path = Path("./output/.checkpoint.json")

    with open(checkpoint_path) as f:
        data = json.load(f)

    if data["total_pages"] <= 0:
        print("❌ FAIL: Invalid total_pages")
        return False

    if data["last_processed_page"] <= 0:
        print("❌ FAIL: Invalid last_processed_page")
        return False

    if not isinstance(data["all_extractions"], list):
        print("❌ FAIL: all_extractions is not a list")
        return False

    if len(data["all_extractions"]) != data["last_processed_page"]:
        print(f"❌ FAIL: Extraction count mismatch: {len(data['all_extractions'])} != {data['last_processed_page']}")
        return False

    print(f"✓ PASS: Checkpoint contains {data['last_processed_page']} page(s) of data")
    return True


def print_checkpoint_summary():
    """Display checkpoint summary."""
    checkpoint_path = Path("./output/.checkpoint.json")

    with open(checkpoint_path) as f:
        data = json.load(f)

    total_questions = sum(len(pe["questions"]) for pe in data["all_extractions"])

    print("\n" + "="*60)
    print("CHECKPOINT SUMMARY")
    print("="*60)
    print(f"PDF: {Path(data['pdf_path']).name}")
    print(f"Progress: {data['last_processed_page']}/{data['total_pages']} pages")
    print(f"Extracted Q&As: {total_questions}")
    print(f"Timestamp: {data['timestamp']}")
    print(f"Resolve references: {data['resolve_references']}")
    print("="*60 + "\n")


if __name__ == "__main__":
    print("Testing checkpoint functionality...\n")

    tests = [
        test_checkpoint_exists,
        test_checkpoint_structure,
        test_checkpoint_content,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ FAIL: {test.__name__} raised exception: {e}")
            results.append(False)
        print()

    if all(results):
        print_checkpoint_summary()
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print(f"❌ {sum(not r for r in results)} test(s) failed")
        sys.exit(1)
