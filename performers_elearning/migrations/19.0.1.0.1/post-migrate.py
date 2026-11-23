# -*- coding: utf-8 -*-
"""Adds the "More than one business?" note (Booking Requests Go To) to the
Book a Date lesson. The lesson data is install-only, so copy the new text in
here, but only where the lesson still holds our own text."""
from lxml import etree

from odoo import SUPERUSER_ID, api
from odoo.tools.misc import file_path


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lesson = env.ref('performers_elearning.channel_bookings_s1_l1', raise_if_not_found=False)
    if not lesson or 'Booking Requests Go To' in (lesson.html_content or ''):
        return
    if 'Times past midnight' not in (lesson.html_content or ''):
        return  # edited by hand: leave it
    tree = etree.parse(file_path('performers_elearning/data/slide_channel_data.xml'))
    field = tree.find(".//record[@id='channel_bookings_s1_l1']/field[@name='html_content']")
    lesson.html_content = ''.join(etree.tostring(child, encoding='unicode') for child in field)
