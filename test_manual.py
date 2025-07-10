#!/usr/bin/env python3
"""
Ручное тестирование классического метода балансировки.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import (
    calculate_sensitivity, find_classical_gruz, find_optimal_gruz,
    classic_vector_balance, parse_vector_input
)

def test_manual_balancing():
    """Тестирование на примере реалистичных данных."""
    print("=== Тестирование классического метода балансировки ===")
    
    # Реалистичные данные (приближенные к реальным измерениям)
    pusk0 = [
        ["8.5/15", "6.2/110"],     # Режим 1 - 1 критика
        ["12.3/45", "9.1/145"],    # Режим 2 - 2 критика  
        ["15.7/80", "11.8/185"]    # Режим 3 - Раб. обороты
    ]
    
    pusk1 = [
        ["10.2/25", "7.8/125"],    # После 1-го груза
        ["14.1/55", "10.5/160"],
        ["17.9/95", "13.2/200"]
    ]
    
    pusk2 = [
        ["9.1/35", "6.9/135"],     # После 2-го груза
        ["12.8/65", "9.3/170"],
        ["16.4/105", "12.1/210"]
    ]
    
    gruzes = [
        (0.8, 15),   # Груз 1: 0.8 кг, 15°
        (0.6, 180)   # Груз 2: 0.6 кг, 180°
    ]
    
    print("Исходные данные:")
    print("Пуск 0 (без грузов):")
    for i, row in enumerate(pusk0):
        print(f"  Режим {i+1}: {row}")
    
    print("\nПуск 1 (с 1-м грузом):")
    for i, row in enumerate(pusk1):
        print(f"  Режим {i+1}: {row}")
    
    print("\nПуск 2 (с 2-м грузом):")
    for i, row in enumerate(pusk2):
        print(f"  Режим {i+1}: {row}")
    
    print(f"\nГрузы: {gruzes}")
    
    # Вычисляем чувствительности
    print("\n=== Расчет чувствительностей ===")
    sensitivities = calculate_sensitivity(pusk0, pusk1, pusk2, gruzes, unit_conversion_factor=1.0)
    
    # Классический метод
    print("\n=== Классический метод (поопорный) ===")
    mass1_cl, phase1_cl, mass2_cl, phase2_cl, min_sum_cl, residuals_cl = find_classical_gruz(
        pusk0, sensitivities, max_mass=3.0, 
        coarse_mass_step=0.1, fine_mass_step=0.02,
        coarse_phase_step=20, fine_phase_step=5
    )
    
    print(f"Результат классического метода:")
    print(f"  Плоскость 1: масса={mass1_cl:.4f} кг, фаза={phase1_cl:.1f}°")
    print(f"  Плоскость 2: масса={mass2_cl:.4f} кг, фаза={phase2_cl:.1f}°")
    print(f"  Остатки (√sum_sq): {min_sum_cl:.3f}")
    
    # Оптимальный метод для сравнения
    print("\n=== Оптимальный метод (одновременная оптимизация) ===")
    mass1_op, phase1_op, mass2_op, phase2_op, min_sum_op, residuals_op = find_optimal_gruz(
        pusk0, sensitivities, max_mass=3.0, 
        coarse_mass_step=0.1, fine_mass_step=0.02,
        coarse_phase_step=20, fine_phase_step=5
    )
    
    print(f"Результат оптимального метода:")
    print(f"  Плоскость 1: масса={mass1_op:.4f} кг, фаза={phase1_op:.1f}°")
    print(f"  Плоскость 2: масса={mass2_op:.4f} кг, фаза={phase2_op:.1f}°")
    print(f"  Остатки (√sum_sq): {min_sum_op:.3f}")
    
    # Сравнение остатков
    print(f"\n=== Сравнение остатков ===")
    print("Классический метод:")
    for i, row in enumerate(residuals_cl):
        print(f"  Режим {i+1}: ", end="")
        for j, val in enumerate(row):
            if val is not None:
                amp, ang = val
                print(f"Оп.{j+1}: {amp:.3f}/{ang:.1f}°  ", end="")
            else:
                print(f"Оп.{j+1}: ---  ", end="")
        print()
    
    print("Оптимальный метод:")
    for i, row in enumerate(residuals_op):
        print(f"  Режим {i+1}: ", end="")
        for j, val in enumerate(row):
            if val is not None:
                amp, ang = val
                print(f"Оп.{j+1}: {amp:.3f}/{ang:.1f}°  ", end="")
            else:
                print(f"Оп.{j+1}: ---  ", end="")
        print()
    
    # Исходные значения для сравнения
    print(f"\n=== Исходные значения для сравнения ===")
    original_sum = 0
    for i, row in enumerate(pusk0):
        print(f"  Режим {i+1}: ", end="")
        for j, val_str in enumerate(row):
            val = parse_vector_input(val_str)
            if val:
                amp, ang = val
                original_sum += amp ** 2
                print(f"Оп.{j+1}: {amp:.3f}/{ang:.1f}°  ", end="")
            else:
                print(f"Оп.{j+1}: ---  ", end="")
        print()
    
    print(f"Исходный √sum_sq: {(original_sum ** 0.5):.3f}")
    
    # Проверка эффективности
    print(f"\n=== Эффективность коррекции ===")
    original_rms = (original_sum ** 0.5)
    classical_improvement = (original_rms - min_sum_cl) / original_rms * 100
    optimal_improvement = (original_rms - min_sum_op) / original_rms * 100
    
    print(f"Классический метод: снижение на {classical_improvement:.1f}%")
    print(f"Оптимальный метод: снижение на {optimal_improvement:.1f}%")
    
    # Проверка различий в подходах
    print(f"\n=== Различия в методах ===")
    print(f"Разница в массе плоскости 1: {abs(mass1_cl - mass1_op):.4f} кг")
    print(f"Разница в фазе плоскости 1: {abs(phase1_cl - phase1_op):.1f}°")
    print(f"Разница в массе плоскости 2: {abs(mass2_cl - mass2_op):.4f} кг")
    print(f"Разница в фазе плоскости 2: {abs(phase2_cl - phase2_op):.1f}°")
    print(f"Разница в остатках: {abs(min_sum_cl - min_sum_op):.3f}")
    
    # Интеграционный тест - проверяем классический векторный баланс
    print(f"\n=== Интеграционный тест - classic_vector_balance ===")
    results, residuals = classic_vector_balance(
        pusk0, pusk1, pusk2, gruzes,
        probe_weights=[1.0, 2.0], 
        speed_weights=[2500.0, 3000.0], 
        unit_conversion_factor=1.0
    )
    
    print("Результаты по режимам:")
    for i, res in enumerate(results):
        print(f"  Режим {i+1}: ", end="")
        for j, (mass, phase) in enumerate(res):
            print(f"Пл.{j+1}: {mass:.4f}кг/{phase:.1f}°  ", end="")
        print()
    
    # Средние значения
    ms_avg = [sum(res[j][0] for res in results) / len(results) for j in range(len(results[0]))]
    phis_avg = [sum(res[j][1] for res in results) / len(results) for j in range(len(results[0]))]
    
    print(f"Средние значения:")
    for j in range(len(ms_avg)):
        print(f"  Плоскость {j+1}: {ms_avg[j]:.4f} кг, {phis_avg[j]:.1f}°")
    
    print("\n=== Тестирование завершено ===")

if __name__ == "__main__":
    test_manual_balancing()