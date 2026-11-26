# -*- coding: utf-8 -*-
"""Automatic blocks become Info (counted and charted, not listed for review).

A blocked address knocking again was logged as "IP Blocked" with severity
Warning, the same as a new block, and every scanner block was a Warning too:
on meskis.net that was ~600 events in a few weeks, burying the few that need
a person (like the bank-account change at an odd hour).
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE security_event
           SET event_type = 'request_refused', severity = 'info'
         WHERE event_type = 'ip_blocked'
           AND detail LIKE '%%refused by an active%%'
    """)
    cr.execute("""
        UPDATE security_event SET severity = 'info'
         WHERE event_type IN ('probe_blocked', 'ip_blocked')
    """)
    # Older cooldown events didn't record which login was tried, so there's
    # no telling whether it was a real user's: they're past anyway.
    cr.execute("""
        UPDATE security_event SET severity = 'info'
         WHERE event_type = 'login_cooldown' AND login IS NULL
    """)
