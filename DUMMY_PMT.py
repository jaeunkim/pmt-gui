# -*- coding: utf-8 -*-
"""
Created on Mon Aug 02 2021

@author: jaeunkim
"""
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
        
        self.cnt = 0
        
    def PMT_count_measure(self):
        self.sequencer = DUMMY_SEQUENCER()
        self.cnt += 1
        return self.cnt


class DUMMY_SEQUENCER():
    def release():
        pass


#%%
if __name__ == '__main__':
    PMT = PMT()
    count = PMT.PMT_count_measure()
