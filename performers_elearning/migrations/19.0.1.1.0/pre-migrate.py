# -*- coding: utf-8 -*-


def migrate(cr, version):
    """The courses were first installed as noupdate data, which keeps every
    later lesson change from reaching an installed database. They follow
    the code now: lift the flag so this and future upgrades rewrite them."""
    cr.execute("""
        UPDATE ir_model_data SET noupdate = false
         WHERE module = 'performers_elearning' AND noupdate
    """)
