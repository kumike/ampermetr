import curses
import time
import multiprocessing
import signal

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
line = '_' * 36
discharg =   'Статус: Разряжается'#[:width-1]
charg =      'Статус: Заряжается '#[:width-1]
charg_full = 'Статус: Заряжен    '
percent_charge = 'Заряд: '
capacity = 'Состояние: '
manufacturer_name = 'Производитель: '
model = 'Модель: '
type_bat = 'Тип батареи: '
full_bat = 'Емкость батареи: '
volt_bat = 'Напряжение: '
exit = 'Нажмите q для выхода'


half_width = width // 2
start_x_current_now    = int(half_width - (len(empty) // 2) - len(empty) % 2)
start_x_line           = int(half_width - (len(line) // 2) - len(line) % 2)
start_x_empty          = int(half_width - (len(empty) // 2) - len(empty) % 2)
start_x_discharg       = int(half_width - (len(discharg) // 2) - len(discharg) % 2)
start_x_charg          = int(half_width - (len(charg) // 2 ) - len(charg) % 2)
start_x_percent_charge = int(half_width - (len(percent_charge) // 2) - len(percent_charge) % 2)
start_x_manufacturer   = int(half_width - (len(manufacturer_name) // 2) - len(manufacturer_name) % 2)
start_x_model          = int(half_width - (len(model) // 2) - len(model) % 2)
start_x_technology     = int(half_width - (len(type_bat) // 2) - len(type_bat) % 2)
start_x_full_design    = int(half_width - (len(full_bat) // 2) - len(full_bat) % 2)
start_x_voltage        = int(half_width - (len(volt_bat) // 2) - len(volt_bat) % 2)
start_x_exit           = int(half_width - (len(exit) // 2) - len(exit) % 2)
start_y = int((height // 2) - 10)



def mainCycle():
    path = '/sys/class/power_supply/BAT1/'

    ### Читаем неизменяимые данные вне цикла, меньше обращений к диску, в цикле только выводим значения ###
    ### Тип батареи
    with open(path+'technology') as f:
        technology = f.read()

    ### Заводская емкость батареи
    with open(path+'charge_full_design') as f:
        charge_full_design = f.read()

    ### производитель и модель батареи
    with open(path+'manufacturer') as f:
        manufacturer = f.read()

    with open(path+'model_name') as f:
        model_name = f.read()

    while True:
        ### Статус батареи, заряжается\разряжается
        with open(path+'status') as f:
            status = f.read()

        if 'Discharging' in status:
            prefix = '-'
            color_num = 3
            myscreen.addstr(start_y, start_x_discharg, discharg)#,curses.color_pair(1))
        elif 'Charging' in status:
            prefix = ' '
            color_num = 2
            myscreen.addstr(start_y, start_x_charg, charg)
        elif 'Full' in status:
            prefix = ' '
            color_num = 2
            myscreen.addstr(start_y, start_x_charg, charg_full)

        ### текущий заряд/розряд в микроАмперах : /1000 = миниАмперы /1000000 = амперы
        with open(path+'current_now') as f:
            current_now = f.read()
        myscreen.attron(curses.color_pair(color_num))    
        myscreen.attron(curses.A_BOLD)    
        myscreen.addstr(start_y - 3, start_x_current_now - 6, prefix+str(round(int(current_now) / 1000))+' mA ')#, curses.color_pair(2))
        myscreen.attroff(curses.A_BOLD)
        myscreen.attroff(curses.color_pair(color_num))
        myscreen.addstr(start_y - 2, start_x_line - 2, line)
        myscreen.addstr(start_y - 1, start_x_empty + 1,'')

        ### текущий процкнт заряда батареи
        with open(path+'charge_now') as f:
            charge_now = f.read()

        with open(path+'charge_full') as f:
            charge_full = f.read()
        myscreen.addstr(start_y + 1, start_x_percent_charge - 5, percent_charge+str(round(int(charge_now) * 100 / int(charge_full),1))+' % ')

        ### Тип батареи
        myscreen.addstr(start_y + 2, start_x_technology - 8, type_bat+technology[:-1])

        ### Заводская емкость батареи
        myscreen.addstr(start_y + 3, start_x_full_design - 10, full_bat+str(int(charge_full_design) // 1000)+' mAh ')

        ### Текущее напряжение
        with open(path+'voltage_now') as f:
            voltage_now = f.read()
        myscreen.addstr(start_y + 4, start_x_voltage - 8, volt_bat+str(round(int(voltage_now) / 1000000, 1))+' V ')

        ### производитель и модель батареи
        myscreen.addstr(start_y + 5, start_x_manufacturer - 9, manufacturer_name+manufacturer[:-1])
        myscreen.addstr(start_y + 6, start_x_model - 6, model+model_name[:-1])

        ### выход
        myscreen.addstr(start_y + 11, start_x_exit - 4, exit)
        
        myscreen.refresh()
        time.sleep(1)

            
def exitFunc():
    try:
        if myscreen.getch() == 113: ### 113 это ord('q')
            main_cycle_proc.terminate() ### мгновенно убиваем главный цикл
    except KeyboardInterrupt:
        main_cycle_proc.terminate()
        myscreen.clear()
        curses.endwin()

### Процесoм сделано для того чтобы не было задержки выхода по q организованому в главном цикле, запускается отдельным процесом и прибивается функцией exitFunc()
main_cycle_proc = multiprocessing.Process(target=mainCycle)
main_cycle_proc.start()

exitFunc()
