# -*- coding: utf-8 -*-
{
    'name': 'eLearning Lesson Digest',
    'version': '19.0.1.0.0',
    'category': 'Website/eLearning',
    'summary': 'One email per course for lessons added by a module update, and no re-announcing published lessons',
    'description': """
eLearning: Publication Digest
=============================

Odoo announces a lesson to the course's members whenever it's saved as
published, even when it already was. Courses shipped as module data are
re-saved on every update, so each update emailed every lesson again, one
email per lesson.

* A lesson is announced only when it becomes published.
* Lessons published by a module install or update are gathered and sent
  as one message per course a minute later ("3 new lessons in ..."), with
  links, instead of one email each.
* Publishing a lesson by hand works as before.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'support': 'sales@meskis.net',
    'images': ['static/description/banner.png'],
    'depends': ['website_slides'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
    ],
    'installable': True,
}
