# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.sms_smstunnel.tools.sms_api import SmsApiSmsTunnel
from odoo.addons.sms_smstunnel.tools.smstunnel_client import DEFAULT_SERVER_URL, SmsTunnelClient

_logger = logging.getLogger(__name__)

# Minutes to wait before trying again, after 1, 2, 3... failures in a row to reach SMSTunnel.
RETRY_DELAYS = (1, 2, 5, 10, 30, 60)
SERVER_URL_PARAM = 'sms_smstunnel.server_url'


def _module_version():
    try:
        from odoo.modules.module import get_manifest
        return get_manifest('sms_smstunnel').get('version') or '1.0'
    except Exception:  # noqa: BLE001 - only used for the User-Agent header
        return '1.0'


class ResCompany(models.Model):
    _inherit = 'res.company'

    sms_provider = fields.Selection(
        selection_add=[('smstunnel', 'Send via SMSTunnel')],
        ondelete={'smstunnel': 'set default'},
    )
    smstunnel_api_key = fields.Char(
        'SMSTunnel API key', groups='base.group_system', copy=False,
        help="The key of an app in your SMSTunnel dashboard (Apps → Add an app). It is shown only once there.")
    smstunnel_device_id = fields.Char(
        'Phone ID', groups='base.group_system', copy=False,
        help="Which of your phones sends the texts. Empty: your main phone. "
             "Copy a phone's ID under Phones in your SMSTunnel dashboard.")
    smstunnel_country_code = fields.Char(
        'Default country code', groups='base.group_system',
        help="Completes numbers written without + or 00, such as 0721 123 456. "
             "Empty: the calling code of the company's country.")
    # When SMSTunnel could not be reached (or asked to slow down), texts wait in the queue until then.
    smstunnel_retry_at = fields.Datetime('SMSTunnel: retry at', groups='base.group_system', copy=False, readonly=True)
    smstunnel_failures = fields.Integer('SMSTunnel: failures in a row', groups='base.group_system', copy=False, readonly=True)

    @api.constrains('smstunnel_country_code')
    def _check_smstunnel_country_code(self):
        for company in self.sudo():
            code = (company.smstunnel_country_code or '').strip()
            if code and not re.fullmatch(r'(\+|00)?[1-9]\d{0,3}', code):
                raise ValidationError(_("The default country code must be a calling code such as +40, 40 or 0040."))

    def _get_sms_api_class(self):
        self.ensure_one()
        if self.sms_provider == 'smstunnel':
            return SmsApiSmsTunnel
        return super()._get_sms_api_class()

    # ------------------------------------------------------------
    # SMSTunnel settings
    # ------------------------------------------------------------

    def _smstunnel_client(self, raise_if_missing=False):
        """A client for this company's API key, or None when no key is set."""
        self.ensure_one()
        api_key = (self.sudo().smstunnel_api_key or '').strip()
        if not api_key:
            if raise_if_missing:
                raise UserError(_("Add your SMSTunnel API key first (Apps → Add an app in your SMSTunnel dashboard)."))
            return None
        server_url = self.env['ir.config_parameter'].sudo().get_param(SERVER_URL_PARAM) or DEFAULT_SERVER_URL
        return SmsTunnelClient(api_key, server_url=server_url, version=_module_version())

    def _smstunnel_country_code(self):
        """The calling code that completes local numbers: the setting, else the company's country."""
        self.ensure_one()
        code = (self.sudo().smstunnel_country_code or '').strip()
        if code:
            return code
        return str(self.country_id.phone_code) if self.country_id.phone_code else ''

    def _smstunnel_send_options(self):
        self.ensure_one()
        return {
            'device_id': (self.sudo().smstunnel_device_id or '').strip() or None,
            'country_code': self._smstunnel_country_code() or None,
        }

    # ------------------------------------------------------------
    # When SMSTunnel can't take texts
    # ------------------------------------------------------------

    def _smstunnel_wait(self, error):
        """SMSTunnel could not be reached, failed (5xx) or asked to slow down (429): keep this company's
        texts in the queue for a while, and have the SMS queue cron send them then."""
        self.ensure_one()
        company = self.sudo()
        if error.status == 429:
            failures = company.smstunnel_failures
            delay = timedelta(seconds=error.retry_after or 60)
        else:
            failures = company.smstunnel_failures + 1
            delay = timedelta(minutes=RETRY_DELAYS[min(failures, len(RETRY_DELAYS)) - 1])
        retry_at = fields.Datetime.now() + delay
        company.write({'smstunnel_retry_at': retry_at, 'smstunnel_failures': failures})
        _logger.info('SMSTunnel: texts of company %s wait in the queue until %s', company.id, retry_at)
        self._smstunnel_trigger_queue(retry_at)

    def _smstunnel_resume(self):
        """SMSTunnel took a text: stop waiting."""
        self.ensure_one()
        company = self.sudo()
        if company.smstunnel_retry_at or company.smstunnel_failures:
            company.write({'smstunnel_retry_at': False, 'smstunnel_failures': 0})

    def _smstunnel_trigger_queue(self, at=None):
        cron = self.env.ref('sms.ir_cron_sms_scheduler_action', raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger(at=at)

    def _action_open_sms_smstunnel_account_manage(self):
        return {
            'name': _('SMSTunnel'),
            'res_model': 'sms.smstunnel.account.manage',
            'res_id': False,
            'context': self.env.context,
            'type': 'ir.actions.act_window',
            'views': [(False, 'form')],
            'view_mode': 'form',
            'target': 'new',
        }
