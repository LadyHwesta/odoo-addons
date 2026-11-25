# -*- coding: utf-8 -*-
import base64

from odoo import SUPERUSER_ID, api
from odoo.tools import file_open

COVERS = {
    "channel_video_meetings": "cover_video_meetings.png",
}


def migrate(cr, version):
    """Courses now have their own cover pictures. Course data loads as
    noupdate, so set the picture here, and only where a course has none
    (never replace a picture someone chose)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, image in COVERS.items():
        channel = env.ref(f"elearning_video_meetings.{xmlid}", raise_if_not_found=False)
        if channel and not channel.image_1920:
            with file_open(f"elearning_video_meetings/static/img/{image}", "rb") as f:
                channel.image_1920 = base64.b64encode(f.read())
