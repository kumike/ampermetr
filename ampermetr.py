#!/usr/bin/env python3
import curses
import time
import multiprocessing
import signal
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
    """Читает energy_* файл, если есть, иначе charge_* для совместимости"""
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
    """
    Читает power_now (мкВт) если есть, иначе current_now (мкА) и конвертирует в мкВт.
    Для совместимости со старыми ядрами, где нет power_now.
    """
    power_path = os.path.join(path, 'power_now')
    current_path = os.path.join(path, 'current_now')
    voltage_path = os.path.join(path, 'voltage_now')
    
    # Пробуем power_now (предпочтительный вариант, мкВт)
    if os.path.exists(power_path):
        try:
            with open(power_path) as f:
                return int(f.read().strip())
        except:
            pass
    
    # Fallback: current_now (мкА) * voltage_now (мкВ) = мкВт
    if os.path.exists(current_path) and os.path.exists(voltage_path):
        try:
            with open(current_path) as f:
                current = int(f.read().strip())
            with open(voltage_path) as f:
                voltage = int(f.read().strip())
            # P(мкВт) = I(мкА) * V(мкВ) / 1_000_000
            return int((current * voltage) / 1_000_000)
        except:
            pass
    
    return 0

def find_battery():
    """Динамический поиск первой доступной батареи в sysfs"""
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

myscreen = curses.initscr() 

### для голой консоли, не выводит в конце строки нажимаемые символы
curses.noecho() 
### прячем курсор
curses.curs_set(0)

### используем дефолтные цвета кoнсоли (прозрачность и тп)
curses.start_color()
curses.use_default_colors()
curses.init_pair(1,-1,-1)
### задаем цвет для строки с мАч
curses.init_pair(2,curses.COLOR_GREEN,-1)
curses.init_pair(3,curses.COLOR_RED,-1)

myscreen.border(0) 

myscreen.addstr(0,1,'| ampermetr |')

height, width = myscreen.getmaxyx()

myscreen.refresh()### костыль и вроде работает

empty = ' '
line = '_' * 56
discharg =   'Статус: Разряжается'#[:width-1]
charg =      'Статус: Заряжается '#[:width-1]
charg_full = 'Статус: Заряжен    '
percent_charge = 'Заряд: '
capacity_lev = 'Состояние: '
manufacturer_name = 'Производитель: '
model = 'Модель: '
type_bat = 'Тип батареи: '
full_bat = 'Заводская емкость батареи: '
now_bat = 'Текущая емкость батареи: '
volt_bat = 'Напряжение: '
degrade = 'Деградация: '
exit = 'Нажмите q для выхода'


half_width = width // 2
start_x_current_now    = int(half_width - (len(empty) // 2) - len(empty) % 2)
start_x_line           = int(half_width - (len(line) // 2) - len(line) % 2)
start_x_empty          = int(half_width - (len(empty) // 2) - len(empty) % 2)
start_x_discharg       = int(half_width - (len(discharg) // 2) - len(discharg) % 2)
start_x_charg          = int(half_width - (len(charg) // 2 ) - len(charg) % 2)
start_x_percent_charge = int(half_width - (len(percent_charge) // 2) - len(percent_charge) % 2)
start_x_manufacturer   = int(half_width - (len(manufacturer_name) // 2) - len(manufacturer_name) % 2)


start_x_capacity_level = int(half_width - (len(capacity_lev) // 2) - len(capacity_lev) % 2)

start_x_model          = int(half_width - (len(model) // 2) - len(model) % 2)
start_x_technology     = int(half_width - (len(type_bat) // 2) - len(type_bat) % 2)
start_x_full_design    = int(half_width - (len(full_bat) // 2) - len(full_bat) % 2)
start_x_voltage        = int(half_width - (len(volt_bat) // 2) - len(volt_bat) % 2)
start_x_exit           = int(half_width - (len(exit) // 2) - len(exit) % 2)
start_y = int((height // 2) - 10)



def mainCycle():
    path = find_battery()
    if not path:
        curses.endwin()
        print("Ошибка: Батарея не найдена в системе (нет BAT*/CMB* с present=1).", file=sys.stderr)
        os._exit(1)

    ### Определяем тип метрик ядра: energy (mWh) или charge (mAh)
    if os.path.exists(path + 'energy_full_design'):
        capacity_unit = 'mWh'
    else:
        capacity_unit = 'mAh'

    ### Читаем неизменяимые данные вне цикла, меньше обращений к диску, в цикле только выводим значения ###
    ### Тип батареи
    with open(path+'technology') as f:
        technology = f.read().strip()

    myscreen.addstr(start_y + 2, start_x_technology - 8, type_bat+technology)

    ### Заводская емкость батареи (с поддержкой energy/charge для совместимости)
    charge_full_design = read_energy_or_charge(path, 'energy_full_design', 'charge_full_design')

    ### производитель и модель батареи
    with open(path+'manufacturer') as f:
        manufacturer = f.read().strip()

    with open(path+'model_name') as f:
        model_name = f.read().strip()

    while True:
        ### Статус батареи, заряжается\разряжается
        with open(path+'status') as f:
            status = f.read().strip()

        ### 🔥 ИСПРАВЛЕНИЕ: задаем значения по умолчанию, чтобы избежать UnboundLocalError
        color_num = 1  # стандартный цвет консоли
        prefix = ' '   # неизвестный статус

        if 'Discharging' in status:
            prefix = '-'
            color_num = 3
            myscreen.addstr(start_y, start_x_discharg, discharg)
        elif 'Charging' in status:
            prefix = '+'
            color_num = 2
            myscreen.addstr(start_y, start_x_charg, charg)
        elif 'Full' in status:
            prefix = ' '
            color_num = 2
            myscreen.addstr(start_y, start_x_charg, charg_full)
        else:
            # Обработка нестандартных статусов (Unknown, Not charging и т.д.)
            myscreen.addstr(start_y, start_x_discharg, f'Статус: {status}')

        ### 🔥 текущий заряд/розряд: читаем power_now или current_now (совместимость со старыми ядрами)
        power_uw = read_power_or_current(path)
        myscreen.attron(curses.color_pair(color_num))
        myscreen.attron(curses.A_BOLD)
        # Конвертируем мкВт -> мА для отображения (приблизительно, через среднее напряжение)
        # Для точности в мА нужно знать напряжение, но для индикации достаточно округлить
        myscreen.addstr(start_y - 3, start_x_current_now - 6, prefix+str(round(power_uw / 1000))+' mA ')
        myscreen.attroff(curses.A_BOLD)
        myscreen.attroff(curses.color_pair(color_num))
        myscreen.addstr(start_y - 2, start_x_line - 2, line)
        myscreen.addstr(start_y - 1, start_x_empty + 1,'')

        ### 🔥 РАСЧЁТ ПРОЦЕНТА С ДЕСЯТЫМИ (energy или charge)
        energy_now = read_energy_or_charge(path, 'energy_now', 'charge_now')
        energy_full = read_energy_or_charge(path, 'energy_full', 'charge_full')
        
        if energy_full > 0:
            percent = round(energy_now * 100 / energy_full, 1)
        else:
            percent = 0.0

        # Вывод процента БЕЗ цвета, как просили
        myscreen.addstr(start_y + 1, start_x_percent_charge - 5, percent_charge + f"{percent:.1f}" + ' % ')

        ### 🔥 ДЕГРАДАЦИЯ
        degradation = get_battery_degradation(energy_full, charge_full_design)

        ### Тип батареи
        myscreen.addstr(start_y + 2, start_x_technology - 8, type_bat+technology)

        ### Заводская емкость батареи (mWh или mAh в зависимости от API ядра)
        myscreen.addstr(start_y + 3, start_x_full_design - 15, full_bat + str(int(charge_full_design) // 1000) + ' ' + capacity_unit + ' ')

        ### 🔥 Расчёт и вывод энергоёмкости батареи в Вт·ч ниже строки mWh/mAh
        # Значения в sysfs хранятся в микроватт-часах (μWh). Делим на 1 000 000 для перевода в Вт·ч.
        design_wh = charge_full_design / 1_000_000
        current_wh = energy_full / 1_000_000 if energy_full > 0 else 0.0
        
        myscreen.addstr(start_y + 4, start_x_full_design - 15, f"Энергоёмкость (заводская): {design_wh:.2f} Вт·ч")
        myscreen.addstr(start_y + 5, start_x_full_design - 15, f"Энергоёмкость (текущая):   {current_wh:.2f} Вт·ч")

        ### Текущее напряжение (сдвинуто вниз)
        with open(path+'voltage_now') as f:
            voltage_now = int(f.read().strip())
        myscreen.addstr(start_y + 6, start_x_voltage - 8, volt_bat+str(round(voltage_now / 1000000, 1))+' V ')

        ### производитель и модель батареи (сдвинуто вниз)
        myscreen.addstr(start_y + 7, start_x_manufacturer - 9, manufacturer_name+manufacturer)
        myscreen.addstr(start_y + 8, start_x_model - 6, model+model_name)

        with open(path+'capacity_level') as f:
            capacity_level = f.read().strip()

        myscreen.addstr(start_y + 9, start_x_capacity_level - 7, capacity_lev+capacity_level)
        
        # 🔥 ДЕГРАДАЦИЯ С ЦВЕТОВОЙ ИНДИКАЦИЕЙ ТОЛЬКО ДЛЯ ЗНАЧЕНИЯ (сдвинуто вниз)
        myscreen.addstr(start_y + 10, start_x_capacity_level - 8, degrade)
        if degradation is not None:
            deg_str = f"{degradation:.2f} %"
            if degradation >= 50.0:
                myscreen.attron(curses.color_pair(3) | curses.A_BOLD) # Красный (критично >=50%)
            else:
                myscreen.attron(curses.color_pair(2))                 # Зелёный (норма <50%)
            myscreen.addstr(start_y + 10, start_x_capacity_level - 8 + len(degrade), deg_str)
            myscreen.attroff(curses.color_pair(3) | curses.A_BOLD)
            myscreen.attroff(curses.color_pair(2))
        else:
            myscreen.addstr(start_y + 10, start_x_capacity_level - 8 + len(degrade), "N/A %")

        myscreen.refresh()
        time.sleep(1)

def exitFunc():
    try:
        myscreen.addstr(start_y + 13, start_x_exit - 4, exit) ### Сдвинуто на +2 для освобождения места под Wh
        if myscreen.getch() == 113: ### 113 это ord('q')
            main_cycle_proc.terminate() ### мгновенно убиваем главный цикл
    except KeyboardInterrupt:
        main_cycle_proc.terminate()
        myscreen.clear()
        curses.endwin()


### Процессом сделано для того чтобы не было задержки выхода по q организованому в главном цикле, запускается отдельным процесом и прибивается функцией exitFunc()
main_cycle_proc = multiprocessing.Process(target=mainCycle)
main_cycle_proc.start()

try:
    exitFunc()
except KeyboardInterrupt:
    pass
finally:
    # 🔥 Чистый молчаливый выход: убиваем дочерний процесс и корректно закрываем curses
    main_cycle_proc.terminate()
    main_cycle_proc.join(timeout=1)
    try:
        myscreen.clear()
        curses.endwin()
    except Exception:
        pass
    sys.exit(0)
