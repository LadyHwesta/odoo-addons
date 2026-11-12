# -*- coding: utf-8 -*-
import base64
from datetime import datetime, timedelta

from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLinkedFiles(TransactionCase):

    def test_linked_files_are_shared_not_copied_and_go_with_invitations(self):
        partner_model = self.env.ref('base.model_res_partner')
        storage = self.env['dms.storage'].create({
            'name': 'Board Storage', 'save_type': 'attachment',
            'inherit_access_from_parent_record': True,
            'model_ids': [(6, 0, [partner_model.id])]})
        root = self.env['dms.directory'].create({
            'name': 'Board Root', 'is_root_directory': True,
            'storage_id': storage.id, 'model_id': partner_model.id})
        holder = self.env['res.partner'].create({'name': 'Board'})
        folder = self.env['dms.directory'].create({
            'name': 'Board Papers', 'parent_id': root.id, 'res_model': 'res.partner',
            'res_id': holder.id, 'storage_id': storage.id, 'model_id': partner_model.id})
        dms_file = self.env['dms.file'].create({
            'name': 'Budget.txt', 'directory_id': folder.id,
            'content': base64.b64encode(b'Budget 2027')})
        guest = self.env['res.partner'].create({'name': 'Board Member', 'email': 'board@example.com'})
        start = datetime.now() + timedelta(days=7)
        meeting = self.env['calendar.event'].create({
            'name': 'Board Meeting', 'start': start, 'stop': start + timedelta(hours=1),
            'partner_ids': [Command.set([guest.id])],
            'dms_file_ids': [Command.link(dms_file.id)]})

        self.assertEqual(dms_file.attachment_id.res_model, 'res.partner', "still the folder's")
        self.assertEqual(self.env['dms.file'].search_count([('name', '=', 'Budget.txt')]), 1)
        sent = self.env['mail.message'].search([
            ('model', '=', 'calendar.event'), ('res_id', '=', meeting.id)]).attachment_ids
        self.assertIn('Budget.txt', sent.mapped('name'))
