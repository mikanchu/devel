#!/usr/bin/env python
# conftest.py
#
# Copyright (C) 2008-2018 Stanislav Evseev, Veselin Penev  https://bitdust.io
#
# This file (conftest.py) is part of BitDust Software.
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

import pytest
import time
import requests
import asyncio
import itertools

from .testsupport import run_ssh_command_and_wait, open_tunnel, tunnel_url

#------------------------------------------------------------------------------

DHT_SEED_NODES = 'dht_seed_1:14441, dht_seed_2:14441, stun_1:14441, stun_2:14441'

PROXY_ROUTERS = 'http://is:8084/proxy_server_1.xml http://is:8084/proxy_server_2.xml'

# TODO: keep this list up to date with docker-compose links
ALL_ROLES = {
    'dht-seeds': [
        'dht_seed_1',
        'dht_seed_2',
    ],
    'identity-servers': [
        'is',
    ],
    'stun-servers': [
        'stun_1',
        'stun_2',
    ],
    'proxy-servers': [
        'proxy_server_1',
        'proxy_server_2',
    ],
    'suppliers': [
        'supplier_1',
        'supplier_2',
        'supplier_3',
        'supplier_4',
        'supplier_5',
        'supplier_6',
        'supplier_7',
        'supplier_8',
    ],
    'customers': [
        {'name': 'customer_1', 'join_network': True, 'num_suppliers': 2, },
        {'name': 'customer_2', 'join_network': True, 'num_suppliers': 2, },
        {'name': 'customer_3', 'join_network': True, 'num_suppliers': 2, },
        {'name': 'customer_4', 'join_network': True, 'num_suppliers': 2, },
        {'name': 'customer_5', 'join_network': True, 'num_suppliers': 4, },

        {'name': 'customer_backup', 'join_network': True, 'num_suppliers': 2, },
        {'name': 'customer_restore', 'join_network': False, 'num_suppliers': 2, },
    ],
}


def _get_nodes_from_roles(roles):
    temp_nodes = itertools.chain.from_iterable(roles.values())
    nodes = []
    for n in temp_nodes:
        try:
            n = n['name']
        except (TypeError, KeyError):
            pass

        nodes.append(n)

    return nodes


ALL_NODES = _get_nodes_from_roles(ALL_ROLES)


#------------------------------------------------------------------------------

def health_check(node):
    count = 0
    while True:
        if count > 5:
            assert False, f'node {node} is not healthy after 5 seconds'

        try:
            response = requests.get(tunnel_url(node, 'process/health/v1'))
        except Exception as exc:
            print(f'[{node}] retry {count}   GET:process/health/v1  :  {exc}')
            response = None

        if response and response.status_code == 200 and response.json()['status'] == 'OK':
            break

        time.sleep(1)
        count += 1
    print(f'health_check [{node}] : OK\n')


def create_identity(node, identity_name):
    count = 0
    while True:
        if count > 10:
            assert False, f'node {node} failed to create identity after 10 retries'
        response = requests.post(
            url=tunnel_url(node, 'identity/create/v1'),
            json={
                'username': identity_name,
            },
        )
        if response.json()['status'] == 'OK':
            # print('\n' + response.json()['result'][0]['xml'] + '\n')
            break
        if not response.status_code == 200 or (response.json()['status'] == 'ERROR' and response.json()['errors'][0] == 'network connection error'):
            count += 1
            # print('[%s] retry %d   POST:identity/create/v1  username=%s     network connection error' % (node, count, identity_name, ))
            continue

        assert False, f'[{node}] bad response from /identity/create/v1'

    print(f'create_identity [{node}] with name {identity_name} : OK\n')


def connect_network(node):
    count = 0
    response = requests.get(url=tunnel_url(node, 'network/connected/v1?wait_timeout=1'))
    assert response.json()['status'] == 'ERROR'
    while True:
        if count > 5:
            assert False, f'node {node} failed to connect to the network after few retries'
        response = requests.get(tunnel_url(node, 'network/connected/v1?wait_timeout=5'))
        if response.json()['status'] == 'OK':
            break
        count += 1
        # print('[%s] retry %d   GET:network/connected/v1' % (node, count, ))
        time.sleep(5)
    print(f'connect_network [{node}] : OK\n')

#------------------------------------------------------------------------------

def start_daemon(node):
    run_ssh_command_and_wait(node, 'mkdir -pv /root/.bitdust/metadata/')
    run_ssh_command_and_wait(node, 'echo "docker" > /root/.bitdust/metadata/networkname')
    bitdust_daemon = run_ssh_command_and_wait(node, 'bitdust daemon')
    print('\n' + bitdust_daemon[0].strip())
    assert (
        bitdust_daemon[0].strip().startswith('main BitDust process already started') or
        bitdust_daemon[0].strip().startswith('new BitDust process will be started in daemon mode')
    )
    print(f'start_daemon [{node}] OK\n')


def stop_daemon(node, skip_checks=False):
    bitdust_stop = run_ssh_command_and_wait(node, 'bitdust stop')
    print('\n' + bitdust_stop[0].strip())
    if not skip_checks:
        assert (
            (
                bitdust_stop[0].strip().startswith('BitDust child processes found') and
                bitdust_stop[0].strip().endswith('BitDust stopped')
            ) or (
                bitdust_stop[0].strip().startswith('found main BitDust process:') and
                bitdust_stop[0].strip().endswith('BitDust process finished correctly')
            )
        )
    print(f'stop_daemon [{node}] OK\n')

#------------------------------------------------------------------------------

def start_identity_server(node):
    print(f'\nNEW IDENTITY SERVER at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # configure and enable ID server
    run_ssh_command_and_wait(node, f'bitdust set services/identity-server/host {node}')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-server/enabled true')
    # start BitDust daemon
    start_daemon(node)
    health_check(node)
    print(f'\nSTARTED IDENTITY SERVER [{node}]\n')


def start_dht_seed(node, wait_seconds=0):
    print(f'\nNEW DHT SEED (with STUN SERVER) at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # enable Stun server
    run_ssh_command_and_wait(node, 'bitdust set services/ip-port-responder/enabled true')
    # start BitDust daemon
    print(f'sleep {wait_seconds} seconds')
    time.sleep(wait_seconds)
    start_daemon(node)
    health_check(node)
    print(f'\nSTARTED DHT SEED (with STUN SERVER) [{node}]\n')


def start_stun_server(node):
    print(f'\nNEW STUN SERVER at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/private-messages/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/nodes-lookup/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/enabled false')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # enable Stun server
    run_ssh_command_and_wait(node, 'bitdust set services/ip-port-responder/enabled true')
    # start BitDust daemon
    start_daemon(node)
    health_check(node)
    print(f'\nSTARTED STUN SERVER [{node}]\n')


def start_proxy_server(node, identity_name):
    print(f'\nNEW PROXY SERVER {identity_name} at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-transport/enabled false')
    # configure ID servers
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/min-servers 1')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/max-servers 1')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # enable ProxyServer service
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled true')
    # start BitDust daemon and create new identity for proxy server
    start_daemon(node)
    health_check(node)
    create_identity(node, identity_name)
    connect_network(node)
    print(f'\nSTARTED PROXY SERVER [{node}]\n')


def start_supplier(node, identity_name):
    print(f'\nNEW SUPPLIER {identity_name} at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')
    # configure ID servers
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/min-servers 1')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/max-servers 1')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # set desired Proxy router
    run_ssh_command_and_wait(node, f'bitdust set services/proxy-transport/preferred-routers "{PROXY_ROUTERS}"')
    # enable supplier service
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled true')
    # start BitDust daemon and create new identity for supplier
    start_daemon(node)
    health_check(node)
    create_identity(node, identity_name)
    connect_network(node)
    print(f'\nSTARTED SUPPLIER [{node}]\n')


def start_customer(node, identity_name, join_network=True, num_suppliers=2):
    print(f'\nNEW CUSTOMER {identity_name} at [{node}]\n')
    # use short key to run tests faster
    run_ssh_command_and_wait(node, 'bitdust set personal/private-key-size 1024')
    # disable unwanted services
    run_ssh_command_and_wait(node, 'bitdust set services/supplier/enabled false')
    run_ssh_command_and_wait(node, 'bitdust set services/proxy-server/enabled false')
    # configure ID servers
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/min-servers 1')
    run_ssh_command_and_wait(node, 'bitdust set services/identity-propagate/max-servers 1')
    # configure DHT udp port
    run_ssh_command_and_wait(node, 'bitdust set services/entangled-dht/udp-port "14441"')
    # set desired Proxy router
    run_ssh_command_and_wait(node, f'bitdust set services/proxy-transport/preferred-routers "{PROXY_ROUTERS}"')
    # enable customer service and prepare tests
    run_ssh_command_and_wait(node, 'bitdust set services/customer/enabled true')
    run_ssh_command_and_wait(node, f'bitdust set services/customer/suppliers-number {num_suppliers}')
    # create randomized file to test file upload/download
    run_ssh_command_and_wait(node, f'dd bs=1024 count=1 skip=0 if=/dev/urandom of=/{node}/file_{node}.txt')
    run_ssh_command_and_wait(node, f'dd bs=1024 count=1 skip=0 if=/dev/urandom of=/{node}/second_file_{node}.txt')
    # start BitDust daemon and create new identity for supplier
    start_daemon(node)
    health_check(node)
    if join_network:
        create_identity(node, identity_name)
        connect_network(node)
    print(f'\nSTARTED CUSTOMER [{node}]\n')

#------------------------------------------------------------------------------

async def open_one_tunnel(node):
    open_tunnel(node)


def open_all_tunnels(event_loop, nodes):
    event_loop.run_until_complete(asyncio.wait([
        asyncio.ensure_future(open_one_tunnel(node)) for node in nodes
    ]))

#------------------------------------------------------------------------------

async def start_one_supplier(supplier):
    start_supplier(node=supplier, identity_name=supplier)


async def start_one_customer(customer):
    start_customer(
        node=customer['name'],
        identity_name=customer['name'],
        join_network=customer['join_network'],
        num_suppliers=customer['num_suppliers'],
    )


def start_all_nodes(event_loop):
    # TODO: keep up to date with docker-compose links
    print('\nStarting nodes\n') 

    for number, dhtseed in enumerate(ALL_ROLES['dht-seeds']):
        # first seed to be started immediately, all other seeds must wait a bit before start
        start_dht_seed(
            node=dhtseed,
            # wait_seconds=(10 if number > 0 else 0),
            wait_seconds=15,
        )

    for idsrv in ALL_ROLES['identity-servers']:
        start_identity_server(node=idsrv)

    for stunsrv in ALL_ROLES['stun-servers']:
        start_stun_server(node=stunsrv)

    for proxysrv in ALL_ROLES['proxy-servers']:
        start_proxy_server(node=proxysrv, identity_name=proxysrv)

    event_loop.run_until_complete(asyncio.wait([
        asyncio.ensure_future(start_one_supplier(supplier)) for supplier in ALL_ROLES['suppliers']
    ]))

    event_loop.run_until_complete(asyncio.wait([
        asyncio.ensure_future(start_one_customer(customer)) for customer in ALL_ROLES['customers']
    ]))

    print('\nALL NODES STARTED\n')


async def stop_one_node(node):
    stop_daemon(node, skip_checks=True)


def stop_all_nodes(event_loop):
    print('\nstop all nodes\n')
    event_loop.run_until_complete(asyncio.wait([
        asyncio.ensure_future(stop_one_node(node)) for node in ALL_NODES
    ]))
    print('\nALL NODES STOPPED\n')

#------------------------------------------------------------------------------

async def report_one_node(node):
    main_log = run_ssh_command_and_wait(node, 'cat /root/.bitdust/logs/main.log')[0].strip()
    num_warnings = main_log.count('WARNING')
    num_errors = main_log.count('ERROR!!!')
    num_exceptions = main_log.count('Exception:')
    num_tracebacks = main_log.count('Traceback')
    num_failures = main_log.count('Failure')
    # assert num_exceptions == 0, 'found some critical errors in the log file on node %s' % node
    print(f'[{node}]  Warnings: {num_warnings}     Errors: {num_errors}     Tracebacks: {num_tracebacks}     '
          f'Failures: {num_failures}    Exceptions: {num_exceptions}')


async def print_exceptions_one_node(node):
    exceptions_out = run_ssh_command_and_wait(node, 'cat /root/.bitdust/logs/exception_*.log')[0].strip()
    if exceptions_out:
        print(f'\n[{node}]:\n\n{exceptions_out}\n\n')


def report_all_nodes(event_loop):
    print('\n\nTest report:')
    event_loop.run_until_complete(asyncio.wait([
        asyncio.ensure_future(report_one_node(node)) for node in ALL_NODES
    ]))
    print('\n\nALL EXCEPTIONS:')
    event_loop.run_until_complete(asyncio.wait([
        asyncio.ensure_future(print_exceptions_one_node(node)) for node in ALL_NODES
    ]))


#------------------------------------------------------------------------------


async def clean_one_node(node, skip_checks=False):
    # stop_daemon(node, skip_checks=skip_checks)
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/metadata')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/identitycache')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/identityserver')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/keys')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/customers')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/suppliers')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/backups')
    run_ssh_command_and_wait(node, 'rm -rf /root/.bitdust/messages')


async def clean_one_customer(node):
    run_ssh_command_and_wait(node, 'rm -rf /%s/*' % node)


def clean_all_nodes(event_loop, skip_checks=False):
    event_loop.run_until_complete(asyncio.wait([
        asyncio.ensure_future(clean_one_node(node, skip_checks=skip_checks)) for node in ALL_NODES
    ]))
    event_loop.run_until_complete(asyncio.wait([
        asyncio.ensure_future(clean_one_customer(node)) for node in ALL_ROLES['customers']]))
    print('All nodes cleaned')


#------------------------------------------------------------------------------

def kill_all_nodes():
    for node in ALL_NODES:
        print('Shutdown %s' % node)
        run_ssh_command_and_wait(node, 'pkill -e sshd')
    print('All nodes stopped')

#------------------------------------------------------------------------------

@pytest.yield_fixture(scope='session')
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

#------------------------------------------------------------------------------

@pytest.yield_fixture(scope='session', autouse=True)
def global_wrapper(event_loop):
    _begin = time.time()

    open_all_tunnels(event_loop, ALL_NODES)
    clean_all_nodes(event_loop, skip_checks=True)
    start_all_nodes(event_loop)
    
    print('\nStarting all roles and execute tests')
 
    yield

    # stop_all_nodes(event_loop)
    report_all_nodes(event_loop)
    # TODO: use ENV variables to control cleanup
    # clean_all_nodes()
    # close_all_tunnels()
    # kill_all_nodes()

    print('\nTest suite completed in %5.3f seconds\n' % (time.time() - _begin))
