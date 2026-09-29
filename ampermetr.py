#!/usr/bin/env python3
import curses
import time
import multiprocessing
import os
import glob
import sys

def get_battery_degradation(full, design):
    try:
        if design <= 0:
            return None
        health = full / design * 100
        degradation = 100 - health
        return round(degradation, 2)
    except:
        return None

def read_energy_or_charge(path, name_energy, name_charge):
    """Reads energy_* file if present, otherwise charge_* for compatibility"""
    energy_path = os.path.join(path, name_energy)
    charge_path = os.path.join(path, name_charge)
    
    if os.path.exists(energy_path):
        with open(energy_path) as f:
            return int(f.read().strip())
    elif os.path.exists(charge_path):
        with open(charge_path) as f:
            return int(f.read().strip())
    else:
        return 0

def read_power_or_current(path):
    """Reads power_now (uW) if present, otherwise current_now (uA) and converts to uW."""
    power_path = os.path.join(path, 'power_now')
    current_path = os.path.join(path, 'current_now')
    voltage_path = os.path.join(path, 'voltage_now')
    
    if os.path.exists(power_path):
        try:
            with open(power_path) as f:
                return int(f.read().strip())
        except:
            pass
    
    if os.path.exists(current_path) and os.path.exists(voltage_path):
        try:
            with open(current_path) as f:
                current = int(f.read().strip())
            with open(voltage_path) as f:
                voltage = int(f.read().strip())
            return int((current * voltage) / 1_000_000)
        except:
            pass
    
    return 0

def find_battery():
    """Dynamic search for the first available battery in sysfs"""
    patterns = ['/sys/class/power_supply/BAT*', '/sys/class/power_supply/CMB*', '/sys/class/power_supply/BATT*']
    for pattern in patterns:
        for bat_path in sorted(glob.glob(pattern)):
            present_file = os.path.join(bat_path, 'present')
            if os.path.exists(present_file):
                try:
                    with open(present_file) as f:
                        if f.read().strip() == '1':
                            return bat_path + '/'
                except:
                    pass
    return None

# Глобальные переменные для экрана (инициализируются в родителе)
myscreen = None
MIN_HEIGHT = 15
MIN_WIDTH = 65

def draw_centered(y, text, color_pair=1, bold=False):
    """Безопасная функция для центрирования текста с защитой от ошибок ресайза"""
    global myscreen
    try:
        # Пересчитываем ширину каждый раз на случай ресайза
        _, width = myscreen.getmaxyx()
        x = max(0, (width - len(text)) // 2)
        # Обрезаем текст, если он вдруг шире экрана
        safe_text = text[:width-1] 
        
        if bold:
            myscreen.attron(curses.A_BOLD | curses.color_pair(color_pair))
        myscreen.addstr(y, x, safe_text)
        if bold:
            myscreen.attroff(curses.A_BOLD | curses.color_pair(color_pair))
    except curses.error:
        pass # Игнорируем ошибки отрисовки при резком изменении размера

def mainCycle():
    global myscreen
    path = find_battery()
    if not path:
        # Если мы в дочернем процессе, пытаемся корректно завершить curses
        try:
            curses.endwin()
        except:
            pass
        print("Error: Battery not found in system (no BAT*/CMB* with present=1).", file=sys.stderr)
        os._exit(1)

    if os.path.exists(path + 'energy_full_design'):
        capacity_unit = 'mWh'
    else:
        capacity_unit = 'mAh'

    # Читаем статические данные один раз
    try:
        with open(path+'technology') as f:
            technology = f.read().strip()
        charge_full_design = read_energy_or_charge(path, 'energy_full_design', 'charge_full_design')
        with open(path+'manufacturer') as f:
            manufacturer = f.read().strip()
        with open(path+'model_name') as f:
            model_name = f.read().strip()
    except Exception:
        pass # Защита от внезапного исчезновения файлов

    while True:
        # 🔥 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Принудительно обновляем размеры экрана для дочернего процесса
        curses.update_lines_cols()
        height, width = myscreen.getmaxyx()

        # 🔥 ПРОВЕРКА МИНИМАЛЬНОГО РАЗМЕРА ОКНА
        if height < MIN_HEIGHT or width < MIN_WIDTH:
            myscreen.clear()
            try:
                myscreen.addstr(0, 0, f" Window too small! ".center(width), curses.A_REVERSE)
                myscreen.addstr(1, 0, f" Required: {MIN_WIDTH}x{MIN_HEIGHT} | Current: {width}x{height} ".center(width))
                myscreen.addstr(2, 0, " Please resize your terminal or tmux pane ".center(width))
            except curses.error:
                pass
            myscreen.refresh()
            time.sleep(0.5)
            continue # Пропускаем отрисовку основного интерфейса, ждем ресайза

        # Очищаем экран только если он был в состоянии "too small", иначе можно убрать clear для уменьшения мерцания
        # myscreen.clear() # Раскомментируйте, если есть артефакты при ресайзе

        try:
            with open(path+'status') as f:
                status = f.read().strip()
        except:
            status = 'Unknown'

        color_num = 1
        prefix = ' '

        if 'Discharging' in status:
            prefix = '-'
            color_num = 3
            draw_centered(0, 'Status: Discharging')
        elif 'Charging' in status:
            prefix = '+'
            color_num = 2
            draw_centered(0, 'Status: Charging   ')
        elif 'Full' in status:
            prefix = ' '
            color_num = 2
            draw_centered(0, 'Status: Full       ')
        else:
            draw_centered(0, f'Status: {status}')

        power_uw = read_power_or_current(path)
        
        # Рисуем линию и ток
        line = '_' * min(56, width - 4)
        draw_centered(1, line)
        draw_centered(3, f" {prefix}{round(power_uw / 1000)} mA ", color_num, bold=True)

        energy_now = read_energy_or_charge(path, 'energy_now', 'charge_now')
        energy_full = read_energy_or_charge(path, 'energy_full', 'charge_full')
        
        if energy_full > 0:
            percent = round(energy_now * 100 / energy_full, 1)
        else:
            percent = 0.0

        draw_centered(4, f"Charge: {percent:.1f} % ")

        degradation = get_battery_degradation(energy_full, charge_full_design)

        draw_centered(5, f"Battery type: {technology}")
        
        cap_str = f"Factory capacity: {int(charge_full_design) // 1000} {capacity_unit}"
        draw_centered(6, cap_str)

        design_wh = charge_full_design / 1_000_000
        current_wh = energy_full / 1_000_000 if energy_full > 0 else 0.0
        
        draw_centered(7, f"Energy capacity (factory): {design_wh:.2f} Wh")
        draw_centered(8, f"Energy capacity (current): {current_wh:.2f} Wh")

        try:
            with open(path+'voltage_now') as f:
                voltage_now = int(f.read().strip())
            draw_centered(9, f"Voltage: {round(voltage_now / 1000000, 1)} V ")
        except:
            pass

        draw_centered(10, f"Manufacturer: {manufacturer}")
        draw_centered(11, f"Model: {model_name}")

        try:
            with open(path+'capacity_level') as f:
                capacity_level = f.read().strip()
            draw_centered(12, f"Condition: {capacity_level}")
        except:
            pass

        # Degradation with color
        deg_text = "Degradation: "
        if degradation is not None:
            deg_str = f"{degradation:.2f} %"
            deg_color = 3 if degradation >= 50.0 else 2
            # Для деградации рисуем чуть иначе, чтобы применить цвет только к цифрам, но в центре это выглядит так:
            draw_centered(13, f"{deg_text}{deg_str}", deg_color, bold=(degradation >= 50.0))
        else:
            draw_centered(13, f"{deg_text}N/A %")

        myscreen.refresh()
        time.sleep(1)

def exitFunc():
    global myscreen
    try:
        # Пытаемся нарисовать подсказку, но безопасно
        height, width = myscreen.getmaxyx()
        exit_text = "Press q to exit"
        if height > 14 and width > len(exit_text):
            x = max(0, (width - len(exit_text)) // 2)
            myscreen.addstr(14, x, exit_text)
            myscreen.refresh()
            
            # Неблокирующее ожидание ввода не получится легко с multiprocessing, 
            # поэтому используем обычный getch, но с обработкой ошибок
            myscreen.nodelay(False)
            if myscreen.getch() == 113: # 'q'
                pass
    except KeyboardInterrupt:
        pass
    except curses.error:
        pass
    finally:
        # Чистый выход
        try:
            myscreen.clear()
            curses.endwin()
        except Exception:
            pass
        sys.exit(0)

if __name__ == '__main__':
    # Инициализация только в главном процессе
    myscreen = curses.initscr()
    curses.noecho()
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, -1, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)
    
    # Рисуем рамку один раз при старте
    try:
        myscreen.border(0)
        myscreen.addstr(0, 1, '| ampermetr |')
        myscreen.refresh()
    except curses.error:
        pass

    main_cycle_proc = multiprocessing.Process(target=mainCycle)
    main_cycle_proc.start()

    try:
        exitFunc()
    except KeyboardInterrupt:
        pass
    finally:
        main_cycle_proc.terminate()
        main_cycle_proc.join(timeout=1)
        try:
            myscreen.clear()
            curses.endwin()
        except Exception:
            pass
        sys.exit(0)
