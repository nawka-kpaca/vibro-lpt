import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import tkinter.font as tkfont
import numpy as np
import sys
import json
import threading
import logging
from uuid import uuid4

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def polar_to_cartesian(radius, angle_deg):
    """Преобразует полярные координаты (радиус, угол в градусах) в декартовы (x, y)."""
    angle_rad = np.deg2rad(angle_deg)
    return radius * np.cos(angle_rad), radius * np.sin(angle_rad)

def cartesian_to_polar(x, y):
    """Преобразует декартовы координаты (x, y) в полярные (радиус, угол в градусах)."""
    radius = np.hypot(x, y)
    angle_deg = np.rad2deg(np.arctan2(y, x)) % 360
    return round(radius, 3), round(angle_deg, 1)

def calculate_statica_dynamica(vector1, vector2):
    """Вычисляет статическую и динамическую компоненты для двух векторов."""
    x1, y1 = polar_to_cartesian(*vector1)
    x2, y2 = polar_to_cartesian(*vector2)
    x_sum, y_sum = x1 + x2, y1 + y2
    x_diff, y_diff = x1 - x2, y1 - y2
    r_sum, a_sum = cartesian_to_polar(x_sum, y_sum)
    r_diff, a_diff = cartesian_to_polar(x_diff, y_diff)
    return (round(r_sum / 2, 3), a_sum), (round(r_diff / 2, 3), a_diff)

def parse_vector_input(text):
    """
    Парсит входную строку формата 'амплитуда/угол' в кортеж (радиус, угол).
    Возвращает None при некорректном вводе.
    """
    try:
        text = text.replace(',', '.').strip()
        if not text or text == "0/0":
            return None
        parts = text.split('/')
        if len(parts) != 2:
            raise ValueError("Ожидается формат 'амплитуда/угол'")
        radius = float(parts[0].replace(',', '.'))
        angle = float(parts[1].replace("°", "").replace(',', '.'))
        if radius < 0 or not (-360 <= angle <= 360):
            return None
        return radius, angle
    except Exception as e:
        logger.warning(f"Некорректный ввод вектора: {text}, ошибка: {e}")
        return None

def validate_entry(entry):
    """Подсвечивает поле ввода красным, если данные некорректны."""
    val = entry.get()
    entry.config(bg="#ffe6e6" if not val or not parse_vector_input(val) else "white")

def mean_angle_deg(angles):
    """Вычисляет средний угол в градусах для списка углов."""
    sin_sum = np.sum(np.sin(np.deg2rad(angles)))
    cos_sum = np.sum(np.cos(np.deg2rad(angles)))
    return (np.rad2deg(np.arctan2(sin_sum, cos_sum)) % 360)

def calculate_sensitivity(pusk0, pusk1, pusk2, gruzes, unit_conversion_factor=1.0):
    """
    Вычисляет чувствительность для двух плоскостей на основе пусковых данных.
    unit_conversion_factor: 1.0 для мм/с, 1000.0 для мкм.
    """
    n_probes = 2  # Только 1-я кр. 1 оп. и 1-я кр. 2 оп.
    n_speeds = 3
    sensitivities = {'plane1': [], 'plane2': []}
    gruz1 = gruzes[0][0] if gruzes and len(gruzes) > 0 else 0.5
    gruz2 = gruzes[1][0] if gruzes and len(gruzes) > 1 else 0.5

    # Чувствительность для плоскости 1 (Пуск 1 - Пуск 0)
    for i in range(n_speeds):
        row = []
        for j in range(n_probes):
            v0 = parse_vector_input(pusk0[i][j]) or (0, 0)
            v1 = parse_vector_input(pusk1[i][j]) or (0, 0)
            if v0[0] == 0 and v1[0] == 0:
                row.append((0, 0))
                logger.info(f"Плоскость 1, Режим {i+1}, Опора {j+1}: Пропущено (нулевые значения)")
                continue
            x0, y0 = polar_to_cartesian(*v0)
            x1, y1 = polar_to_cartesian(*v1)
            dx, dy = x1 - x0, y1 - y0
            amp, ang = cartesian_to_polar(dx, dy)
            sens_amp = (amp / unit_conversion_factor) / gruz1 if gruz1 > 0 and amp > 0 else 0
            row.append((max(sens_amp, 1e-6), ang))
            logger.info(f"Плоскость 1, Режим {i+1}, Опора {j+1}: {sens_amp:.3f}/{ang:.1f}°")
        sensitivities['plane1'].append(row)

    # Чувствительность для плоскости 2 (Пуск 2 - Пуск 1)
    for i in range(n_speeds):
        row = []
        for j in range(n_probes):
            v1 = parse_vector_input(pusk1[i][j]) or (0, 0)
            v2 = parse_vector_input(pusk2[i][j]) or (0, 0)
            if v1[0] == 0 and v2[0] == 0:
                row.append((0, 0))
                logger.info(f"Плоскость 2, Режим {i+1}, Опора {j+1}: Пропущено (нулевые значения)")
                continue
            x1, y1 = polar_to_cartesian(*v1)
            x2, y2 = polar_to_cartesian(*v2)
            dx, dy = x2 - x1, y2 - y1
            amp, ang = cartesian_to_polar(dx, dy)
            sens_amp = (amp / unit_conversion_factor) / gruz2 if gruz2 > 0 and amp > 0 else 0
            row.append((max(sens_amp, 1e-6), ang))
            logger.info(f"Плоскость 2, Режим {i+1}, Опора {j+1}: {sens_amp:.3f}/{ang:.1f}°")
        sensitivities['plane2'].append(row)

    return sensitivities

def find_optimal_gruz(pusk0, sensitivities, max_mass=3.0, coarse_mass_step=0.1, fine_mass_step=0.01, coarse_phase_step=10, fine_phase_step=1):
    """
    Находит оптимальные грузы для минимизации вибрации с двухэтапным поиском.
    """
    best_mass1, best_phase1, best_mass2, best_phase2, min_sum = None, None, None, None, float('inf')
    n_probes = 2  # Только 1-я кр. 1 оп. и 1-я кр. 2 оп.
    n_speeds = 3
    speed_weights = [1.0, 1.0, 1.0]  # Равномерные веса

    # Грубый поиск
    coarse_best = None
    for mass1 in np.arange(0, max_mass + coarse_mass_step/2, coarse_mass_step):
        for phase1 in range(0, 360, coarse_phase_step):
            for mass2 in np.arange(0, max_mass + coarse_mass_step/2, coarse_mass_step):
                for phase2 in range(0, 360, coarse_phase_step):
                    sum_sq = 0
                    valid_modes = 0
                    for i in range(n_speeds):
                        all_zero = all(parse_vector_input(pusk0[i][j])[0] == 0 for j in range(n_probes) if parse_vector_input(pusk0[i][j]))
                        if all_zero:
                            continue
                        row_sum_sq = 0
                        for j in range(n_probes):
                            v0 = parse_vector_input(pusk0[i][j]) or (0, 0)
                            if v0[0] == 0:
                                continue
                            x0, y0 = polar_to_cartesian(*v0)
                            sens1 = sensitivities['plane1'][i][j]
                            sens2 = sensitivities['plane2'][i][j]
                            x_corr = x0 - (mass1 * np.cos(np.deg2rad(phase1)) * sens1[0] +
                                          mass2 * np.cos(np.deg2rad(phase2)) * sens2[0])
                            y_corr = y0 - (mass1 * np.sin(np.deg2rad(phase1)) * sens1[0] +
                                          mass2 * np.sin(np.deg2rad(phase2)) * sens2[0])
                            amp, _ = cartesian_to_polar(x_corr, y_corr)
                            row_sum_sq += amp ** 2
                        if row_sum_sq > 0:
                            sum_sq += row_sum_sq * (speed_weights[i] / 1.0)
                            valid_modes += 1
                    if valid_modes > 0:
                        sum_sq /= valid_modes
                    if sum_sq < min_sum and sum_sq < 1e6:
                        min_sum = sum_sq
                        coarse_best = (float(mass1), float(phase1), float(mass2), float(phase2))

    # Тонкий поиск вокруг лучшей точки
    if coarse_best:
        mass1, phase1, mass2, phase2 = coarse_best
        mass_range = np.arange(max(0, mass1 - coarse_mass_step), min(max_mass, mass1 + coarse_mass_step) + fine_mass_step, fine_mass_step)
        phase_range = range(max(0, int(phase1 - coarse_phase_step)), min(360, int(phase1 + coarse_phase_step) + fine_phase_step), fine_phase_step)
        for m1 in mass_range:
            for p1 in phase_range:
                for m2 in np.arange(max(0, mass2 - coarse_mass_step), min(max_mass, mass2 + coarse_mass_step) + fine_mass_step, fine_mass_step):
                    for p2 in range(max(0, int(phase2 - coarse_phase_step)), min(360, int(phase2 + coarse_phase_step) + fine_phase_step), fine_phase_step):
                        sum_sq = 0
                        valid_modes = 0
                        for i in range(n_speeds):
                            all_zero = all(parse_vector_input(pusk0[i][j])[0] == 0 for j in range(n_probes) if parse_vector_input(pusk0[i][j]))
                            if all_zero:
                                continue
                            row_sum_sq = 0
                            for j in range(n_probes):
                                v0 = parse_vector_input(pusk0[i][j]) or (0, 0)
                                if v0[0] == 0:
                                    continue
                                x0, y0 = polar_to_cartesian(*v0)
                                sens1 = sensitivities['plane1'][i][j]
                                sens2 = sensitivities['plane2'][i][j]
                                x_corr = x0 - (m1 * np.cos(np.deg2rad(p1)) * sens1[0] +
                                              m2 * np.cos(np.deg2rad(p2)) * sens2[0])
                                y_corr = y0 - (m1 * np.sin(np.deg2rad(p1)) * sens1[0] +
                                              m2 * np.sin(np.deg2rad(p2)) * sens2[0])
                                amp, _ = cartesian_to_polar(x_corr, y_corr)
                                row_sum_sq += amp ** 2
                            if row_sum_sq > 0:
                                sum_sq += row_sum_sq * (speed_weights[i] / 1.0)
                                valid_modes += 1
                        if valid_modes > 0:
                            sum_sq /= valid_modes
                        if sum_sq < min_sum and sum_sq < 1e6:
                            min_sum = sum_sq
                            best_mass1, best_phase1, best_mass2, best_phase2 = float(m1), float(p1), float(m2), float(p2)
                            logger.info(f"Новый минимум: m1={m1:.4f}кг, p1={p1:.1f}°, m2={m2:.4f}кг, p2={p2:.1f}°, √sum_sq={np.sqrt(min_sum):.3f}")
    else:
        logger.warning("Грубый поиск не нашёл подходящего решения, возвращены нулевые грузы")
        best_mass1, best_phase1, best_mass2, best_phase2 = 0.0, 0.0, 0.0, 0.0

    # Расчет остатков
    residuals = []
    for i in range(n_speeds):
        row = []
        for j in range(n_probes):
            v0 = parse_vector_input(pusk0[i][j]) or (0, 0)
            if v0[0] == 0:
                row.append(None)
                continue
            x0, y0 = polar_to_cartesian(*v0)
            sens1 = sensitivities['plane1'][i][j]
            sens2 = sensitivities['plane2'][i][j]
            x_corr = x0 - (best_mass1 * np.cos(np.deg2rad(best_phase1)) * sens1[0] +
                          best_mass2 * np.cos(np.deg2rad(best_phase2)) * sens2[0])
            y_corr = y0 - (best_mass1 * np.sin(np.deg2rad(best_phase1)) * sens1[0] +
                          best_mass2 * np.sin(np.deg2rad(best_phase2)) * sens2[0])
            amp, ang = cartesian_to_polar(x_corr, y_corr)
            row.append((amp, ang))
        residuals.append(row)
    return best_mass1, best_phase1, best_mass2, best_phase2, np.sqrt(min_sum), residuals

def find_classical_gruz(pusk0, sensitivities, max_mass=3.0, coarse_mass_step=0.1, fine_mass_step=0.01, coarse_phase_step=10, fine_phase_step=1):
    """
    Находит оптимальные грузы для минимизации вибрации с классическим поопорным подходом.
    Сначала оптимизирует плоскость 1, затем плоскость 2.
    """
    n_probes = 2  # Только 1-я кр. 1 оп. и 1-я кр. 2 оп.
    n_speeds = 3
    speed_weights = [1.0, 1.0, 1.0]  # Равномерные веса

    # Этап 1: Оптимизация плоскости 1 (игнорируем плоскость 2)
    logger.info("Этап 1: Оптимизация плоскости 1")
    best_mass1, best_phase1, min_sum1 = 0.0, 0.0, float('inf')
    
    # Грубый поиск для плоскости 1
    coarse_best1 = None
    for mass1 in np.arange(0, max_mass + coarse_mass_step/2, coarse_mass_step):
        for phase1 in range(0, 360, coarse_phase_step):
            sum_sq = 0
            valid_modes = 0
            for i in range(n_speeds):
                all_zero = all(parse_vector_input(pusk0[i][j])[0] == 0 for j in range(n_probes) if parse_vector_input(pusk0[i][j]))
                if all_zero:
                    continue
                row_sum_sq = 0
                for j in range(n_probes):
                    v0 = parse_vector_input(pusk0[i][j]) or (0, 0)
                    if v0[0] == 0:
                        continue
                    x0, y0 = polar_to_cartesian(*v0)
                    sens1 = sensitivities['plane1'][i][j]
                    # Коррекция только плоскости 1
                    x_corr = x0 - (mass1 * np.cos(np.deg2rad(phase1)) * sens1[0])
                    y_corr = y0 - (mass1 * np.sin(np.deg2rad(phase1)) * sens1[0])
                    amp, _ = cartesian_to_polar(x_corr, y_corr)
                    row_sum_sq += amp ** 2
                if row_sum_sq > 0:
                    sum_sq += row_sum_sq * (speed_weights[i] / 1.0)
                    valid_modes += 1
            if valid_modes > 0:
                sum_sq /= valid_modes
            if sum_sq < min_sum1 and sum_sq < 1e6:
                min_sum1 = sum_sq
                coarse_best1 = (float(mass1), float(phase1))

    # Тонкий поиск для плоскости 1
    if coarse_best1:
        mass1, phase1 = coarse_best1
        mass_range = np.arange(max(0, mass1 - coarse_mass_step), min(max_mass, mass1 + coarse_mass_step) + fine_mass_step, fine_mass_step)
        phase_range = range(max(0, int(phase1 - coarse_phase_step)), min(360, int(phase1 + coarse_phase_step) + fine_phase_step), fine_phase_step)
        for m1 in mass_range:
            for p1 in phase_range:
                sum_sq = 0
                valid_modes = 0
                for i in range(n_speeds):
                    all_zero = all(parse_vector_input(pusk0[i][j])[0] == 0 for j in range(n_probes) if parse_vector_input(pusk0[i][j]))
                    if all_zero:
                        continue
                    row_sum_sq = 0
                    for j in range(n_probes):
                        v0 = parse_vector_input(pusk0[i][j]) or (0, 0)
                        if v0[0] == 0:
                            continue
                        x0, y0 = polar_to_cartesian(*v0)
                        sens1 = sensitivities['plane1'][i][j]
                        # Коррекция только плоскости 1
                        x_corr = x0 - (m1 * np.cos(np.deg2rad(p1)) * sens1[0])
                        y_corr = y0 - (m1 * np.sin(np.deg2rad(p1)) * sens1[0])
                        amp, _ = cartesian_to_polar(x_corr, y_corr)
                        row_sum_sq += amp ** 2
                    if row_sum_sq > 0:
                        sum_sq += row_sum_sq * (speed_weights[i] / 1.0)
                        valid_modes += 1
                if valid_modes > 0:
                    sum_sq /= valid_modes
                if sum_sq < min_sum1 and sum_sq < 1e6:
                    min_sum1 = sum_sq
                    best_mass1, best_phase1 = float(m1), float(p1)
                    logger.info(f"Плоскость 1 - новый минимум: m1={m1:.4f}кг, p1={p1:.1f}°, √sum_sq={np.sqrt(min_sum1):.3f}")

    logger.info(f"Оптимальная плоскость 1: масса={best_mass1:.4f}кг, фаза={best_phase1:.1f}°")

    # Этап 2: Оптимизация плоскости 2 (учитываем уже найденную плоскость 1)
    logger.info("Этап 2: Оптимизация плоскости 2")
    best_mass2, best_phase2, min_sum2 = 0.0, 0.0, float('inf')
    
    # Грубый поиск для плоскости 2
    coarse_best2 = None
    for mass2 in np.arange(0, max_mass + coarse_mass_step/2, coarse_mass_step):
        for phase2 in range(0, 360, coarse_phase_step):
            sum_sq = 0
            valid_modes = 0
            for i in range(n_speeds):
                all_zero = all(parse_vector_input(pusk0[i][j])[0] == 0 for j in range(n_probes) if parse_vector_input(pusk0[i][j]))
                if all_zero:
                    continue
                row_sum_sq = 0
                for j in range(n_probes):
                    v0 = parse_vector_input(pusk0[i][j]) or (0, 0)
                    if v0[0] == 0:
                        continue
                    x0, y0 = polar_to_cartesian(*v0)
                    sens1 = sensitivities['plane1'][i][j]
                    sens2 = sensitivities['plane2'][i][j]
                    # Коррекция обеих плоскостей (плоскость 1 зафиксирована)
                    x_corr = x0 - (best_mass1 * np.cos(np.deg2rad(best_phase1)) * sens1[0] +
                                  mass2 * np.cos(np.deg2rad(phase2)) * sens2[0])
                    y_corr = y0 - (best_mass1 * np.sin(np.deg2rad(best_phase1)) * sens1[0] +
                                  mass2 * np.sin(np.deg2rad(phase2)) * sens2[0])
                    amp, _ = cartesian_to_polar(x_corr, y_corr)
                    row_sum_sq += amp ** 2
                if row_sum_sq > 0:
                    sum_sq += row_sum_sq * (speed_weights[i] / 1.0)
                    valid_modes += 1
            if valid_modes > 0:
                sum_sq /= valid_modes
            if sum_sq < min_sum2 and sum_sq < 1e6:
                min_sum2 = sum_sq
                coarse_best2 = (float(mass2), float(phase2))

    # Тонкий поиск для плоскости 2
    if coarse_best2:
        mass2, phase2 = coarse_best2
        mass_range = np.arange(max(0, mass2 - coarse_mass_step), min(max_mass, mass2 + coarse_mass_step) + fine_mass_step, fine_mass_step)
        phase_range = range(max(0, int(phase2 - coarse_phase_step)), min(360, int(phase2 + coarse_phase_step) + fine_phase_step), fine_phase_step)
        for m2 in mass_range:
            for p2 in phase_range:
                sum_sq = 0
                valid_modes = 0
                for i in range(n_speeds):
                    all_zero = all(parse_vector_input(pusk0[i][j])[0] == 0 for j in range(n_probes) if parse_vector_input(pusk0[i][j]))
                    if all_zero:
                        continue
                    row_sum_sq = 0
                    for j in range(n_probes):
                        v0 = parse_vector_input(pusk0[i][j]) or (0, 0)
                        if v0[0] == 0:
                            continue
                        x0, y0 = polar_to_cartesian(*v0)
                        sens1 = sensitivities['plane1'][i][j]
                        sens2 = sensitivities['plane2'][i][j]
                        # Коррекция обеих плоскостей (плоскость 1 зафиксирована)
                        x_corr = x0 - (best_mass1 * np.cos(np.deg2rad(best_phase1)) * sens1[0] +
                                      m2 * np.cos(np.deg2rad(p2)) * sens2[0])
                        y_corr = y0 - (best_mass1 * np.sin(np.deg2rad(best_phase1)) * sens1[0] +
                                      m2 * np.sin(np.deg2rad(p2)) * sens2[0])
                        amp, _ = cartesian_to_polar(x_corr, y_corr)
                        row_sum_sq += amp ** 2
                    if row_sum_sq > 0:
                        sum_sq += row_sum_sq * (speed_weights[i] / 1.0)
                        valid_modes += 1
                if valid_modes > 0:
                    sum_sq /= valid_modes
                if sum_sq < min_sum2 and sum_sq < 1e6:
                    min_sum2 = sum_sq
                    best_mass2, best_phase2 = float(m2), float(p2)
                    logger.info(f"Плоскость 2 - новый минимум: m2={m2:.4f}кг, p2={p2:.1f}°, √sum_sq={np.sqrt(min_sum2):.3f}")

    logger.info(f"Оптимальная плоскость 2: масса={best_mass2:.4f}кг, фаза={best_phase2:.1f}°")

    # Расчет итоговых остатков с обеими плоскостями
    residuals = []
    final_sum_sq = 0
    valid_modes = 0
    for i in range(n_speeds):
        row = []
        row_sum_sq = 0
        for j in range(n_probes):
            v0 = parse_vector_input(pusk0[i][j]) or (0, 0)
            if v0[0] == 0:
                row.append(None)
                continue
            x0, y0 = polar_to_cartesian(*v0)
            sens1 = sensitivities['plane1'][i][j]
            sens2 = sensitivities['plane2'][i][j]
            x_corr = x0 - (best_mass1 * np.cos(np.deg2rad(best_phase1)) * sens1[0] +
                          best_mass2 * np.cos(np.deg2rad(best_phase2)) * sens2[0])
            y_corr = y0 - (best_mass1 * np.sin(np.deg2rad(best_phase1)) * sens1[0] +
                          best_mass2 * np.sin(np.deg2rad(best_phase2)) * sens2[0])
            amp, ang = cartesian_to_polar(x_corr, y_corr)
            row.append((amp, ang))
            row_sum_sq += amp ** 2
        residuals.append(row)
        if row_sum_sq > 0:
            final_sum_sq += row_sum_sq * (speed_weights[i] / 1.0)
            valid_modes += 1
    
    if valid_modes > 0:
        final_sum_sq /= valid_modes
    
    logger.info(f"Классический расчет завершен. Итоговый √sum_sq={np.sqrt(final_sum_sq):.3f}")
    
    return best_mass1, best_phase1, best_mass2, best_phase2, np.sqrt(final_sum_sq), residuals

def classic_vector_balance(pusk0, pusk1, pusk2, gruzes, probe_weights=[1.0, 2.0], speed_weights=[2500.0, 3000.0], unit_conversion_factor=1.0):
    """Классический метод балансировки с расчётом корректирующих грузов по новому алгоритму."""
    if len(gruzes) < 2:
        logger.warning("Недостаточно грузов для расчёта классической балансировки")
        return [[(0, 0), (0, 0)] for _ in range(3)], []

    logger.info("Начинаем классический расчет балансировки")
    
    # Вычисляем чувствительности
    sensitivities = calculate_sensitivity(pusk0, pusk1, pusk2, gruzes, unit_conversion_factor)
    
    # Используем новый классический метод поопорной оптимизации
    best_mass1, best_phase1, best_mass2, best_phase2, min_sum, residuals = find_classical_gruz(
        pusk0, sensitivities, max_mass=3.0
    )
    
    # Формируем результат в том же формате, что и раньше
    result = []
    for i in range(3):  # 3 режима
        result.append([(best_mass1, best_phase1), (best_mass2, best_phase2)])
    
    logger.info(f"Классический расчет завершен: м1={best_mass1:.4f}кг, φ1={best_phase1:.1f}°, м2={best_mass2:.4f}кг, φ2={best_phase2:.1f}°")
    
    return result, residuals

def calc_residuals_after_balance(pusk0, reco_masses, reco_phis):
    """Вычисляет остатки вибрации после применения корректирующих грузов."""
    result = []
    n_probes = 2
    for i in range(3):
        row = []
        for j in range(n_probes):
            v0 = parse_vector_input(pusk0[i][j])
            if not v0:
                row.append(("—", "—"))
                continue
            x0, y0 = polar_to_cartesian(*v0)
            mass, phase = reco_masses[j], reco_phis[j]
            xg, yg = polar_to_cartesian(mass, phase)
            x_res = x0 + xg
            y_res = y0 + yg
            amp, ang = cartesian_to_polar(x_res, y_res)
            row.append((f"{amp:.3f}", f"{ang:.1f}°"))
        result.append(row)
    return result

class BalancingApp:
    def __init__(self, root):
        """Инициализирует приложение для балансировки вибраций."""
        self.root = root
        self.root.title("Балансировка вибрации (Классика, схемы)")
        self.root.geometry("1240x880")
        self.tabs = {}
        self.tab_count = 0
        self.result_frame = None
        self.unit_conversion_factor = tk.DoubleVar(value=1.0)
        self.create_menu()
        self.create_control_panel()
        self.create_notebook()
        self.create_new_tab(initial=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.on_tab_changed()

    def create_menu(self):
        """Создаёт меню приложения."""
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Сохранить проект...", command=self.save_project)
        filemenu.add_command(label="Открыть проект...", command=self.load_project)
        filemenu.add_separator()
        filemenu.add_command(label="Выход", command=self.root.quit)
        menubar.add_cascade(label="Файл", menu=filemenu)
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="О программе", command=self.show_about)
        menubar.add_cascade(label="Справка", menu=helpmenu)
        self.root.config(menu=menubar)

    def save_project(self):
        """Сохраняет проект в JSON-файл."""
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if not path:
            return
        data = {}
        for tab_name, tab_info in self.tabs.items():
            ent_data = [[entry[0].get(), entry[1].get()] for entry in tab_info['frame'].entries]
            gruzes = [entry.get() for gruz_frame, entry, _ in tab_info['frame'].gruzes] if tab_name != "Пуск 0" else []
            data[tab_name] = {
                'entries': ent_data,
                'gruzes': gruzes,
                'protected': tab_info.get('protected', False),
                'scheme': tab_info['frame'].scheme_var.get()
            }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Сохранено", f"Проект сохранён в {path}")
        except Exception as e:
            logger.error(f"Ошибка сохранения проекта: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить проект: {e}")

    def load_project(self):
        """Загружает проект из JSON-файла."""
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            while self.notebook.tabs():
                self.notebook.forget(0)
            self.tabs = {}
            self.tab_count = 0
            for tab_name, tab_info in data.items():
                scheme = tab_info.get('scheme', "Единичная")
                frame = tk.Frame(self.notebook, padx=10, pady=10)
                frame.entries = []
                frame.gruzes = []
                frame.gruz_container = tk.Frame(frame)
                frame.gruz_container.grid(row=5, column=0, columnspan=10, pady=(10, 0), sticky='we')
                frame.scheme_var = tk.StringVar(value=scheme)
                frame.scheme_label = tk.Label(frame, text=f"Система грузов: {scheme}", font=('Arial', 10, 'italic'), fg="blue")
                if tab_name != "Пуск 0":
                    frame.scheme_label.grid(row=0, column=8, padx=4, sticky='e')
                frame.residuals_block = None
                self.create_tab_content(frame, tab_name)
                if tab_name != "Пуск 0":
                    for gruz_val in tab_info['gruzes']:
                        self.add_gruz(frame)
                        frame.gruzes[-1][1].insert(0, gruz_val)
                for i, (e1_val, e2_val) in enumerate(tab_info['entries']):
                    e1, e2, *_ = frame.entries[i]
                    e1.insert(0, e1_val)
                    e2.insert(0, e2_val)
                self.tabs[tab_name] = {
                    'frame': frame,
                    'protected': tab_info.get('protected', False),
                    'scheme_var': frame.scheme_var
                }
                self.notebook.add(frame, text=tab_name if tab_info.get('protected', False) else tab_name + " ✕")
                if not tab_info.get('protected', False):
                    try:
                        idx = int(tab_name.split()[-1])
                        self.tab_count = max(self.tab_count, idx)
                    except:
                        pass
            self.update_tab_choices()
            self.update_all_tabs()
            self.on_tab_changed()
            messagebox.showinfo("Загружено", f"Проект '{path}' успешно открыт")
        except Exception as e:
            logger.error(f"Ошибка загрузки проекта: {e}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить проект: {e}")

    def create_control_panel(self):
        """Создаёт панель управления приложения."""
        self.control_panel = tk.Frame(self.root, bg='#f0f0f0', padx=5, pady=5)
        panel = self.control_panel
        panel.pack(fill='x', pady=(0, 5))
        btn_frame = tk.Frame(panel, bg='#f0f0f0')
        btn_frame.pack(side='left')
        tk.Button(btn_frame, text="➕ Новый Пуск", command=self.create_new_tab,
                  bg='#4CAF50', fg='white').pack(side='left', padx=2)
        tk.Button(btn_frame, text="✖ Удалить Вкладку", command=self.delete_selected_tab,
                  bg='#f44336', fg='white').pack(side='left', padx=2)
        self.scheme_calc_frame = tk.Frame(panel, bg='#f0f0f0')
        self.scheme_calc_frame.pack(side='left', padx=12)
        calc_frame = tk.Frame(self.scheme_calc_frame, bg='#f0f0f0')
        calc_frame.pack(side='left', padx=10)
        tk.Label(calc_frame, text="Расчёт между:", bg='#f0f0f0').pack(side='left')
        self.combo_from = ttk.Combobox(calc_frame, width=16, state='readonly')
        self.combo_to = ttk.Combobox(calc_frame, width=16, state='readonly')
        self.combo_from.pack(side='left', padx=2)
        self.combo_to.pack(side='left', padx=2)
        tk.Button(calc_frame, text="🔧 Классический расчёт", command=self.compute_classic_balance,
                  bg='#2196F3', fg='white').pack(side='left', padx=10)
        tk.Button(panel, text="Оптимальный (графика/подбор)", command=self.start_optimal_gruz,
                  bg='#673ab7', fg='white').pack(side='left', padx=10)
        unit_frame = tk.Frame(panel, bg='#f0f0f0')
        unit_frame.pack(side='left', padx=10)
        tk.Label(unit_frame, text="Единицы:", bg='#f0f0f0').pack(side='left')
        tk.Radiobutton(unit_frame, text="мм/с", variable=self.unit_conversion_factor, value=1.0,
                       bg='#f0f0f0', command=self.update_unit).pack(side='left')
        tk.Radiobutton(unit_frame, text="мкм", variable=self.unit_conversion_factor, value=1000.0,
                       bg='#f0f0f0', command=self.update_unit).pack(side='left')

    def update_unit(self):
        """Обновляет интерфейс при смене единиц измерения."""
        self.update_all_tabs()
        if self.result_frame:
            self.compute_classic_balance()

    def start_optimal_gruz(self):
        """Запускает расчёт оптимального груза в отдельном потоке."""
        names = list(self.tabs.keys())
        if len(names) < 3 or not self.combo_from.get():
            messagebox.showwarning("Ошибка", "Нужно минимум 3 пуска для расчёта оптимального груза.")
            return
        tab0 = self.tabs[names[0]]
        tab1 = self.tabs[names[1]]
        tab2 = self.tabs[names[2]]
        pusk0 = [[e[0].get(), e[1].get()] for e in tab0['frame'].entries]
        pusk1 = [[e[0].get(), e[1].get()] for e in tab1['frame'].entries]
        pusk2 = [[e[0].get(), e[1].get()] for e in tab2['frame'].entries]
        gruzes = []
        for gruz_frame, entry, _ in tab1['frame'].gruzes:
            gruzes.append(parse_vector_input(entry.get()) or (0, 0))
        for gruz_frame, entry, _ in tab2['frame'].gruzes:
            gruzes.append(parse_vector_input(entry.get()) or (0, 0))
        self.root.config(cursor="wait")
        threading.Thread(target=self.compute_optimal_gruz_thread, args=(pusk0, pusk1, pusk2, gruzes), daemon=True).start()

    def compute_optimal_gruz_thread(self, pusk0, pusk1, pusk2, gruzes):
        """Выполняет расчёт оптимального груза в отдельном потоке."""
        try:
            sensitivities = calculate_sensitivity(pusk0, pusk1, pusk2, gruzes, self.unit_conversion_factor.get())
            m1, p1, m2, p2, min_sum, residuals = find_optimal_gruz(pusk0, sensitivities, max_mass=3.0)
            self.root.after(0, lambda m1=m1, p1=p1, m2=m2, p2=p2, min_sum=min_sum, residuals=residuals, pusk0=pusk0:
                            self.display_optimal_result(m1, p1, m2, p2, min_sum, residuals, pusk0))
        except Exception as e:
            logger.error(f"Ошибка в расчёте оптимального груза: {e}")
            self.root.after(0, lambda e=e: messagebox.showerror("Ошибка", f"Ошибка в расчёте оптимального груза: {e}"))
        finally:
            self.root.after(0, lambda: self.root.config(cursor=""))

    def display_optimal_result(self, m1, p1, m2, p2, min_sum, residuals, pusk0):
        """Отображает результаты оптимального подбора грузов."""
        if m1 is None or min_sum > 1e6:
            messagebox.showinfo("Подбор груза", "Оптимальный груз не найден или результат аномален.")
            return
        unit = "мм/с" if self.unit_conversion_factor.get() == 1.0 else "мкм"
        text = f"Оптимальные грузы для плоскостей:\nПлоскость 1: Масса: {m1:.4f} кг, Фаза: {p1:.1f}°\nПлоскость 2: Масса: {m2:.4f} кг, Фаза: {p2:.1f}°\n√(сумма квадратов остатков): {min_sum:.3f} {unit}\n"
        text += "Остатки вибрации по режимам/опорам (1-я кр. 1 оп., 1-я кр. 2 оп.):\n"
        for i, row in enumerate(residuals):
            line = f"Режим {i+1} (1 критика, 2 критика, Раб. обороты): "
            for j, val in enumerate(row[:2]):
                if val is not None:
                    amp, ang = val
                    line += f"Оп.{j+1}: {amp:.3f} / {ang:.1f}°; "
            text += line.strip() + "\n"
        messagebox.showinfo("Графический подбор", text)

    def compute_classic_balance(self):
        """Выполняет классический расчёт балансировки."""
        name1 = self.combo_from.get()
        name2 = self.combo_to.get()
        if not name1 or not name2 or name1 == name2:
            messagebox.showwarning("Ошибка", "Выберите два разных пуска.")
            return
        if self.result_frame:
            self.result_frame.destroy()
        self.result_frame = tk.Frame(self.root)
        self.result_frame.pack(fill='x', padx=10, pady=10)
        tab1 = self.tabs[name1]
        tab2 = self.tabs[name2]
        scheme = tab2['frame'].scheme_var.get()
        gruzes = []
        for gruz_frame, entry, _ in tab2['frame'].gruzes:
            mass_angle = entry.get()
            if "/" in mass_angle:
                m, phi = mass_angle.replace(",", ".").split("/")
            else:
                m, phi = mass_angle.replace(",", "."), "0"
            try:
                gruzes.append((float(m), float(phi)))
            except Exception:
                logger.warning(f"Некорректный ввод груза: {mass_angle}")
                continue
        if len(gruzes) < 2:
            messagebox.showwarning("Ошибка", "Не введены пробные грузы для двух плоскостей.")
            return
        def get_pusk(tab):
            return [[entry[0].get(), entry[1].get()] for entry in tab['frame'].entries]
        pusk0 = get_pusk(tab1)
        pusk1 = get_pusk(tab2)
        pusk2 = None
        for name in self.tabs:
            if name not in [name1, name2] and 'frame' in self.tabs[name] and hasattr(self.tabs[name]['frame'], 'entries'):
                pusk2 = get_pusk(self.tabs[name])
                break
        
        # Используем новый классический метод
        results, residuals = classic_vector_balance(pusk0, pusk1, pusk2, gruzes, 
                                                   probe_weights=[1.0, 2.0], 
                                                   speed_weights=[2500.0, 3000.0], 
                                                   unit_conversion_factor=self.unit_conversion_factor.get())
        
        n_plo = len(results[0])
        ms = [[] for _ in range(n_plo)]
        phis = [[] for _ in range(n_plo)]
        for res in results:
            for p in range(n_plo):
                ms[p].append(res[p][0])
                phis[p].append(res[p][1])
        ms_avg = [np.mean(m) for m in ms]
        phis_avg = [mean_angle_deg(phi) for phi in phis]
        
        dkv_frame = tk.LabelFrame(self.result_frame, text=f"Классический расчёт ({scheme})", padx=10, pady=10)
        dkv_frame.pack(fill='x', pady=5, side='top', anchor='n')
        tk.Label(dkv_frame, text="Режим", font=('Arial',10,'bold'), width=12).grid(row=0,column=0)
        for p in range(n_plo):
            tk.Label(dkv_frame, text=f"М оп.{p+1}, кг", font=('Arial',10,'bold'), width=12).grid(row=0,column=1+2*p)
            tk.Label(dkv_frame, text=f"φ оп.{p+1}", font=('Arial',10,'bold'), width=12).grid(row=0,column=2+2*p)
        for i, res in enumerate(results):
            tk.Label(dkv_frame, text=f"{i+1} (1 критика, 2 критика, Раб. обороты)").grid(row=i+1,column=0)
            for p in range(n_plo):
                m, phi = res[p]
                tk.Label(dkv_frame, text=f"{m:.4f}").grid(row=i+1,column=1+2*p)
                tk.Label(dkv_frame, text=f"{phi:.1f}°").grid(row=i+1,column=2+2*p)
        tk.Label(dkv_frame, text="Среднее", font=('Arial',10,'bold')).grid(row=1+len(results),column=0)
        for p in range(n_plo):
            tk.Label(dkv_frame, text=f"{ms_avg[p]:.4f}", font=('Arial',10,'bold')).grid(row=1+len(results),column=1+2*p)
            tk.Label(dkv_frame, text=f"{phis_avg[p]:.1f}°", font=('Arial',10,'bold')).grid(row=1+len(results),column=2+2*p)
        
        # Отображаем остатки из классического расчета
        resid_frame = tk.LabelFrame(self.result_frame, text="Остатки вибрации после коррекции", padx=10, pady=10)
        resid_frame.pack(fill='x', pady=5, side='top', anchor='n')
        n_probes = 2
        tk.Label(resid_frame, text="Режим", font=('Arial',10,'bold'), width=12).grid(row=0,column=0)
        for p in range(n_probes):
            tk.Label(resid_frame, text=f"Оп.{p+1}", font=('Arial',10,'bold'), width=12).grid(row=0,column=1+p)
        
        unit = "мм/с" if self.unit_conversion_factor.get() == 1.0 else "мкм"
        for i, row in enumerate(residuals):
            tk.Label(resid_frame, text=f"{i+1} (1 критика, 2 критика, Раб. обороты)").grid(row=i+1,column=0)
            for p, val in enumerate(row[:n_probes]):
                if val is not None:
                    amp, ang = val
                    text = f"{amp:.3f} / {ang:.1f}°"
                else:
                    text = "— / —"
                tk.Label(resid_frame, text=text).grid(row=i+1,column=1+p)
        
        btn = tk.Button(self.result_frame, text="Показать таблицу ДКВ",
                        command=lambda: self.show_dkv_table(pusk0, pusk1, name1, name2),
                        bg="#fbc02d", fg="black")
        btn.pack(side='top', pady=6)
        explain_label = tk.Label(self.result_frame, text=f"Расчёт выполнен между пусками: {name1} и {name2}. Использован классический поопорный метод.", fg="gray", font=('Arial', 10, 'italic'))
        explain_label.pack(side='top', pady=4)

    def show_dkv_table(self, pusk_a, pusk_b, name_a, name_b):
        """Отображает таблицу векторной разницы между пусками."""
        dkv_win = tk.Toplevel(self.root)
        dkv_win.title(f"Векторная разница Δ = {name_b} – {name_a}")
        tk.Label(dkv_win, text="Режим", font=('Arial',10,'bold'), width=9).grid(row=0,column=0)
        tk.Label(dkv_win, text="Оп.1 (A/φ)", font=('Arial',10,'bold'), width=12).grid(row=0,column=1)
        tk.Label(dkv_win, text="Оп.2 (A/φ)", font=('Arial',10,'bold'), width=12).grid(row=0,column=2)
        for i in range(3):
            tk.Label(dkv_win, text=f"{i+1} (1 критика, 2 критика, Раб. обороты)", font=('Arial',10), width=9).grid(row=i+1,column=0)
            for j in range(2):
                v1 = parse_vector_input(pusk_a[i][j])
                v2 = parse_vector_input(pusk_b[i][j])
                if v1 and v2:
                    x1, y1 = polar_to_cartesian(*v1)
                    x2, y2 = polar_to_cartesian(*v2)
                    dx, dy = x2 - x1, y2 - y1
                    amp, ang = cartesian_to_polar(dx, dy)
                    text = f"{amp:.3f} / {ang:.1f}°"
                else:
                    text = "—"
                tk.Label(dkv_win, text=text, font=('Arial',10), width=12).grid(row=i+1,column=1+j)
        tk.Label(dkv_win, text=f"Δ = {name_b} – {name_a}", font=('Arial',9,'italic')).grid(row=4,column=0,columnspan=3)

    def create_new_tab(self, initial=False):
        """Создаёт новую вкладку для пусковых данных."""
        tab_name = "Пуск 0" if initial else f"Пуск {self.tab_count + 1}"
        frame = tk.Frame(self.notebook, padx=10, pady=10)
        frame.entries = []
        frame.gruzes = []
        frame.gruz_container = tk.Frame(frame)
        frame.gruz_container.grid(row=5, column=0, columnspan=10, pady=(10, 0), sticky='we')
        frame.scheme_var = tk.StringVar(value="Единичная")
        frame.scheme_label = tk.Label(frame, text="Система грузов: Единичная", font=('Arial', 10, 'italic'), fg="blue")
        if tab_name != "Пуск 0":
            frame.scheme_label.grid(row=0, column=8, padx=4, sticky='e')
        frame.residuals_block = None
        self.create_tab_content(frame, tab_name)
        self.tabs[tab_name] = {
            'frame': frame,
            'protected': initial,
            'scheme_var': frame.scheme_var,
        }
        if tab_name != "Пуск 0":
            self.update_gruz_fields_for_scheme(frame)
        self.notebook.add(frame, text=tab_name if initial else tab_name + " ✕")
        self.update_tab_choices()
        self.notebook.select(frame)
        self.on_tab_changed()
        if not initial:
            self.tab_count += 1

    def create_tab_content(self, frame, tab_name):
        """Создаёт содержимое вкладки с полями ввода."""
        headers = ["Режим", "Опора 1", "Опора 2", "Статика", "Динамика"]
        colors = ['#daeaf6', '#e3f6da', '#e3f6da', '#f9f9c5', '#f9f9c5']
        for i, text in enumerate(headers):
            tk.Label(frame, text=text, font=('Arial', 10, 'bold'), bg=colors[i], relief='groove', width=14).grid(row=0, column=i, sticky='nsew', pady=(0, 5), padx=1)
        modes = ["1 критика", "2 критика", "Раб. обороты"]
        for i, mode in enumerate(modes, 1):
            tk.Label(frame, text=mode, bg='#daeaf6').grid(row=i, column=0, sticky='nsew', padx=1)
            e1 = tk.Entry(frame, width=12, font=('Arial', 10))
            e2 = tk.Entry(frame, width=12, font=('Arial', 10))
            e1.grid(row=i, column=1, padx=1)
            e2.grid(row=i, column=2, padx=1)
            stat_label = tk.Label(frame, text="—", width=13, bg='#f9f9c5')
            dyn_label = tk.Label(frame, text="—", width=13, bg='#f9f9c5')
            stat_label.grid(row=i, column=3, padx=1)
            dyn_label.grid(row=i, column=4, padx=1)
            frame.entries.append((e1, e2, stat_label, dyn_label))
            e1.bind("<KeyRelease>", lambda e, entry=e1: [self.update_all_tabs(), validate_entry(entry)])
            e2.bind("<KeyRelease>", lambda e, entry=e2: [self.update_all_tabs(), validate_entry(entry)])
            e1.bind("<FocusOut>", lambda e, entry=e1: validate_entry(entry))
            e2.bind("<FocusOut>", lambda e, entry=e2: validate_entry(entry))
        if tab_name != "Пуск 0":
            add_btn = tk.Button(frame, text="➕ Добавить груз", command=lambda: self.add_gruz(frame),
                                bg='#4CAF50', fg='white')
            add_btn.grid(row=4, column=0, columnspan=10, pady=5)

    def update_gruz_fields_for_scheme(self, frame):
        """Пустой метод для возможного расширения (сохранён для совместимости)."""
        pass

    def auto_detect_scheme(self, frame):
        """Автоматически определяет схему грузов на основе введённых углов."""
        angles = []
        for gruz_frame, entry, _ in frame.gruzes:
            val = entry.get().replace(",", ".")
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
        frame.scheme_var.set(scheme)
        if hasattr(frame, 'scheme_label'):
            frame.scheme_label.config(text=f"Система грузов: {scheme}")

    def add_gruz(self, parent_frame):
        """Добавляет поле для ввода груза."""
        gruz_frame = tk.Frame(parent_frame.gruz_container)
        gruz_frame.pack(fill='x', pady=2)
        input_entry = tk.Entry(gruz_frame, width=18, font=('Arial', 10))
        input_entry.pack(side='left', padx=2)
        del_btn = tk.Button(gruz_frame, text="✕", command=lambda gf=gruz_frame: self.remove_gruz(parent_frame, gf),
                            bg='#f44336', fg='white', width=3)
        del_btn.pack(side='left')
        input_entry.bind("<KeyRelease>", lambda e, f=parent_frame: self.on_gruz_entry_change(f))
        input_entry.bind("<FocusOut>", lambda e, f=parent_frame: self.on_gruz_entry_change(f))
        parent_frame.gruzes.append((gruz_frame, input_entry, del_btn))
        self.on_gruz_entry_change(parent_frame)

    def remove_gruz(self, parent_frame, gruz_frame):
        """Удаляет поле груза."""
        for idx, (gf, _, _) in enumerate(parent_frame.gruzes):
            if gf == gruz_frame:
                gf.destroy()
                parent_frame.gruzes.pop(idx)
                break
        self.on_gruz_entry_change(parent_frame)

    def on_gruz_entry_change(self, frame):
        """Обновляет схему грузов при изменении полей ввода."""
        self.auto_detect_scheme(frame)

    def on_tab_click(self, event):
        """Обрабатывает клик по вкладке для закрытия (если есть ✕)."""
        x, y = event.x, event.y
        try:
            index = self.notebook.index(f"@{x},{y}")
            tab_text = self.notebook.tab(index, "text")
            if not tab_text.endswith("✕"):
                return
            tab_name = tab_text[:-2].rstrip()
            if tab_name in self.tabs and self.tabs[tab_name].get('protected', False):
                return
            bbox = self.notebook.bbox(index)
            if not bbox:
                return
            font = tkfont.nametofont("TkDefaultFont")
            label_width = font.measure(tab_name)
            close_button_width = font.measure("✕") + 6
            tab_x, tab_y, tab_width, tab_height = bbox
            close_start = tab_x + label_width + 4
            close_end = close_start + close_button_width
            if close_start <= x <= close_end and tab_y <= y <= tab_y + tab_height:
                self.notebook.forget(index)
                if tab_name in self.tabs:
                    del self.tabs[tab_name]
                self.update_tab_choices()
        except tk.TclError:
            logger.warning("Ошибка обработки клика по вкладке")
            pass

    def delete_selected_tab(self):
        """Удаляет выбранную вкладку, кроме 'Пуск 0'."""
        current = self.notebook.select()
        if not current:
            return
        index = self.notebook.index(current)
        tab_text = self.notebook.tab(index, "text")
        if tab_text == "Пуск 0":
            messagebox.showinfo("Информация", "Вкладка 'Пуск 0' не может быть удалена")
            return
        tab_name = tab_text.replace(" ✕", "") if "✕" in tab_text else tab_text
        self.notebook.forget(index)
        if tab_name in self.tabs:
            del self.tabs[tab_name]
        self.update_tab_choices()

    def on_tab_right_click(self, event):
        """Обрабатывает правый клик по вкладке для контекстного меню."""
        try:
            index = self.notebook.index(f"@{event.x},{event.y}")
            tab_text = self.notebook.tab(index, "text")
            if tab_text == "Пуск 0":
                return
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Переименовать", command=lambda: self.rename_tab(index))
            menu.add_command(label="Закрыть", command=lambda: self.close_tab_by_index(index))
            menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            logger.warning("Ошибка обработки правого клика по вкладке")
            pass

    def rename_tab(self, index):
        """Переименовывает вкладку."""
        current_name = self.notebook.tab(index, "text").replace(" ✕", "")
        new_name = simpledialog.askstring("Переименовать", "Введите новое имя:",
                                         initialvalue=current_name)
        if new_name and new_name != current_name:
            if new_name in self.tabs:
                messagebox.showerror("Ошибка", "Вкладка с таким именем уже существует")
                return
            self.tabs[new_name] = self.tabs.pop(current_name)
            self.notebook.tab(index, text=new_name + " ✕")
            self.update_tab_choices()

    def close_tab_by_index(self, index):
        """Закрывает вкладку по индексу."""
        tab_text = self.notebook.tab(index, "text")
        if tab_text == "Пуск 0":
            return
        tab_name = tab_text.replace(" ✕", "")
        self.notebook.forget(index)
        if tab_name in self.tabs:
            del self.tabs[tab_name]
        self.update_tab_choices()

    def update_tab_choices(self):
        """Обновляет списки выбора вкладок в выпадающих меню."""
        names = list(self.tabs.keys())
        self.combo_from['values'] = names
        self.combo_to['values'] = names
        if len(names) >= 2:
            self.combo_from.current(0)
            self.combo_to.current(1)

    def update_all_tabs(self):
        """Обновляет содержимое всех вкладок (статические и динамические значения)."""
        for tab_name, tab in self.tabs.items():
            for i, entry in enumerate(tab['frame'].entries):
                e1, e2, stat_label, dyn_label = entry
                v1 = parse_vector_input(e1.get())
                v2 = parse_vector_input(e2.get())
                if v1 and v2:
                    statica, dynamica = calculate_statica_dynamica(v1, v2)
                    stat_label.config(text=f"{statica[0]} / {statica[1]}°")
                    dyn_label.config(text=f"{dynamica[0]} / {dynamica[1]}°")
                else:
                    stat_label.config(text="—")
                    dyn_label.config(text="—")

    def show_about(self):
        """Отображает информацию о программе."""
        messagebox.showinfo(
            "О программе",
            "Балансировка вибрации (Классика, схемы)\n"
            "• Классический расчёт по каждому режиму отдельно, итог — среднее значение\n"
            "• Поддержка схем грузов: симметричная, кососимметричная, V-система, единичная, произвольная\n"
            "• Система грузов определяется автоматически по введённым грузам\n"
            "• Показывает остатки после коррекции\n"
            "• Кнопка 'Оптимальный (графика/подбор)' — подбор для всех опор/режимов"
        )

    def on_tab_changed(self, event=None):
        """Обрабатывает смену активной вкладки."""
        tab_idx = self.notebook.index(self.notebook.select())
        tab_text = self.notebook.tab(tab_idx, "text").replace(" ✕", "")
        if tab_text == "Пуск 0":
            self.scheme_calc_frame.pack_forget()
        else:
            self.scheme_calc_frame.pack(side='left', padx=12)
        tab = self.tabs[tab_text]
        frame = tab['frame']
        if hasattr(frame, 'residuals_block') and frame.residuals_block:
            frame.residuals_block.destroy()
            frame.residuals_block = None

    def create_notebook(self):
        """Создаёт notebook для вкладок."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=1, fill='both', padx=5, pady=5)
        self.notebook.bind("<Button-1>", self.on_tab_click)
        self.notebook.bind("<Button-3>", self.on_tab_right_click)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = BalancingApp(root)
        root.mainloop()
    except Exception as e:
        error_msg = f"Критическая ошибка: {str(e)}"
        logger.error(error_msg)
        messagebox.showerror("Ошибка запуска", error_msg)
        sys.exit(1)