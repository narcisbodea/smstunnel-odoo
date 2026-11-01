# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import timedelta

from odoo import api, fields, models

from odoo.addons.sms_smstunnel.tools.smstunnel_client import SmsTunnelError

_logger = logging.getLogger(__name__)

# How long the cron follows a text: one waiting for an offline phone, and one sent but not yet delivered.
FOLLOW_WAITING_DAYS = 3
FOLLOW_SENT_HOURS = 24
# Status requests per cron run (SMSTunnel allows 100 requests a minute) and the pause between two checks.
STATUS_CHECKS_PER_RUN = 50
STATUS_CHECK_INTERVAL = timedelta(minutes=10)


class SmsTracker(models.Model):
    _inherit = 'sms.tracker'

    smstunnel_message_id = fields.Char('SMSTunnel message ID', readonly=True, index='btree_not_null')
    smstunnel_company_id = fields.Many2one('res.company', 'SMSTunnel company', readonly=True, ondelete='cascade')
    # pending: waits for the phone; sent: handed to the SIM; then delivered / failed / unconfirmed (final).
    smstunnel_status = fields.Char('SMSTunnel status', readonly=True)
    smstunnel_checked_at = fields.Datetime('SMSTunnel status checked at', readonly=True)

    @api.model
    def _cron_smstunnel_update_status(self):
        """Follow texts that SMSTunnel accepted: "Processing" (phone offline) becomes "Sent" when the phone
        sends it, "Sent" becomes "Delivered" with a delivery report, and a text the phone could not send
        becomes an error with the phone's reason."""
        now = fields.Datetime.now()
        trackers = self.search([
            ('smstunnel_message_id', '!=', False),
            '|', ('smstunnel_checked_at', '=', False), ('smstunnel_checked_at', '<=', now - STATUS_CHECK_INTERVAL),
            '|',
            '&', ('smstunnel_status', '=', 'pending'), ('create_date', '>=', now - timedelta(days=FOLLOW_WAITING_DAYS)),
            '&', ('smstunnel_status', '=', 'sent'), ('create_date', '>=', now - timedelta(hours=FOLLOW_SENT_HOURS)),
        ], order='smstunnel_checked_at asc nulls first, id', limit=STATUS_CHECKS_PER_RUN)

        for company, company_trackers in trackers.grouped('smstunnel_company_id').items():
            client = company._smstunnel_client() if company else None
            if not client:
                company_trackers.write({'smstunnel_status': 'unknown', 'smstunnel_checked_at': now})
                continue
            for tracker in company_trackers:
                try:
                    status = client.message_status(tracker.smstunnel_message_id)
                except SmsTunnelError as error:
                    if error.status == 404:
                        tracker.write({'smstunnel_status': 'unknown', 'smstunnel_checked_at': now})
                        continue
                    # 401/403 (key changed or not allowed to read statuses), 429, 5xx, no answer: try later.
                    _logger.info('SMSTunnel: status check stopped for company %s (HTTP %s): %s',
                                 company.id, error.status or '-', error.message)
                    break
                tracker._smstunnel_apply_status(status, now)

    def _smstunnel_apply_status(self, status, now=None):
        """Report SMSTunnel's status of a text on its notification (chatter) or trace."""
        self.ensure_one()
        state = status.get('deliveryStatus') or status.get('status')
        if status.get('unconfirmed'):
            state = 'unconfirmed'
        values = {'smstunnel_checked_at': now or fields.Datetime.now()}
        if state == 'sent':
            self._action_update_from_sms_state('pending')
        elif state == 'delivered':
            self._action_update_from_sms_state('sent')
        elif state == 'unconfirmed':
            # Handed to the SIM without a confirmation from the phone: probably sent, never sent again.
            self._action_update_from_sms_state('pending')
        elif state == 'failed':
            self.with_context(sms_known_failure_reason=status.get('errorMessage') or False)\
                ._action_update_from_provider_error('not_delivered')
        if state in ('pending', 'sent', 'delivered', 'failed', 'unconfirmed'):
            values['smstunnel_status'] = state
        self.write(values)
