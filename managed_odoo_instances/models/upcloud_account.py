# -*- coding: utf-8 -*-
from odoo import fields, models

from .upcloud_client import UpCloudClient

# Confirmed live 2026-09-15: the standard Debian/Ubuntu cloud-init
# templates, by their real UUIDs on the user's own account.
DEFAULT_TEMPLATE_UUID = '01000000-0000-4000-8000-000020070100'  # Debian 12 (Bookworm)


class UpCloudAccount(models.Model):
    """The reseller's own UpCloud account - one record normally covers
    every dedicated server provisioned this way (a single API token),
    but kept as its own model rather than a singleton config screen so
    a second account (different billing entity, different region
    defaults) is possible without a schema change later.
    """
    _name = 'upcloud.account'
    _description = 'UpCloud Account'
    _rec_name = 'name'

    name = fields.Char(required=True)
    api_token = fields.Char(
        required=True,
        help="An UpCloud API token (the \"ucat_...\" kind, created in "
             "the UpCloud control panel or via upctl) - not a "
             "subaccount username/password.")
    ssh_public_key = fields.Text(
        required=True,
        help="Injected into every new server's root login at "
             "creation, so you (never the customer) can SSH in "
             "afterward to run the bootstrap script.")
    default_zone = fields.Char(
        default='us-chi1', required=True,
        help="An UpCloud zone id, e.g. \"us-chi1\" - see UpCloud's "
             "own zone list for the full set.")
    default_plan = fields.Char(
        default='STARTER-1xCPU-2GB', required=True,
        help="An UpCloud plan name, e.g. \"STARTER-1xCPU-2GB\".")
    default_template_uuid = fields.Char(
        default=DEFAULT_TEMPLATE_UUID, required=True,
        help="The OS template's UUID to clone for a new server's "
             "disk - defaults to Debian 12, matching "
             "meskis-deploy-agent's own bootstrap script.")

    def _get_client(self):
        self.ensure_one()
        return UpCloudClient(self.api_token)
