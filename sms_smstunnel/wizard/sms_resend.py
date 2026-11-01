# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class SmsResend(models.TransientModel):
    """The "Sending Failures" dialog of a failed text in the chatter."""
    _inherit = 'sms.resend'

    smstunnel = fields.Boolean(compute='_compute_smstunnel')

    @api.depends('mail_message_id')
    def _compute_smstunnel(self):
        for wizard in self:
            company = wizard.mail_message_id.record_company_id or self.env.company
            wizard.smstunnel = company.sms_provider == 'smstunnel'


class SmsResendRecipient(models.TransientModel):
    _inherit = 'sms.resend.recipient'

    failure_reason = fields.Text(
        related='notification_id.failure_reason', string='Details', related_sudo=True, readonly=True)
