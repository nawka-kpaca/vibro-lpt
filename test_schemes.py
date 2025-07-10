#!/usr/bin/env python3
"""
Test script for vibration balancing scheme-based optimization
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import (
    find_optimal_gruz, calculate_sensitivity, parse_vector_input,
    polar_to_cartesian, cartesian_to_polar
)
import numpy as np

def test_scheme_optimization():
    """Test that different schemes produce expected optimization behavior"""
    print("Testing scheme-based optimization...")
    
    # Create test data
    pusk0 = [
        ["10.0/0", "8.0/90"],     # режим 1
        ["12.0/45", "9.0/135"],   # режим 2  
        ["11.0/30", "7.0/120"]    # режим 3
    ]
    
    pusk1 = [
        ["15.0/10", "12.0/100"],  # режим 1 с грузом
        ["17.0/55", "13.0/145"],  # режим 2 с грузом
        ["16.0/40", "11.0/130"]   # режим 3 с грузом
    ]
    
    pusk2 = [
        ["8.0/20", "6.0/110"],    # режим 1 с двумя грузами
        ["9.0/65", "7.0/155"],    # режим 2 с двумя грузами
        ["8.5/50", "5.5/140"]     # режим 3 с двумя грузами
    ]
    
    # Test weights for sensitivity calculation
    gruzes = [(1.0, 0), (1.0, 0)]  # 1kg at 0 degrees for both planes
    
    # Calculate sensitivities
    sensitivities = calculate_sensitivity(pusk0, pusk1, pusk2, gruzes, 1.0)
    
    print("Testing different schemes:")
    
    # Test symmetric scheme
    print("\n1. Symmetric scheme (Симметричная):")
    m1_sym, p1_sym, m2_sym, p2_sym, min_sum_sym, residuals_sym = find_optimal_gruz(
        pusk0, sensitivities, "Симметричная", max_mass=2.0, 
        coarse_mass_step=0.2, fine_mass_step=0.05, 
        coarse_phase_step=30, fine_phase_step=5
    )
    print(f"  Plane 1: mass={m1_sym:.4f}kg, phase={p1_sym:.1f}°")
    print(f"  Plane 2: mass={m2_sym:.4f}kg, phase={p2_sym:.1f}°")
    print(f"  Expected: mass2 = mass1, phase2 = phase1")
    print(f"  Verification: mass_equal={abs(m2_sym - m1_sym) < 1e-6}, phase_equal={abs(p2_sym - p1_sym) < 1e-6}")
    
    # Test anti-symmetric scheme
    print("\n2. Anti-symmetric scheme (Кососимметричная):")
    m1_anti, p1_anti, m2_anti, p2_anti, min_sum_anti, residuals_anti = find_optimal_gruz(
        pusk0, sensitivities, "Кососимметричная", max_mass=2.0,
        coarse_mass_step=0.2, fine_mass_step=0.05,
        coarse_phase_step=30, fine_phase_step=5
    )
    print(f"  Plane 1: mass={m1_anti:.4f}kg, phase={p1_anti:.1f}°")
    print(f"  Plane 2: mass={m2_anti:.4f}kg, phase={p2_anti:.1f}°")
    print(f"  Expected: mass2 = mass1, phase2 = (phase1 + 180) % 360")
    expected_phase2 = (p1_anti + 180) % 360
    print(f"  Verification: mass_equal={abs(m2_anti - m1_anti) < 1e-6}, phase_180={abs(p2_anti - expected_phase2) < 1e-6}")
    
    # Test other scheme (independent optimization)
    print("\n3. Other scheme (Единичная):")
    m1_other, p1_other, m2_other, p2_other, min_sum_other, residuals_other = find_optimal_gruz(
        pusk0, sensitivities, "Единичная", max_mass=2.0,
        coarse_mass_step=0.2, fine_mass_step=0.05,
        coarse_phase_step=30, fine_phase_step=5
    )
    print(f"  Plane 1: mass={m1_other:.4f}kg, phase={p1_other:.1f}°")
    print(f"  Plane 2: mass={m2_other:.4f}kg, phase={p2_other:.1f}°")
    print(f"  Expected: independent optimization")
    print(f"  Verification: independent masses and phases (no constraint)")
    
    print("\nOptimization scores:")
    print(f"  Symmetric: {min_sum_sym:.6f}")
    print(f"  Anti-symmetric: {min_sum_anti:.6f}")
    print(f"  Other: {min_sum_other:.6f}")
    
    return True

if __name__ == "__main__":
    try:
        test_scheme_optimization()
        print("\nAll tests completed successfully!")
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)