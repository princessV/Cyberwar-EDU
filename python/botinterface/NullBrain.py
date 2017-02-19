'''
Created on Feb 17, 2017

@author: sethjn
'''
from time import sleep
from threading import RLock

class NullBrain(object):
    def __init__(self):
        self.__stopped = False
        self.__running = True
        self.__gameLock = RLock()
    
    def gameLoop(self):
        with self.__gameLock:
            self.__running = True
            
        while not self.__stopped:
            sleep(1.0)
            
        with self.__gameLock:
            self.__running = False
        
    def status(self):
        with self.__gameLock:
            if self.__running:
                return "Running"
            elif not self.__stopped:
                return "Not yet running"
            else:
                return "Stopped"
        
    def stop(self):
        with self.__gameLock:
            self.__stopped = True
        