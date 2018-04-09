'''
Created on Feb 14, 2018

@author: seth_
'''

from ..controlplane.objectdefinitions import ControlPlaneObjectAttribute, Tangible, Observer
from ..controlplane.objectdefinitions import ControlPlaneObject
from ..core.PickleLoader import PickleLoader, pickle
import subprocess, os, asyncio

HEALTH_CHECK_TIME = 30.0

def kill(pid):
    try:
        os.kill(pid, 2)
    except:
        pass
    
# TODO:
# Broken things. The launching thing is a hack. Unify. Simplify.
class BrainEnabled(ControlPlaneObjectAttribute):
    REQUIRED = [Tangible]
    
    RUNNING_PIDS = set([])
    LOAD_REQUIRED = []
    
    @classmethod
    def ShutdownAll(cls):
        print("Shutdown all {}".format(cls.RUNNING_PIDS))
        brains = list(cls.RUNNING_PIDS) # make a copy. stop clears itself from list
        for brain in brains:
            brain.stop()
        cls.RUNNING_PIDS = set([])
            
    
    def __init__(self, directory, brainIdentifier):
        super().__init__("brain_enabled")
        self._directory = directory
        self._brainIdentifier = brainIdentifier
        self._p = None
        self._pid = None
        self._stopped = False
        
        self.start()
        
    def __str__(self):
        return "Brain({}, {})".format(self._directory, self._brainIdentifier)
    
    def brainPath(self):
        return self._directory
        
    def brainIdentifier(self):
        return self._brainIdentifier
        
    def start(self, retryCount=0):
        if not Loader.PYPY_PATH:
            raise Exception("Cannot start brain. Pypy path not configured.")
        self._stopped = False
        # Turn on PNetworking
        subprocess.call("pnetworking on", shell=True, cwd=self._directory)
        
        # NOTE ON HEAPSIZE. PyPy currently breaks if heapsize is too small. Even 10m was
        # too small. Based on some internal stuff in pypy, I decided to try 32m and that
        # seemed to work.
        args = ["python", "./brain_interact.py", "--heapsize=32m", "--tmp={}".format(self._directory),
                "--gameobj={}".format(self._brainIdentifier), 
                "pypy3-c-sandbox", "-S", "brain.py"]
        print("Starting",args)
        env = os.environ.copy()
        env["PYTHONPATH"] = Loader.PYPY_PATH
        print("Seeting PYTHONPATH to ",env["PYTHONPATH"])
        self._p = subprocess.Popen(args, cwd=os.getcwd(), env=env)
        self._pid = self._p.pid
        self.RUNNING_PIDS.add(self)
        
        asyncio.get_event_loop().call_later(HEALTH_CHECK_TIME, self._checkHealth, retryCount+1)
        
    def stop(self):
        if self._stopped: return
        self._stopped = True
        #self.brainRunning() and self._p.terminate()
        # just in case that didn't work. Let's force an os kill
        kill(self._pid)
        
        # shutdown pnetworking
        print("calling pnetworking off in {}".format(self._directory))
        subprocess.call("pnetworking off", shell=True, cwd=self._directory)
        
        self.RUNNING_PIDS.remove(self)
        self._pid = None
        
    def brainRunning(self):
        return self._p and (self._p.poll() is None)
        
    def _checkHealth(self, retryCount):
        if self._stopped: return
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
    
    CAN_LAUNCH_BRAINS = False
    
    # Don't know where this should go either. It is set by outside modules
    PYPY_PATH = None
    
    @classmethod
    def GetObjectByBrainID(cls, brainId):
        return cls.BRAINID_TO_OBJECT.get(brainId, None)
    
    def load(self, row):
        objId, objData = row
        object = pickle.loads(objData)
        ControlPlaneObject.OBJECT_ID = max(object.numericIdentifier(), ControlPlaneObject.OBJECT_ID)
        brainAttr = object.getAttribute(BrainEnabled)
        
        self.BRAINID_TO_OBJECT[brainAttr.brainIdentifier()] = object
        ControlPlaneObject.OBJECT_LOOKUP[object.numericIdentifier()] = object
        
        if brainAttr._pid:
            kill(brainAttr._pid)
        if not self.CAN_LAUNCH_BRAINS:
            BrainEnabled.LOAD_REQUIRED.append((brainAttr))
        else:
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