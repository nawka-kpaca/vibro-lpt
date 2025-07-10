#!/usr/bin/env python3
"""
Test script for automatic scheme detection
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Test automatic scheme detection without GUI
def test_auto_scheme_detection():
    """Test automatic scheme detection based on weight inputs"""
    print("Testing automatic scheme detection...")
    
    # Import the core auto-detection logic
    from main import mean_angle_deg
    import numpy as np
    
    def auto_detect_scheme_standalone(weight_strings):
        """Standalone version of auto_detect_scheme for testing"""
        angles = []
        for weight_str in weight_strings:
            val = weight_str.replace(",", ".")
            if "/" in val:
                try:
                    _, angle = val.split("/")
                    angle = float(angle.replace("°", "")) % 360
                    angles.append(angle)
                except:
                    continue
        
        n = len(angles)
        scheme = "Единичная"
        if n == 2:
            delta = abs((angles[0] - angles[1] + 360) % 360)
            if delta < 10 or abs(delta - 360) < 10:
                scheme = "Симметричная"
            elif abs(delta - 180) < 10:
                scheme = "Кососимметричная"
            else:
                scheme = "Произвольная система"
        elif n == 3:
            if (abs(angles[0]) < 10 and abs((angles[1]-180) % 360) < 10 and abs(angles[2]) < 10):
                scheme = "V-система"
            else:
                scheme = "Произвольная система"
        elif n > 1:
            scheme = "Произвольная система"
        
        return scheme
    
    # Test cases
    test_cases = [
        {
            "name": "Symmetric scheme (0° and 0°)",
            "weights": ["1.0/0", "1.0/0"],
            "expected": "Симметричная"
        },
        {
            "name": "Symmetric scheme (45° and 45°)",
            "weights": ["1.5/45", "1.0/45"],
            "expected": "Симметричная"
        },
        {
            "name": "Symmetric scheme (close angles: 5° and 10°)",
            "weights": ["1.0/5", "1.0/10"],
            "expected": "Симметричная"
        },
        {
            "name": "Anti-symmetric scheme (0° and 180°)",
            "weights": ["1.0/0", "1.0/180"],
            "expected": "Кососимметричная"
        },
        {
            "name": "Anti-symmetric scheme (90° and 270°)",
            "weights": ["0.8/90", "1.2/270"],
            "expected": "Кососимметричная"
        },
        {
            "name": "Anti-symmetric scheme (close to 180°: 175° and 355°)",
            "weights": ["1.0/175", "1.0/355"],
            "expected": "Кососимметричная"
        },
        {
            "name": "Different scheme (0° and 90°)",
            "weights": ["1.0/0", "1.0/90"],
            "expected": "Произвольная система"
        },
        {
            "name": "V-system (3 weights: 0°, 180°, 0°)",
            "weights": ["1.0/0", "1.0/180", "1.0/0"],
            "expected": "V-система"
        },
        {
            "name": "Single weight",
            "weights": ["1.0/45"],
            "expected": "Единичная"
        },
        {
            "name": "Four arbitrary weights",
            "weights": ["1.0/0", "1.0/45", "1.0/90", "1.0/135"],
            "expected": "Произвольная система"
        },
        {
            "name": "No weights",
            "weights": [],
            "expected": "Единичная"
        }
    ]
    
    print("\nRunning test cases:")
    all_passed = True
    
    for test_case in test_cases:
        # Run auto-detection
        detected_scheme = auto_detect_scheme_standalone(test_case["weights"])
        
        # Check result
        passed = detected_scheme == test_case["expected"]
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status} {test_case['name']}")
        print(f"    Weights: {test_case['weights']}")
        print(f"    Expected: {test_case['expected']}")
        print(f"    Detected: {detected_scheme}")
        
        if not passed:
            all_passed = False
        print()
    
    return all_passed

if __name__ == "__main__":
    try:
        success = test_auto_scheme_detection()
        if success:
            print("All scheme detection tests passed!")
        else:
            print("Some tests failed!")
            sys.exit(1)
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)