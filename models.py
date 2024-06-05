import os
import logging
import joblib
from odoo import models, api,fields, _
# Assurez-vous d'importer _ pour la traduction
_logger = logging.getLogger(__name__)

class CustomMrpProduction(models.Model):
    _inherit = 'mrp.production'
    sale_order_id = fields.Many2one('sale.order',string="Référence de commande")
    # def write(self, vals):
    #     res = super(CustomMrpProduction, self).write(vals)
    #     if 'state' in vals:
    #         for mo in self:
    #             related_order = self.env['sale.order'].search([('name', '=', mo.name)], limit=1)
    #             if related_order:
    #                 related_order._compute_status_commande()
    #     return res
