# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class SmsSms(models.Model):
    _inherit = 'sms.sms'

    smstunnel_message_id = fields.Char('SMSTunnel message ID', copy=False, readonly=True)
    smstunnel_tries = fields.Integer(
        'SMSTunnel tries', copy=False, readonly=True,
        help="How many times SMSTunnel could not be reached for this text. It stays in the queue until it "
             "has been tried 8 times.")
    smstunnel_sign_in_code = fields.Boolean(
        'Sign-in code',
        help="For custom code that sends sign-in or verification codes: SMSTunnel sends the text through its "
             "sign-in code service, with its own daily allowance. The text must contain the code (4 to 10 "
             "digits, or 123-456) and be at most 320 characters.")

    def write(self, vals):
        # A text put back in the queue by hand (Resend, Retry) gets its tries back.
        if vals.get('state') == 'outgoing' and 'smstunnel_tries' not in vals:
            vals = dict(vals, smstunnel_tries=0)
        return super().write(vals)

    # SEND
    # ------------------------------------------------------------

    def _split_by_api(self):
        """Send the texts of companies that chose SMSTunnel through it; leave the others to Twilio / Odoo IAP.
        While SMSTunnel can't take texts (see ``res.company._smstunnel_wait``), a company's texts stay in the
        queue: the SMS queue cron sends them later."""
        todo_via_super = self.browse()
        now = fields.Datetime.now()
        for company, company_sms in self.grouped(lambda sms: sms._get_sms_company()).items():
            company_sudo = company.sudo()
            if company_sudo.sms_provider != 'smstunnel':
                todo_via_super |= company_sms
            elif company_sudo.smstunnel_retry_at and company_sudo.smstunnel_retry_at > now:
                _logger.info('SMSTunnel: %s text(s) of company %s stay in the queue until %s',
                             len(company_sms), company.id, company_sudo.smstunnel_retry_at)
            else:
                sms_api = company._get_sms_api_class()(self.env)
                sms_api._set_company(company)
                yield sms_api, company_sms
        if todo_via_super:
            yield from super(SmsSms, todo_via_super)._split_by_api()

    def _get_send_batch_size(self):
        companies = self._get_sms_company()
        if companies and any(company.sms_provider == 'smstunnel' for company in companies):
            # Each text is its own request: small batches keep the commits close to the requests.
            return int(self.env['ir.config_parameter'].sudo().get_param('sms_smstunnel.session.batch.size', 10))
        return super()._get_send_batch_size()

    def _handle_call_result_hook(self, results):
        """Keep SMSTunnel's message ID, on the text and on its tracker (texts are deleted once sent)."""
        smstunnel_sms = self.filtered(lambda sms: sms._get_sms_company().sms_provider == 'smstunnel')
        if smstunnel_sms:
            sms_by_uuid = smstunnel_sms.grouped('uuid')
            for result in results:
                message_id = result.get('smstunnel_message_id')
                sms = sms_by_uuid.get(result.get('uuid'))
                if not sms or not message_id:
                    continue
                sms.smstunnel_message_id = message_id
                if sms.sms_tracker_id:
                    sms.sms_tracker_id.write({
                        'smstunnel_message_id': message_id,
                        'smstunnel_company_id': sms._get_sms_company().id,
                        'smstunnel_status': 'pending' if result.get('state') == 'processing' else 'sent',
                    })
        super(SmsSms, self - smstunnel_sms)._handle_call_result_hook(results)

    def _smstunnel_is_marketing(self):
        """True for a text of an SMS Marketing mailing (when that app is installed)."""
        return bool('mailing_id' in self._fields and self.mailing_id)
