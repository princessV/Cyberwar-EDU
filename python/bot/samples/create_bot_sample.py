'''
Created on Feb 27, 2017

@author: sethjn
'''
import os, shutil
from dulwich.tests.test_server import ONE

SAMPLE_DIRECTORY = os.path.dirname(__file__)

class SampleCreator(object):

    ADDRESS_FILE = "address.txt"
    PASSWORD_FILE = "password.txt"
    
    CMD_GENERATE_KEY = 'openssl genrsa -out %(KEY_FILENAME)s 2048'
    CMD_GENERATE_CSR = 'openssl req -new -key %(KEY_FILENAME)s -out %(CSR_FILENAME)s -subj /C=US/ST=MD/L=Baltimore/O=Cyberwar/OU=Bot/CN=%(COMMON_NAME)s -batch'
    CMD_SELFSIGN_ROOT_CERT = 'openssl x509 -req -days 30 -in %(ROOT_CSR_FILENAME)s -signkey %(ROOT_KEY_FILENAME)s -out %(ROOT_CERT_FILENAME)s -set_serial 1' 
    CMD_SIGN_ADDR_CERT = 'openssl x509 -req -days 30 -in %(ADDR_CSR_FILENAME)s -CA %(ROOT_CERT_FILENAME)s -CAkey %(ROOT_KEY_FILENAME)s -out %(ADDR_CERT_FILENAME)s -set_serial 2'
    
    def __init__(self):
        self.botAddress = "0.0.0.1"
        self.botClientAddress = "0.0.0.2"
        self.password = "222222"
        
    def generatePki(self, targetDir):
        lastDir = os.getcwd()
        
        os.chdir(targetDir)
        certFactorySrcFile = os.path.join(SAMPLE_DIRECTORY, "CertFactory.py")
        shutil.copy(certFactorySrcFile, ".")
        
        # create pki subfolder
        if not os.path.exists("pki"): os.mkdir("pki")
        
        # Go into pki folder to create certs/keys
        os.chdir('pki')
        # create root cert
        commonPkiArgs = {"ROOT_CSR_FILENAME":"root.csr", "ROOT_KEY_FILENAME":"root.key", "ROOT_CERT_FILENAME":"root.cert"}
        rootPkiArgs = {"KEY_FILENAME":"root.key", "CSR_FILENAME":"root.csr"}
        rootPkiArgs["COMMON_NAME"] = "0."
        rootPkiArgs.update(commonPkiArgs)
        
        os.system(self.CMD_GENERATE_KEY % rootPkiArgs)
        os.system(self.CMD_GENERATE_CSR % rootPkiArgs)
        os.system(self.CMD_SELFSIGN_ROOT_CERT % rootPkiArgs)
        
        addrPkiArgs = {"KEY_FILENAME":"private.key", "CSR_FILENAME":"bot.csr", "ADDR_CSR_FILENAME":"bot.csr", "ADDR_CERT_FILENAME":"public.cert"}
        addrPkiArgs["COMMON_NAME"] = self.botAddress
        addrPkiArgs.update(commonPkiArgs)
        os.system(self.CMD_GENERATE_KEY % addrPkiArgs)
        os.system(self.CMD_GENERATE_CSR % addrPkiArgs)
        print self.CMD_SIGN_ADDR_CERT % addrPkiArgs
        os.system(self.CMD_SIGN_ADDR_CERT % addrPkiArgs)
        
        os.chdir("..")
        os.system("tar -czf CertFactory.tar.gz CertFactory.py pki/root.cert pki/public.cert pki/private.key")
        
        os.chdir("pki")
        addrPkiArgs["COMMON_NAME"] = self.botClientAddress
        os.system(self.CMD_GENERATE_KEY % addrPkiArgs)
        os.system(self.CMD_GENERATE_CSR % addrPkiArgs)
        os.system(self.CMD_SIGN_ADDR_CERT % addrPkiArgs)
        
        os.chdir(lastDir)

    def createBotSample(self, targetDirectory="."):
        addressFile = os.path.join(targetDirectory,self.ADDRESS_FILE)
        with open(addressFile, "w+") as f:
            f.write(self.botAddress)
            
        passwordFile = os.path.join(targetDirectory, self.PASSWORD_FILE)
        with open(passwordFile, "w+") as f:
            f.write(self.password)
        
    def createBotClientSample(self, targetDirectory="."):
        self.generatePki(targetDirectory)
        protocolStackSrc = os.path.join(SAMPLE_DIRECTORY, "NullProtocol.py")
        protocolStackTarget = os.path.join(targetDirectory, "ProtocolStack")
        
        if not os.path.exists(protocolStackTarget): 
            os.mkdir(protocolStackTarget)
            
        shutil.copy(protocolStackSrc, os.path.join(protocolStackTarget, "__init__.py"))

        os.system("cd %s; tar -czf ProtocolStack.tar.gz ProtocolStack" % targetDirectory)
        
        brainTarget = os.path.join(targetDirectory, "Brain")
        if not os.path.exists(brainTarget):
            os.mkdir(brainTarget)
            
        brainFileSrc = os.path.join(SAMPLE_DIRECTORY, "remote_worker.py")
        shutil.copy(brainFileSrc, brainTarget)
        brainInit = os.path.join(brainTarget, "__init__.py")
        with open(brainInit,"w+") as f:
            f.write("from remote_worker import *\n")
        os.system("cd %s; tar -czf Brain.tar.gz Brain" % targetDirectory)
        
if __name__=="__main__":
    import sys
    USAGE = """
%s <bot_directory> <bot_client_directory>

Create a Sample Bot Setup. The sample is created in *TWO* directories; one
for the bot, and one for the client to reprogram it.
""" % sys.argv[0]
    args = []
    opts = {}
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            k,v = arg.split("=")
            opts[k] = v
        else:
            args.append(arg)
            
    if not len(args) == 2:
        sys.exit(USAGE)
    botDir, botClientDir = args
    print botDir, botClientDir
    creator = SampleCreator()
    creator.createBotSample(botDir)
    creator.createBotClientSample(botClientDir)