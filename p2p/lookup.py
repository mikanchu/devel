#!/usr/bin/python
# lookup.py
#
# Copyright (C) 2008-2016 Veselin Penev, http://bitdust.io
#
# This file (lookup.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#

"""
.. module:: lookup.

.. role:: red
"""

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import sys
import time

try:
    from twisted.internet import reactor
except:
    sys.exit('Error initializing twisted.internet.reactor in lookup.py')

from twisted.internet.defer import DeferredList, Deferred

#------------------------------------------------------------------------------

from logs import lg

#------------------------------------------------------------------------------

_KnownIDURLsDict = {}
_DiscoveredIDURLsList = []
_NextLookupTask = None
_LookupMethod = None  # method to get a list of random nodes
_ObserveMethod = None  # method to get IDURL from given node
_ProcessMethod = None  # method to do some stuff with discovered IDURL

#------------------------------------------------------------------------------


def init(lookup_method=None, observe_method=None, process_method=None):
    """
    
    """
    global _LookupMethod
    global _ObserveMethod
    global _ProcessMethod
    _LookupMethod = lookup_method
    _ObserveMethod = observe_method
    _ProcessMethod = process_method
    if _Debug:
        lg.out(_DebugLevel, "lookup.init")


def shutdown():
    """
    
    """
    global _LookupMethod
    global _ObserveMethod
    global _ProcessMethod
    _LookupMethod = None
    _ObserveMethod = None
    _ProcessMethod = None
    if _Debug:
        lg.out(_DebugLevel, "lookup.shutdown")

#------------------------------------------------------------------------------


def known_idurls():
    global _KnownIDURLsDict
    return _KnownIDURLsDict


def discovered_idurls():
    global _DiscoveredIDURLsList
    return _DiscoveredIDURLsList

#------------------------------------------------------------------------------


def consume_discovered_idurls(count=1):
    if not discovered_idurls():
        if _Debug:
            lg.out(_DebugLevel, 'lookup.consume_discovered_idurls returns empty list')
        return []
    results = []
    while len(results) < count and discovered_idurls():
        results.append(discovered_idurls().pop(0))
    if _Debug:
        lg.out(_DebugLevel, 'lookup.consume_discovered_idurls : %s' % results)
    return results


def extract_discovered_idurls(count=1):
    if not discovered_idurls():
        if _Debug:
            lg.out(_DebugLevel, 'lookup.extract_discovered_idurls returns empty list')
        return []
    results = discovered_idurls()[:count]
    if _Debug:
        lg.out(_DebugLevel, 'lookup.extract_discovered_idurls : %s' % results)
    return results


def schedule_next_lookup(current_lookup_task, delay=60):
    global _NextLookupTask
    if _NextLookupTask:
        if _Debug:
            lg.out(_DebugLevel, 'lookup.schedule_next_lookup SKIP, next lookup will start soon')
        return
    if _Debug:
        lg.out(_DebugLevel, 'lookup.schedule_next_lookup after %d seconds' % delay)
    _NextLookupTask = reactor.callLater(
        delay,
        start,
        count=current_lookup_task.count,
        consume=current_lookup_task.consume,
        lookup_method=current_lookup_task.lookup_method,
        observe_method=current_lookup_task.observe_method,
        process_method=current_lookup_task.process_method
    )


def reset_next_lookup():
    """
    """
    global _NextLookupTask
    if _NextLookupTask and not _NextLookupTask.called and not _NextLookupTask.cancelled:
        _NextLookupTask.cancel()
        _NextLookupTask = None

#------------------------------------------------------------------------------

def start(count=1, consume=True, lookup_method=None, observe_method=None, process_method=None,):
    """
    NOTE: no parallel threads, DHT lookup can be started only one at time.
    """
    t = DiscoveryTask(
        count=count,
        consume=consume,
        lookup_method=lookup_method,
        observe_method=observe_method,
        process_method=process_method,
    )
    if len(discovered_idurls()) > count:
        if _Debug:
            lg.out(_DebugLevel - 4, 'lookup.start  knows %d discovered nodes, SKIP and return %d nodes' % (
                len(discovered_idurls()), count))
        if consume:
            t.result_defer.callback(consume_discovered_idurls(count))
        else:
            t.result_defer.callback(extract_discovered_idurls(count))
        return t
    reset_next_lookup()
    if _Debug:
        lg.out(_DebugLevel - 4, 'lookup.start  new DiscoveryTask created for %d nodes' % count)
    t.start()
    return t  # .result_defer

#------------------------------------------------------------------------------

class DiscoveryTask(object):

    def __init__(self,
                 count,
                 consume=True,
                 lookup_method=None,
                 observe_method=None,
                 process_method=None,):
        global _LookupMethod
        global _ObserveMethod
        global _ProcessMethod
        self.lookup_method = lookup_method or _LookupMethod
        self.observe_method = observe_method or _ObserveMethod
        self.process_method = process_method or _ProcessMethod
        self.started = time.time()
        self.count = count
        self.consume = consume
        self.succeed = 0
        self.failed = 0
        self.lookup_now = False
        self.stopped = False
        self.lookup_task = None
        self.result_defer = Deferred(canceller=lambda x: self.stop())
        # self.result_defer = Deferred(canceller=lambda d: setattr(self, 'stopped', True))

    def __del__(self):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.__del__')

    def start(self):
        if self.stopped:
            lg.warn('DiscoveryTask already stopped')
            return None
        if self.lookup_task and not self.lookup_task.called:
            lg.warn('lookup_nodes() method already called')
            return self.lookup_task
        self.lookup_task = self.lookup_nodes()
        self.lookup_task.addBoth(lambda x: setattr(self, 'lookup_task', None))
        self.lookup_task.addErrback(lambda err: None if self.stopped else schedule_next_lookup(self))
        if self.result_defer:
            self.lookup_task.addErrback(lambda err: [self.report_result([]), self.close()])
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask.start')
        return self.lookup_task

    def stop(self):
        self.stopped = True
        if self.lookup_task and not self.lookup_task.called:
            self.lookup_task.cancel()
            self.lookup_task = None
        if _Debug:
            lg.out(_DebugLevel, 'lookup.DiscoveryTask.stop')

    def close(self):
        self.stopped = True
        self.lookup_method = None
        self.observe_method = None
        self.process_method = None
        self.result_defer = None
        if _Debug:
            lg.out(_DebugLevel, 'lookup.close finished in %f seconds' % round(time.time() - self.started, 3))

    def lookup_nodes(self):
        if self.stopped:
            return
        if self.lookup_now:
            return
        self.lookup_now = True
        if _Debug:
            lg.out(_DebugLevel, 'lookup.lookup_nodes')
        d = self.lookup_method()
        d.addCallback(self.on_nodes_discovered)
        d.addErrback(lambda err: setattr(self, 'lookup_now', False))
        return d

    def observe_nodes(self, nodes):
        if self.stopped:
            return []
        observe_list = []
        for node in nodes:
            d = self.observe_method(node)
            d.addCallback(self.on_node_observed, node)
            d.addErrback(self.on_node_failed, node)
            observe_list.append(d)
        dl = DeferredList(observe_list, consumeErrors=False)
        dl.addCallback(self.on_all_nodes_observed)
        return nodes

    def report_result(self, results=None):
        if results is None:
            if self.consume:
                results = consume_discovered_idurls(self.count)
            else:
                results = extract_discovered_idurls(self.count)
        if self.result_defer:
            self.result_defer.callback(results)
        self.result_defer = None

    def on_node_succeed(self, node, info):
        self.succeed += 1
        if _Debug:
            lg.out(_DebugLevel + 10, 'lookup.on_succeed %s info: %s' % (node, info))

    def on_node_failed(self, err, arg=None):
        self.failed += 1
        if _Debug:
            lg.warn('%r : %r' % (arg, err))

    def on_node_observed(self, idurl, node):
        if self.stopped:
            return None
        if idurl in known_idurls():
            if _Debug:
                lg.out(_DebugLevel + 10, 'lookup.on_node_observed SKIP %r' % idurl)
            return None
        if _Debug:
            lg.out(_DebugLevel + 10, 'lookup.on_node_observed %r : %r' % (node, idurl))
        d = self.process_method(idurl, node)
        d.addErrback(self.on_node_failed, node)
        d.addCallback(self.on_identity_cached, node)
        return d

    def on_node_processed(self, node, idurl):
        if _Debug:
            if len(discovered_idurls()) < self.count:
                lg.out(_DebugLevel + 10, 'lookup.on_node_processed %s, but need more nodes' % idurl)
            else:
                lg.out(_DebugLevel + 10, 'lookup.on_node_processed %s, have enough nodes now' % idurl)

    def on_all_nodes_observed(self, results):
        if self.stopped:
            return
        if _Debug:
            lg.out(_DebugLevel, 'lookup.on_all_nodes_observed results: %d, discovered nodes: %d' % (
                len(results), len(discovered_idurls())))
        if len(discovered_idurls()) == 0:
            self.report_result()
            self.close()
            return
        # if len(discovered_idurls()) < self.count:
        #     # self.lookup_task = self.lookup_nodes()
        #     self.start()
        #     return
        self.report_result()
        self.close()

    def on_identity_cached(self, idurl, node):
        if self.stopped:
            return None
        if idurl is None:
            return None
        discovered_idurls().append(idurl)
        known_idurls()[idurl] = time.time()
        self.on_node_succeed(node, idurl)
        reactor.callLater(0, self.on_node_processed, node, idurl)
        if _Debug:
            lg.out(_DebugLevel + 10, 'lookup.on_identity_cached : %s' % idurl)
        return idurl

    def on_nodes_discovered(self, nodes):
        if _Debug:
            lg.out(_DebugLevel, 'lookup.on_nodes_discovered : %s, stopped=%s' % (nodes, self.stopped))
        if self.stopped:
            self.close()
            return
        self.lookup_now = False
        # if not nodes or len(discovered_idurls()) + len(nodes) < self.count:
            # self.lookup_task = self.lookup_nodes()
            # self.start()
        if len(nodes) == 0:
            self.report_result(result=[])
            self.close()
            return []
        return self.observe_nodes(nodes)

#------------------------------------------------------------------------------
