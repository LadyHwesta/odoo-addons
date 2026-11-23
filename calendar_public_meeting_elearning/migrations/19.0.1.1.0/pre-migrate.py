# -*- coding: utf-8 -*-
"""The course was first loaded as never-update data: let this update refresh
its lessons (the data file no longer marks them that way)."""


def migrate(cr, version):
    cr.execute(
        "UPDATE ir_model_data SET noupdate = false "
        "WHERE module = 'calendar_public_meeting_elearning' AND noupdate")
