'''
Created on Feb 12, 2018

@author: seth_
'''
import unittest

from cyberwar.core.Board import Board, ContentsRequest, PutRequest, LocateRequest 
from cyberwar.core.Board import InitializeObjectRequest, RemoveRequest, InvalidLocation
from cyberwar.core.ObjectStore import ObjectStore
import sqlite3

class Test_Board(unittest.TestCase):

    class TestLoader:
        def initializeDatabase(self, db):
            db.execute("CREATE TABLE IF NOT EXISTS game_objects (objId INTEGER, field1 INTEGER, field2 TEXT)")
        def newObject(self, field1, field2):
            return Test_Board.TestObject(field1, field2)
        def load(self, row):
            objId, field1, field2 = row
            return self.newObject(field1, field2)
        def unload(self, obj):
            return [obj.field1, obj.field2]
        def tableName(self): return "game_objects"
        
    class TestObject:
        def __init__(self, f1, f2):
            self.field1 = f1
            self.field2 = f2

    def testBasic1(self):
        db = sqlite3.connect(":memory:")
        
        Board.NewBoard(db, 10, 10)
        
        store = ObjectStore(db)
        
        loader = self.TestLoader()
        loader.initializeDatabase(db)
        
        store.registerLoader("testtype", loader)
        store.initialize()
        
        obj1 = loader.newObject(1,"Ivan")
        #obj2 = loader.newObject(2, "Bob")
        #obj3 = loader.newObject(3, "Sally")
        
        #store.addObjectToGame("testtype", obj1)
        #store.addObjectToGame("testtype", obj2)
        #store.addObjectToGame("testtype", obj3)
        
        b = Board(db, store)
        
        response = b.send(InitializeObjectRequest("app", obj1, "testtype"))
        self.assertTrue(response)
        
        response = b.send(ContentsRequest("app", 5, 5))
        
        self.assertTrue(response)
        self.assertEqual(response.Value, [])
        
        response = b.send(PutRequest("app", 5, 5, obj1))
        
        self.assertTrue(response)
        self.assertEqual(response.Value, True)
        
        response = b.send(ContentsRequest("app", 5, 5))
        
        self.assertTrue(response)
        self.assertEqual(response.Value, [obj1])
        
        response = b.send(PutRequest("app", 4, 4, obj1))
        
        self.assertTrue(response)
        self.assertEqual(response.Value, True)
        
        response = b.send(LocateRequest("app", obj1))
        
        self.assertTrue(response)
        self.assertEqual(response.Value, (4,4))
        
        response = b.send(ContentsRequest("app", 11, 11))
        self.assertTrue(isinstance(response, InvalidLocation))
        self.assertFalse(response)
        
        response = b.send(RemoveRequest("app", obj1))
        self.assertTrue(response)
        
        response = b.send(ContentsRequest("app", 4, 4))
        self.assertEqual(response.Value, [])
        


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testBasic1']
    unittest.main()