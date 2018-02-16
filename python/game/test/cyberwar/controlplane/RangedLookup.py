'''
Created on Feb 14, 2018

@author: seth_
'''
import unittest
from cyberwar.controlplane.RangedLookup import RangedLookup
from cyberwar.controlplane.objectdefinitions import ControlPlaneObject, Observer


class Test_RangedLookup(unittest.TestCase):


    def testBasic1(self):
        
        fixedLocation = (25,25)
        observationRange = 5
        for i in range(fixedLocation[0]-(observationRange+1), fixedLocation[0]+(observationRange+2)):
            for j in range(fixedLocation[1]-(observationRange+1), fixedLocation[1]+(observationRange+2)):
                checkLocation = (i,j)
                distance = abs(checkLocation[0]-fixedLocation[0]) + abs(checkLocation[1]-fixedLocation[1])
                if distance >= observationRange:
                    self.assertFalse(RangedLookup.InRange(fixedLocation, checkLocation, observationRange))
                else:
                    self.assertTrue(RangedLookup.InRange(fixedLocation, checkLocation, observationRange))
        
        obj1 = ControlPlaneObject(Observer(observationRange=5))
        obj2 = ControlPlaneObject(Observer(observationRange=7))
        
        r = RangedLookup()
        
        fixedLocation = (32,27)
        r.observe(obj1, fixedLocation)
        r.observe(obj2, fixedLocation)
        
        self.assertEqual(r.getLocation(obj1), fixedLocation)
        self.assertEqual(r.getLocation(obj2), fixedLocation)
        
        for i in range(fixedLocation[0]-(observationRange+1), fixedLocation[0]+(observationRange+2)):
            for j in range(fixedLocation[1]-(observationRange+1), fixedLocation[1]+(observationRange+2)):
                checkLocation = (i,j)
                observers = r.getObserversInRange(checkLocation)
                if RangedLookup.InRange(checkLocation, fixedLocation, 7):
                    self.assertTrue(obj2 in observers)
                else:
                    self.assertFalse(obj2 in observers)
                if RangedLookup.InRange(checkLocation, fixedLocation, 5):
                    self.assertTrue(obj1 in observers)
                else:
                    self.assertFalse(obj1 in observers)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()