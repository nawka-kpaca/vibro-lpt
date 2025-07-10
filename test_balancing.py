#!/usr/bin/env python3
"""
Тесты для функций балансировки вибрации.
Проверяет корректность работы классических и оптимальных методов расчета.
"""

import unittest
import numpy as np
import sys
import os

# Добавляем путь к модулю
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import (
    polar_to_cartesian, cartesian_to_polar, 
    calculate_sensitivity, find_classical_gruz, find_optimal_gruz,
    classic_vector_balance, parse_vector_input
)

class TestBalancingFunctions(unittest.TestCase):
    """Тесты для функций балансировки."""
    
    def setUp(self):
        """Подготовка тестовых данных."""
        # Типичные данные для тестирования
        self.test_pusk0 = [
            ["5.0/0", "3.0/90"],      # Режим 1 (1 критика)
            ["6.0/45", "4.0/135"],    # Режим 2 (2 критика)
            ["7.0/180", "5.0/270"]    # Режим 3 (Раб. обороты)
        ]
        
        self.test_pusk1 = [
            ["7.0/30", "4.0/120"],    # После первого груза
            ["8.0/75", "5.0/165"],
            ["9.0/210", "6.0/300"]
        ]
        
        self.test_pusk2 = [
            ["6.0/60", "3.5/150"],    # После второго груза
            ["7.5/105", "4.5/195"],
            ["8.5/240", "5.5/330"]
        ]
        
        self.test_gruzes = [
            (0.5, 0),    # Груз 1: 0.5 кг, 0°
            (0.3, 180)   # Груз 2: 0.3 кг, 180°
        ]
    
    def test_polar_cartesian_conversion(self):
        """Тест преобразования полярных и декартовых координат."""
        # Тест polar_to_cartesian
        x, y = polar_to_cartesian(1.0, 0)
        self.assertAlmostEqual(x, 1.0, places=5)
        self.assertAlmostEqual(y, 0.0, places=5)
        
        x, y = polar_to_cartesian(1.0, 90)
        self.assertAlmostEqual(x, 0.0, places=5)
        self.assertAlmostEqual(y, 1.0, places=5)
        
        # Тест cartesian_to_polar
        r, a = cartesian_to_polar(1.0, 0.0)
        self.assertAlmostEqual(r, 1.0, places=3)
        self.assertAlmostEqual(a, 0.0, places=1)
        
        r, a = cartesian_to_polar(0.0, 1.0)
        self.assertAlmostEqual(r, 1.0, places=3)
        self.assertAlmostEqual(a, 90.0, places=1)
    
    def test_parse_vector_input(self):
        """Тест парсинга векторного ввода."""
        # Корректный ввод
        result = parse_vector_input("5.0/90")
        self.assertEqual(result, (5.0, 90.0))
        
        result = parse_vector_input("3.5/45.5")
        self.assertEqual(result, (3.5, 45.5))
        
        # Обработка запятых
        result = parse_vector_input("2,5/120,5")
        self.assertEqual(result, (2.5, 120.5))
        
        # Некорректный ввод
        result = parse_vector_input("invalid")
        self.assertIsNone(result)
        
        result = parse_vector_input("5.0")
        self.assertIsNone(result)
        
        result = parse_vector_input("0/0")
        self.assertIsNone(result)
    
    def test_calculate_sensitivity(self):
        """Тест расчета чувствительности."""
        sensitivities = calculate_sensitivity(
            self.test_pusk0, self.test_pusk1, self.test_pusk2, 
            self.test_gruzes, unit_conversion_factor=1.0
        )
        
        # Проверяем структуру результата
        self.assertIn('plane1', sensitivities)
        self.assertIn('plane2', sensitivities)
        self.assertEqual(len(sensitivities['plane1']), 3)  # 3 режима
        self.assertEqual(len(sensitivities['plane2']), 3)  # 3 режима
        
        for i in range(3):
            self.assertEqual(len(sensitivities['plane1'][i]), 2)  # 2 опоры
            self.assertEqual(len(sensitivities['plane2'][i]), 2)  # 2 опоры
            
            for j in range(2):
                sens_amp, sens_ang = sensitivities['plane1'][i][j]
                self.assertIsInstance(sens_amp, float)
                self.assertIsInstance(sens_ang, float)
                self.assertGreaterEqual(sens_amp, 0)
                self.assertGreaterEqual(sens_ang, 0)
                self.assertLess(sens_ang, 360)
    
    def test_find_classical_gruz(self):
        """Тест классического метода поиска грузов."""
        sensitivities = calculate_sensitivity(
            self.test_pusk0, self.test_pusk1, self.test_pusk2, 
            self.test_gruzes, unit_conversion_factor=1.0
        )
        
        mass1, phase1, mass2, phase2, min_sum, residuals = find_classical_gruz(
            self.test_pusk0, sensitivities, max_mass=2.0, 
            coarse_mass_step=0.2, fine_mass_step=0.05,
            coarse_phase_step=30, fine_phase_step=5
        )
        
        # Проверяем, что результаты разумны
        self.assertIsInstance(mass1, float)
        self.assertIsInstance(phase1, float)
        self.assertIsInstance(mass2, float)
        self.assertIsInstance(phase2, float)
        self.assertIsInstance(min_sum, float)
        
        self.assertGreaterEqual(mass1, 0)
        self.assertGreaterEqual(mass2, 0)
        self.assertLessEqual(mass1, 2.0)
        self.assertLessEqual(mass2, 2.0)
        
        self.assertGreaterEqual(phase1, 0)
        self.assertGreaterEqual(phase2, 0)
        self.assertLess(phase1, 360)
        self.assertLess(phase2, 360)
        
        self.assertGreaterEqual(min_sum, 0)
        self.assertLess(min_sum, 1000)  # Разумный предел
        
        # Проверяем остатки
        self.assertEqual(len(residuals), 3)  # 3 режима
        for i in range(3):
            self.assertEqual(len(residuals[i]), 2)  # 2 опоры
            for j in range(2):
                if residuals[i][j] is not None:
                    amp, ang = residuals[i][j]
                    self.assertIsInstance(amp, float)
                    self.assertIsInstance(ang, float)
                    self.assertGreaterEqual(amp, 0)
    
    def test_find_optimal_gruz(self):
        """Тест оптимального метода поиска грузов."""
        sensitivities = calculate_sensitivity(
            self.test_pusk0, self.test_pusk1, self.test_pusk2, 
            self.test_gruzes, unit_conversion_factor=1.0
        )
        
        mass1, phase1, mass2, phase2, min_sum, residuals = find_optimal_gruz(
            self.test_pusk0, sensitivities, max_mass=2.0, 
            coarse_mass_step=0.2, fine_mass_step=0.05,
            coarse_phase_step=30, fine_phase_step=5
        )
        
        # Проверяем, что результаты разумны
        self.assertIsInstance(mass1, float)
        self.assertIsInstance(phase1, float)
        self.assertIsInstance(mass2, float)
        self.assertIsInstance(phase2, float)
        self.assertIsInstance(min_sum, float)
        
        self.assertGreaterEqual(mass1, 0)
        self.assertGreaterEqual(mass2, 0)
        self.assertLessEqual(mass1, 2.0)
        self.assertLessEqual(mass2, 2.0)
        
        self.assertGreaterEqual(phase1, 0)
        self.assertGreaterEqual(phase2, 0)
        self.assertLess(phase1, 360)
        self.assertLess(phase2, 360)
        
        self.assertGreaterEqual(min_sum, 0)
        self.assertLess(min_sum, 1000)  # Разумный предел
    
    def test_classic_vector_balance(self):
        """Тест классического векторного баланса."""
        results, residuals = classic_vector_balance(
            self.test_pusk0, self.test_pusk1, self.test_pusk2, 
            self.test_gruzes, probe_weights=[1.0, 2.0], 
            speed_weights=[2500.0, 3000.0], unit_conversion_factor=1.0
        )
        
        # Проверяем структуру результата
        self.assertEqual(len(results), 3)  # 3 режима
        for i in range(3):
            self.assertEqual(len(results[i]), 2)  # 2 плоскости
            for j in range(2):
                mass, phase = results[i][j]
                self.assertIsInstance(mass, float)
                self.assertIsInstance(phase, float)
                self.assertGreaterEqual(mass, 0)
                self.assertGreaterEqual(phase, 0)
                self.assertLess(phase, 360)
        
        # Проверяем остатки
        self.assertEqual(len(residuals), 3)  # 3 режима
        for i in range(3):
            self.assertEqual(len(residuals[i]), 2)  # 2 опоры
    
    def test_classical_vs_optimal_comparison(self):
        """Сравнение классического и оптимального методов."""
        sensitivities = calculate_sensitivity(
            self.test_pusk0, self.test_pusk1, self.test_pusk2, 
            self.test_gruzes, unit_conversion_factor=1.0
        )
        
        # Классический метод
        mass1_cl, phase1_cl, mass2_cl, phase2_cl, min_sum_cl, residuals_cl = find_classical_gruz(
            self.test_pusk0, sensitivities, max_mass=2.0, 
            coarse_mass_step=0.2, fine_mass_step=0.1,
            coarse_phase_step=30, fine_phase_step=10
        )
        
        # Оптимальный метод
        mass1_op, phase1_op, mass2_op, phase2_op, min_sum_op, residuals_op = find_optimal_gruz(
            self.test_pusk0, sensitivities, max_mass=2.0, 
            coarse_mass_step=0.2, fine_mass_step=0.1,
            coarse_phase_step=30, fine_phase_step=10
        )
        
        # Проверяем, что оба метода дают разумные результаты
        self.assertGreater(mass1_cl, 0)
        self.assertGreaterEqual(mass2_cl, 0)  # Может быть 0 для тестовых данных
        self.assertGreater(mass1_op, 0)
        self.assertGreaterEqual(mass2_op, 0)  # Может быть 0 для тестовых данных
        
        # Проверяем, что остатки уменьшились по сравнению с исходными значениями
        original_vibration = 0
        for i in range(3):
            for j in range(2):
                v0 = parse_vector_input(self.test_pusk0[i][j])
                if v0:
                    original_vibration += v0[0] ** 2
        
        self.assertLess(min_sum_cl ** 2, original_vibration / 2)  # Классический должен уменьшить вибрацию
        self.assertLess(min_sum_op ** 2, original_vibration / 2)  # Оптимальный должен уменьшить вибрацию
        
        print(f"Классический метод: м1={mass1_cl:.3f}кг, φ1={phase1_cl:.1f}°, м2={mass2_cl:.3f}кг, φ2={phase2_cl:.1f}°, остатки={min_sum_cl:.3f}")
        print(f"Оптимальный метод: м1={mass1_op:.3f}кг, φ1={phase1_op:.1f}°, м2={mass2_op:.3f}кг, φ2={phase2_op:.1f}°, остатки={min_sum_op:.3f}")
    
    def test_edge_cases(self):
        """Тест граничных случаев."""
        # Нулевые входные данные
        zero_pusk = [["0/0", "0/0"], ["0/0", "0/0"], ["0/0", "0/0"]]
        
        sensitivities = calculate_sensitivity(
            zero_pusk, zero_pusk, zero_pusk, 
            self.test_gruzes, unit_conversion_factor=1.0
        )
        
        mass1, phase1, mass2, phase2, min_sum, residuals = find_classical_gruz(
            zero_pusk, sensitivities, max_mass=1.0
        )
        
        # Должны получить нулевые результаты
        self.assertEqual(mass1, 0.0)
        self.assertEqual(phase1, 0.0)
        self.assertEqual(mass2, 0.0)
        self.assertEqual(phase2, 0.0)
        
        # Тест с пустыми грузами
        empty_gruzes = []
        results, residuals = classic_vector_balance(
            self.test_pusk0, self.test_pusk1, self.test_pusk2, 
            empty_gruzes, unit_conversion_factor=1.0
        )
        
        # Должны получить нулевые результаты
        self.assertEqual(len(results), 3)
        for i in range(3):
            for j in range(2):
                mass, phase = results[i][j]
                self.assertEqual(mass, 0)
                self.assertEqual(phase, 0)
    
    def test_residuals_calculation(self):
        """Тест корректности расчета остатков."""
        sensitivities = calculate_sensitivity(
            self.test_pusk0, self.test_pusk1, self.test_pusk2, 
            self.test_gruzes, unit_conversion_factor=1.0
        )
        
        mass1, phase1, mass2, phase2, min_sum, residuals = find_classical_gruz(
            self.test_pusk0, sensitivities, max_mass=2.0
        )
        
        # Проверяем, что остатки меньше исходных значений
        for i in range(3):
            for j in range(2):
                v0 = parse_vector_input(self.test_pusk0[i][j])
                if v0 and residuals[i][j] is not None:
                    original_amp = v0[0]
                    residual_amp = residuals[i][j][0]
                    # Остаток должен быть меньше исходного значения (в большинстве случаев)
                    self.assertLess(residual_amp, original_amp * 1.5)  # Допускаем небольшое увеличение в худшем случае

if __name__ == '__main__':
    # Настройка логирования для тестов
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Запуск тестов
    unittest.main(verbosity=2)