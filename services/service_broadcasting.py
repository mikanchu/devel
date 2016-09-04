#!/usr/bin/python
#service_broadcasting.py
#
# <<<COPYRIGHT>>>
#
#
#
#

"""
.. module:: service_broadcasting

"""

from services.local_service import LocalService

def create_service():
    return BroadcastingService()
    
class BroadcastingService(LocalService):
    
    service_name = 'service_broadcasting'
    config_path = 'services/broadcasting/enabled'
    
    scope = [] # set to [idurl1,idurl2,...] to receive only messages from certain nodes
    
    def dependent_on(self):
        return ['service_p2p_hookups', 
                'service_entangled_dht',
                ]
    
    def start(self):
        from broadcast import broadcasters_finder
        from broadcast import broadcaster_node
        from broadcast import broadcast_listener
        from broadcast import broadcast_service
        from main.config import conf
        from main import settings
        broadcasters_finder.A('init')
        if settings.enableBroadcastRouting():
            broadcaster_node.A('init', broadcast_service.on_incoming_broadcast_message)
            broadcaster_node.A().addStateChangedCallback(
                self._on_broadcaster_node_switched)
        else:
            broadcast_listener.A('init', broadcast_service.on_incoming_broadcast_message)
            broadcast_listener.A().addStateChangedCallback(
                self._on_broadcast_listener_switched)
            broadcast_listener.A('connect', self.scope)
        conf().addCallback(
            'services/broadcasting/routing-enabled',
            self._on_broadcast_routing_enabled_disabled
        )
        return True
    
    def stop(self):
        from broadcast import broadcaster_node
        from broadcast import broadcasters_finder
        from broadcast import broadcast_listener
        from main.config import conf
        if broadcaster_node.A() is not None:
            broadcaster_node.A().removeStateChangedCallback(
                self._on_broadcaster_node_switched)
            broadcaster_node.A('shutdown')
        if broadcast_listener.A() is not None:
            broadcast_listener.A().removeStateChangedCallback(
                self._on_broadcast_listener_switched)
            broadcast_listener.A('shutdown')
        broadcasters_finder.A('shutdown')
        conf().removeCallback('services/broadcasting/routing-enabled')
        return True
    
    def request(self, request, info):
        from logs import lg
        from p2p import p2p_service
        from main import settings
        words = request.Payload.split(' ')
        if len(request.Payload) > 1024 * 10:
            return None
        try:
            mode = words[1][:10]
        except:
            lg.exc()
            return None
        if mode != 'route' and mode != 'listen':
            lg.out(8, "service_broadcasting.request DENIED, wrong mode provided : %s" % mode)
            return None
        if not settings.enableBroadcastRouting():
            lg.out(8, "service_broadcasting.request DENIED, broadcast routing disabled")
            return p2p_service.SendFail(request, 'broadcast routing disabled')
        from broadcast import broadcaster_node
        if not broadcaster_node.A():
            lg.out(8, "service_broadcasting.request DENIED, broadcast routing disabled")
            return p2p_service.SendFail(request, 'broadcast routing disabled')
        if broadcaster_node.A().state not in ['BROADCASTING', 'OFFLINE', 'BROADCASTERS?',]:
            lg.out(8, "service_broadcasting.request DENIED, current state is : %s" % broadcaster_node.A().state)
            return p2p_service.SendFail(request, 'currently not broadcasting')
        if mode == 'route':
            broadcaster_node.A('new-broadcaster-connected', request.OwnerID)
            lg.out(8, "service_broadcasting.request ACCEPTED, mode: %s" % words)
            return p2p_service.SendAck(request, 'accepted')
        if mode == 'listen':
            broadcaster_node.A().add_listener(request.OwnerID, ' '.join(words[2:]))
            lg.out(8, "service_broadcasting.request ACCEPTED, mode: %s" % words[1])
            return p2p_service.SendAck(request, 'accepted')
        return None

    def _on_broadcast_routing_enabled_disabled(self, path, value, oldvalue, result):
        from logs import lg
        from broadcast import broadcaster_node
        from broadcast import broadcast_listener
        from broadcast import broadcast_service
        lg.out(2, 'service_broadcasting._on_broadcast_routing_enabled_disabled : %s->%s : %s' % (
            oldvalue, value, path))
        if not value:
            if broadcaster_node.A() is not None:
                broadcaster_node.A().removeStateChangedCallback(
                    self._on_broadcaster_node_switched)
                broadcaster_node.A('shutdown')
            broadcast_listener.A('init', broadcast_service.on_incoming_broadcast_message)
            broadcast_listener.A().addStateChangedCallback(
                self._on_broadcast_listener_switched)
            broadcast_listener.A('connect', self.scope)
        else:
            if broadcast_listener.A() is not None:
                broadcast_listener.A().removeStateChangedCallback(
                    self._on_broadcast_listener_switched)
                broadcast_listener.A('shutdown')
            broadcaster_node.A('init', broadcast_service.on_incoming_broadcast_message)
            broadcaster_node.A().addStateChangedCallback(
                self._on_broadcaster_node_switched)
    
    def _on_broadcast_listener_switched(self, oldstate, newstate, evt, args):
        from logs import lg
        from twisted.internet import reactor
        from broadcast import broadcast_listener
        if newstate == 'OFFLINE':
            reactor.callLater(60, broadcast_listener.A, 'connect', self.scope)
            lg.out(8, 'service_broadcasting._on_broadcast_listener_switched will try to connect again after 1 minute')
 
    def _on_broadcaster_node_switched(self, oldstate, newstate, evt, args):
        from logs import lg
        from twisted.internet import reactor
        from broadcast import broadcaster_node
        if newstate == 'OFFLINE':
            reactor.callLater(60, broadcaster_node.A, 'reconnect')
            lg.out(8, 'service_broadcasting._on_broadcaster_node_switched will try to reconnect again after 1 minute')
 
 
#     def cancel(self, request, info):
#         from logs import lg
#         from p2p import p2p_service
#         words = request.Payload.split(' ')
#         try:
#             mode = words[1][:20]
#         except:
#             lg.exc()
#             return p2p_service.SendFail(request, 'wrong mode provided')
#         if mode == 'route' and False: # and not settings.getBroadcastRoutingEnabled():      
#             # TODO check if this is enabled in settings
#             # so broadcaster_node should be existing already
#             lg.out(8, "service_broadcasting.request DENIED, broadcast routing disabled")
#             return p2p_service.SendFail(request, 'broadcast routing disabled')
#         from broadcast import broadcaster_node
#         if broadcaster_node.A().state not in ['BROADCASTING', ]:
#             lg.out(8, "service_broadcasting.request DENIED, current state is : %s" % broadcaster_node.A().state)
#             return p2p_service.SendFail(request, 'currently not broadcasting')        
#         broadcaster_node.A('broadcaster-disconnected', request)
#         return p2p_service.SendAck(request, 'accepted')
