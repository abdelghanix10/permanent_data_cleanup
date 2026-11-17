from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_permanent_delete = fields.Boolean(
        string="Allow Permanent Data Deletion",
        compute="_compute_allow_permanent_delete",
        inverse="_inverse_allow_permanent_delete",
        store=False,
        help="Grant this user permission to permanently delete POS Orders, Sessions, Payments, Production, and Inventory.",
    )

    def _compute_allow_permanent_delete(self):
        for user in self:
            user.allow_permanent_delete = user.has_group(
                'permanent_data_cleanup.group_permanent_delete_manager'
            )

    def _inverse_allow_permanent_delete(self):
        group = self.env.ref('permanent_data_cleanup.group_permanent_delete_manager')
        for user in self:
            if user.allow_permanent_delete:
                user.sudo().write({'group_ids': [fields.Command.link(group.id)]})
            else:
                user.sudo().write({'group_ids': [fields.Command.unlink(group.id)]})