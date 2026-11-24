# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Texts from before "Handled" existed were dealt with already (or
    never will be): don't put the whole history on everyone's My Day."""
    cr.execute("UPDATE signalwire_sms SET handled = TRUE WHERE handled IS NOT TRUE")
