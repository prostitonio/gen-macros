import sys
import os
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QHeaderView, 
    QTableWidgetItem, QItemDelegate, QLineEdit  # <-- Добавлены QItemDelegate и QLineEdit
)
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator
from PyQt5 import uic
import pyqtgraph as pg
import string
import pandas as pd
import spec2nexus
from spec2nexus import spec

from PyQt5.QtWidgets import QSpinBox,QDoubleSpinBox  # Добавьте этот импорт в начало файла

class IntegerRangeDelegate(QItemDelegate):
    """Делегат для ограничения ввода целыми числами с возможностью прокрутки"""
    def __init__(self, min_val, max_val, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val

    def createEditor(self, parent, option, index):
        # Создаем QSpinBox вместо QLineEdit
        editor = QSpinBox(parent)
        editor.setRange(self.min_val, self.max_val)  # Устанавливаем диапазон
        editor.setSingleStep(1)  # Шаг изменения
        return editor

    def setEditorData(self, editor, index):
        # При начале редактирования подставляем текущее значение
        value = index.model().data(index, Qt.EditRole)
        if value is not None:
            editor.setValue(int(value))
        else:
            editor.setValue(self.min_val)

    def setModelData(self, editor, model, index):
        # При завершении редактирования сохраняем значение обратно в модель
        model.setData(index, editor.value(), Qt.EditRole)

class DoubleRangeDelegate(QItemDelegate):
    """Делегат для ввода дробных чисел с возможностью прокрутки"""
    def __init__(self, min_val, max_val, decimals=2, step=0.1, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.decimals = decimals  # Количество знаков после запятой
        self.step = step          # Шаг прокрутки

    def createEditor(self, parent, option, index):
        editor = QDoubleSpinBox(parent)
        editor.setRange(self.min_val, self.max_val)
        editor.setDecimals(self.decimals)
        editor.setSingleStep(self.step)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        if value is not None:
            editor.setValue(float(value))
        else:
            editor.setValue(self.min_val)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value(), Qt.EditRole)

class MacroGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # === ЗАГРУЗКА UI ФАЙЛА ===
        # Определяем путь к .ui файлу относительно текущего скрипта
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = os.path.join(base_dir, "interface.ui")
        uic.loadUi(ui_path, self)
        
        # Данные для графика
        self.x_data = None
        self.y_data = None
        self.plot_items = []  # Маркеры пиков
        
        # === НАСТРОЙКА ВИДЖЕТОВ ПОСЛЕ ЗАГРУЗКИ ===
        self._post_init_ui()
        
        # === ПОДКЛЮЧЕНИЕ СИГНАЛОВ ===
        self._connect_signals()

    def _post_init_ui(self):
        """Настройки, которые неудобно делать в Designer"""
                # === НОВОЕ: Применяем валидацию к столбцам 2, 3 и 4 (диапазон 1-1000) ===
        self.numeric_delegate = IntegerRangeDelegate(1, 5000, self)#
        self.table.setItemDelegateForColumn(2, self.numeric_delegate)#
        self.table.setItemDelegateForColumn(3, self.numeric_delegate)#
        self.table.setItemDelegateForColumn(4, self.numeric_delegate)#
        self.double_delegate_5 = DoubleRangeDelegate(
            min_val=-50.0, max_val=50.0, decimals=2, step=0.1, parent=self
        )
        self.table.setItemDelegateForColumn(5, self.double_delegate_5)
        self.double_delegate_6 = DoubleRangeDelegate(
            min_val=0.0, max_val=5, decimals=2, step=0.1, parent=self
        )
        self.table.setItemDelegateForColumn(6, self.double_delegate_6)
        self.double_delegate_7 = DoubleRangeDelegate(
            min_val=0.0, max_val=50., decimals=2, step=0.1, parent=self
        )
        self.table.setItemDelegateForColumn(7, self.double_delegate_7)
        # Растягиваем колонки таблицы
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # Начальные размеры панелей
        self.splitter.setSizes([800, 800])

        # === НОВОЕ: Заполняем комбобокс буквами A-Z ===
        letters = list(string.ascii_uppercase)  # ['A', 'B', 'C', ..., 'Z']
        self.name_pos.addItems(letters)
        self.name_pos.setCurrentText('A')  # По умолчанию выбрана буква A

        # === НОВОЕ: Настройка спинбокса start_time ===
        self.start_time.setMinimum(1)       # Минимум 1 секунда
        self.start_time.setMaximum(1000)    # Максимум 1 час
        self.start_time.setSingleStep(1)    # Шаг изменения
        self.start_time.setSuffix(" сек")   # Суффикс для наглядности
        self.start_time.setValue(10)        # Начальное значение
        
        self.positions.setMinimum(1)       # Минимум 1 секунда
        self.positions.setMaximum(5000)    # Максимум 1 час
        self.positions.setSingleStep(1)    # Шаг изменения
        self.positions.setValue(2000)        # Начальное значение

        self.split.setMinimum(1)       # Минимум 1 секунда
        self.split.setMaximum(100)    # Максимум 1 час
        self.split.setSingleStep(1)    # Шаг изменения
        self.split.setValue(1)  
        
        self.pos_Z.setMinimum(1)
        self.pos_Z.setMaximum(50)
        self.pos_Z.setSingleStep(0.1)
        self.pos_Z.setValue(10)

        TimeStep  = ["сек", "мин", "*30 мин", "час"]
        self.time_step.addItems(TimeStep)
        self.time_step.setCurrentText('сек')
        self.multi  = 1
        

        # Настройка графика
        self.plot_widget.setTitle("Date log .log")
        self.plot_widget.setLabel('left', 'I0')
        self.plot_widget.setLabel('bottom', 'point')
        self.plot_widget.showGrid(x=True, y=True)
        


        # === НОВОЕ: Светлая тема для графика ===
        self.plot_widget.setBackground('w')  # Белый фон
        self.plot_widget.getAxis('left').setPen('k')  # Чёрная ось Y
        self.plot_widget.getAxis('bottom').setPen('k')  # Чёрная ось X
        self.plot_widget.getAxis('left').setTextPen('k')  # Чёрный текст оси Y
        self.plot_widget.getAxis('bottom').setTextPen('k')  # Чёрный текст оси X

    def _connect_signals(self):
        """Подключаем кнопки к функциям"""
        self.btn_load.clicked.connect(self.load_log_file)
        #self.btn_add_row.clicked.connect(self.add_row)
        self.add_to_list.clicked.connect(self.add_to_list_func)
        self.btn_remove_row.clicked.connect(self.remove_row)
        self.btn_remove_all_row.clicked.connect(self.remove_all_row)
        self.btn_generate.clicked.connect(self.generate_macro)
        self.btn_mark_peaks.clicked.connect(self.mark_peaks)
        self.comboBox_scans.currentIndexChanged.connect(self.select_comboBox_scans)
        self.time_step.currentTextChanged.connect(self.changeTimeStep)
 
    # ================= ЛОГИКА ТАБЛИЦЫ =================
    """
    def add_row(self):
        
        
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)
        
        # === НОВОЕ: Берём букву из комбобокса ===
        current_letter = self.name_pos.currentText()
        
        # Считаем, сколько уже строк с такой буквой, чтобы номер был уникальным
        same_letter_count = 0
        for row in range(row_position):
            item = self.table.item(row, 0)
            if item and item.text().startswith(current_letter):
                same_letter_count += 1
        
        position_name = f"{current_letter}{same_letter_count + 1}"
        
        # === НОВОЕ: Берём время из спинбокса ===
        time_value = self.start_time.value()

        self.table.setItem(row_position, 0, QTableWidgetItem(position_name))
        self.table.setItem(row_position, 1, QTableWidgetItem(f"Образец_{row_position+1}"))
        self.table.setItem(row_position, 2, QTableWidgetItem(str(time_value)))
    """
    def changeTimeStep(self,text):
        self.start_time.setSuffix(f" {text}") 
        if text == "сек":
            self.multi = 1
        elif text == "мин":
            self.multi = 60
        elif text == "*30 мин":
            self.multi = 60*30
        elif text == "час":
            self.multi = 60*60
    
    def _create_numeric_item(self, value):
        """Создает ячейку таблицы с числовым типом данных"""
        item = QTableWidgetItem()
        item.setData(Qt.EditRole, int(value))  # Храним как число, а не как строку
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # Выравнивание по правому краю
        return item
    def _create_double_item(self, value):
        """Создает ячейку таблицы с дробным числом"""
        item = QTableWidgetItem()
        item.setData(Qt.EditRole, float(value))
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return item

    def add_to_list_func(self):
        
        time_value = self.start_time.value()*self.multi
        position = self.positions.value()
        split = self.split.value()
        pick_x_new = self.pick_x_new 
        std = self.std
        old_count = self.table.rowCount()
        Pos_Z = self.pos_Z.value()
        self.table.setRowCount(len(self.prefixs)+old_count) 

        for row in range(len(self.prefixs)):
            # 2. FIX: Call setItem directly on self.table, not on 'item'
            self.table.setItem(row+old_count, 0, QTableWidgetItem(self.prefixs[row]))
            self.table.setItem(row+old_count, 1, QTableWidgetItem("Образец"))
            self.table.setItem(row+old_count, 2, self._create_numeric_item(time_value))
            self.table.setItem(row+old_count, 3, self._create_numeric_item(position))
            self.table.setItem(row+old_count, 4, self._create_numeric_item(split))
            self.table.setItem(row+old_count, 5, self._create_double_item(pick_x_new[row]))
            self.table.setItem(row+old_count, 6, self._create_double_item(std[row]))
            self.table.setItem(row+old_count, 7, self._create_double_item(Pos_Z))

    def remove_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
    def remove_all_row(self):
        self.table.setRowCount(0)
        #if current_row >= 0:
        #    self.table.removeRow(current_row)

    # ================= ЗАГРУЗКА И ПАРСИНГ =================
    def load_log_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите .log файл", "",
            "Log Files (*.log);;All Files (*)"
        )
        if file_path:
            self.parse_and_plot(file_path)

    def parse_and_plot(self, file_path):
        spec_data = spec.SpecDataFile(file_path)
        self.all_scans = {}
        for scan_number, scan in spec_data.scans.items():
            if scan.data:
                df = pd.DataFrame(scan.data)
                motor_name = scan.scanCmd.split()[1] if scan.scanCmd else 'motor'
                if motor_name in df.columns:
                    df = df.set_index(motor_name)
            else:
                df = pd.DataFrame()  # пустой скан (например, прерванный #S 84)
            
            self.all_scans[scan_number] = {
                'meta': scan.date,
                'data': df,
            }

        self.comboBox_scans.clear()
        self.comboBox_scans.addItems(self.all_scans.keys())
        self.comboBox_scans.setCurrentIndex(self.comboBox_scans.count()-1)
        scan = self.all_scans[list(self.all_scans.keys())[-1]]
        time,data = scan["meta"],scan["data"]
        if "X" in column_list:
            self.label_scan_data.setText(f"X:{time}")
        elif "Z" in column_list:
            self.label_scan_data.setText(f"Z:{time}")



    def select_comboBox_scans(self):
        text = self.comboBox_scans.currentText()
        scan = self.all_scans[text]
        time,data = scan["meta"],scan["data"]
        column_list = data.columns.tolist()
        
        if "X" in column_list:
            x = data["X"].to_numpy()
            self.label_scan_data.setText(f"X:{time}")
        elif "Z" in column_list:
            x = data["Z"].to_numpy()
            self.label_scan_data.setText(f"Z:{time}")
        y = data["Pil Roi0"].to_numpy()
        ind_sort = x.argsort()
        self.x_data = x[ind_sort]
        self.y_data = y[ind_sort]
        #print(self.x_data)
        #print(self.y_data)
        self.plot_data()


    def plot_data(self):
        self.plot_widget.clear()
        self.plot_items.clear()
        if self.x_data is not None and self.y_data is not None:
            self.plot_widget.plot(self.x_data, self.y_data, pen=pg.mkPen('b', width=1.5))

    # ================= НУМЕРАЦИЯ ПИКОВ =================
    def find_cross_point(self,xData,yData,H):
        yData[0]=0
        yData[-1]=0
        Y1, Y2 = yData[:-1], yData[1:]
        X1, X2 = xData[:-1], xData[1:]
        a1 = (Y2 - Y1) / (X2 - X1)
        b1 = (Y1 * X2 - Y2 * X1) / (X2 - X1)
        x0 = (H - b1) / a1
        x0_mask = (X1 < x0) & (x0 < X2)
        x0_start_end_space = x0[x0_mask]
        start_end_space_list = x0_start_end_space.reshape(len(x0_start_end_space)//2,2)
        return start_end_space_list

    def filter_pick(self,aS,step):
        m = np.max(aS)
        all_m = np.linspace(0 ,m,step)[::-1]
        t   = np.zeros(len(aS))
        idx = np.arange(len(aS))
        for _m in all_m[1:-1]:
            list_range = self.find_cross_point(idx,aS,_m)
            for lr in list_range:
                l,r = lr
                mask = (idx>=l)&(idx<=r)
                sel_idx = idx[mask ]
                ind_max = sel_idx[np.argmax(aS[mask])]
                t[ind_max]+=1 
        #t[t<4]=0
        t = t/np.max(t)*m
        return t
    
    def fill_find_pick(self):
        x,y = self.x_data,self.y_data
        max_y = np.max(y)
        y_new = -(y-max_y)
        s_flt = self.filter_pick(y_new,10)
        main_mask = np.where(s_flt>0)[0]
        pick_x = x[main_mask]
        pick_y = y_new[main_mask]
        all_pick = []
        for xi,yi in zip(pick_x,pick_y):
            start_end_space_list = self.find_cross_point(x,y_new,yi/2)
            l,r = start_end_space_list.T
            mask = (l<=xi) & (xi<=r) 
            lm,rm = start_end_space_list[mask][0]   
            all_pick.append([(lm+rm)/2,np.abs(rm-lm)])
        mean_std = np.round(all_pick,2)
        mean,std = mean_std.T
        pick_y_new = -pick_y/2 + max_y
        mean_new = mean-np.min(mean)

        diff = np.diff(mean_new)
        if len(diff)>0:
            min_diff = np.min(diff)
            d = np.round(diff/min_diff).astype(int)
            ind = np.append([0],np.cumsum(d))
        else:
            ind = np.array([0])

        return mean,pick_y_new, std, ind

    def mark_peaks(self):
        self.plot_widget.clear()
        self.plot_widget.plot(self.x_data,self.y_data, pen=pg.mkPen('b', width=2),s=4)
        prefix     = self.name_pos.currentText()
        start      = self.start_pick.value()
        step       = self.step_pick.value()
        pick_x_new , pick_y_new , std, ind = self.fill_find_pick()
        new_ind = start + ind*step
        self.prefixs = np.array([f"{prefix}{i}" for i in new_ind ])
        self.pick_x_new = pick_x_new 
        self.std = std

        for x,y,s,i in zip(pick_x_new , pick_y_new , std, new_ind):
            self.plot_widget.plot([x-s/2, x+s/2], [y, y], pen=pg.mkPen('r', width=2),s=4) 
            self.plot_widget.plot([x, x], [y-s/2, y+s/2], pen=pg.mkPen('r', width=2),s=4)
            text_item = pg.TextItem(f"{prefix}{i}\nx0:{x}\nw:{s}", color="k")
            self.plot_widget.addItem(text_item)
            text_item.setPos(x+s/2, y) 

    def clear_peak_markers(self):
        for item in self.plot_items:
            self.plot_widget.removeItem(item)
        self.plot_items.clear()

    # ================= ГЕНЕРАЦИЯ МАКРОСА =================
    def generate_macro(self):
        macro_lines = [
            "; --- НАЧАЛО МАКРОСА ---",
            f"; Дата: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ]
        all_data = {}
        for row in range(self.table.rowCount()):
            Id       = self.table.item(row, 0).text()
            Name     = self.table.item(row, 1).text()
            Time     = int(self.table.item(row, 2).data(Qt.EditRole))
            Position = int(self.table.item(row, 3).data(Qt.EditRole))
            Split    = int(self.table.item(row, 4).data(Qt.EditRole))
            Center   = float(self.table.item(row, 5).data(Qt.EditRole))
            Width    = float(self.table.item(row, 6).data(Qt.EditRole))
            Pos_z    = float(self.table.item(row, 7).data(Qt.EditRole))
            all_data[Id] = {"Name":Name,"Time":Time,"Position":Position,"Split":Split,"Center":Center,"Width":Width,"Pos_Z":Pos_z}
        #pos = np.array([for k,val in ])
        pos = np.array([v["Position"] for k,v in all_data.items()])
        ids  = np.array([k for k,v in all_data.items()])
        #print(pos)
        unique_pos = np.unique(pos)
        macro_lines = [
                    "; --- НАЧАЛО МАКРОСА ---",
                    f"; Дата: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ]

        for p in unique_pos:
            ind = np.where(pos==p)[0]
            sel_ids = ids[ind]
            i_sel_ids = np.array([int(i[1:]) for i in sel_ids])
            ind_sort = np.argsort(i_sel_ids)
            sel_ids_sort = sel_ids[ind_sort]
            #print(sel_ids_sort)
            macro_lines.append(f"set pos {p}")
            for id in sel_ids_sort:
                value = all_data[id]
                name = value["Name"]
                time = value["Time"]
                center = value["Center"]
                width = value["Width"] 
                split = value["Split"]
                for i in range(split):
                    t_time= time//split
                    macro_lines.append(f"# {id}:{name}")
                    macro_lines.append(f"umv x {center}")
                    macro_lines.append(f"set_sample_thickness {width}")
                    macro_lines.append(f"_motor_goto_lim wind lim-")
                    macro_lines.append(f"multiexp {split}"+f" {t_time}"*split)
                    macro_lines.append(f"\n")
            #print(sel_ids_sort)
        macro_lines.append("; --- КОНЕЦ МАКРОСА ---")

        #"""
        self.macro_text.setPlainText("\n".join(macro_lines))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MacroGeneratorApp()
    window.show()
    sys.exit(app.exec_())