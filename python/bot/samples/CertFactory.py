'''
Created on Oct 26, 2016

@author: sethjn
'''

import os
filepath = os.path.abspath(os.path.dirname(__file__))
filepath = os.path.join(filepath, "pki")

def getCertsForAddr(*args):
  with open(os.path.join(filepath, "public.cert")) as f:
    return [f.read()]

def getPrivateKeyForAddr(*args):
  with open(os.path.join(filepath, "private.key")) as f:
    return f.read()

def getRootCert(*args):
  with open(os.path.join(filepath, "root.cert")) as f:
    return f.read()
