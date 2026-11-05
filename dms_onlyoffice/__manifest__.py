# -*- coding: utf-8 -*-
{
    'name': 'ONLYOFFICE for DMS',
    'version': '19.0.1.3.0',
    'category': 'Productivity/Documents',
    'summary': 'Edit dms.file documents in ONLYOFFICE Docs',
    'description': """
ONLYOFFICE for DMS
====================================

Bridges ONLYOFFICE's own generic document-editing engine
(``onlyoffice_odoo``) to OCA's Community-Edition-compatible document
management module (``dms``). ONLYOFFICE's own ready-made bridge,
``onlyoffice_odoo_documents``, only works with Odoo's Enterprise-only
``documents`` app - this module fills that gap for CE.

- Adds an "Edit in ONLYOFFICE" action to ``dms.file`` records, opening
  ONLYOFFICE's own editor against the file's underlying attachment.
- Fixes a real gap between the two projects: ONLYOFFICE's own
  save-back callback writes straight to the underlying
  ``ir.attachment`` with no idea ``dms`` exists, which otherwise
  leaves ``dms.file``'s own checksum/size/mimetype/extension stale
  after every edit. This module keeps them in sync.
- Adds "New Document", which creates a blank document, spreadsheet,
  presentation or PDF form in a folder and opens it in the editor.
- Only supports ``dms.file`` records stored on a ``dms.storage`` whose
  save type is "Attachment" - that is the one case with a genuine
  backing ``ir.attachment`` for ONLYOFFICE to open. See the README for
  why the other two storage types are out of scope.

Requires a running ONLYOFFICE Docs server (self-hosted or cloud),
``onlyoffice_odoo`` installed and configured with that server's URL
and JWT secret, and ``dms`` installed. See the README for setup.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['dms', 'onlyoffice_odoo'],
    'data': [
        'security/ir.model.access.csv',
        'views/dms_file_views.xml',
        'wizards/new_document_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dms_onlyoffice/static/src/js/*',
        ],
    },
    'installable': True,
    'application': False,
}
