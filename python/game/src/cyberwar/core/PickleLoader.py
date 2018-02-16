'''
Created on Feb 12, 2018

@author: seth_
'''

import pickle

class PickleLoader:
    @classmethod
    def TableName(cls):
        raise NotImplementedError("Subclasses must implement class method TableName()")
    
    @classmethod
    def InitializeDatabase(cls, db):
        sqlTemplate = "CREATE TABLE IF NOT EXISTS {} (objId INTEGER, objData TEXT)"
        db.execute(sqlTemplate.format(cls.TableName()))
        
    def tableName(self):
        return self.TableName()
    
    def unload(self, obj):
        return [pickle.dumps(obj)] # One element tuple
    
    def load(self, row):
        objId, objData = row
        return pickle.loads(objData)