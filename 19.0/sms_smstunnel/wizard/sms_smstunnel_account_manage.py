# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.sms_smstunnel.tools.smstunnel_client import SmsTunnelClient, SmsTunnelError


class SmsSmsTunnelAccountManage(models.TransientModel):
    _name = 'sms.smstunnel.account.manage'
    _description = 'SMSTunnel Connection Wizard'

    company_id = fields.Many2one(
        'res.company', required=True, readonly=True, default=lambda self: self.env.company)
    smstunnel_api_key = fields.Char(related='company_id.smstunnel_api_key', readonly=False)
    smstunnel_device_id = fields.Char(related='company_id.smstunnel_device_id', readonly=False)
    smstunnel_country_code = fields.Char(related='company_id.smstunnel_country_code', readonly=False)
    smstunnel_country_code_hint = fields.Char(compute='_compute_smstunnel_country_code_hint')
    test_number = fields.Char('Test number', default=lambda self: self._default_test_number())

    def _default_test_number(self):
        return self.env.user.partner_id.phone or ''

    @api.depends('company_id')
    def _compute_smstunnel_country_code_hint(self):
        for wizard in self:
            country = wizard.company_id.country_id
            if country.phone_code:
                wizard.smstunnel_country_code_hint = _(
                    "Empty: +%(code)s, the calling code of %(country)s (the company's country).",
                    code=country.phone_code, country=country.name)
            else:
                wizard.smstunnel_country_code_hint = _("Empty: the country set for your phone in SMSTunnel.")

    # ------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------

    def action_send_test(self):
        """Send one text straight away, to check the key, the phone and the number."""
        self.ensure_one()
        number = (self.test_number or '').strip()
        if not number:
            raise UserError(_("Type the number that should get the test text."))
        company = self.company_id
        client = company._smstunnel_client(raise_if_missing=True)
        number = self.env.user._phone_format(number=number) or number
        try:
            answer = client.send(
                number,
                _("This is a test text from Odoo, sent through SMSTunnel from your own phone."),
                **company._smstunnel_send_options())
        except SmsTunnelError as error:
            return self._notify('danger', self._explain(error))
        # SMSTunnel works: texts that waited in the queue can go out now.
        company._smstunnel_resume()
        if self.env['sms.sms'].sudo().search_count([('state', '=', 'outgoing')], limit=1):
            company._smstunnel_trigger_queue()
        if SmsTunnelClient.is_queued(answer):
            message = _("SMSTunnel took the test text for %(number)s. Your phone is offline right now: "
                        "the text goes out as soon as it is back online.", number=number)
        else:
            message = _("SMSTunnel took the test text for %(number)s and your phone is sending it now.",
                        number=number)
        return self._notify('success', message)

    def action_check_connection(self):
        """Check the key and list the phones of the SMSTunnel account."""
        self.ensure_one()
        client = self.company_id._smstunnel_client(raise_if_missing=True)
        try:
            data = client.devices()
        except SmsTunnelError as error:
            return self._notify('danger', self._explain(error))
        devices = data.get('devices') or []
        if not devices:
            return self._notify('warning', _(
                "The key works, but no phone is linked to this SMSTunnel account yet. Install the SMSTunnel app "
                "from Google Play on your Android phone and sign in, or link it under Phones → Add phone."))
        # A plain loop: _() finds the user's language in this method's frame, not in a generator's.
        phones = []
        for device in devices:
            phones.append(_('%(name)s (%(state)s, ID %(id)s)', name=device.get('name') or _('Phone'),
                            state=_('online') if device.get('isOnline') else _('offline'), id=device.get('id')))
        message = _("The key works. Phones: %(phones)s.", phones=', '.join(phones))
        device_id = (self.smstunnel_device_id or '').strip()
        if device_id and device_id not in {device.get('id') for device in devices}:
            return self._notify('warning', message + ' ' + _(
                "The Phone ID set here is not one of them: copy it again, or leave it empty."))
        return self._notify('success', message, sticky=True)

    def action_save(self):
        return {'type': 'ir.actions.act_window_close'}

    # ------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------

    @api.model
    def _explain(self, error):
        if error.status == 401:
            return _("SMSTunnel did not accept the API key (%(message)s). Copy it again from Apps in your "
                     "SMSTunnel dashboard.", message=error.message)
        if error.status == 403:
            return _("SMSTunnel did not allow it: %(message)s", message=error.message)
        if error.status == 404:
            return _("SMSTunnel could not find the phone (%(message)s). Check the Phone ID, or leave it empty "
                     "to use your main phone.", message=error.message)
        if error.status == 429:
            return _("SMSTunnel asks to slow down. Try again in %(seconds)s seconds.",
                     seconds=error.retry_after or 60)
        if error.transient:
            return _("%(message)s. Try again in a moment.", message=error.message)
        return _("SMSTunnel refused it: %(message)s", message=error.message)

    def _notify(self, notif_type, message, sticky=None):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("SMSTunnel"),
                'message': message,
                'type': notif_type,
                'sticky': notif_type != 'success' if sticky is None else sticky,
            },
        }
