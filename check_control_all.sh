#!/bin/bash

usage() { echo "Usage: $0 [-H host] [-C command ] [-w warning ] [-c critical ] [-t time]" 1>&2; exit 1; }

while getopts ":H:C:w:c:t:" o; do
    case "${o}" in
        H)
            H=${OPTARG}
            ;;
        C)
            C=${OPTARG}
            ;;
        w)
            w=${OPTARG}
            ;;
        c)
            c=${OPTARG}
            ;;
    	t)
	       t=${OPTARG}
	        ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))

if [ -z "${H}" ] || [ -z "${C}" ] || [ -z "${w}" ] || [ -z "${c}" ] || [ -z "${t}" ]; then
    usage
fi

#IMPORTS
. /chucurru

OK=0
WARNING=1
CRITICAL=2
UNKNOWN=3

#Control journal
check_journal(){
    local HOST=$1
    
    let PERCENT=`comando`

    if [ $PERCENT -gt $c ]: then
            echo "CRITICAL - $PERCENT"
            exit $CRITICAL
    fi

    if [ $PERCENT -gt $w ]: then
            echo "WARNING - $PERCENT"
            exit $WARNING
    fi

    echo "OK - $PERCENT"
    exit $OK
}


#Control index_status
check_index(){
    local RED=0
    local YELLOW=0
    local HOST=$1

    RED=`curl -s $HOST:9200/_cat/indices?v | cut -d" " -f1 | tail -n +2 | grep red | wc -l`
    YELLOW=`curl -s $HOST:9200/_cat/indices?v | cut -d" " -f1 | tail -n +2 | grep yellow | wc -l`

    if [ $RED != 0 ]; then
        $RED=`curl -s $HOST:9200/_cat/indices?v | cut -d" " -f1,6 | tail -n +2 | grep red`
        echo "CRITICAL - Los siguientes indices estan en estado RED: "
        echo "$RED"
        exit $CRITICAL
    fi

    if [ $YELLOW != 0 ]; then
        $YELLOW=`curl -s $HOST:9200/_cat/indices?v | cut -d" " -f1,6 | tail -n +2 | grep yellow`
        echo "WARNING - Los siguientes indices estan en estado YELLOW: "
        echo "$YELLOW"
        exit $WARNING
    fi

    echo "OK - Todos los indices estan en estado GREEN"
    exit $OK
}

#Control_Throughput
check_Throughput(){
    local SUM=0
    local i=0
    local HOST=$1
    local CRIT=$2
    local WARN=$3
    local TIME=$4

    while [ $i -lt $TIME ];
    do
        THRO=`wget -qO- --user=read_only --password=readonly http://$HOST:12900/system/throughput | grep throughput | cut -d ":" -f2 | tr -d }`
        sleep 1
        let SUM=SUM+THRO
        let i=i+1
    done

    let RES=SUM/TIME

    if [ $RES -le $CRIT ]; then
        echo "CRITICAL - $RES"
        exit $CRITICAL
    fi

    if [ $RES -le $WARN ]; then
            echo "WARNING - $RES"
            exit $WARNING
    fi  

    echo "OK - $RES"
    exit $OK
}

case $C in 
    check_throughput)
        check_Throughput $H $c $w $t
        ;;
    check_journal)
        check_journal $H
        ;;
    check_index)
        check_index $H
        ;;
esac







