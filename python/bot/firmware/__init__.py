
import sys, os

# we need to add the botprogramming path to the sys path for imports
BotInterfacePath = os.path.dirname(__file__) # Get the current directory
BotProgrammingPath = os.path.join(BotInterfacePath, "../../botprogramming")
BotProgrammingPath = os.path.abspath(BotProgrammingPath)
sys.path.insert(0,BotProgrammingPath)

from controller import Controller
#from ReprogrammingClientProtocol import ReprogrammingClientProtocol
