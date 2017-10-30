#!/usr/bin/env python
#
#  Author: Celtha
#  Date: 2017-07-23
#
#

"""
Nagios plugin to check Graylog and ElasticSearch.

"""

__author__ = "celtha.sh"
__title__ = "Graylog & ElasticSearch Monitor"
__version__ = "2"

# yum install python2-pip.noarch
# pip install --upgrade pip
# pip install requests

import os, sys, getopt, re, json, datetime, optparse, subprocess, requests, argparse, time
from datetime import timedelta
from requests.auth import HTTPBasicAuth

requests.packages.urllib3.disable_warnings()

# USER Reader role.
USER = "read_only"
PASSWORD = "XXXXX"

# USER2 Admin role.
USER2 = "admin_role"
PASSWORD2 = "YYYYY"


def check_diskusage():
    # Check disk usage. - Query= 'disk'
    # Evaluate whether the percentage of disk used is greater than critical or warning.
    # If value for critical or warning has not been evaluated, 90 and 80 respectively

    crit = warn = 0
    crit = warn = 0
    crit_msg = warn_msg = ok_msg = ""

    if options.critical is not None:
        critical = str(options.critical)
    else:
        critical = 90
    if options.warning is not None:
        warning = str(options.warning)
    else:
        warning = 80

    index_response = requests.get('http://'+host+':'+str(port)+'/_cat/allocation?h=*&v&format=json&pretty', auth=HTTPBasicAuth(USER, PASSWORD))
    index_json = index_response.json()

    for allocation in index_json:
        name = allocation['node']
        diskusage = allocation['disk.percent']
        if int(diskusage) >= int(critical):
            crit += 1
            crit_msg = crit_msg+' | %s: %s percent usage' % (name, diskusage)
        elif int(diskusage) >= int(warning):
            warn += 1
            warn_msg = warn_msg+' | %s: %s percent usage' % (name, diskusage)
        else:
            ok_msg = ok_msg+' |  %s: %s percent usage' % (name, diskusage)

    if crit > 0:
        print "CRITICAL: "+crit_msg
        sys.exit(2)
    elif warn > 0:
        print "WARNING: "+warn_msg
        sys.exit(1)
    else:
        print "OK: "+ok_msg
        sys.exit(0)


def check_multi(query):
    # Check multiple values. - Query= 'mem | heap | filedesc | cpu | load | nodes'
    # If critical or warning value has not been evaluated...
    # Apply 2 for critical in "nodes" option
    # Apply 90 and 80 respectively for the rest options.
    
    crit = warn = 0
    crit_msg = warn_msg = ok_msg = ""

    index_response = requests.get('http://'+host+':'+str(port)+'/_cat/nodes?h=*&v&format=json&pretty', auth=HTTPBasicAuth(USER, PASSWORD))
    index_json = index_response.json()

    if query == "nodes":

        if options.critical is None:
            critical = 2
        else:
            critical = int(options.critical)

        if len(index_json) < int(critical):
            crit += 1
            crit_msg = 'Error only %s nodes in a cluster of %s' % (len(index_json), critical)
        else:
            print "OK: All nodes up. %s Nodes" % (len(index_json))
            sys.exit(0)
    else:

        for item in index_json:
            name = item['name']
            usage = item[query]

            if options.critical is None:
                critical = 90
            else:
                critical = int(options.critical)

            if options.warning is None:
                warning = 80
            else:
                warning = int(options.warning)

            if query == "load":
                usage = int(float(str(usage)))

            if int(usage) >= critical:
                crit += 1
                crit_msg = crit_msg+' | %s: %s percent usage' % (name, usage)
            elif int(usage) >= warning:
                warn += 1
                warn_msg = warn_msg+' | %s: %s percent usage' % (name, usage)
            else:
                ok_msg = ok_msg+' |  %s: %s percent usage' % (name, usage)

    if crit > 0:
        print "CRITICAL: "+crit_msg
        sys.exit(2)
    elif warn > 0:
        print "WARNING: "+warn_msg
        sys.exit(1)
    else:
        print "OK: "+ok_msg
        sys.exit(0)


def check_cluster():
    # Check that cluster state is green. - Query= 'cluster'
    # No critical values applied.
    # Status are green, red or yellow.

    index_response = requests.get('http://'+host+':'+str(port)+'/_cluster/health', auth=HTTPBasicAuth(USER, PASSWORD))
    index_json = index_response.json()
    cluster_status = index_json['status']

    if cluster_status == "green":
        print "OK: Cluster status is: %s" % cluster_status
        sys.exit(0)
    elif cluster_status == "yellow":
        print "WARNING: Cluster status is: %s" % cluster_status
        sys.exit(1)
    else:
        print "CRITICAL: Cluster status is: %s" % cluster_status
        sys.exit(2)


def check_throughput():
    # Check graylog throughput. - Query= 'throughput'

    if options.number is None:
        number = 3
    else:
        number = int(options.number)

    count = throughput = res = 0

    while count < number:
        time.sleep(1)
        count = count + 1

        index_response = requests.get('https://'+host+':'+str(port)+'/API/system/throughput', verify=False, auth=HTTPBasicAuth(USER, PASSWORD))
        index_json = index_response.json()
        throughput = index_json['throughput']

        if throughput > 0:
            res = res + 1

    if res > 0:
        #print "OK: %s msg/s Throughput is greather than 0." % throughput
        print "OK: %s msg/s Throughput is greather than 0. | msg=%sMSG;0;0;0;" % (throughput, throughput)
        sys.exit(0)
    else:
        print "CRITICAL: Throughput is 0 msg/s ."
        sys.exit(2)


def checks_shards_state():
    # Check that all shards are STARTED. - Query= 'shards'

    cont = 0
    text = ""
    
    shard_response = requests.get('http://'+host+':'+str(port)+'/_cat/shards?h=*&v&format=json&pretty', auth=HTTPBasicAuth(USER, PASSWORD))
    shard_json = shard_response.json()
    for shard in shard_json:
        if shard['state'] != "STARTED":
            cont += 1
            text = text +"Indice:%s - Shard: %s - PriRep: %s - State: %s | " % (shard['index'], shard['shard'], shard['prirep'], shard['state'])
    if cont > 0:
        print "CRITICAL: %s" % text[:-3]
        sys.exit(2)
    else:
        print "OK: All shards are STARTED."
        sys.exit(0)


def checks_indices_state():
    # Check that all indices are GREEN. - Query= 'indices'

    cont = 0
    text = ""

    indice_response = requests.get('http://'+host+':'+str(port)+'/_cat/indices?h=*&v&format=json&pretty', auth=HTTPBasicAuth(USER, PASSWORD))
    indice_json = indice_response.json()
    for indice in indice_json:
        if indice['health'] != "green":
            cont += 1
            text = text +"Indice:%s - Health: %s - State: %s | " % (indice['index'], indice['health'], indice['status'])
    if cont > 0:
        print "CRITICAL: Indices are not GREEN - %s" % text[:-3]
        sys.exit(2)
    else:
        print "OK: All indices are GREEN."
        sys.exit(0)


def checks_streams_state():
    # Check that all streams are enabled. - Query= 'streams'

    dict_str_ena = {}
    dict_str_all = {}

    text = ""
    
    stream_all_response = requests.get('https://'+host+':'+str(port)+'/API/streams', verify=False, auth=HTTPBasicAuth(USER2, PASSWORD2))
    streams_all_json = stream_all_response.json()

    stream_ena_response = requests.get('https://'+host+':'+str(port)+'/API/streams/enabled', verify=False, auth=HTTPBasicAuth(USER2, PASSWORD2))
    streams_ena_json = stream_ena_response.json()

    if streams_ena_json['total'] == streams_all_json['total']:
        print "OK: %s / %s all streams enabled" % (streams_ena_json['total'], streams_all_json['total'])
        sys.exit(0)
    else:
        for str_ena in streams_ena_json['streams']:
            for str_ena_rule in str_ena['rules']:
                id1 = str_ena_rule['stream_id']
                title1 = str_ena['title']
                dict_str_ena[id1] = {'title': title1}
    
        for str_all in streams_all_json['streams']:
            for str_all_rule in str_all['rules']:
                id2 = str_all_rule['stream_id']
                title2 = str_all['title']
                dict_str_all[id2] = {'title': title2}
    
        for id_str_all in dict_str_all.keys():
            if id_str_all not in dict_str_ena:
                text +=  "ID: [%s] - TITLE: [%s] | " % (str(id_str_all), dict_str_all[str(id_str_all)]['title'])

        print "CRITICAL: %s / %s - %s are not enabled" % (streams_ena_json['total'], streams_all_json['total'], text[:-3])
        sys.exit(2)


def checks_inputs_state():
    # Check that all inputs are STARTED - Query= 'inputs'

    cont = 0
    text = ""

    inputs_response = requests.get('https://'+host+':'+str(port)+'/API/system/inputs', verify=False, auth=HTTPBasicAuth(USER, PASSWORD))
    inputs_json = inputs_response.json()
    inputs = inputs_json['inputs']
    dict_inputs = {}

    for input in inputs:
        id1 = str(input['id'])
        name1 = input['name']
        title1 = input['title']

        dict_inputs[id1] = {'name': name1, 'title': title1}


    inputs_response = requests.get('https://'+host+':'+str(port)+'/API/system/inputstates', verify=False, auth=HTTPBasicAuth(USER, PASSWORD))
    inputs_json = inputs_response.json()
    inputs2 = inputs_json['states']

    dict_stats = {}

    for input2 in inputs2:
        name2 = input2['message_input']['name']
        title2 = input2['message_input']['title']
        id2 = str(input2['id'])

        dict_stats[id2] = {'name': name2, 'title': title2}

    for id_input in dict_inputs.keys():
        if id_input not in dict_stats:
            text += "ID: [%s] - NAME: [%s] - DESC: [%s] | " % (str(id_input), dict_inputs[str(id_input)]['name'], dict_inputs[str(id_input)]['title'])
            cont += 1

    if cont > 0:
        print "CRITICAL: %s are not RUNNING" % text[:-3]
        sys.exit(2)
    else:
        print "OK: All inputs RUNNIG"
        sys.exit(0)


def checks_reindex_state():
    # Check that at least one index has been recalculated less than N seconds ago.- Query= 'reindex'

    cont = 0

    if options.number is None:
        number = 300
    else:
        number = int(options.number)

    evaluate_time = datetime.datetime.now() - timedelta(seconds=number)
    
    index_response = requests.get('https://'+host+':'+str(port)+'/API/system/indices/ranges', verify=False, auth=HTTPBasicAuth(USER2, PASSWORD2))
    index_json = index_response.json()
    index_ranges = index_json['ranges']

    for index_range in index_ranges:
        calculated_at_aux = index_range['calculated_at']
        calculated_at = datetime.datetime.strptime(calculated_at_aux, "%Y-%m-%dT%H:%M:%S.%fZ")

        if calculated_at > evaluate_time:
            cont += 1
    if cont > 0:
        print "OK: Some index recalculated less than %s seconds ago." % number
        sys.exit(0)
    else:
        print "CRITICAL: All indexes recalculated more than %s seconds ago" % number
        sys.exit(2)


def check_system_deflector():
    # Check that deflector index are up.

    deflec_response = requests.get('https://'+host+':'+str(port)+'/API/system/deflector', verify=False, auth=HTTPBasicAuth(USER2, PASSWORD2))
    deflec_json = deflec_response.json()
    name = deflec_json['current_target']

    if deflec_json['is_up']:
        print "OK: %s deflector is UP." % name
        sys.exit(0)
    else:
        print "CRITICAL: Deflector is not enabled."
        sys.exit(2)


def check_system_journal():
    # Check that journal dont have more than n messages uncommited.

    journal_response = requests.get('https://'+host+':'+str(port)+'/API/system/journal', verify=False, auth=HTTPBasicAuth(USER, PASSWORD))
    journal_json = journal_response.json()
    res = journal_json['uncommitted_journal_entries']

    if options.number is None:
        number = 1000
    else:
        number = int(options.number)

    if res > number:
        print "CRITICAL: %s uncommited journal entries." % res
        sys.exit(2)
    else:
        print "OK: %s - Less than %s uncommited journal entries." % (res, number)
        sys.exit(0)


def check_system_notifications():
    #  Check that you've made notifications for less than n seconds..

    if options.number is None:
        number = 18000
    else:
        number = int(options.number)

    evaluate_time = datetime.datetime.now() - timedelta(seconds=number)

    cont = 0
    text = ""

    noti_response = requests.get('https://'+host+':'+str(port)+'/API/system/notifications', verify=False, auth=HTTPBasicAuth(USER2, PASSWORD2))
    print 'https://'+host+':'+str(port)+'/API/system/notifications'
    print noti_response
    noti_json = noti_response.json()
    print noti_json
    noti = noti_json['notifications']
    print noti
    for n in noti:
        timestamp_aux = n['timestamp']
        timestamp = datetime.datetime.strptime(timestamp_aux, "%Y-%m-%dT%H:%M:%S.%fZ")
        print timestamp
        texto = n['type']

        if timestamp > evaluate_time:
            cont += 1
            text += "MSG: %s / %s | " % (timestamp, texto)

    if cont > 0:
        print "CRITICAL: Have %s notifications: %s " % (cont, text[:-3])
        sys.exit(2)
    else:
        print "OK: No notifications."
        sys.exit(0)


def check_system_messages():
    # Check that you've made messages for less than n seconds.
    
    if options.number is None:
        number = 18000
    else:
        number = int(options.number)

    evaluate_time = datetime.datetime.now() - timedelta(seconds=number)

    cont = 0
    text = ""
    dict_msg = {}

    msg_response = requests.get('https://'+host+':'+str(port)+'/API/system/messages', verify=False, auth=HTTPBasicAuth(USER2, PASSWORD2))
    msg_json = msg_response.json()
    msg = msg_json['messages']

    for m in msg:
        timestamp_aux = m['timestamp']
        timestamp = datetime.datetime.strptime(timestamp_aux, "%Y-%m-%dT%H:%M:%S.%fZ")
        texto = m['content']

        if timestamp > evaluate_time:
            cont += 1
            text += "MSG: %s / %s | " % (timestamp, texto)
                    
    if cont > 0:
        print "CRITICAL: Have %s errors mesages: %s " % (cont, text[:-3])
        sys.exit(2)
    else:
        print "OK: No error messages"
        sys.exit(0)


def check_nofuturemessages():
    # Check that graylog dont have messages with dates in the future. - Query= 'nofuturemessages'
    
    res = 0
    list_indices = ""


    index_response = requests.get('https://'+host+':'+str(port)+'/API/system/indices/ranges', verify=False, auth=HTTPBasicAuth(USER2, PASSWORD2))
    index_json = index_response.json()
    index_ranges = index_json['ranges']


    for index_range in index_ranges:
        nombre = index_range['index_name']
        ahora = datetime.datetime.now()
        end = index_range['end']
        end_time = datetime.datetime.strptime(end, "%Y-%m-%dT%H:%M:%S.%fZ")

        if end_time > ahora:
            res += 1
            list_indices = list_indices+nombre+" "
    if res>0:
        print "CRITICAL: Indices with future msg: %s" % list_indices
        sys.exit(2)
    else:
        print "OK: No indices with future msg."
        sys.exit(0)

if __name__ == "__main__":

    # Define format to permit add newlines
    class MyParser(optparse.OptionParser):
        def format_epilog(self, formatter):
            return self.epilog

    parser = MyParser(description=
"""## %s v.%s - %s ##""" % (__title__ , __version__, __author__)
, epilog=
"""Examples:

CLUSTER: Check if cluster are in green state.
./monitoriza.py -H 127.0.0.1 -p 9200 -q cluster
-------------------------------------------------------------------------------
CPU: Check if the cpu usage is higher than indicated.
./monitoriza.py -H 127.0.0.1 -p 9200 -q cpu 
./monitoriza.py -H 127.0.0.1 -p 9200 -q cpu -W 80 -C 90
-------------------------------------------------------------------------------
DEFLECTOR: Check if deflector index is UP.
./monitoriza.py -H 127.0.0.1 -p 9000 -q deflector
-------------------------------------------------------------------------------
DISK: Check if the disk consumption is higher than indicated.
./monitoriza.py -H 127.0.0.1 -p 9200 -q disk
./monitoriza.py -H 127.0.0.1 -p 9200 -q disk -W 80 -C 90 
-------------------------------------------------------------------------------
FILEDESC: Check if the filedesc consumption is higher than indicated.
./monitoriza.py -H 127.0.0.1 -p 9200 -q filedesc
./monitoriza.py -H 127.0.0.1 -p 9200 -q filedesc -W 80 -C 90
-------------------------------------------------------------------------------
HEAP: Check if the memory consumption in heap is higher than indicated.
./monitoriza.py -H 127.0.0.1 -p 9200 -q heap
./monitoriza.py -H 127.0.0.1 -p 9200 -q heap -W 80 -C 90
-------------------------------------------------------------------------------
INDICES: Check if all indexes are in green state.
./monitoriza.py -H 127.0.0.1 -p 9200 -q indices
-------------------------------------------------------------------------------
INPUTS: Check if all inputs are enabled.
./monitoriza.py -H 127.0.0.1 -p 9000 -q inputs
-------------------------------------------------------------------------------
JOURNAL: Check if have more than n uncommited journal entries.
./monitoriza.py -H 127.0.0.1 -p 9000 -q journal
./monitoriza.py -H 127.0.0.1 -p 9000 -q journal -n 1000
-------------------------------------------------------------------------------
LOAD: Check if the load value is higher than indicated.
./monitoriza.py -H 127.0.0.1 -p 9200 -q load
./monitoriza.py -H 127.0.0.1 -p 9200 -q load -W 80 -C 90
-------------------------------------------------------------------------------
MEM: Check if the memory consumption is higher than indicated.
./monitoriza.py -H 127.0.0.1 -p 9200 -q mem
./monitoriza.py -H 127.0.0.1 -p 9200 -q mem -W 80 -C 90
-------------------------------------------------------------------------------
MESSAGES: Check if there are messages.
./monitoriza.py -H 127.0.0.1 -p 9000 -q messages
./monitoriza.py -H 127.0.0.1 -p 9000 -q messages -n 18000
-------------------------------------------------------------------------------
NODES: Check if all nodes are up.
./monitoriza.py -H 127.0.0.1 -p 9200 -q nodes
./monitoriza.py -H 127.0.0.1 -p 9200 -q nodes -C 2
-------------------------------------------------------------------------------
NOFUTUREMESSAGES: Check if there are messages in the future in some index.
./monitoriza.py -H 127.0.0.1 -0 9000 -q nofuturemessages
-------------------------------------------------------------------------------
NOTIFICATIONS: Check if there are notifications.
./monitoriza.py -H 127.0.0.1 -p 9000 -q notifications
./monitoriza.py -H 127.0.0.1 -p 9000 -q notifications -n 18000
-------------------------------------------------------------------------------
REINDEX: Check if any index has been recalculated less than N seconds ago.
./monitoriza.py -H 127.0.0.1 -p 9000 -q reindex
./monitoriza.py -H 127.0.0.1 -p 9000 -q reindex -n 600
-------------------------------------------------------------------------------
SHARDS: Check if all shards are started.
./monitoriza.py -H 127.0.0.1 -p 9200 -q shards
-------------------------------------------------------------------------------
STREAMS: Check if all streams are enabled.
./monitoriza.py -H 127.0.0.1 -p 9000 -q streams
-------------------------------------------------------------------------------
THROUGHPUT: Check if throughput is greater than 0.
./monitoriza.py -H 127.0.0.1 -0 9000 -q throughput
./monitoriza.py -H 127.0.0.1 -0 9000 -q throughput -n 5
-------------------------------------------------------------------------------
""")

    parser.add_option("-H", "--host", dest="host", type="string", help="Ip host")
    parser.add_option("-p", "--port", dest="port", type="int", help="Destination port")
    parser.add_option("-C", "--critical", dest="critical", type="int", help="Add Critical value")
    parser.add_option("-W", "--warning", dest="warning", type="int", help="Add Warning value")
    parser.add_option("-n", "--number", dest="number", type="int", help="Add Number value")
    parser.add_option("-q", "--query", dest="query", type="string", help="Add check to run: cluster (EL) | indices (EL) | shards (EL) | inputs (GL) | streams (GL) | reindex (GL) | messages (GL) | mem (EL) | heap (EL) | filedesc (EL) | cpu (EL) | load (EL) | disk (EL) | nodes (EL) | throughput (GL) | nofuturemessages (GL) | notifications (GL) | deflector (GL) | journal (GL)")

    (options, args) = parser.parse_args()

    if not options.host:   # if host is not given
        print "Host is required."
        sys.exit(1)

    if not options.port:   # if port is not given
        print "Port is required."
        sys.exit(1) 

    host = str(options.host)
    port = int(options.port)
    query = str(options.query)

    if query == "cluster":
        check_cluster()
    elif query == "indices":
        checks_indices_state()
    elif query == "shards":
        checks_shards_state()
    elif query == "inputs":
        checks_inputs_state()
    elif query == "reindex":
        checks_reindex_state()
    elif query == "messages":
        check_system_messages()
    elif query == "notifications":
        check_system_notifications()
    elif query == "throughput":
        check_throughput()
    elif query == "nofuturemessages":
        check_nofuturemessages()
    elif query == "disk":
        check_diskusage()
    elif query == "mem":
        check_multi("ram.percent")
    elif query == "heap":
        check_multi("heap.percent")
    elif query == "filedesc":
        check_multi("file_desc.percent")
    elif query == "cpu":
        check_multi("cpu")
    elif query == "load":
        check_multi("load")
    elif query == "nodes":
        check_multi("nodes")
    elif query == "streams":
        checks_streams_state()
    elif query == "deflector":
        check_system_deflector()
    elif query == "journal":
        check_system_journal()
    else:
        print "Invalid option"

