#!/usr/bin/env python
#
# Author: Justin Lintz
# Copyright 2013 Chartbeat
# http://www.chartbeat.com
#
# Nagios check to alert on any retiring instances or
# instances that need rebooting
#

import sys
import re

from datetime import datetime
from datetime import timedelta
from boto.ec2.connection import EC2Connection
from boto.exception import EC2ResponseError

# Setup IAM User with read-only EC2 access
KEY_ID = ""
ACCESS_KEY = ""

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3


def get_instance(instance_id):
    """
    Return an Instance object for the given instance id

    @param instance_id: Instance id (string)
    @return: Instance object, or None if not found
    """

    conn = EC2Connection(KEY_ID, ACCESS_KEY)
    try:
        reservations = conn.get_all_instances([instance_id])
    except EC2ResponseError, ex:
        print 'Got exception when calling EC2 for instance "%s": %s' % \
                        (instance_id, ex.error_message)
        return None

    for r in reservations:
        if len(r.instances) and r.instances[0].id == instance_id:
            return r.instances[0]

    return None


class AmazonEventCheck(object):
    """
    Nagios check for the Amazon events.
    Will warn/error if any pending events based on time till event occurs
    """

    def __init__(self):
        pass

    def _get_instances_pending_events(self):
        """
        Get list of instances that have pending events.

        @return: List(Instance, String , Datetime), List of (Instance, instance
                 Event, Scheduled Date) for hosts with pending events
        """

        conn = EC2Connection(KEY_ID, ACCESS_KEY)
        stats = conn.get_all_instance_status()
        ret = []
        for stat in stats:
            if stat.events:
                for event in stat.events:
                    if re.match('^\[Completed\]', event.description):
                        continue
                    ret.append((stat.id, get_instance(stat.id).tags['Name'], event.code, event.not_before))
        return ret

    def check(self, critical_threshold=2):
        """
        Check pending instance events, alert if
        event time is less than critical_threshold
        Warn otherwise

        @param critical_threshold: int, number of days before an event that nagios should alert
        """

        events = self._get_instances_pending_events()

        if not events:
            print 'OK: no pending events'
            return OK

        critical_events = []
        warning_events = []

        for event in events:
            event_time = datetime.strptime(event[3], '%Y-%m-%dT%H:%M:%S.000Z')
            # Are we close enough to the instance event that we should alert?
            if datetime.utcnow() > (event_time - timedelta(days=critical_threshold)):
                critical_events.append(event)
            else:
                warning_events.append(event)

        if critical_events:
            print 'CRITICAL: instances with events in %d days - %s' % (critical_threshold, [(event[0], event[1]) for event in critical_events])
            return CRITICAL

        print 'WARNING: instances with scheduled events %s' % ([(event[0], event[1]) for event in warning_events])
        return WARNING


def main():
    if len(sys.argv) != 2:
        print >> sys.stderr, 'Usage: %s <critical threshold>' % sys.argv[0]
        return UNKNOWN

    eventcheck = AmazonEventCheck()
    return eventcheck.check(int(sys.argv[1]))

if __name__ == '__main__':
    sys.exit(main())
