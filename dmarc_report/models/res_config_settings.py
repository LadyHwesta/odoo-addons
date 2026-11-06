# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dmarc_reporting_address = fields.Char(
        string='Reporting address', config_parameter='dmarc_report.reporting_address',
        help='The address in your DMARC records (rua=mailto:...). Used to suggest each domain\'s records.')
    dmarc_window_days = fields.Integer(
        string='Findings cover the last', config_parameter='dmarc_report.window_days', default=30)
    dmarc_alert_new_senders = fields.Boolean(
        string='Alert on new failing senders', config_parameter='dmarc_report.alert_new_senders',
        default=True)

    def action_dmarc_mail_servers(self):
        return self.env['ir.actions.act_window']._for_xml_id('mail.action_email_server_tree')
