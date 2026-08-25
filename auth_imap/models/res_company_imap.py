# -*- coding: utf-8 -*-
import imaplib
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 15


class ResCompanyImap(models.Model):
    _name = 'res.company.imap'
    _description = 'Company IMAP Authentication Server'
    _order = 'sequence'
    _rec_name = 'imap_server'

    sequence = fields.Integer(default=10)
    company = fields.Many2one('res.company', string='Company', required=True, ondelete='cascade')
    active = fields.Boolean(default=True)
    imap_server = fields.Char(
        string='IMAP Server address', required=True,
        help='Hostname of the IMAP server, e.g. imap.example.com')
    imap_server_port = fields.Integer(string='IMAP Server port', required=True, default=993)
    imap_encryption = fields.Selection([
        ('ssl', 'SSL/TLS'),
        ('starttls', 'STARTTLS'),
        ('none', 'None'),
    ], string='Encryption', required=True, default='ssl')

    @api.onchange('imap_encryption')
    def _onchange_imap_encryption(self):
        default_ports = {'ssl': 993, 'starttls': 143, 'none': 143}
        if self.imap_encryption and self.imap_server_port in (993, 143, 0, False):
            self.imap_server_port = default_ports[self.imap_encryption]

    def _get_imap_dicts(self):
        """
        Retrieve res_company_imap resources from the database in
        dictionary format.
        :return: IMAP configurations
        :rtype: list of dictionaries
        """
        return self.sudo().search_read(
            [('imap_server', '!=', False)],
            ['id', 'company', 'imap_server', 'imap_server_port', 'imap_encryption'],
            order='sequence',
        )

    def _connect(self, conf):
        """
        Open a connection to an IMAP server specified by an IMAP
        configuration dictionary. Does not authenticate.
        :param dict conf: IMAP configuration
        :return: an imaplib IMAP4/IMAP4_SSL connection
        """
        host = conf['imap_server']
        port = conf['imap_server_port']
        if conf['imap_encryption'] == 'ssl':
            return imaplib.IMAP4_SSL(host, port, timeout=CONNECT_TIMEOUT)
        connection = imaplib.IMAP4(host, port, timeout=CONNECT_TIMEOUT)
        if conf['imap_encryption'] == 'starttls':
            connection.starttls()
        return connection

    def _authenticate(self, conf, login, password):
        """
        Authenticate a user against the specified IMAP server by
        attempting a real ``LOGIN``.

        :param dict conf: IMAP configuration
        :param login: username (mailbox login)
        :param password: password for the IMAP account
        :return: True if the server accepted the credentials, False
                 otherwise - including when the server couldn't be reached
                 at all. Callers must treat "couldn't verify" the same as
                 "invalid": never authenticate on a connection failure.
        :rtype: bool
        """
        if not password:
            return False
        connection = None
        try:
            connection = self._connect(conf)
            connection.login(login, password)
        except imaplib.IMAP4.error:
            # Bad credentials (or the server aborted the session) - not
            # logged as an error, this is the expected shape of a wrong
            # password.
            return False
        except OSError as exc:
            _logger.error(
                'IMAP connection error while authenticating %r against %s:%s - %s',
                login, conf['imap_server'], conf['imap_server_port'], exc,
            )
            return False
        else:
            return True
        finally:
            if connection is not None:
                try:
                    connection.logout()
                except Exception:
                    pass

    def action_test_imap_connection(self):
        """Test that the configured IMAP server is reachable (and that TLS
        negotiates, for ssl/starttls) - not a credential check, there's no
        single "test" user's password to check here.
        """
        self.ensure_one()
        conf = {
            'imap_server': self.imap_server,
            'imap_server_port': self.imap_server_port,
            'imap_encryption': self.imap_encryption,
        }
        connection = None
        try:
            connection = self._connect(conf)
        except imaplib.IMAP4.error as exc:
            return self._imap_test_notification('danger', _('Connection Test Failed!'), str(exc))
        except OSError as exc:
            return self._imap_test_notification(
                'danger', _('Connection Test Failed!'),
                _('Cannot contact IMAP server at %(server)s:%(port)s - %(error)s',
                  server=self.imap_server, port=self.imap_server_port, error=exc))
        finally:
            if connection is not None:
                try:
                    connection.logout()
                except Exception:
                    pass
        return self._imap_test_notification(
            'success', _('Connection Test Successful!'),
            _('Successfully connected to IMAP server at %(server)s:%(port)s',
              server=self.imap_server, port=self.imap_server_port))

    def _imap_test_notification(self, ntype, title, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'type': ntype, 'title': title, 'message': message, 'sticky': False},
        }
