# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _
from odoo.addons.sms.tools.sms_api import SmsApiBase

from .smstunnel_client import MAX_CODE_TEXT_LENGTH, MAX_TEXT_LENGTH, SmsTunnelClient, SmsTunnelError

_logger = logging.getLogger(__name__)

# A text that keeps failing because SMSTunnel can't be reached is marked as failed after this many tries.
MAX_TRIES = 8


class SmsApiSmsTunnel(SmsApiBase):
    """Sends Odoo's texts through SMSTunnel: the company's own Android phone sends them from its own number.

    Like the core Twilio provider, it is chosen per company (``res.company.sms_provider``) and sends one
    request per number. What each answer becomes in Odoo:

    - accepted, phone online: ``success`` → SMS "Sent" (``pending``);
    - accepted, phone offline: ``processing`` → SMS "Processing" (``process``): the text waits on SMSTunnel
      and goes out when the phone is back; a cron then follows its status;
    - refused: an error state with the reason in words (see ``PROVIDER_TO_SMS_FAILURE_TYPE``);
    - SMSTunnel could not be reached, answered 5xx or asked to slow down (429): no result, so the text stays
      in Odoo's queue ("In Queue") and the SMS queue cron sends it later (see ``res.company._smstunnel_wait``).
    """

    PROVIDER_TO_SMS_FAILURE_TYPE = SmsApiBase.PROVIDER_TO_SMS_FAILURE_TYPE | {
        'smstunnel_not_set_up': 'sms_acc',
        'smstunnel_key': 'sms_acc',
        'smstunnel_not_allowed': 'sms_acc',
        'smstunnel_plan': 'sms_credit',
        # Not mapped on purpose, they become "unknown" with the reason in words: smstunnel_marketing,
        # smstunnel_phone, smstunnel_too_long, smstunnel_empty, smstunnel_refused.
    }

    def _get_sms_api_error_messages(self):
        messages = super()._get_sms_api_error_messages()
        messages.update({
            'smstunnel_marketing': _(
                "SMSTunnel sends texts people expect, one at a time; use it for transactional texts, "
                "not SMS marketing."),
            'smstunnel_not_set_up': _(
                "SMSTunnel isn't set up yet: add your API key in Settings → General Settings → "
                "Send SMS → Configure SMSTunnel."),
            'smstunnel_key': _(
                "SMSTunnel did not accept the API key. Check it in Settings → General Settings → "
                "Send SMS → Configure SMSTunnel."),
            'smstunnel_not_allowed': _("SMSTunnel did not allow this text with this API key."),
            'smstunnel_plan': _("Your SMSTunnel plan does not cover this text."),
            'smstunnel_phone': _(
                "SMSTunnel could not find the phone set as Phone ID. Copy the ID again under Phones in your "
                "SMSTunnel dashboard, or leave it empty to send from your main phone."),
            'smstunnel_too_long': _(
                "The text is too long: SMSTunnel takes up to %(text)s characters (%(code)s for a sign-in code).",
                text=MAX_TEXT_LENGTH, code=MAX_CODE_TEXT_LENGTH),
            'smstunnel_empty': _("The text is empty."),
            'smstunnel_refused': _("SMSTunnel refused the text."),
            'server_error': _(
                "SMSTunnel could not be reached, even after several tries. Resend the text when it is back."),
            'wrong_number_format': _(
                "The number is not valid. Write it in international format, with + and the country code."),
            'sms_number_missing': _("There is no number to send the text to."),
        })
        return messages

    def _send_sms_batch(self, messages, delivery_reports_url=False):
        """Send each number its own text. See ``sms/tools/sms_api.py`` for the arguments.

        :return: one result per number that got an answer, as ``{'uuid', 'state', 'failure_reason'}``,
          plus ``smstunnel_message_id`` for an accepted text. A number without a result stays in the queue.
        """
        company = (self.company or self.env.company).sudo()
        uuids = [number['uuid'] for message in messages for number in message.get('numbers') or []]
        sms_by_uuid = {sms.uuid: sms for sms in self.env['sms.sms'].sudo().search([('uuid', 'in', uuids)])}
        # The SMS Marketing "Test" wizard calls this method directly, with texts that are not linked to the
        # mailing yet; it is opened with the mailing in its context.
        marketing_test = bool(self.env.context.get('default_mailing_id'))
        client = company._smstunnel_client()
        options = company._smstunnel_send_options()

        results = []
        waiting = None  # set when SMSTunnel can't take texts right now: the other texts stay in the queue
        accepted = False
        for message in messages:
            body = message.get('content') or ''
            for number_info in message.get('numbers') or []:
                uuid = number_info['uuid']
                if waiting:
                    continue
                number = (number_info.get('number') or '').strip()
                sms = sms_by_uuid.get(uuid, self.env['sms.sms'].sudo())
                sign_in_code = bool(sms.smstunnel_sign_in_code)

                if marketing_test or sms._smstunnel_is_marketing():
                    results.append(self._failure(uuid, 'smstunnel_marketing'))
                elif not client:
                    results.append(self._failure(uuid, 'smstunnel_not_set_up'))
                elif not number:
                    results.append(self._failure(uuid, 'sms_number_missing'))
                elif not body.strip():
                    results.append(self._failure(uuid, 'smstunnel_empty'))
                elif len(body) > (MAX_CODE_TEXT_LENGTH if sign_in_code else MAX_TEXT_LENGTH):
                    results.append(self._failure(uuid, 'smstunnel_too_long'))
                else:
                    try:
                        answer = client.send(number, body, sign_in_code=sign_in_code, **options)
                    except SmsTunnelError as error:
                        if error.transient:
                            waiting = error
                            result = self._failure_after_tries(sms, uuid, error)
                        else:
                            result = self._failure_from_error(uuid, error)
                        if result:
                            results.append(result)
                        continue
                    accepted = True
                    results.append({
                        'uuid': uuid,
                        'state': 'processing' if SmsTunnelClient.is_queued(answer) else 'success',
                        'failure_reason': False,
                        'smstunnel_message_id': SmsTunnelClient.message_id_of(answer),
                    })

        if marketing_test:
            # The wizard leaves its texts in the queue: close them, or the SMS queue cron would send them.
            self.env['sms.sms'].sudo().browse([sms.id for sms in sms_by_uuid.values()]).filtered(
                lambda sms: sms.state == 'outgoing').write({
                    'state': 'error',
                    'failure_type': 'unknown',
                    'smstunnel_failure_reason': self._get_sms_api_error_messages()['smstunnel_marketing'],
                })
        if waiting:
            company._smstunnel_wait(waiting)
        elif accepted:
            company._smstunnel_resume()
        return results

    # ------------------------------------------------------------
    # Results
    # ------------------------------------------------------------

    def _failure(self, uuid, state, reason=None):
        return {
            'uuid': uuid,
            'state': state,
            'failure_reason': reason or self._get_sms_api_error_messages().get(state) or state,
        }

    def _failure_from_error(self, uuid, error):
        """A refusal from SMSTunnel (4xx): the state for Odoo, and SMSTunnel's own words as the reason."""
        message = error.message or ''
        if error.status == 401:
            state = 'smstunnel_key'
        elif error.status == 402 or (error.status == 403 and 'plan' in message.lower()):
            state = 'smstunnel_plan'
        elif error.status == 403:
            state = 'smstunnel_not_allowed'
        elif error.status == 404:
            state = 'smstunnel_phone'
        elif error.is_number_error:
            state = 'wrong_number_format'
        else:
            state = 'smstunnel_refused'
        _logger.info('SMSTunnel refused a text (HTTP %s): %s', error.status, message)
        explanation = self._get_sms_api_error_messages()[state]
        reason = _('%(explanation)s SMSTunnel said: %(message)s', explanation=explanation, message=message)
        return self._failure(uuid, state, reason)

    def _failure_after_tries(self, sms, uuid, error):
        """SMSTunnel could not take the text right now. The text stays in the queue (no result) until it
        has been tried ``MAX_TRIES`` times; a 429 (too many requests) does not count as a try."""
        _logger.info('SMSTunnel could not take a text now (HTTP %s): %s', error.status or '-', error.message)
        if error.status == 429 or not sms:
            return None
        tries = sms.smstunnel_tries + 1
        sms.smstunnel_tries = tries
        if tries < MAX_TRIES:
            return None
        reason = _('%(explanation)s Last answer: %(message)s',
                   explanation=self._get_sms_api_error_messages()['server_error'], message=error.message)
        return self._failure(uuid, 'server_error', reason)
