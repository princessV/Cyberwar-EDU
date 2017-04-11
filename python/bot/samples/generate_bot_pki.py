'''
Created on Feb 27, 2017

@author: sethjn
'''
import random, os, shutil


MAX_SERIAL_NUMBER = 1000000
def generatePki(botAddress, botClientAddress, serialNumbers=None):
    if not serialNumbers:
        rootSerial, botSerial, botClientSerial = random.randint(0,MAX_SERIAL_NUMBER), random.randint(0,MAX_SERIAL_NUMBER), random.randint(0,MAX_SERIAL_NUMBER)
    else:
        rootSerial, botSerial, botClientSerial = serialNumbers
    botRoot = botAddress.split(".")[0]
    botClientRoot = botClientAddress.split(".")[0]
    if botRoot != botClientRoot:
        raise Exception("Cannot generate PKI for two addresses with different root values (%s, %s)" % (botRoot, botClientRoot))

    CMD_GENERATE_KEY = 'openssl genrsa -out %(KEY_FILENAME)s 2048'
    CMD_GENERATE_CSR = 'openssl req -new -key %(KEY_FILENAME)s -out %(CSR_FILENAME)s -subj /C=US/ST=MD/L=Baltimore/O=Cyberwar/OU=Bot/CN=%(COMMON_NAME)s -batch'
    CMD_SELFSIGN_ROOT_CERT = 'openssl x509 -req -days 30 -in %(ROOT_CSR_FILENAME)s -signkey %(ROOT_KEY_FILENAME)s -out %(ROOT_CERT_FILENAME)s -set_serial %(ROOT_SERIAL_NUMBER)d' 
    CMD_SIGN_ADDR_CERT = 'openssl x509 -req -days 30 -in %(ADDR_CSR_FILENAME)s -CA %(ROOT_CERT_FILENAME)s -CAkey %(ROOT_KEY_FILENAME)s -out %(ADDR_CERT_FILENAME)s -set_serial %(ADDR_SERIAL_NUMBER)d'
    
    lastDir = os.getcwd()
        
    # create pki subfolder
    if not os.path.exists("pki"): os.mkdir("pki")
        
    # Go into pki folder to create certs/keys
    os.chdir('pki')
    # create root cert
    commonPkiArgs = {"ROOT_CSR_FILENAME":"root.csr", "ROOT_KEY_FILENAME":"root.key", "ROOT_CERT_FILENAME":"root.cert",
                     "ROOT_SERIAL_NUMBER":rootSerial}
    rootPkiArgs = {"KEY_FILENAME":"root.key", "CSR_FILENAME":"root.csr"}
    rootPkiArgs["COMMON_NAME"] = "%s." % botRoot
    rootPkiArgs.update(commonPkiArgs)
        
    os.system(CMD_GENERATE_KEY % rootPkiArgs)
    os.system(CMD_GENERATE_CSR % rootPkiArgs)
    os.system(CMD_SELFSIGN_ROOT_CERT % rootPkiArgs)
        
    addrPkiArgs = {"KEY_FILENAME":"private.key", "CSR_FILENAME":"bot.csr", "ADDR_CSR_FILENAME":"bot.csr", "ADDR_CERT_FILENAME":"public.cert"}
    addrPkiArgs["COMMON_NAME"] = botAddress
    addrPkiArgs["ADDR_SERIAL_NUMBER"] = botSerial
    addrPkiArgs.update(commonPkiArgs)
    os.system(CMD_GENERATE_KEY % addrPkiArgs)
    os.system(CMD_GENERATE_CSR % addrPkiArgs)
    print CMD_SIGN_ADDR_CERT % addrPkiArgs
    os.system(CMD_SIGN_ADDR_CERT % addrPkiArgs)
        
    os.chdir("..")
    os.system("tar -czf CertFactory.tar.gz CertFactory.py pki/root.cert pki/public.cert pki/private.key")
        
    os.chdir("pki")
    addrPkiArgs["COMMON_NAME"] = botClientAddress
    addrPkiArgs["ADDR_SERIAL_NUMBER"] = botClientSerial
    os.system(CMD_GENERATE_KEY % addrPkiArgs)
    os.system(CMD_GENERATE_CSR % addrPkiArgs)
    os.system(CMD_SIGN_ADDR_CERT % addrPkiArgs)
        
    os.chdir(lastDir)

if __name__=="__main__":
    import sys
    USAGE = """
%s <bot_address> <bot_client_address>

Create a Sample Bot Setup. The sample is created in *TWO* directories; one
for the bot, and one for the client to reprogram it.
""" % sys.argv[0]
   
    args = sys.argv[1:] 
    if not len(args) == 2:
        sys.exit(USAGE)
    botAddr, botClientAddr = args
    print "Creating PKI for bot with address %s and C&C address %s" % (botAddr, botClientAddr)
    generatePki(botAddr, botClientAddr)
