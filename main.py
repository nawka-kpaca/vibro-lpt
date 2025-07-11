import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def polar_to_cartesian(radius, angle_deg):
    angle_rad = np.deg2rad(angle_deg)
    return radius * np.cos(angle_rad), radius * np.sin(angle_rad)

def cartesian_to_polar(x, y):
    radius = np.hypot(x, y)
    angle_deg = np.rad2deg(np.arctan2(y, x)) % 360
    return round(radius, 3), round(angle_deg, 1)

def parse_vector_input(text):
    try:
        text = text.replace(',', '.').strip()
        if not text or text == "0/0":
            return None
        parts = text.split('/')
        if len(parts) != 2:
            raise ValueError("Ожидается формат 'амплитуда/угол'")
        radius = float(parts[0])
        angle = float(parts[1].replace("°", ""))
        return radius, angle
    except Exception:
        return None

def mean_angle_deg(angles):
    sin_sum = np.sum(np.sin(np.deg2rad(angles)))
    cos_sum = np.sum(np.cos(np.deg2rad(angles)))
    return (np.rad2deg(np.arctan2(sin_sum, cos_sum)) % 360)

def calculate_sensitivity(pusk0, pusk1, pusk2, gruzes):
    """
    Вычисляет чувствительность для двух плоскостей.
    pusk0, pusk1, pusk2 - списки с данными по плоскостям [plane1, plane2]
    gruzes - массы грузов [(mass1, angle1), (mass2, angle2)]
    """
    sensitivities = {'plane1': [], 'plane2': []}
    gruz1 = gruzes[0][0] if gruzes and len(gruzes) > 0 else 0.5
    gruz2 = gruzes[1][0] if gruzes and len(gruzes) > 1 else 0.5
    
    # Чувствительность для плоскости 1 (влияние груза 1)
    v0 = pusk0[0] if pusk0[0] else (0, 0)
    v1 = pusk1[0] if pusk1[0] else (0, 0)
    x0, y0 = polar_to_cartesian(*v0)
    x1, y1 = polar_to_cartesian(*v1)
    dx, dy = x1 - x0, y1 - y0
    amp, ang = cartesian_to_polar(dx, dy)
    sens_amp = (amp / gruz1) if gruz1 > 0 and amp > 0 else 1e-6
    sensitivities['plane1'].append((max(sens_amp, 1e-6), ang))
    
    # Чувствительность для плоскости 2 (влияние груза 2) 
    v1_2 = pusk1[1] if pusk1[1] else (0, 0)
    v2 = pusk2[1] if pusk2[1] else (0, 0)
    x1_2, y1_2 = polar_to_cartesian(*v1_2)
    x2, y2 = polar_to_cartesian(*v2)
    dx2, dy2 = x2 - x1_2, y2 - y1_2
    amp2, ang2 = cartesian_to_polar(dx2, dy2)
    sens_amp2 = (amp2 / gruz2) if gruz2 > 0 and amp2 > 0 else 1e-6
    sensitivities['plane2'].append((max(sens_amp2, 1e-6), ang2))
    
    return sensitivities

def classic_balance(vib0, sens_plane1, sens_plane2):
    """
    Классический расчет по матрице чувствительности (2 опоры, 2 независимых груза).
    vib0: [(amp1, phase1), (amp2, phase2)] - исходные вибрации
    sens_plane1, sens_plane2: [(sens_amp, sens_phase)] - чувствительности
    """
    # Преобразуем исходные вибрации в декартовы координаты
    x1, y1 = polar_to_cartesian(*vib0[0])
    x2, y2 = polar_to_cartesian(*vib0[1])
    vib_vec = np.array([x1, y1, x2, y2]).reshape(4, 1)
    
    # Строим матрицу чувствительности 4x2 (4 датчика, 2 груза)
    # Груз 1 влияет на плоскость 1, груз 2 влияет на плоскость 2
    sens_matrix = np.zeros((4, 2))
    
    if sens_plane1:
        s1_x, s1_y = polar_to_cartesian(*sens_plane1[0])
        sens_matrix[0, 0] = s1_x  # влияние груза 1 на x1
        sens_matrix[1, 0] = s1_y  # влияние груза 1 на y1
    
    if sens_plane2:
        s2_x, s2_y = polar_to_cartesian(*sens_plane2[0])
        sens_matrix[2, 1] = s2_x  # влияние груза 2 на x2  
        sens_matrix[3, 1] = s2_y  # влияние груза 2 на y2
    
    # Решаем систему методом наименьших квадратов
    try:
        M, residuals, rank, s = np.linalg.lstsq(sens_matrix, vib_vec.flatten(), rcond=None)
        mass1 = np.hypot(M[0], 0)  # масса груза 1
        mass2 = np.hypot(M[1], 0)  # масса груза 2
        phase1 = 0 if M[0] >= 0 else 180  # фаза груза 1
        phase2 = 0 if M[1] >= 0 else 180  # фаза груза 2
        
        result1 = (round(abs(mass1), 3), round(phase1, 1))
        result2 = (round(abs(mass2), 3), round(phase2, 1))
        
        # Среднее значение
        mean_mass = round((abs(mass1) + abs(mass2)) / 2, 3)
        mean_phase = round((phase1 + phase2) / 2, 1)
        
        return [result1, result2], (mean_mass, mean_phase)
        
    except np.linalg.LinAlgError:
        # Fallback если матрица вырожденная
        return [(0.0, 0.0), (0.0, 0.0)], (0.0, 0.0)

def optimal_balance(vib0, system_type="cososym"):
    # Статика: сумма векторов обеих опор; динамика: разность
    x1, y1 = polar_to_cartesian(*vib0[0])
    x2, y2 = polar_to_cartesian(*vib0[1])
    static_x = (x1 + x2) / 2
    static_y = (y1 + y2) / 2
    dynamic_x = (x1 - x2) / 2
    dynamic_y = (y1 - y2) / 2
    # Теперь подбираем массу и фазу для одного груза (статическая и динамическая коррекция)
    min_sum = float('inf')
    opt_mass = 0
    opt_phase = 0
    for mass in np.arange(0.01, 2.0, 0.01):
        for phase in range(0, 360):
            # Для симметричной: фаза2 = фаза1
            # Для кососимметричной: фаза2 = фаза1 + 180
            if system_type == "sym":
                phi2 = phase
            else:
                phi2 = (phase + 180) % 360
            # Корректирующие векторы
            x_corr1, y_corr1 = polar_to_cartesian(mass, phase)
            x_corr2, y_corr2 = polar_to_cartesian(mass, phi2)
            # Корректируем исходные вибрации
            x_res1 = x1 - x_corr1
            y_res1 = y1 - y_corr1
            x_res2 = x2 - x_corr2
            y_res2 = y2 - y_corr2
            sum_sq = np.hypot(x_res1, y_res1) + np.hypot(x_res2, y_res2)
            if sum_sq < min_sum:
                min_sum = sum_sq
                opt_mass = mass
                opt_phase = phase
    return round(opt_mass,3), round(opt_phase,1)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Программа расчета чувствительностей и балансировки")
        self.geometry("900x600")
        self.resizable(True, True)
        self.create_widgets()

    def create_widgets(self):
        # --- Ввод исходных вибраций ---
        self.lbl_vib0 = tk.Label(self, text="Исходные вибрации (Плоскость 1 и 2):")
        self.lbl_vib0.grid(row=0, column=0, columnspan=2, sticky="w")
        self.entry_vib0_1 = tk.Entry(self, width=15)
        self.entry_vib0_1.grid(row=1, column=0)
        self.entry_vib0_2 = tk.Entry(self, width=15)
        self.entry_vib0_2.grid(row=1, column=1)
        self.entry_vib0_1.insert(0, "10.2/45")
        self.entry_vib0_2.insert(0, "6.2/120")

        # --- Ввод вибраций пуск1 и пуск2 ---
        self.lbl_pusk1 = tk.Label(self, text="Вибрации после груза 1 (Плоскость 1 и 2):")
        self.lbl_pusk1.grid(row=2, column=0, columnspan=2, sticky="w")
        self.entry_pusk1_1 = tk.Entry(self, width=15)
        self.entry_pusk1_1.grid(row=3, column=0)
        self.entry_pusk1_2 = tk.Entry(self, width=15)
        self.entry_pusk1_2.grid(row=3, column=1)
        self.entry_pusk1_1.insert(0, "3.5/60")
        self.entry_pusk1_2.insert(0, "2.2/110")

        self.lbl_pusk2 = tk.Label(self, text="Вибрации после груза 2 (Плоскость 1 и 2):")
        self.lbl_pusk2.grid(row=4, column=0, columnspan=2, sticky="w")
        self.entry_pusk2_1 = tk.Entry(self, width=15)
        self.entry_pusk2_1.grid(row=5, column=0)
        self.entry_pusk2_2 = tk.Entry(self, width=15)
        self.entry_pusk2_2.grid(row=5, column=1)
        self.entry_pusk2_1.insert(0, "0/0")
        self.entry_pusk2_2.insert(0, "0/0")

        # --- Ввод масс грузов ---
        self.lbl_gruzes = tk.Label(self, text="Массы грузов:")
        self.lbl_gruzes.grid(row=6, column=0, columnspan=2, sticky="w")
        self.entry_gruz1 = tk.Entry(self, width=10)
        self.entry_gruz1.grid(row=7, column=0)
        self.entry_gruz2 = tk.Entry(self, width=10)
        self.entry_gruz2.grid(row=7, column=1)
        self.entry_gruz1.insert(0, "0.5")
        self.entry_gruz2.insert(0, "0.5")

        # --- Выбор системы грузов ---
        self.system_var = tk.StringVar(value="cososym")
        self.lbl_system = tk.Label(self, text="Система грузов:")
        self.lbl_system.grid(row=8, column=0, sticky="w")
        self.combo_system = ttk.Combobox(self, textvariable=self.system_var, values=["cososym", "sym"], width=12)
        self.combo_system.grid(row=8, column=1)
        self.combo_system.set("cososym")

        # --- Кнопки расчета ---
        self.btn_classic = tk.Button(self, text="Классический расчет", command=self.on_classic)
        self.btn_classic.grid(row=9, column=0, pady=8)
        self.btn_optimal = tk.Button(self, text="Оптимальный (графика/подбор)", command=self.on_optimal)
        self.btn_optimal.grid(row=9, column=1, pady=8)

        # --- Вывод результатов ---
        self.txt_result = tk.Text(self, width=110, height=20)
        self.txt_result.grid(row=10, column=0, columnspan=6, pady=10)

    def get_inputs(self):
        vib0 = [self.entry_vib0_1.get(), self.entry_vib0_2.get()]
        pusk1 = [self.entry_pusk1_1.get(), self.entry_pusk1_2.get()]
        pusk2 = [self.entry_pusk2_1.get(), self.entry_pusk2_2.get()]
        gruz1 = self.entry_gruz1.get()
        gruz2 = self.entry_gruz2.get()
        gruzes = []
        try:
            gruzes.append((float(gruz1), 0))
        except:
            gruzes.append((0.5, 0))
        try:
            gruzes.append((float(gruz2), 0))
        except:
            gruzes.append((0.5, 0))
        return vib0, pusk1, pusk2, gruzes

    def on_classic(self):
        vib0, pusk1, pusk2, gruzes = self.get_inputs()
        vib0_vec = [parse_vector_input(vib0[0]), parse_vector_input(vib0[1])]
        pusk1_vec = [parse_vector_input(pusk1[0]), parse_vector_input(pusk1[1])]
        pusk2_vec = [parse_vector_input(pusk2[0]), parse_vector_input(pusk2[1])]
        
        # Проверяем корректность данных
        if not all([vib0_vec[0], vib0_vec[1], pusk1_vec[0], pusk1_vec[1]]):
            self.txt_result.delete(1.0, tk.END)
            self.txt_result.insert(tk.END, "Ошибка: Некорректные входные данные для классического расчета\n")
            return
            
        sens = calculate_sensitivity(vib0_vec, pusk1_vec, pusk2_vec, gruzes)
        sens_plane1 = sens['plane1']
        sens_plane2 = sens['plane2']
        
        results, mean = classic_balance(vib0_vec, sens_plane1, sens_plane2)
        
        self.txt_result.delete(1.0, tk.END)
        self.txt_result.insert(tk.END, "Классический расчет по опорам:\n")
        self.txt_result.insert(tk.END, f"Груз 1 (плоскость 1): Масса={results[0][0]} кг, Фаза={results[0][1]}°\n")
        self.txt_result.insert(tk.END, f"Груз 2 (плоскость 2): Масса={results[1][0]} кг, Фаза={results[1][1]}°\n")
        self.txt_result.insert(tk.END, f"\nСреднее значение: Масса={mean[0]} кг, Фаза={mean[1]}°\n")

    def on_optimal(self):
        vib0, _, _, _ = self.get_inputs()
        vib0_vec = [parse_vector_input(vib0[0]), parse_vector_input(vib0[1])]
        
        # Проверяем корректность данных
        if not all([vib0_vec[0], vib0_vec[1]]):
            self.txt_result.delete(1.0, tk.END)
            self.txt_result.insert(tk.END, "Ошибка: Некорректные входные данные для оптимального расчета\n")
            return
            
        system_type = self.system_var.get()
        mass, phase = optimal_balance(vib0_vec, system_type=system_type)
        if system_type == "sym":
            phi2 = phase
        else:
            phi2 = (phase + 180) % 360
        self.txt_result.delete(1.0, tk.END)
        self.txt_result.insert(tk.END, "Оптимальный расчет по статике/динамике:\n")
        self.txt_result.insert(tk.END, f"Масса корректирующего груза: {mass} кг\n")
        self.txt_result.insert(tk.END, f"Фаза груза 1 (плоскость 1): {phase}°\n")
        self.txt_result.insert(tk.END, f"Фаза груза 2 (плоскость 2): {phi2}°\n")

if __name__ == "__main__":
    app = App()
    app.mainloop()