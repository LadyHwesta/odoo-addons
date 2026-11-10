# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged

PADDING = '͏'  # COMBINING GRAPHEME JOINER, Odoo's invisible padding


@tagged('post_install', '-at_install')
class TestNoHiddenPreview(TransactionCase):

    def test_preview_template_renders_nothing(self):
        html = self.env['ir.qweb']._render('mail.notification_preview', {
            'message': self.env['mail.message'].new({'body': '<p>Hello there</p>'}),
            'tracking_values': [], 'subtype_internal': False,
        })
        self.assertFalse(str(html).strip())

    def test_notification_email_has_no_hidden_block(self):
        author = self.env['res.partner'].create({'name': 'Author', 'email': 'author@example.com'})
        recipient = self.env['res.partner'].create({'name': 'Recipient', 'email': 'r@example.com'})
        record = self.env['res.partner'].create({'name': 'Record'})
        record.with_context(mail_notify_force_send=False).message_post(
            body='Hello recipient, this is a real sentence.', author_id=author.id,
            partner_ids=recipient.ids, message_type='comment', subtype_xmlid='mail.mt_comment')
        mail = self.env['mail.mail'].search([('recipient_ids', 'in', recipient.ids)],
                                            order='id desc', limit=1)
        self.assertTrue(mail, "a notification email was queued")
        self.assertIn('Hello recipient', mail.body_html)
        self.assertNotIn(PADDING, mail.body_html)
        self.assertNotIn('font-size:0px', mail.body_html.replace(' ', ''))
