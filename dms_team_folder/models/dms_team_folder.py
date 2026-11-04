# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MANAGER_GROUP = 'dms_team_folder.group_team_folder_manager'


class DmsTeamFolder(models.Model):
    """A shared folder whose access is decided by its own member lists.

    An attachment's access follows the record it's linked to. Each folder is
    that record for its files, so these record rules protect the files in DMS
    and the attachments behind them alike.

    Members need create, write and unlink rights on this model, because that's
    how DMS and ir.attachment check whether they can change a folder's files.
    Changing the folder itself is limited to managers in create/write/unlink.
    """
    _name = 'dms.team.folder'
    _description = 'Team Folder'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    description = fields.Text()
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True,
        help="Leave empty to share this folder across companies.")
    member_ids = fields.Many2many(
        'res.users', 'dms_team_folder_member_rel', 'folder_id', 'user_id',
        string='Members', domain=[('share', '=', False)],
        help="Can add, edit and delete this folder's files.")
    viewer_ids = fields.Many2many(
        'res.users', 'dms_team_folder_viewer_rel', 'folder_id', 'user_id',
        string='Viewers', domain=[('share', '=', False)],
        help="Can only read this folder's files.")
    directory_id = fields.Many2one(
        'dms.directory', readonly=True, copy=False, ondelete='set null')
    file_count = fields.Integer(compute='_compute_file_count')
    can_manage = fields.Boolean(compute='_compute_can_manage')

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        # Views are cached across users, and _get_view varies by this group.
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + (self.env.user.has_group(MANAGER_GROUP),)

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        # Views default to no New or Delete, since only managers can use them.
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type in ('list', 'form') and self.env.user.has_group(MANAGER_GROUP):
            arch.set('create', '1')
            arch.set('delete', '1')
        return arch, view

    @api.constrains('member_ids', 'viewer_ids')
    def _check_member_viewer_overlap(self):
        for folder in self:
            overlap = folder.member_ids & folder.viewer_ids
            if overlap:
                raise ValidationError(self.env._(
                    "%(users)s can't be both a member and a viewer of %(folder)s.",
                    users=', '.join(overlap.mapped('name')), folder=folder.name))

    @api.depends('directory_id')
    def _compute_file_count(self):
        for folder in self:
            folder.file_count = self.env['dms.file'].sudo().search_count(
                [('directory_id', 'child_of', folder.directory_id.id)]
            ) if folder.directory_id else 0

    @api.depends_context('uid')
    def _compute_can_manage(self):
        can_manage = self.env.user.has_group(MANAGER_GROUP)
        for folder in self:
            folder.can_manage = can_manage

    def _check_can_manage(self):
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(self.env._(
                "Only Team Folder Managers can change team folders."))

    def _grant_documents_access(self):
        """Members and viewers need the Documents app to reach their files."""
        group = self.env.ref('dms.group_dms_user').sudo()
        users = self.sudo().member_ids | self.sudo().viewer_ids
        missing = users.filtered(lambda user: group not in user.all_group_ids)
        if missing:
            missing.write({'group_ids': [(4, group.id)]})

    def _create_directory(self):
        root = self.env.ref('dms_team_folder.directory_team_folders').sudo()
        for folder in self.sudo():
            folder.directory_id = root.env['dms.directory'].with_context(
                check_name=False).create({
                    'name': folder.name,
                    'parent_id': root.id,
                    'storage_id': root.storage_id.id,
                    'model_id': root.model_id.id,
                    'res_model': self._name,
                    'res_id': folder.id,
                })

    @api.model_create_multi
    def create(self, vals_list):
        self._check_can_manage()
        folders = super().create(vals_list)
        folders._create_directory()
        folders._grant_documents_access()
        return folders

    def write(self, vals):
        self._check_can_manage()
        res = super().write(vals)
        if 'name' in vals:
            for folder in self.sudo().filtered('directory_id'):
                folder.directory_id.with_context(check_name=False).name = folder.name
        if {'member_ids', 'viewer_ids'} & vals.keys():
            self._grant_documents_access()
        return res

    def unlink(self):
        self._check_can_manage()
        if any(folder.file_count for folder in self):
            raise UserError(self.env._(
                "This folder still has files. Delete them first, or archive "
                "the folder instead."))
        directories = self.sudo().directory_id
        res = super().unlink()
        directories.unlink()
        return res

    def action_view_files(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('dms.action_dms_file')
        action['domain'] = [('directory_id', 'child_of', self.directory_id.id)]
        action['context'] = {'default_directory_id': self.directory_id.id}
        action['display_name'] = self.name
        return action
