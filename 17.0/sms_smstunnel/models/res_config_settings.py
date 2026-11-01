# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_open_sms_smstunnel_account_manage(self):
        return self.company_id._action_open_sms_smstunnel_account_manage()
