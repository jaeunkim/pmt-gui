# -*- coding: utf-8 -*-
"""
Created on Wed Jul 31 22:44:57 2019

@author: seongmyeongseok
"""
import sys
sys.path.append("Q://Experiment_Scripts/Chamber_4G_SNU/SecularFreq/")
from SequencerProgram_v1_07 import SequencerProgram, reg
import HardwareDefinition_SNU_v4_01 as hd
import SequencerUtility_v1_01 as su
from ArtyS7_v1_02 import ArtyS7
import numpy as np
import time

class PMT():
    def __init__(self, 
                 N_500us = 2,
                 T_500us = 50000-3-2,
                 max_run_count = 100,
                 port = 'COM11'
                 ):
        self.N_500us = N_500us
        self.T_500us = T_500us
        self.max_run_count = max_run_count
        self.port = port
        self.run_counter = reg[0]
        self.wait_counter = reg[1]
        self.PMT_sp= SequencerProgram()
        self.setup_PMT_sp()
        
    
    #  def __del__(self):
    #    self.sequencer.close

    def setup_PMT_sp(self):
        #Reset run_numb0.41er
        #print("setup_PMT")
        self.PMT_sp.load_immediate(self.run_counter, 0, 'reg[0] will be used for run number')
        
        # Start of the repeating part
        self.PMT_sp.repeat_run = \
        \
        self.PMT_sp.load_immediate(self.wait_counter,  0)
        self.PMT_sp.trigger_out([hd.PMT1_counter_reset], 'Reset single counter')
        self.PMT_sp.set_output_port(hd.counter_control_port, [(hd.PMT1_counter_enable, 1), ], 'Start counter')
        
        self.PMT_sp.repeat_wait = \
        \
        self.PMT_sp.wait_n_clocks(self.T_500us, 'Wait for 50000 * 10 ns unconditionally')
        self.PMT_sp.add(self.wait_counter, self.wait_counter, 1)
        self.PMT_sp.branch_if_less_than('repeat_wait', self.wait_counter, self.N_500us)
        
        self.PMT_sp.set_output_port(hd.counter_control_port, [(hd.PMT1_counter_enable, 0), ], 'Stop counter')
        
        self.PMT_sp.read_counter(reg[10], hd.PMT1_counter_result)
        self.PMT_sp.write_to_fifo(self.run_counter, reg[10], reg[10], 10, 'Counts within 1 ms')
        
        
        # Decide whether we will repeat running
        self.PMT_sp.decide_repeat = \
        \
        self.PMT_sp.add(self.run_counter, self.run_counter, 1, 'run_counter++')
        self.PMT_sp.branch_if_less_than('repeat_run', self.run_counter, self.max_run_count)
        self.PMT_sp.stop()
        
        #print("setup complete")
     
    def flush_out_FIFO(self, debug = False):
        pass
#        self.sequencer.flush_Output_FIFO(debug= debug)
        
    def PMT_count_measure(self):
        
        self.sequencer = ArtyS7(self.port)
        self.sequencer.check_version(hd.HW_VERSION)
        self.PMT_sp.program(show=False, target=self.sequencer)
        
        self.sequencer.auto_mode()
        self.sequencer.send_command('START SEQUENCER')
        
        data_count = self.sequencer.fifo_data_length()
        data = self.sequencer.read_fifo_data(data_count)
        total_data_count = data_count
        
        while self.sequencer.sequencer_running_status() == 'running':
            data_count = self.sequencer.fifo_data_length()
            data += self.sequencer.read_fifo_data(data_count)
            total_data_count += data_count
        
        data_count = self.sequencer.fifo_data_length()
        while data_count > 0:
            data += self.sequencer.read_fifo_data(data_count)
            total_data_count += data_count
            data_count = self.sequencer.fifo_data_length()
        
        if total_data_count == self.max_run_count:
            print('FIFO data length:', total_data_count)
            
        else:
            print("Error: FIFO data length:", total_data_count)
            return None
		
        self.sequencer.close()
		
        real_data = []
        for n in range(len(data)):
            real_data.append(data[n][1])
        
        # PMT_count
        print(np.average(real_data))
        return np.average(real_data)
        
#%%
if __name__ == '__main__':
    PMT = PMT(port = 'COM7')
    count = PMT.PMT_count_measure()
