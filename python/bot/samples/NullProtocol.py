from twisted.internet.protocol import Factory, Protocol
from playground.network.common.Protocol import StackingProtocolMixin, StackingFactoryMixin, StackingTransport


class NullTransport(StackingTransport):
	pass

class NullProtocol(Protocol, StackingProtocolMixin):
	def connectionMade(self):
		Protocol.connectionMade(self)
		self.higherProtocol().makeConnection(NullTransport(self.transport))

	def connectionLost(self, reason=None):
		Protocol.connectionLost(self)
		self.higherProtocol().transport = None
		self.higherProtocol().connectionLost(reason)

	def dataReceived(self, data):
		self.higherProtocol().dataReceived(data)

class ConnectFactory(Factory, StackingFactoryMixin):
    protocol = NullProtocol
    
class ListenFactory(Factory, StackingFactoryMixin):
    protocol = NullProtocol
