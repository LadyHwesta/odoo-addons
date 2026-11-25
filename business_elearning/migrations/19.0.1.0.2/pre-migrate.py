# -*- coding: utf-8 -*-


def migrate(cr, version):
    """The My Day lesson has a new screenshot and caption. Courses load as
    noupdate data, so let this upgrade rewrite that lesson."""
    cr.execute("""
        UPDATE ir_model_data SET noupdate = false
         WHERE module = 'business_elearning' AND name = 'channel_sales_s1_l1'
    """)
