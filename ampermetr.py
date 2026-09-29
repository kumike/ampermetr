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
    """
    Reads power_now (uW) if present, otherwise current_now (uA) and converts to uW.
    For compatibility with older kernels that lack power_now.
    """
    power_path = os.path.join(path, 'power_now')
    current_path = os.path.join(path, 'current_now')
    voltage_path = os.path.join(path, 'voltage_now')
    
    # Try power_now (preferred option, uW)
    if os.path.exists(power_path):
        try:
            with open(power_path) as f:
                return int(f.read().strip())
        except:
            pass
    
    # Fallback: current_now (uA) * voltage_now (uV) = uW
    if os.path.exists(current_path) and os.path.exists(voltage_path):
        try:
            with open(current_path) as f:
                current = int(f.read().strip())
            with open(voltage_path) as f:
                voltage = int(f.read().strip())
            # P(uW) = I(uA) * V(uV) / 1_000_000
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

myscreen = curses.initscr() 

### for bare console, does not echo pressed characters at the end of the line
curses.noecho() 
### hide cursor
curses.curs_set(0)

### use default console colors (transparency, etc.)
curses.start_color()
curses.use_default_colors()
curses.init_pair(1,-1,-1)
### set color for the mAh line
curses.init_pair(2,curses.COLOR_GREEN,-1)
curses.init_pair(3,curses.COLOR_RED,-1)

myscreen.border(0) 

myscreen.addstr(0,1,'| ampermetr |')

height, width = myscreen.getmaxyx()

myscreen.refresh()### hack and seems to work

empty = ' '
line = '_' * 56
discharg =   'Status: Discharging'
charg =      'Status: Charging   '
charg_full = 'Status: Full       '
percent_charge = 'Charge: '
capacity_lev = 'Condition: '
manufacturer_name = 'Manufacturer: '
model = 'Model: '
type_bat = 'Battery type: '
full_bat = 'Factory battery capacity: '
now_bat = 'Current battery capacity: '
volt_bat = 'Voltage: '
degrade = 'Degradation: '
exit = 'Press q to exit'


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
        print("Error: Battery not found in system (no BAT*/CMB* with present=1).", file=sys.stderr)
        os._exit(1)

    ### Determine kernel metric type: energy (mWh) or charge (mAh)
    if os.path.exists(path + 'energy_full_design'):
        capacity_unit = 'mWh'
    else:
        capacity_unit = 'mAh'

    ### Read immutable data outside the loop, fewer disk accesses, only output values in the loop ###
    ### Battery type
    with open(path+'technology') as f:
        technology = f.read().strip()

    myscreen.addstr(start_y + 2, start_x_technology - 8, type_bat+technology)

    ### Factory battery capacity (with energy/charge support for compatibility)
    charge_full_design = read_energy_or_charge(path, 'energy_full_design', 'charge_full_design')

    ### battery manufacturer and model
    with open(path+'manufacturer') as f:
        manufacturer = f.read().strip()

    with open(path+'model_name') as f:
        model_name = f.read().strip()

    while True:
        ### Battery status, charging\discharging
        with open(path+'status') as f:
            status = f.read().strip()

        ###  FIX: set default values to avoid UnboundLocalError
        color_num = 1  # default console color
        prefix = ' '   # unknown status

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
            # Handle non-standard statuses (Unknown, Not charging, etc.)
            myscreen.addstr(start_y, start_x_discharg, f'Status: {status}')

        ###  current charge/discharge: read power_now or current_now (compatibility with older kernels)
        power_uw = read_power_or_current(path)
        myscreen.attron(curses.color_pair(color_num))
        myscreen.attron(curses.A_BOLD)
        # Convert uW -> mA for display (approximately, via average voltage)
        # For accuracy in mA, voltage is needed, but rounding is sufficient for indication
        myscreen.addstr(start_y - 3, start_x_current_now - 6, prefix+str(round(power_uw / 1000))+' mA ')
        myscreen.attroff(curses.A_BOLD)
        myscreen.attroff(curses.color_pair(color_num))
        myscreen.addstr(start_y - 2, start_x_line - 2, line)
        myscreen.addstr(start_y - 1, start_x_empty + 1,'')

        ###  PERCENTAGE CALCULATION WITH DECIMALS (energy or charge)
        energy_now = read_energy_or_charge(path, 'energy_now', 'charge_now')
        energy_full = read_energy_or_charge(path, 'energy_full', 'charge_full')
        
        if energy_full > 0:
            percent = round(energy_now * 100 / energy_full, 1)
        else:
            percent = 0.0

        # Output percentage WITHOUT color, as requested
        myscreen.addstr(start_y + 1, start_x_percent_charge - 5, percent_charge + f"{percent:.1f}" + ' % ')

        ###  DEGRADATION
        degradation = get_battery_degradation(energy_full, charge_full_design)

        ### Battery type
        myscreen.addstr(start_y + 2, start_x_technology - 8, type_bat+technology)

        ### Factory battery capacity (mWh or mAh depending on kernel API)
        myscreen.addstr(start_y + 3, start_x_full_design - 15, full_bat + str(int(charge_full_design) // 1000) + ' ' + capacity_unit + ' ')

        ###  Calculate and output battery energy capacity in Wh below the mWh/mAh line
        # Values in sysfs are stored in microwatt-hours (uWh). Divide by 1,000,000 to convert to Wh.
        design_wh = charge_full_design / 1_000_000
        current_wh = energy_full / 1_000_000 if energy_full > 0 else 0.0
        
        myscreen.addstr(start_y + 4, start_x_full_design - 15, f"Energy capacity (factory): {design_wh:.2f} Wh")
        myscreen.addstr(start_y + 5, start_x_full_design - 15, f"Energy capacity (current):   {current_wh:.2f} Wh")

        ### Current voltage (shifted down)
        with open(path+'voltage_now') as f:
            voltage_now = int(f.read().strip())
        myscreen.addstr(start_y + 6, start_x_voltage - 8, volt_bat+str(round(voltage_now / 1000000, 1))+' V ')

        ### battery manufacturer and model (shifted down)
        myscreen.addstr(start_y + 7, start_x_manufacturer - 9, manufacturer_name+manufacturer)
        myscreen.addstr(start_y + 8, start_x_model - 6, model+model_name)

        with open(path+'capacity_level') as f:
            capacity_level = f.read().strip()

        myscreen.addstr(start_y + 9, start_x_capacity_level - 7, capacity_lev+capacity_level)
        
        #  DEGRADATION WITH COLOR INDICATION FOR VALUE ONLY (shifted down)
        myscreen.addstr(start_y + 10, start_x_capacity_level - 8, degrade)
        if degradation is not None:
            deg_str = f"{degradation:.2f} %"
            if degradation >= 50.0:
                myscreen.attron(curses.color_pair(3) | curses.A_BOLD) # Red (critical >=50%)
            else:
                myscreen.attron(curses.color_pair(2))                 # Green (normal <50%)
            myscreen.addstr(start_y + 10, start_x_capacity_level - 8 + len(degrade), deg_str)
            myscreen.attroff(curses.color_pair(3) | curses.A_BOLD)
            myscreen.attroff(curses.color_pair(2))
        else:
            myscreen.addstr(start_y + 10, start_x_capacity_level - 8 + len(degrade), "N/A %")

        myscreen.refresh()
        time.sleep(1)

def exitFunc():
    try:
        myscreen.addstr(start_y + 13, start_x_exit - 4, exit) ### Shifted by +2 to free up space for Wh
        if myscreen.getch() == 113: ### 113 is ord('q')
            main_cycle_proc.terminate() ### instantly kill the main cycle
    except KeyboardInterrupt:
        main_cycle_proc.terminate()
        myscreen.clear()
        curses.endwin()


### Made as a process so there is no delay exiting on q organized in the main loop, runs as a separate process and is killed by exitFunc()
main_cycle_proc = multiprocessing.Process(target=mainCycle)
main_cycle_proc.start()

try:
    exitFunc()
except KeyboardInterrupt:
    pass
finally:
    #  Clean silent exit: kill child process and correctly close curses
    main_cycle_proc.terminate()
    main_cycle_proc.join(timeout=1)
    try:
        myscreen.clear()
        curses.endwin()
    except Exception:
        pass
    sys.exit(0)
