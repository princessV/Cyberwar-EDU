'''
Created on Feb 4, 2017

@author: sethjn
'''

class AgentSpecification(object):
    @classmethod
    def required(cls):
        pass
    
    def __init__(self, className, hp):
        self.name = className