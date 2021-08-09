# -*- coding: utf-8 -*-
"""
Created on Sun Aug  8 09:55:49 2021

"""
import numpy as np
import time
from tqdm import tqdm
from PyQt5.QtCore import QThread, QMutex, QWaitCondition, pyqtSignal
from PyQt5.QtWidgets import QMainWindow

import matplotlib.pyplot as plt

#%% Dummies
class MyDummyStage(object):
    
    def __init__(self, serial):
        self.pos = 0
        self.serial = None
        
    def go_to_position(self, pos):
        pos_list = np.linspace(self.pos, pos, int(abs(pos-self.pos)/10))
        
        for pos in pos_list:
            #print("position: %.3f" % pos)
            self.pos = pos
            time.sleep(0.3)
        time.sleep(1)
            
        return (self.pos)

class MyDummyPMT(object):
    
    def __init__(self, exp_time_in_ms):
        self._count_mean = 25.6
        self._count_std  = 2.5
        
        self.exp_time_in_ms = exp_time_in_ms
        
    def get_pmt_count(self, exp_time):
        sampled_rnd_count = np.random.normal(self._count_mean, self._count_std)
        pmt_count = sampled_rnd_count * self.exp_time_in_ms
        
        return pmt_count

#%% Example main
class Master(QMainWindow):
    
    def __init__(self):
        super().__init__()
        stage_x = MyDummyStage('x_serial')
        stage_y = MyDummyStage('y_serial')
        self.stage = {"x": MyStage_Thread(stage_x),
                      "y": MyStage_Thread(stage_y)}
        self.pmt   = MyDummyPMT(1)
        
        self.stage_thread = MyScanner_Thread(self.pmt, self.stage)        
        self.pmt_thread   = MyPMT_Thread(self.pmt)
        
        self.pmt_thread.pmt_count.connect(self.pmtPrint)
        self.stage_thread.scan_arr.connect(self.scanPrint)
        
    def stageMove(self, x, y):
        self.stage_thread.start(x, y)  # Jaeun question: does start() need params?
        print("Stage moving done.")
        return
        
    def contScan_run(self, time_in_ms):
        self.pmt_thread.exp_time   = time_in_ms
        self.pmt_thread.single_run = False
        print("Contiuous scanning go.") 
        self.pmt_thread.start(1)  # Jaeun question: does start() need params?
        return
        
    def contScan_stop(self):
        self.pmt_thread.single_run = True       
        
        while self.pmt_thread.isRunning():
            time.sleep(0.1)
        print ("Continuous scan is finished.")
        
    def arrayScan(self, x_start, x_end, x_step, y_start, y_end, y_step):
        self.stage_thread.mutex.unlock()  # Jaeun question: where is mutex lock?
        x_scan = np.arange(x_start, x_end, x_step)
        y_scan = np.arange(y_start, y_end, y_step)
        
        x_arr, y_arr = np.meshgrid(x_scan, y_scan)
        
        # zigzag
        x_arr[::2] = np.flip(x_arr[::2], axis=1)
        
        self.stage_thread.im_shape = np.shape(x_arr)
        self.stage_thread.x_list = x_arr.reshape(-1)
        self.stage_thread.y_list = y_arr.reshape(-1)
        self.stage_thread.im_list = np.zeros(np.shape(x_arr.reshape(-1)))
        
        print("Scanning ready")
        
        self.stage_thread.start()
        
    def pmtPrint(self, pmt_float):
        print("PMT counts: %.3f" % pmt_float)
        
    def scanPrint(self, scan_dict):
        print("recieved x: %.3f, y: %.3f, pmt: %.2f" % (scan_dict["x"], scan_dict["y"], scan_dict["pmt"]))
        img = self.stage_thread.im_list.reshape(self.stage_thread.im_shape)
        img[::2] = np.flip(img[::2], axis=1)
        
        plt.imshow(img)
        
    def scanPause(self):
        self.stage_thread.pause_flag = True
        
    def scanContinue(self):
        self.stage_thread.pause_flag = False
        self.stage_thread.cond.wakeAll()
        
        
class MyScanner_Thread(QThread):
    
    scan_arr = pyqtSignal(dict)
    
    def __init__(self, pmt, stage:dict):
        super().__init__()
        """
        Scanner thread takes stage in dict because the axes are user-defined.
        """
        self.pmt = pmt
        self.exp_time = 1
        
        if not isinstance(stage, dict):
            raise TypeError ("stage must be a dict.")
        self.stage = stage
        
        # Scanning args
        self.im_shape = 0
        self.x_list  = []
        self.y_list  = []
        self.im_list = []
        
        # conditions
        self.cond = QWaitCondition()
        self.mutex = QMutex()
        self.pause_flag = False
        
    def run(self):
        for idx in tqdm(range(len(self.x_list))):
            self.mutex.lock()
                
            self.stage["x"].target_position = self.x_list[idx]
            self.stage["y"].target_position = self.y_list[idx]
            
						# Threads are started asynchronuously
            self.stage["x"].start()
            self.stage["y"].start()
            
						# The handling thread waits until both finish their job.
            self.stage["x"].wait()
            self.stage["y"].wait()
            
            self.im_list[idx] = pmt_count = self.pmt.get_pmt_count(self.exp_time)
            
            self.scan_arr.emit({"x": self.x_list[idx],
                                "y": self.y_list[idx],
                                'pmt': pmt_count})
            if self.pause_flag:
                self.cond.wait(self.mutex)
                print("Paused scanning")
                
            self.mutex.unlock()
    
    
class MyStage_Thread(QThread):
    
    stage_position = pyqtSignal(float)
    
    def __init__(self, stage):
        super().__init__()
        self.stage = stage
        self.target_position = 0
        
    def run(self):
        pos = self.stage.go_to_position(self.target_position)
        self.stage_position.emit(pos)
          
    
class MyPMT_Thread(QThread):
    
    pmt_count = pyqtSignal(float)
    
    def __init__(self, pmt):
        super().__init__()
        self.pmt = pmt
        self.single_run = False
        self.exp_time = 0
        
    def run(self):
        while True:
            cnt = self.pmt.get_pmt_count(self.exp_time)
            self.pmt_count.emit(cnt)
            time.sleep(0.2)
            if self.single_run:
                break
```