import curses
import time
import multiprocessing

myscreen = curses.initscr() 

### для голой консоли, не выводит в конце строки нажимаемые символы
curses.noecho()
#curses.cbreak() #disable line buffers to run the keypress immediately
### прячем курсор
curses.curs_set(0)
#myscreen.keypad(1) #enable keyboard use


### используем дефолтные цвета кoнсоли (прозрачность и тп)
curses.start_color()
curses.use_default_colors()
curses.init_pair(1,-1,-1)
### задаем цвет для строки с мАч
curses.init_pair(2,curses.COLOR_GREEN,-1)
curses.init_pair(3,curses.COLOR_RED,-1)



line              = '_' * 36
stat_us           = 'Статус: '
discharg          = 'Разряжается'
charg             = 'Заряжается '
charg_full        = 'Заряжен    '
percent_charge    = 'Заряд: '
capacity          = 'Состояние: '
manufacturer_name = 'Производитель: '
model             = 'Модель: '
type_bat          = 'Тип батареи: '
full_bat          = 'Емкость батареи: '
volt_bat          = 'Напряжение: '
exit              = 'Нажмите q для выхода'



def mainCycle():
    path = '/sys/class/power_supply/BAT1/'

    ### Читаем неизменяимые данные вне цикла, меньше обращений к диску, в цикле только выводим значения ###
    ### Тип батареи
    with open(path+'technology') as f:
        technology = f.read()
    
    ### Заводская емкость батареи
    with open(path+'energy_full_design') as f:
        charge_full_design = f.read()
    
    ### производитель и модель батареи
    with open(path+'manufacturer') as f:
        manufacturer = f.read()

    with open(path+'model_name') as f:
        model_name = f.read()


    while True:
        ### координаты экрана
        height, width = myscreen.getmaxyx()
        
        ### проверка на размер окна.
        if height < 18 or width < 38:
            myscreen.clear()
            curses.endwin()
            print('Xmin:38 Ymin:18')
            break  


        half_width = width // 2
        start_y = height // 4 

        start_x_line           = int(half_width - len(line) // 2)
        start_x_discharg       = int(half_width - len(stat_us))
        start_x_charg          = int(half_width - len(stat_us))
        start_x_percent_charge = int(half_width - len(percent_charge))
        start_x_manufacturer   = int(half_width - len(manufacturer_name))
        start_x_model          = int(half_width - len(model))
        start_x_technology     = int(half_width - len(type_bat))
        start_x_full_design    = int(half_width - len(full_bat))
        start_x_voltage        = int(half_width - len(volt_bat))
        start_x_exit           = int(half_width - len(exit) // 2)

        ### линия по краю
        myscreen.refresh()### костыль но работает
        myscreen.border(0) 
        myscreen.addstr(0,1,'| ampermetr |')

        curses.init_pair(2,curses.COLOR_GREEN,-1)
        curses.init_pair(3,curses.COLOR_RED,-1)
        
        
        
        ### Статус батареи, заряжается\разряжается
        with open(path+'status') as f:
            status = f.read()

        if 'Discharging' in status:
            prefix = '-'
            color_num = 3
            myscreen.addstr(start_y, start_x_discharg, stat_us)
            myscreen.addstr(start_y, half_width, discharg)
        
        elif 'Charging' in status:
            prefix = ' '
            color_num = 2
            myscreen.addstr(start_y, start_x_charg, stat_us)
            myscreen.addstr(start_y, half_width, charg)

        elif 'Full' in status:
            prefix = ' '
            color_num = 2
            myscreen.addstr(start_y, start_x_charg, stat_us)
            myscreen.addstr(start_y, half_width, charg_full)


        ### текущий заряд/розряд в микроАмперах : /1000 = миниАмперы /1000000 = амперы
        with open(path+'power_now') as f:
            current_now = f.read()

        myscreen.attron(curses.color_pair(color_num))    
        myscreen.attron(curses.A_BOLD)    

        curr_n='   '+prefix+str(round(int(current_now) / 1000))
        myscreen.addstr(start_y - 3, int(half_width - len(curr_n))-1,curr_n)
        myscreen.addstr(start_y - 3,half_width,'mA')
     
        myscreen.attroff(curses.A_BOLD)
        myscreen.attroff(curses.color_pair(color_num))

        ### разд. линия
        myscreen.addstr(start_y - 2, start_x_line, line)

        ### текущий процент заряда батареи
        with open(path+'energy_now') as f:
            charge_now = f.read()
        
        with open(path+'energy_full') as f:
            charge_full = f.read()
        
        myscreen.addstr(start_y + 1, start_x_percent_charge, percent_charge)
        myscreen.addstr(start_y + 1, half_width, str(round(int(charge_now) * 100 / int(charge_full),1))+'% ')

        ### Тип батареи
        myscreen.addstr(start_y + 2, start_x_technology , type_bat)
        myscreen.addstr(start_y + 2, half_width , technology[:-1])


        ### Заводская емкость батареи
        myscreen.addstr(start_y + 3, start_x_full_design , full_bat)
        myscreen.addstr(start_y + 3, half_width, str(int(charge_full_design) // 1000)+' mAh ')

        ### Текущее напряжение
        with open(path+'voltage_now') as f:
            voltage_now = f.read()

        myscreen.addstr(start_y + 4, start_x_voltage, volt_bat)
        myscreen.addstr(start_y + 4, half_width, str(round(int(voltage_now) / 1000000, 1))+' V ')

        ### производитель и модель батареи
        myscreen.addstr(start_y + 5, start_x_manufacturer,  manufacturer_name)
        myscreen.addstr(start_y + 5, half_width,    manufacturer[:-1])
        myscreen.addstr(start_y + 6, start_x_model, model)
        myscreen.addstr(start_y + 6, half_width, model_name[:-1])

        ### выход
        myscreen.addstr(start_y + 11, start_x_exit, exit)
        
        ### 
        myscreen.refresh()
        time.sleep(1)
        myscreen.clear()

            

### Процесoм сделано для того чтобы не было задержки выхода по q организованому в главном цикле, запускается отдельным процесом и прибивается функцией exitFunc()
main_cycle_proc = multiprocessing.Process(target=mainCycle)


###  сделано отдельной функцией для выхода без задержки
def exitFunc():
    try:
        while True:
            if myscreen.getch() == 113: ### 113 это ord('q') гетчар() блокирует цикл и ждёт след символ пока не будет q
                main_cycle_proc.terminate() ### мгновенно убиваем главный цикл
                myscreen.clear() ### походу можно и без этой строки, всё работает и без неё
                curses.endwin()
                break
    except KeyboardInterrupt:
        main_cycle_proc.terminate()
        myscreen.clear()
        curses.endwin()


exit_func_proc = multiprocessing.Process(target=exitFunc)


### min: |y:38 _x:17
### стартуем паралельно наши процесы
main_cycle_proc.start()
exit_func_proc.start()

### следим за маинЦиклом, если разм. окна меньше он заканчиватся и знач прибиваем и екситФункц.
try:
    while True:
        if main_cycle_proc.is_alive() == False:
            exit_func_proc.terminate()
            break
        time.sleep(0.5)
except KeyboardInterrupt:
    myscreen.clear()
    curses.endwin()
