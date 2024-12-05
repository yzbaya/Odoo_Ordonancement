# -*- coding: utf-8 -*-

# my_fabrication.py
from odoo import models, fields

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    sale_order_id = fields.Many2one('sale.order',string="Référence de commande")


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    def button_finish(self, elapsed_seconds=None):
        for order in self:
            if elapsed_seconds:
                order.duration = elapsed_seconds / 3600.0  # Assuming duration is stored in hours
            # Proceed with the original finish process
            super(MrpWorkorder, order).button_finish()
