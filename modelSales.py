from odoo import models, fields, api
from datetime import datetime
from itertools import combinations

class SaleOrder(models.Model):
    _inherit = 'sale.order'


    product_bom = fields.Many2one('mrp.bom', string='Product BOM')
    recommandation = fields.Char(string='Recommandation', compute='_compute_recommandation')
    status_commande = fields.Char(string='Status de Commande', compute='_compute_status_commande')
    quantity = fields.Float(string='Total Quantity',compute='_compute_total_quantity')

    @api.depends('order_line.product_uom_qty')
    def _compute_total_quantity(self):
        for order in self:
            order.quantity = sum(line.product_uom_qty for line in order.order_line)

    @api.depends('order_line')
    def _compute_status_commande(self):
        for order in self:
            mo = self.env['mrp.production'].search([('sale_order_id', '=', order.name)], limit=1)
            if mo:
                order.status_commande = mo.state
            else:
                order.status_commande = 'Unknown1'

    def fetch_odoo_data(self):

        sale_records = self.env['sale.order'].search([('status_commande', '=', 'Unknown1')])

        if not sale_records:
            # self.env['ir.logging'].create({
            #     'name': 'fetch_odoo_data',
            #     'type': 'server',
            #     'level': 'debug',
            #     'message': "No sale records found.",
            #     'path': 'sale_order',
            #     'line': '0',
            #     'func': 'fetch_odoo_data',
            # })
            return None, None

        all_data = []

        products = self.env['product.product'].search([])
        manufacture_route_id = self.env.ref('mrp.route_warehouse0_manufacture').id

        products_without_manufacture = [
            product for product in products if manufacture_route_id not in product.route_ids.ids
        ]

        product_stock = {product.name: product.qty_available for product in products_without_manufacture}

        for sale in sale_records:
            if sale.status_commande != 'Unknown1':
                continue
            order_lines = sale.order_line
            for line in order_lines:
                product_tmpl_id = line.product_id.product_tmpl_id.id if line.product_id else None
                bom_components = {}
                if product_tmpl_id:
                    boms = self.env['mrp.bom'].search([('product_tmpl_id', '=', product_tmpl_id)])
                    if boms:
                        bom_lines_details = self.env['mrp.bom.line'].search([('bom_id', '=', boms.id)])
                        for bom_line in bom_lines_details:
                            component_name = bom_line.product_id.name if bom_line.product_id else ''
                            component_qty = bom_line.product_qty
                            bom_components[component_name] = component_qty * line.product_uom_qty

                date_order = sale.date_order.date()  # Convert datetime to date
                expiration_date = sale.validity_date
                delivery_time = (expiration_date - date_order).days

                all_data.append({
                    'order_name': sale.name,
                    'product': line.product_id.name if line.product_id else '',
                    'product_uom_quantity': line.product_uom_qty,
                    'delivery_time': delivery_time,
                    'date_order': date_order.strftime('%Y-%m-%d'),
                    'amount_total': sale.amount_total,
                    'required_materials': bom_components,
                    'status_commande': sale.status_commande
                })

        # self.env['ir.logging'].create({
        #     'name': 'fetch_odoo_data',
        #     'type': 'server',
        #     'level': 'debug',
        #     'message': f"All data extracted: {all_data}",
        #     'path': 'sale_order',
        #     'line': '0',
        #     'func': 'fetch_odoo_data',
        # })

        return all_data, product_stock

    def generate_combinations(self, orders, stock):
        valid_combinations = []
        for r in range(1, len(orders) + 1):
            for combo in combinations(orders, r):
                material_needed = {}
                for order in combo:
                    for material, quantity in order['required_materials'].items():
                        if material in material_needed:
                            material_needed[material] += quantity * order['product_uom_quantity']
                        else:
                            material_needed[material] = quantity * order['product_uom_quantity']

                # Log material needed and stock details
                # self.env['ir.logging'].create({
                #     'name': 'generate_combinations',
                #     'type': 'server',
                #     'level': 'debug',
                #     'message': f"Combination: {[order['order_name'] for order in combo]}, Material Needed: {material_needed}, Stock: {stock}",
                #     'path': 'sale_order',
                #     'line': '0',
                #     'func': 'generate_combinations',
                # })

                if all(stock.get(material, 0) >= needed_mat for material, needed_mat in material_needed.items()):
                    valid_combinations.append(combo)

        # Log valid combinations found
        # self.env['ir.logging'].create({
        #     'name': 'generate_combinations',
        #     'type': 'server',
        #     'level': 'debug',
        #     'message': f"Valid Combinations: {[[order['order_name'] for order in combo] for combo in valid_combinations]}",
        #     'path': 'sale_order',
        #     'line': '0',
        #     'func': 'generate_combinations',
        # })

        return valid_combinations

    def extract_largest(self, valid_combinations):
        if not valid_combinations:
            return None

        largest_combo = valid_combinations[0]
        for combo in valid_combinations[1:]:
            if len(combo) > len(largest_combo):
                largest_combo = combo
            elif len(combo) == len(largest_combo):
                largest_max_delivery_time = max(order['delivery_time'] for order in largest_combo)
                current_max_delivery_time = max(order['delivery_time'] for order in combo)
                if current_max_delivery_time < largest_max_delivery_time:
                    largest_combo = combo

        # self.env['ir.logging'].create({
        #     'name': 'extract_largest',
        #     'type': 'server',
        #     'level': 'debug',
        #     'message': f"Largest Combo: {largest_combo}",
        #     'path': 'sale_order',
        #     'line': '0',
        #     'func': 'extract_largest',
        # })

        return largest_combo

    def sorted_orders(self, largest_combo):
        if not largest_combo:
            return []
        n = len(largest_combo)
        for i in range(n):
            for j in range(0, n - i - 1):
                if (largest_combo[j]['delivery_time'] > largest_combo[j + 1]['delivery_time']) or (
                        largest_combo[j]['delivery_time'] == largest_combo[j + 1]['delivery_time'] and
                        largest_combo[j]['amount_total'] < largest_combo[j + 1]['amount_total']):
                    largest_combo[j], largest_combo[j + 1] = largest_combo[j + 1], largest_combo[j]
        return largest_combo

    def other_orders(self, orders, largest_combo):
        others = []
        largest_combo_ids = {order['order_name'] for order in largest_combo}
        for order in orders:
            if order['order_name'] not in largest_combo_ids:
                others.append(order)
        sorted_others = self.sorted_orders(others)
        return sorted_others

    @api.depends('order_line')
    def _compute_recommandation(self):
        data, stock = self.fetch_odoo_data()

        if data and stock:
            orders = data
            valid_combinations = self.generate_combinations(orders, stock)

            largest_combo = self.extract_largest(valid_combinations)
            if largest_combo:
                sorted_largest_combo = self.sorted_orders(list(largest_combo))
                recommendations = {}
                for i in range(len(sorted_largest_combo)):
                    recommendations[sorted_largest_combo[i]['order_name']] = i + 1

                other_orders = self.other_orders(orders, largest_combo)
                for i in range(len(other_orders)):
                    recommendations[other_orders[i]['order_name']] = f"Insufficient Stock: {i + 1}"

                for order in self:
                    order.recommandation = recommendations.get(order.name, "")
            else:
                for order in self:
                    order.recommandation = "No valid combination"
        else:
            for order in self:
                order.recommandation = "No data or stock"

        for order in self:
            print(f"Final Order {order.name} recommendation: {order.recommandation}")
