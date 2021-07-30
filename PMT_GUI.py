# -*- coding: utf-8 -*-
"""
Created on Thu Jul 22 2021

@author: Jaeun Kim
@email: jaeunkim@snu.ac.kr

Sequencer files are taken from syspath
PMT and KDC101 files should be in the same folder as this program
"""

################ Importing Sequencer Programs ###################
import sys
sys.path.append("Q://Experiment_Scripts/Chamber_4G_SNU/SecularFreq/")
from SequencerProgram_v1_07 import SequencerProgram, reg
import SequencerUtility_v1_01 as su
from ArtyS7_v1_02 import ArtyS7
import HardwareDefinition_SNU_v4_01 as hd

################# Importing Hardware APIs #######################
from KDC101 import KDC101  # Thorlabs KDC101 Motor Controller
from PMT_v2_00 import PMT

################ Importing GUI Dependencies #####################
import os, time
from PyQt5 import uic
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtCore    import *

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

filename = os.path.abspath(__file__)
dirname = os.path.dirname(filename)
uifile = dirname + '/PMT_GUI.ui'
Ui_Form, QtBaseClass = uic.loadUiType(uifile)

class PMT_GUI(QtWidgets.QMainWindow, Ui_Form):
    scan_request = pyqtSignal(float, float, float)
    
    def __init__(self, window_title="", parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.setWindowTitle(window_title)

        # Plot
        self.toolbar, self.ax, self.canvas = self.create_canvas(self.image_viewer)
        
        # Connect sockets and signals
        self.BTN_start_scanning.clicked.connect(self.start_scanning)
        self.BTN_select_save_file.clicked.connect(self.select_save_file)
        self.BTN_stop_scanning.clicked.connect(self.stop_scanning)

        # Internal 
        self.x_pos_list = []
        self.y_pos_list = []
        self.pmt_exposure_time_in_ms = -1
        self.num_points_done = -1
        self.latest_count = -1
        
        # Setup: scanning thread
        self.scanning_thread = ScanningThread(x_motor_serno = "27002644", y_motor_serno = "27002621", fpga_com_port = "COM7")
        self.scanning_thread.scan_result.connect(self.receive_result)
        self.scan_request.connect(self.scanning_thread.register_request)
        self.scanning_thread.running_flag = False
    
    def update_progress_label(self):
        self.LBL_latest_count.setText(str(self.latest_count))
        self.LBL_points_done.setText(str(self.num_points_done))
        
    def start_scanning(self):
        # read scan settings
        self.x_pos_list = np.arange(float(self.LE_x_start.text()), 
                                       float(self.LE_x_stop.text()), float(self.LE_x_step.text()))
        self.y_pos_list = np.arange(float(self.LE_y_start.text()), 
                                       float(self.LE_y_stop.text()), float(self.LE_y_step.text()))
        self.pmt_exposure_time_in_ms = self.LE_pmt_exposure_time_in_ms.text()
        print("scanning for", self.x_pos_list, self.y_pos_list, self.pmt_exposure_time_in_ms)
        
        # numpy array to store scanned image
        self.x_num = len(self.x_pos_list)
        self.y_num = len(self.y_pos_list)
        self.image = np.zeros((self.x_num, self.y_num))
        
        # update scan_progress labels
        self.num_points_done = 0
        self.latest_count = 0
        self.update_progress_label()
        self.LBL_total_points.setText(str(self.x_num * self.y_num))
        
        # initiate scanning
        if not self.scanning_thread.running_flag:
            self.scanning_thread.running_flag = True
            self.scanning_thread.start()
        self.send_request()
        
    def send_request(self):
        """
        initiates a scan request to the scanning thread
        calculates the scan position based on self.num_points_done
        """
        x_pos = self.x_pos_list[self.num_points_done % self.x_num]
        y_pos = self.y_pos_list[self.num_points_done // self.x_num]
        exposure_time = float(self.LE_pmt_exposure_time_in_ms.text())
        
        # zigzag scanning to minimize backlash
        if y_pos % 2 == 1:  # for even-numbered rows
            original_index = self.num_points_done % self.x_num
            new_index = -1 * (original_index + 1)  # counting from the end of the list
            x_pos = self.x_pos_list[new_index]  # overwriting x_pos
            
        self.scan_request.emit(x_pos, y_pos, exposure_time)
    
    def receive_result(self, x_pos, y_pos, exposure_time, pmt_count):
        # print("entered receive_result ", x_pos, y_pos, exposure_time, pmt_count)

        # update GUI (image & progress)
        x_index = np.where(self.x_pos_list == x_pos)[0][0]
        y_index = np.where(self.y_pos_list == y_pos)[0][0]
        print('x, y', x_index, y_index)
        self.image[x_index, y_index] = pmt_count
        self.show_img()
        self.latest_count = pmt_count
        self.num_points_done += 1
        self.update_progress_label()
        
        # send new request 
        if self.num_points_done != self.x_num * self.y_num:  # if scanning not finished
            self.send_request()
        else:  # if scanning is done
            self.scanning_thread.running_flag = False
        
        # save result only if a line is finished
        if x_index == len(self.x_pos_list) - 1:  # end of a line
            # put data into the correct shape
            x_pos_list_np = np.array(self.x_pos_list)
            y_pos_list_np = np.repeat(y_pos, len(self.x_pos_list))  # expanding a number to a list
            exposure_time_list_np = np.repeat(exposure_time, len(self.x_pos_list))
            pmt_count_list_np = self.image[:,y_index]
            
            # create dataframe & save
            data_chunk_to_append = np.stack([x_pos_list_np, y_pos_list_np, 
                                             exposure_time_list_np, pmt_count_list_np])
            df = pd.DataFrame(data_chunk_to_append).transpose()
    
            if self.save_file is not None:
                with open(self.save_file, 'a') as f:
                    df.to_csv(f, index=False, header=False, line_terminator='\n')
        
    def select_save_file(self):
        # dialog to choose a file
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        self.save_file, _ = QFileDialog.getOpenFileName(self,"load a .tif file", "","*", options=options)
        if not self.save_file:
            return  # user pressed "cancel"

        # show savefile path to GUI
        self.LBL_save_file.setText(self.save_file)
    
    def create_canvas(self, frame):
        fig = plt.Figure(tight_layout=True)
        ax = fig.add_subplot(1,1,1)
        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, self)
        
        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        frame.setLayout(layout)
        
        return toolbar, ax, canvas
    
    def show_img(self):
        # if self.flip_horizontally_cbox.isChecked():
        #     img = np.flip(img, 1)
        # if self.flip_vertically_cbox.isChecked():
        #     img = np.flip(img, 0)
        
        #TODO let user choose vmin and vmax (where?)
        #self.ax.imshow(img, vmin=self.vmin, vmax=self.vmax)
        self.ax.clear()
        self.ax.imshow(self.image)
        self.canvas.draw()
    
    def stop_scanning(self):
        self.scanning_thread.stop_thread_and_clean_up_hardware()

class ScanningThread(QThread):
    """
    Communicates with relevant hardwares (PMT, motors)
    Takes scan request by motor positions and emits scan result
    """
    scan_result = pyqtSignal(float, float, float, float)
    
    def __init__(self, x_motor_serno, y_motor_serno, fpga_com_port):
        super().__init__()
        
        # internal variables
        self.running_flag = False
        self.scan_todo_flag = False  # True when there's a scanning job to do
        self.x_pos = -1
        self.y_pos = -1
        self.exposure_time = -1
        
        # hardware info
        self.x_motor_serno = x_motor_serno
        self.y_motor_serno = y_motor_serno
        self.fpga_com_port = fpga_com_port
        
        self.setup_hardwares()

    
    def setup_hardwares(self):
        self.pmt = PMT(N_500us = 2, T_500us = 50000-3-2, max_run_count = 1, port = self.fpga_com_port)
 
        self.x_motor = KDC101(self.x_motor_serno)
        self.x_motor.load_dll()
        self.x_motor.open()
        self.x_motor.start_polling()
        
        self.y_motor = KDC101(self.y_motor_serno)
        self.y_motor.load_dll()
        self.y_motor.open()
        self.y_motor.start_polling()
        
    def run(self):
        while self.running_flag:
            if self.scan_todo_flag:
                self.move_to_requested_position()  # should be atomic
                my_count = self.pmt.PMT_count_measure()  # should be atomic
                self.scan_todo_flag = False  # job done
                self.scan_result.emit(self.x_pos, self.y_pos, self.exposure_time, my_count)
            time.sleep(0.2)
    
    def register_request(self, x_pos, y_pos, exposure_time):
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.exposure_time = exposure_time
        self.scan_todo_flag = True
        print("registered on thread", x_pos, y_pos, exposure_time)

    def move_to_requested_position(self):
        self.x_motor.move_to_position(self.x_pos)
        self.y_motor.move_to_position(self.y_pos)
    
    def stop_thread_and_clean_up_hardware(self):
        self.running_flag = False
        
        # motor cleanup
        self.x_motor.stop_polling()
        self.x_motor.close()
        self.y_motor.stop_polling()
        self.y_motor.close()
        
        # fpga cleanup
        self.pmt.sequencer.release()
        
        
if __name__ == "__main__":
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    my_pmt_gui = PMT_GUI(window_title="PMT GUI")
    my_pmt_gui.show()
