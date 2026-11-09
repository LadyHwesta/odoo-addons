# -*- coding: utf-8 -*-
from odoo import models


class MailingMailing(models.Model):
    _inherit = 'mailing.mailing'

    def _send_welcome(self, contact):
        """Queue this mailing for one mailing.contact, the way Odoo's own
        sending does (per-recipient unsubscribe link, List-Unsubscribe
        headers, a trace in the mailing's statistics), without marking the
        mailing as sent and without committing mid-request. The mail goes out
        with the next run of the outgoing mail queue.

        Someone who already got it (a trace exists for their address) isn't
        sent it again, so signing the same address up repeatedly sends one
        email at most.
        """
        self.ensure_one()
        mailing = self.with_context(
            **self.env['res.users'].with_user(self.user_id or self.env.user).context_get())
        composer = self.env['mail.compose.message'].with_context(
            active_ids=contact.ids,
            default_composition_mode='mass_mail',
            **mailing._get_mass_mailing_context(),
        ).create({
            'auto_delete': not mailing.keep_archives,
            'auto_delete_keep_log': mailing.reply_to_mode == 'update',
            'author_id': (mailing.user_id.partner_id or self.env.user.partner_id).id,
            'attachment_ids': [(4, attachment.id) for attachment in mailing.attachment_ids],
            'body': mailing._prepend_preview(mailing.body_html or '', mailing.preview),
            'composition_mode': 'mass_mail',
            'email_from': mailing.email_from,
            'mail_server_id': mailing.mail_server_id.id,
            'mailing_list_ids': [(4, mailing_list.id) for mailing_list in mailing.contact_list_ids],
            'mass_mailing_id': mailing.id,
            'model': 'mailing.contact',
            'reply_to': mailing.reply_to if mailing.reply_to_mode == 'new' else False,
            'reply_to_force_new': mailing.reply_to_mode == 'new',
            'subject': mailing.subject,
            'template_id': False,
            'use_exclusion_list': mailing.use_exclusion_list,
        })
        composer._action_send_mail(auto_commit=False)
