'''
Created on Feb 14, 2018

@author: seth_
'''

from ..controlplane.objectdefinitions import ControlPlaneObjectAttribute, Tangible, Observer
from ..core.PickleLoader import PickleLoader, pickle
import subprocess, os, asyncio

HEALTH_CHECK_TIME = 30.0

class BrainEnabled(ControlPlaneObjectAttribute):
    REQUIRED = [Tangible]
    
    RUNNING_PIDS = set([])
    
    WORKING_DIR = "/home/sethjn/WIN_DEV/CyberWar-EDU/python/game/pypy-sandbox/src"
    RPYTHON_DIR = "/home/sethjn/WIN_DEV/pypy_35/pypy3-v5.9.0-src/"
    
    @classmethod
    def ShutdownAll(cls):
        for pid in cls.RUNNING_PIDS:
            try:
                os.kill(pid, 1)
            except:
                pass
        cls.RUNNING_PIDS = set([])
            
    
    def __init__(self, directory, brainIdentifier):
        super().__init__("brain_enabled")
        self._directory = directory
        self._brainIdentifier = brainIdentifier
        self._p = None
        self._pid = None
        
        self.start()
        
    def brainIdentifier(self):
        return self._brainIdentifier
        
    def start(self, retryCount=0):
        args = ["python", "./brain_interact.py", "--tmp={}".format(self._directory),
                "--gameobj={}".format(self._brainIdentifier), 
                "pypy3-c-sandbox", "-S", "brain.py"]
        print("Starting",args)
        env = os.environ.copy()
        env["PYTHONPATH"] = self.RPYTHON_DIR
        self._p = subprocess.Popen(args, cwd=self.WORKING_DIR, env=env)
        self._pid = self._p.pid
        self.RUNNING_PIDS.add(self._pid)
        
        asyncio.get_event_loop().call_later(HEALTH_CHECK_TIME, self._checkHealth, retryCount+1)
        
    def stop(self):
        self.brainRunning() and self._p.terminate()
        self.RUNNING_PIDS.remove(self._pid)
        self._pid = None
        
    def brainRunning(self):
        return self._p and (self._p.poll() is None)
        
    def _checkHealth(self, retryCount):
        if self.brainRunning():
            # still running.
            asyncio.get_event_loop().call_later(HEALTH_CHECK_TIME, self._checkHealth, 0)
        elif retryCount < 10:
            self.start(retryCount)
        else:
            pass # Log error?

class BrainControlledObjectLoader(PickleLoader):
    OBJECT_TYPE = "brain_controlled_object"
    
    @classmethod
    def TableName(cls):
        return "cyberwar_brain_loader"
    
    # THIS SHOULDNT GO HERE. But I don't know where to put it yet.
    # Loaders need to be more general. 
    BRAINID_TO_OBJECT = {}
    
    @classmethod
    def GetObjectByBrainID(cls, brainId):
        return cls.BRAINID_TO_OBJECT.get(brainId, None)
    
    def load(self, row):
        objId, objData = row
        object = pickle.loads(objData)
        brainAttr = object.getAttribute(BrainEnabled)
        
        self.BRAINID_TO_OBJECT[brainAttr.brainIdentifier()] = object
        
        if brainAttr._pid:
            os.kill(brainAttr._pid, 9)
        brainAttr.start()
        return object
    
    def unload(self, object):
        brainAttr = object.getAttribute(BrainEnabled)
        
        # remove pickle data that cannot be restored from brainenabled attribute
        p = brainAttr._p
        brainAttr._p = None
        
        dbData = super().unload(object)
        
        brainAttr._p = p
        return dbData
    
Loader = BrainControlledObjectLoader