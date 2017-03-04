'''
Created on Feb 4, 2017

@author: sethjn
'''

import sqlite3

class sqlite3db(object):
    def __init__(self, filename):
        self.db = sqlite3.open(filename)
        
    def RequiredTable(cls, tableName, spec):
        sqlQuery = "CREATE TABLE IF NOT EXISTS %s (" % tableName
        for columnName, columnType in spec.items():
            sqlQuery += "%s"
        self.db.query("CREATE TABLE IF NOT EXIST")
        