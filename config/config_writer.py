import configparser

config = configparser.ConfigParser()
config['motors'] = {'x_serno': '27000481',  #m07
                    'y_serno': '27250228'}
#with open('M07.ini', 'w') as configfile:
#    config.write(configfile)                   

'''
config['motors'] = {'x_serno' : "27002644", 
                    'y_serno' : "27002621"} 
config['fpga'] = {'com_port' : "COM7",
                  'dna'      : "blah"}

with open('EA109.ini', 'w') as configfile:
    config.write(configfile)
'''