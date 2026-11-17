{
    'name': 'Permanent Delete: POS, Sessions, Payments, Production & Inventory',
    'version': '20.0.1.0.0',
    'category': 'Administration',
    'summary': 'Force delete POS orders, sessions, payments, manufacturing orders, and inventory moves permanently',
    'description': """
Permanent Data Cleanup & Force Delete (Odoo 20)
===============================================
Allows authorized administrators to permanently delete operational records:
- POS Orders & Order Lines (`pos.order`, `pos.order.line`)
- POS Sessions & Cash Statements (`pos.session`, `account.bank.statement.line`)
- POS Payments (`pos.payment`)
- Manufacturing / Production Orders & Workorders (`mrp.production`, `mrp.workorder`, `mrp.unbuild`)
- Inventory Pickings, Stock Moves, Scrap & Quants (`stock.picking`, `stock.move`, `stock.quant`)
- Includes both a centralized Date-Range Cleanup Wizard and contextual "Delete Permanently (Force)" actions in List/Form views.
    """,
    'author': 'Custom',
    'depends': ['base', 'point_of_sale', 'mrp', 'stock', 'account'],
    'data': [
        'security/permanent_delete_security.xml',
        'security/ir.access.csv',
        'views/data_cleanup_views.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}