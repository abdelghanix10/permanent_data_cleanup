from datetime import datetime, time
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PermanentDataCleanupWizard(models.TransientModel):
    _name = 'permanent.data.cleanup.wizard'
    _description = 'Permanent Data Cleanup Wizard'

    filter_mode = fields.Selection(
        [
            ('all', 'All Records (All Time)'),
            ('date_range', 'Specific Date Range'),
        ],
        string='Deletion Scope',
        default='all',
        required=True,
    )
    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date', default=fields.Date.context_today)
    pos_config_id = fields.Many2one(
        'pos.config',
        string='Filter by POS Terminal (Optional)',
        help='If set, only POS Sessions, Orders, and Payments from this POS terminal will be deleted.',
    )

    # Target Selection Checkboxes
    delete_pos_orders = fields.Boolean(string='POS Orders & Order Lines', default=False)
    delete_pos_sessions = fields.Boolean(string='POS Sessions & Cash Statements', default=False)
    delete_pos_payments = fields.Boolean(string='POS Payments', default=False)
    delete_mrp_productions = fields.Boolean(string='Manufacturing / Production Orders', default=False)
    delete_stock_moves = fields.Boolean(string='Inventory Transfers, Stock Moves & Scrap', default=False)
    reset_stock_quants = fields.Boolean(
        string='Reset All On-Hand Inventory (Stock Quants) to 0',
        default=False,
    )
    reset_sequences = fields.Boolean(
        string='Reset POS, Production & Inventory Sequences to 1',
        default=False,
    )

    # Preview Counters
    preview_orders_count = fields.Integer(string='Orders to Delete', compute='_compute_preview_counts')
    preview_sessions_count = fields.Integer(string='Sessions to Delete', compute='_compute_preview_counts')
    preview_payments_count = fields.Integer(string='Payments to Delete', compute='_compute_preview_counts')
    preview_mrp_count = fields.Integer(string='Productions to Delete', compute='_compute_preview_counts')
    preview_moves_count = fields.Integer(string='Stock Moves to Delete', compute='_compute_preview_counts')
    preview_quants_count = fields.Integer(string='Stock Quants to Clear', compute='_compute_preview_counts')

    confirm_text = fields.Char(
        string='Type DELETE to Confirm',
        help='Type DELETE in uppercase to unlock permanent deletion.',
    )

    def _get_datetime_bounds(self):
        if self.filter_mode != 'date_range':
            return None, None
        dt_from = datetime.combine(self.date_from, time.min) if self.date_from else None
        dt_to = datetime.combine(self.date_to, time.max) if self.date_to else None
        return dt_from, dt_to

    def _build_domain(self, date_field, support_pos_config=False, config_field='config_id'):
        domain = []
        dt_from, dt_to = self._get_datetime_bounds()
        if dt_from:
            domain.append((date_field, '>=', dt_from))
        if dt_to:
            domain.append((date_field, '<=', dt_to))
        if support_pos_config and self.pos_config_id:
            domain.append((config_field, '=', self.pos_config_id.id))
        return domain

    @api.depends(
        'filter_mode', 'date_from', 'date_to', 'pos_config_id',
        'delete_pos_orders', 'delete_pos_sessions', 'delete_pos_payments',
        'delete_mrp_productions', 'delete_stock_moves', 'reset_stock_quants',
    )
    def _compute_preview_counts(self):
        for wiz in self:
            ord_dom = wiz._build_domain('date_order', True, 'config_id')
            sess_dom = wiz._build_domain('start_at', True, 'config_id')
            pay_dom = wiz._build_domain('payment_date', True, 'session_id.config_id')
            mrp_dom = wiz._build_domain('create_date', False)
            mov_dom = wiz._build_domain('date', False)

            wiz.preview_orders_count = (
                self.env['pos.order'].sudo().search_count(ord_dom)
                if (wiz.delete_pos_orders or wiz.delete_pos_sessions) else 0
            )
            wiz.preview_sessions_count = (
                self.env['pos.session'].sudo().search_count(sess_dom)
                if wiz.delete_pos_sessions else 0
            )
            wiz.preview_payments_count = (
                self.env['pos.payment'].sudo().search_count(pay_dom)
                if (wiz.delete_pos_payments or wiz.delete_pos_orders or wiz.delete_pos_sessions) else 0
            )
            wiz.preview_mrp_count = (
                self.env['mrp.production'].sudo().search_count(mrp_dom)
                if wiz.delete_mrp_productions else 0
            )
            wiz.preview_moves_count = (
                self.env['stock.move'].sudo().search_count(mov_dom)
                if wiz.delete_stock_moves else 0
            )
            wiz.preview_quants_count = (
                self.env['stock.quant'].sudo().search_count([])
                if wiz.reset_stock_quants else 0
            )

    def action_select_all(self):
        self.write({
            'delete_pos_orders': True,
            'delete_pos_sessions': True,
            'delete_pos_payments': True,
            'delete_mrp_productions': True,
            'delete_stock_moves': True,
            'reset_stock_quants': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_execute_cleanup(self):
        self.ensure_one()
        engine = self.env['permanent.delete.engine']
        engine._check_delete_permission()

        if (self.confirm_text or '').strip() != 'DELETE':
            raise UserError(_("Please type DELETE (in uppercase) in the confirmation box to proceed."))

        if not any([
            self.delete_pos_orders,
            self.delete_pos_sessions,
            self.delete_pos_payments,
            self.delete_mrp_productions,
            self.delete_stock_moves,
            self.reset_stock_quants,
            self.reset_sequences,
        ]):
            raise UserError(_("Please select at least one data category to delete."))

        summary_parts = []

        # 1. POS Sessions (also deletes their orders & payments)
        if self.delete_pos_sessions:
            sess_dom = self._build_domain('start_at', True, 'config_id')
            session_ids = self.env['pos.session'].sudo().search(sess_dom).ids
            count = engine.force_delete_pos_sessions(session_ids)
            summary_parts.append(_("%s POS Sessions", count))

        # 2. POS Orders
        if self.delete_pos_orders:
            ord_dom = self._build_domain('date_order', True, 'config_id')
            order_ids = self.env['pos.order'].sudo().search(ord_dom).ids
            count = engine.force_delete_pos_orders(order_ids)
            summary_parts.append(_("%s POS Orders", count))

        # 3. Standalone POS Payments
        if self.delete_pos_payments:
            pay_dom = self._build_domain('payment_date', True, 'session_id.config_id')
            payment_ids = self.env['pos.payment'].sudo().search(pay_dom).ids
            count = engine.force_delete_pos_payments(payment_ids)
            summary_parts.append(_("%s POS Payments", count))

        # 4. Manufacturing / Production Orders
        if self.delete_mrp_productions:
            mrp_dom = self._build_domain('create_date', False)
            mo_ids = self.env['mrp.production'].sudo().search(mrp_dom).ids
            count = engine.force_delete_productions(mo_ids)
            summary_parts.append(_("%s Manufacturing Orders", count))

        # 5. Inventory Pickings & Stock Moves
        if self.delete_stock_moves:
            pick_dom = self._build_domain('create_date', False)
            picking_ids = self.env['stock.picking'].sudo().search(pick_dom).ids
            pick_count = engine.force_delete_pickings(picking_ids)

            mov_dom = self._build_domain('date', False)
            move_ids = self.env['stock.move'].sudo().search(mov_dom).ids
            mov_count = engine.force_delete_stock_moves(move_ids)
            summary_parts.append(_("%s Transfers & %s Stock Moves", pick_count, mov_count))

        # 6. Reset Stock Quants (On-Hand Inventory)
        if self.reset_stock_quants:
            self.env.cr.execute("DELETE FROM stock_quant")
            self.env.invalidate_all()
            summary_parts.append(_("All Stock Quants Reset to 0"))

        # 7. Reset Sequences
        if self.reset_sequences:
            sequences = self.env['ir.sequence'].sudo().search([
                '|', '|', '|',
                ('code', 'ilike', 'pos.'),
                ('code', 'ilike', 'mrp.'),
                ('code', 'ilike', 'stock.'),
                ('prefix', 'in', ['WH/', 'POS/', 'MO/']),
            ])
            sequences.write({'number_next_actual': 1})
            summary_parts.append(_("%s Sequences Reset", len(sequences)))

        _logger.warning(
            "PERMANENT DATA CLEANUP executed by user %s (ID %s): %s",
            self.env.user.login,
            self.env.uid,
            ", ".join(summary_parts),
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Permanent Deletion Completed'),
                'message': _("Deleted: %s", ", ".join(summary_parts)),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }