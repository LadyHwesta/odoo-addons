# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

UNSUBSCRIBE_LINK = '/unsubscribe_from_list'


class MailingList(models.Model):
    _inherit = 'mailing.list'

    welcome_mailing_id = fields.Many2one(
        'mailing.mailing', string="Welcome Email", ondelete='set null',
        domain="[('mailing_type', '=', 'mail'), ('mailing_model_name', '=', 'mailing.list'), "
               "('contact_list_ids', 'in', id)]",
        help="Sent once to each person who signs up for this list through a website "
             "newsletter block. Write it as a normal mailing aimed at this list and don't "
             "send it yourself. It must contain an unsubscribe link.")

    @api.constrains('welcome_mailing_id')
    def _check_welcome_mailing(self):
        for mailing_list in self.filtered('welcome_mailing_id'):
            mailing = mailing_list.welcome_mailing_id
            if mailing.mailing_type != 'mail' or mailing.mailing_model_real != 'mailing.contact':
                raise ValidationError(self.env._(
                    "The welcome email for %(list)s must be an email mailing sent to "
                    "mailing list contacts.", list=mailing_list.display_name))
            if mailing_list not in mailing.contact_list_ids:
                raise ValidationError(self.env._(
                    "The welcome email \"%(mailing)s\" must be addressed to the list "
                    "%(list)s.", mailing=mailing.subject, list=mailing_list.display_name))
            if UNSUBSCRIBE_LINK not in (mailing.body_html or ''):
                raise ValidationError(self.env._(
                    "The welcome email \"%(mailing)s\" has no unsubscribe link. Add the "
                    "footer block with \"Unsubscribe\" to it, so anyone signed up by "
                    "someone else can leave with one click.", mailing=mailing.subject))
