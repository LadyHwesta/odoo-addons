# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Publish this course's lessons. The course itself was published but its
    lessons never were (a lesson starts unpublished), so only course admins
    could see them. Only this module's own lessons are touched."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    data = env["ir.model.data"].search(
        [("module", "=", "dms_elearning_team_folder"), ("model", "=", "slide.slide")])
    env["slide.slide"].browse(data.mapped("res_id")).exists().write({"is_published": True})
