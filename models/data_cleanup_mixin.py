import logging
from odoo import models, api, _
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class PermanentDeleteEngine(models.AbstractModel):
    _name = 'permanent.delete.engine'
    _description = 'Permanent Delete SQL Engine'

    def _check_delete_permission(self):
        if not self.env.user.has_group('permanent_data_cleanup.group_permanent_delete_manager'):
            raise AccessError(_("You do not have permission to permanently delete records."))

    def _table_exists(self, table_name):
        self.env.cr.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
            (table_name,),
        )
        return self.env.cr.fetchone()[0]

    def _column_exists(self, table_name, column_name):
        self.env.cr.execute(
            "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = %s AND column_name = %s)",
            (table_name, column_name),
        )
        return self.env.cr.fetchone()[0]

    @api.model
    def force_delete_stock_moves(self, move_ids):
        """Permanently deletes stock.move records and their dependent move lines, valuation layers, and account moves."""
        self._check_delete_permission()
        if not move_ids:
            return 0
        move_tuple = tuple(move_ids)
        cr = self.env.cr

        # 1. Collect any accounting journal entries linked to these stock moves
        acct_move_ids = []
        if self._column_exists('account_move', 'stock_move_id'):
            cr.execute("SELECT id FROM account_move WHERE stock_move_id IN %s", (move_tuple,))
            acct_move_ids.extend([r[0] for r in cr.fetchall()])

        # 2. Delete stock_valuation_layer if stock_account is installed
        if self._table_exists('stock_valuation_layer'):
            if self._column_exists('stock_valuation_layer', 'account_move_id'):
                cr.execute(
                    "SELECT account_move_id FROM stock_valuation_layer WHERE stock_move_id IN %s AND account_move_id IS NOT NULL",
                    (move_tuple,),
                )
                acct_move_ids.extend([r[0] for r in cr.fetchall()])
            cr.execute("DELETE FROM stock_valuation_layer WHERE stock_move_id IN %s", (move_tuple,))

        # 3. Delete stock_move_line
        cr.execute("DELETE FROM stock_move_line WHERE move_id IN %s", (move_tuple,))

        # 4. Unlink or delete stock_scrap linked to these moves
        if self._table_exists('stock_scrap') and self._column_exists('stock_scrap', 'move_id'):
            cr.execute("DELETE FROM stock_scrap WHERE move_id IN %s", (move_tuple,))

        # 5. Delete stock_move
        cr.execute("DELETE FROM stock_move WHERE id IN %s", (move_tuple,))

        # 6. Delete linked accounting moves if any
        if acct_move_ids:
            self.force_delete_account_moves(list(set(acct_move_ids)))

        self.env.invalidate_all()
        return len(move_ids)

    @api.model
    def force_delete_account_moves(self, account_move_ids):
        """Permanently deletes account.move and account.move.line records."""
        self._check_delete_permission()
        if not account_move_ids:
            return 0
        am_tuple = tuple(account_move_ids)
        cr = self.env.cr

        if self._table_exists('account_partial_reconcile'):
            cr.execute(
                """
                DELETE FROM account_partial_reconcile
                WHERE debit_move_id IN (SELECT id FROM account_move_line WHERE move_id IN %s)
                   OR credit_move_id IN (SELECT id FROM account_move_line WHERE move_id IN %s)
                """,
                (am_tuple, am_tuple),
            )
        cr.execute("DELETE FROM account_move_line WHERE move_id IN %s", (am_tuple,))
        cr.execute("DELETE FROM account_move WHERE id IN %s", (am_tuple,))
        self.env.invalidate_all()
        return len(account_move_ids)

    @api.model
    def force_delete_pickings(self, picking_ids):
        """Permanently deletes stock.picking records and their stock moves."""
        self._check_delete_permission()
        if not picking_ids:
            return 0
        pick_tuple = tuple(picking_ids)
        cr = self.env.cr

        cr.execute("SELECT id FROM stock_move WHERE picking_id IN %s", (pick_tuple,))
        move_ids = [r[0] for r in cr.fetchall()]
        if move_ids:
            self.force_delete_stock_moves(move_ids)

        if self._table_exists('stock_scrap') and self._column_exists('stock_scrap', 'picking_id'):
            cr.execute("DELETE FROM stock_scrap WHERE picking_id IN %s", (pick_tuple,))

        cr.execute("DELETE FROM stock_picking WHERE id IN %s", (pick_tuple,))
        self.env.invalidate_all()
        return len(picking_ids)

    @api.model
    def force_delete_productions(self, production_ids):
        """Permanently deletes mrp.production orders, workorders, unbuilds, scraps, and stock moves."""
        self._check_delete_permission()
        if not production_ids:
            return 0
        mo_tuple = tuple(production_ids)
        cr = self.env.cr

        # 1. Find all raw and finished stock moves linked to these MOs
        move_ids = []
        if self._column_exists('stock_move', 'production_id'):
            cr.execute("SELECT id FROM stock_move WHERE production_id IN %s", (mo_tuple,))
            move_ids.extend([r[0] for r in cr.fetchall()])
        if self._column_exists('stock_move', 'raw_material_production_id'):
            cr.execute("SELECT id FROM stock_move WHERE raw_material_production_id IN %s", (mo_tuple,))
            move_ids.extend([r[0] for r in cr.fetchall()])

        # 2. Handle mrp.unbuild linked to these MOs
        if self._table_exists('mrp_unbuild') and self._column_exists('mrp_unbuild', 'mo_id'):
            cr.execute("SELECT id FROM mrp_unbuild WHERE mo_id IN %s", (mo_tuple,))
            unbuild_ids = [r[0] for r in cr.fetchall()]
            if unbuild_ids:
                ub_tuple = tuple(unbuild_ids)
                if self._column_exists('stock_move', 'unbuild_id'):
                    cr.execute("SELECT id FROM stock_move WHERE unbuild_id IN %s", (ub_tuple,))
                    move_ids.extend([r[0] for r in cr.fetchall()])
                if self._column_exists('stock_move', 'consume_unbuild_id'):
                    cr.execute("SELECT id FROM stock_move WHERE consume_unbuild_id IN %s", (ub_tuple,))
                    move_ids.extend([r[0] for r in cr.fetchall()])
                cr.execute("DELETE FROM mrp_unbuild WHERE id IN %s", (ub_tuple,))

        if move_ids:
            self.force_delete_stock_moves(list(set(move_ids)))

        # 3. Delete scraps & workorders
        if self._table_exists('stock_scrap') and self._column_exists('stock_scrap', 'production_id'):
            cr.execute("DELETE FROM stock_scrap WHERE production_id IN %s", (mo_tuple,))

        if self._table_exists('mrp_workorder'):
            cr.execute("DELETE FROM mrp_workorder WHERE production_id IN %s", (mo_tuple,))

        # 4. Delete mrp_production
        cr.execute("DELETE FROM mrp_production WHERE id IN %s", (mo_tuple,))
        self.env.invalidate_all()
        return len(production_ids)

    @api.model
    def force_delete_pos_payments(self, payment_ids):
        """Permanently deletes pos.payment records."""
        self._check_delete_permission()
        if not payment_ids:
            return 0
        pay_tuple = tuple(payment_ids)
        cr = self.env.cr

        acct_move_ids = []
        if self._column_exists('pos_payment', 'account_move_id'):
            cr.execute(
                "SELECT account_move_id FROM pos_payment WHERE id IN %s AND account_move_id IS NOT NULL",
                (pay_tuple,),
            )
            acct_move_ids.extend([r[0] for r in cr.fetchall()])

        cr.execute("DELETE FROM pos_payment WHERE id IN %s", (pay_tuple,))
        if acct_move_ids:
            self.force_delete_account_moves(list(set(acct_move_ids)))

        self.env.invalidate_all()
        return len(payment_ids)

    @api.model
    def force_delete_pos_orders(self, order_ids):
        """Permanently deletes pos.order records along with their lines, payments, pickings, and invoices."""
        self._check_delete_permission()
        if not order_ids:
            return 0
        ord_tuple = tuple(order_ids)
        cr = self.env.cr

        # 1. Delete linked pos.payment
        cr.execute("SELECT id FROM pos_payment WHERE pos_order_id IN %s", (ord_tuple,))
        pay_ids = [r[0] for r in cr.fetchall()]
        if pay_ids:
            self.force_delete_pos_payments(pay_ids)

        # 2. Delete linked stock.picking
        if self._column_exists('stock_picking', 'pos_order_id'):
            cr.execute("SELECT id FROM stock_picking WHERE pos_order_id IN %s", (ord_tuple,))
            pick_ids = [r[0] for r in cr.fetchall()]
            if pick_ids:
                self.force_delete_pickings(pick_ids)

        # 3. Collect linked account.move (invoices)
        acct_move_ids = []
        if self._column_exists('pos_order', 'account_move'):
            cr.execute(
                "SELECT account_move FROM pos_order WHERE id IN %s AND account_move IS NOT NULL",
                (ord_tuple,),
            )
            acct_move_ids.extend([r[0] for r in cr.fetchall()])

        # 4. Clear self-referencing refund links & delete pos_order_line and pos_order
        if self._column_exists('pos_order_line', 'refunded_orderline_id'):
            cr.execute(
                "UPDATE pos_order_line SET refunded_orderline_id = NULL WHERE order_id IN %s OR refunded_orderline_id IN (SELECT id FROM pos_order_line WHERE order_id IN %s)",
                (ord_tuple, ord_tuple),
            )
        cr.execute("DELETE FROM pos_order_line WHERE order_id IN %s", (ord_tuple,))
        cr.execute("DELETE FROM pos_order WHERE id IN %s", (ord_tuple,))

        if acct_move_ids:
            self.force_delete_account_moves(list(set(acct_move_ids)))

        self.env.invalidate_all()
        return len(order_ids)

    @api.model
    def force_delete_pos_sessions(self, session_ids):
        """Permanently deletes pos.session records and all orders, pickings, cash statements, and moves inside them."""
        self._check_delete_permission()
        if not session_ids:
            return 0
        sess_tuple = tuple(session_ids)
        cr = self.env.cr

        # 1. Delete all POS orders in these sessions
        cr.execute("SELECT id FROM pos_order WHERE session_id IN %s", (sess_tuple,))
        order_ids = [r[0] for r in cr.fetchall()]
        if order_ids:
            self.force_delete_pos_orders(order_ids)

        # 2. Delete session pickings
        if self._column_exists('stock_picking', 'pos_session_id'):
            cr.execute("SELECT id FROM stock_picking WHERE pos_session_id IN %s", (sess_tuple,))
            pick_ids = [r[0] for r in cr.fetchall()]
            if pick_ids:
                self.force_delete_pickings(pick_ids)

        # 3. Delete bank statement lines (Cash In / Out) linked to these sessions
        acct_move_ids = []
        if self._column_exists('account_bank_statement_line', 'pos_session_id'):
            cr.execute(
                "SELECT move_id FROM account_bank_statement_line WHERE pos_session_id IN %s AND move_id IS NOT NULL",
                (sess_tuple,),
            )
            acct_move_ids.extend([r[0] for r in cr.fetchall()])
            cr.execute("DELETE FROM account_bank_statement_line WHERE pos_session_id IN %s", (sess_tuple,))

        # 4. Collect session journal entry (move_id)
        if self._column_exists('pos_session', 'move_id'):
            cr.execute(
                "SELECT move_id FROM pos_session WHERE id IN %s AND move_id IS NOT NULL",
                (sess_tuple,),
            )
            acct_move_ids.extend([r[0] for r in cr.fetchall()])
            cr.execute("UPDATE pos_session SET move_id = NULL WHERE id IN %s", (sess_tuple,))

        # 5. Delete pos_session
        cr.execute("DELETE FROM pos_session WHERE id IN %s", (sess_tuple,))

        if acct_move_ids:
            self.force_delete_account_moves(list(set(acct_move_ids)))

        self.env.invalidate_all()
        return len(session_ids)


# Extend Operational Models with Contextual "Delete Permanently" Action
class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_force_delete_permanently(self):
        self.env['permanent.delete.engine'].force_delete_pos_orders(self.ids)
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class PosSession(models.Model):
    _inherit = 'pos.session'

    def action_force_delete_permanently(self):
        self.env['permanent.delete.engine'].force_delete_pos_sessions(self.ids)
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    def action_force_delete_permanently(self):
        self.env['permanent.delete.engine'].force_delete_pos_payments(self.ids)
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def action_force_delete_permanently(self):
        self.env['permanent.delete.engine'].force_delete_productions(self.ids)
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_force_delete_permanently(self):
        self.env['permanent.delete.engine'].force_delete_pickings(self.ids)
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class StockMove(models.Model):
    _inherit = 'stock.move'

    def action_force_delete_permanently(self):
        self.env['permanent.delete.engine'].force_delete_stock_moves(self.ids)
        return {'type': 'ir.actions.client', 'tag': 'reload'}