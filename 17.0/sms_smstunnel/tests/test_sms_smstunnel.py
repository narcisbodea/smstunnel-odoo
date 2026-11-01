# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.sms.tools.sms_api import SmsApi
from odoo.addons.sms_smstunnel.tools.sms_api import MAX_TRIES, SmsApiSmsTunnel
from odoo.tests import tagged

from .common import SmsTunnelCase

MARKETING_REFUSAL = ("SMSTunnel sends texts people expect, one at a time; use it for transactional texts, "
                     "not SMS marketing.")


@tagged('post_install', '-at_install', 'sms_smstunnel')
class TestSmsTunnelSend(SmsTunnelCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Ana Pop', 'mobile': '+40721234567'})

    def test_provider_choice(self):
        selection = dict(self.env['res.company']._fields['sms_provider'].selection)
        self.assertIn('smstunnel', selection)
        self.assertIn('twilio', selection, 'The core Twilio choice stays available')
        self.assertIs(self.company._get_sms_api_class(), SmsApiSmsTunnel)
        other_company = self.env['res.company'].create({'name': 'Other company'})
        self.assertIs(other_company._get_sms_api_class(), SmsApi, 'Other companies keep their own provider')

    def test_send_to_number(self):
        with self.mock_smstunnel():
            sms = self.send_to_number('+40721234567')
        self.assertEqual(sms.state, 'pending', 'Accepted by SMSTunnel: "Sent"')
        self.assertFalse(sms.failure_type)
        self.assertTrue(sms.to_delete)
        self.assertTrue(sms.smstunnel_message_id)
        self.assertEqual(len(self.smstunnel_requests), 1)
        request = self.smstunnel_requests[0]
        self.assertEqual(request['method'], 'POST')
        self.assertEqual(request['path'], '/api/v1/sms/send')
        self.assertEqual(request['headers']['X-API-Key'], self.API_KEY)
        self.assertEqual(request['headers']['Content-Type'], 'application/json')
        # Only the fields SMSTunnel accepts (others are refused with 400); the company's country completes
        # local numbers.
        self.assertEqual(request['json'], {
            'to': '+40721234567',
            'message': 'Your order SO042 is ready for pickup.',
            'defaultCountryCode': '40',
        })

    def test_one_request_per_number(self):
        with self.mock_smstunnel():
            sms = self.send_to_number('+40721234567,+40721234568,+40721234569')
        self.assertEqual(len(sms), 3)
        self.assertEqual(set(sms.mapped('state')), {'pending'})
        self.assertEqual(sorted(r['json']['to'] for r in self.smstunnel_requests),
                         ['+40721234567', '+40721234568', '+40721234569'])

    def test_send_to_contact(self):
        with self.mock_smstunnel():
            message = self.send_to_partner(self.partner)
        notification = self.sms_notification(message)
        self.assertEqual(notification.notification_status, 'pending')
        self.assertEqual(notification.sms_number, '+40721234567')
        tracker = notification.sms_tracker_ids
        self.assertTrue(tracker.smstunnel_message_id)
        self.assertEqual(tracker.smstunnel_status, 'sent')
        self.assertEqual(tracker.smstunnel_company_id, self.company)

    def test_phone_offline(self):
        """The phone is offline: SMSTunnel keeps the text and sends it when the phone is back."""
        with self.mock_smstunnel(self.accepted(queued=True)):
            message = self.send_to_partner(self.partner)
        notification = self.sms_notification(message)
        self.assertEqual(notification.notification_status, 'process')
        self.assertEqual(notification.sms_tracker_ids.smstunnel_status, 'pending')

    def test_refusals(self):
        for answer, failure_type, words in [
            (self.refused(401, 'Invalid or expired API key', 'Unauthorized'), 'sms_acc', 'Invalid or expired API key'),
            (self.refused(403, "This API key lacks the 'sms:send' permission", 'Forbidden', 'PERMISSION_REQUIRED'),
             'sms_acc', "lacks the 'sms:send' permission"),
            (self.refused(400, ['Phone number must contain 7-25 characters (digits, spaces, dots, dashes, + allowed)'],
                          'Bad Request'), 'sms_number_format', 'Phone number must contain 7-25 characters'),
            (self.refused(400, 'Sending to short/premium numbers is blocked for security', 'Bad Request'),
             'sms_number_format', 'premium numbers'),
            (self.refused(404, 'Device not found', 'Not Found'), 'unknown', 'Phone ID'),
            (self.refused(400, ['message must be shorter than or equal to 1600 characters'], 'Bad Request'),
             'unknown', 'message must be shorter'),
        ]:
            with self.subTest(status=answer[0], words=words):
                with self.mock_smstunnel(answer):
                    message = self.send_to_partner(self.partner)
                notification = self.sms_notification(message)
                self.assertEqual(notification.notification_status, 'exception')
                self.assertEqual(notification.failure_type, failure_type)
                self.assertIn(words, notification.failure_reason)
                sms = self.env['sms.sms'].sudo().search([('mail_message_id', '=', message.id)])
                self.assertEqual(sms.state, 'error')
                self.assertEqual(sms.failure_type, failure_type)
                self.assertIn(words, sms.smstunnel_failure_reason, 'The reason is kept on the text too')
                self.assertFalse(sms.to_delete, 'Failed texts stay visible')

    def test_sending_failures_dialog(self):
        """The chatter's "Sending Failures" dialog shows SMSTunnel's reason and no Odoo credits button."""
        with self.mock_smstunnel(self.refused(401, 'Invalid or expired API key', 'Unauthorized')):
            message = self.send_to_partner(self.partner)
        wizard = self.env['sms.resend'].with_context(default_mail_message_id=message.id).create({})
        self.assertTrue(wizard.smstunnel)
        self.assertTrue(wizard.has_unregistered_account, 'Odoo still offers to resend once the key is fixed')
        self.assertIn('Invalid or expired API key', wizard.recipient_ids.failure_reason)

    def test_not_set_up(self):
        self.company.smstunnel_api_key = False
        with self.mock_smstunnel():
            message = self.send_to_partner(self.partner)
        self.assertFalse(self.smstunnel_requests)
        notification = self.sms_notification(message)
        self.assertEqual(notification.failure_type, 'sms_acc')
        self.assertIn("SMSTunnel isn't set up yet", notification.failure_reason)

    def test_too_long(self):
        with self.mock_smstunnel():
            sms = self.send_to_number('+40721234567', body='x' * 1601)
        self.assertFalse(self.smstunnel_requests)
        self.assertEqual(sms.state, 'error')
        self.assertEqual(sms.failure_type, 'unknown')

    def test_device_and_country_code(self):
        self.company.write({'smstunnel_device_id': '6ae660e96609f21a1184a210', 'smstunnel_country_code': '+49'})
        with self.mock_smstunnel():
            self.send_to_number('+40721234567')
        self.assertEqual(self.smstunnel_requests[0]['json']['deviceId'], '6ae660e96609f21a1184a210')
        self.assertEqual(self.smstunnel_requests[0]['json']['defaultCountryCode'], '+49')

    def test_sign_in_code(self):
        sms = self.env['sms.sms'].sudo().create({
            'number': '+40721234567', 'body': 'Your sign-in code is 482913', 'smstunnel_sign_in_code': True,
        })
        with self.mock_smstunnel():
            sms.send()
        self.assertEqual(self.smstunnel_requests[0]['path'], '/api/v1/sms/send-2fa')
        self.assertEqual(sms.state, 'pending')

    def test_smstunnel_down_then_back(self):
        """SMSTunnel can't be reached: the texts stay in the queue and go out when it is back."""
        before = fields.Datetime.now()
        with self.mock_smstunnel(self.unreachable()):
            sms = self.send_to_number('+40721234567,+40721234568')
        self.assertEqual(len(self.smstunnel_requests), 1, 'The other texts are not tried while SMSTunnel is down')
        self.assertEqual(set(sms.mapped('state')), {'outgoing'})
        self.assertEqual(sorted(sms.mapped('smstunnel_tries')), [0, 1])
        self.assertEqual(self.company.smstunnel_failures, 1)
        self.assertGreater(self.company.smstunnel_retry_at, before)
        cron = self.env.ref('sms.ir_cron_sms_scheduler_action')
        self.assertTrue(self.env['ir.cron.trigger'].search([('cron_id', '=', cron.id), ('call_at', '>', before)]),
                        'The SMS queue runs again when the wait is over')

        # While waiting, the queue does not call SMSTunnel at all.
        with self.mock_smstunnel():
            self.process_queue()
        self.assertFalse(self.smstunnel_requests)
        self.assertEqual(set(sms.mapped('state')), {'outgoing'})

        # SMSTunnel is back.
        self.company.smstunnel_retry_at = fields.Datetime.now() - timedelta(seconds=1)
        with self.mock_smstunnel():
            self.process_queue()
        self.assertEqual(len(self.smstunnel_requests), 2)
        self.assertEqual(set(sms.mapped('state')), {'pending'})
        self.assertFalse(self.company.smstunnel_retry_at)
        self.assertEqual(self.company.smstunnel_failures, 0)

    def test_server_error_waits_longer_each_time(self):
        sms = self.env['sms.sms'].sudo().create({'number': '+40721234567', 'body': 'Hello'})
        delays = []
        for _attempt in range(3):
            self.company.smstunnel_retry_at = False
            before = fields.Datetime.now()
            with self.mock_smstunnel(self.refused(502, 'Bad Gateway', 'Bad Gateway')):
                sms.send()
            delays.append(self.company.smstunnel_retry_at - before)
        self.assertEqual(sms.state, 'outgoing')
        self.assertEqual(sms.smstunnel_tries, 3)
        self.assertLess(delays[0], delays[1])
        self.assertLess(delays[1], delays[2])

    def test_gives_up_after_max_tries(self):
        sms = self.env['sms.sms'].sudo().create({'number': '+40721234567', 'body': 'Hello'})
        sms.smstunnel_tries = MAX_TRIES - 1
        with self.mock_smstunnel(self.unreachable()):
            sms.send()
        self.assertEqual(sms.state, 'error')
        self.assertEqual(sms.failure_type, 'sms_server')
        # Resending by hand starts counting again.
        sms.resend_failed()
        self.assertEqual(sms.smstunnel_tries, 0)

    def test_too_many_requests(self):
        before = fields.Datetime.now()
        with self.mock_smstunnel(self.refused(429, 'ThrottlerException: Too Many Requests', 'Too Many Requests',
                                              headers={'Retry-After': '30'})):
            sms = self.send_to_number('+40721234567,+40721234568')
        self.assertEqual(len(self.smstunnel_requests), 1)
        self.assertEqual(set(sms.mapped('state')), {'outgoing'})
        self.assertEqual(sms.mapped('smstunnel_tries'), [0, 0], 'Slowing down is not a failed try')
        self.assertEqual(self.company.smstunnel_failures, 0)
        wait = self.company.smstunnel_retry_at - before
        self.assertGreaterEqual(wait, timedelta(seconds=29))
        self.assertLess(wait, timedelta(seconds=40))

    def test_other_company_keeps_its_provider(self):
        company_iap = self.env['res.company'].create({'name': 'Company IAP', 'sms_provider': 'iap'})
        sms_iap = self.env['sms.sms'].sudo().create({
            'number': '+40721234567', 'body': 'Via Odoo', 'record_company_id': company_iap.id,
        })
        sms_smstunnel = self.env['sms.sms'].sudo().create({
            'number': '+40721234568', 'body': 'Via SMSTunnel', 'record_company_id': self.company.id,
        })
        iap_calls = []

        def _iap_send(api, messages, delivery_reports_url=False):
            iap_calls.extend(number['number'] for message in messages for number in message['numbers'])
            return [{'uuid': number['uuid'], 'state': 'success'}
                    for message in messages for number in message['numbers']]

        with self.mock_smstunnel(), patch.object(SmsApi, '_send_sms_batch', autospec=True, side_effect=_iap_send):
            (sms_iap + sms_smstunnel).send()
        self.assertEqual(iap_calls, ['+40721234567'])
        self.assertEqual([r['json']['to'] for r in self.smstunnel_requests], ['+40721234568'])
        self.assertEqual((sms_iap + sms_smstunnel).mapped('state'), ['pending', 'pending'])


@tagged('post_install', '-at_install', 'sms_smstunnel')
class TestSmsTunnelMarketing(SmsTunnelCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'mailing.mailing' not in cls.env:
            return
        cls.mailing = cls.env['mailing.mailing'].create({
            'subject': 'Weekend offer',
            'mailing_type': 'sms',
            'body_plaintext': 'Our shop is open this weekend',
            'mailing_model_id': cls.env['ir.model']._get_id('res.partner'),
        })

    def setUp(self):
        super().setUp()
        if 'mailing.mailing' not in self.env:
            self.skipTest('SMS Marketing (mass_mailing_sms) is not installed')

    def test_mailing_texts_refused(self):
        sms = self.env['sms.sms'].sudo().create({
            'number': '+40721234567', 'body': 'Our shop is open this weekend', 'mailing_id': self.mailing.id,
        })
        with self.mock_smstunnel():
            sms.send()
        self.assertFalse(self.smstunnel_requests)
        self.assertEqual(sms.state, 'error')
        self.assertEqual(sms.failure_type, 'unknown')

    def test_mailing_send_refused(self):
        """Sending an SMS mailing marks each text as failed, with the reason on its trace."""
        partner = self.env['res.partner'].create({'name': 'Ana Pop', 'mobile': '+40721234567'})
        self.mailing.write({
            'mailing_domain': [('id', '=', partner.id)],
            'sms_force_send': True,
        })
        with self.mock_smstunnel():
            self.mailing.action_send_sms()
        self.assertFalse(self.smstunnel_requests)
        trace = self.mailing.mailing_trace_ids
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace.trace_status, 'error')
        self.assertEqual(trace.failure_reason, MARKETING_REFUSAL)

    def test_mailing_test_refused(self):
        wizard = self.env['mailing.sms.test'].with_context(default_mailing_id=self.mailing.id).create({
            'mailing_id': self.mailing.id, 'numbers': '+40721234567',
        })
        with self.mock_smstunnel():
            wizard.action_send_sms()
            # The wizard's texts are closed, so the SMS queue does not send them later either.
            self.process_queue()
        self.assertFalse(self.smstunnel_requests)
        self.assertIn(MARKETING_REFUSAL, self.mailing.message_ids[0].body)
        self.assertFalse(self.env['sms.sms'].sudo().search([('number', '=', '+40721234567'), ('state', '=', 'outgoing')]))
        closed = self.env['sms.sms'].sudo().search([('number', '=', '+40721234567'), ('state', '=', 'error')])
        self.assertEqual(closed.smstunnel_failure_reason, MARKETING_REFUSAL)


@tagged('post_install', '-at_install', 'sms_smstunnel')
class TestSmsTunnelStatus(SmsTunnelCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Ana Pop', 'mobile': '+40721234567'})

    def _send(self, queued=False):
        with self.mock_smstunnel(self.accepted(queued=queued)):
            message = self.send_to_partner(self.partner)
        return self.sms_notification(message)

    def test_status_updates(self):
        for queued, answer, notification_status, smstunnel_status in [
            (True, self.status_answer('pending'), 'process', 'pending'),
            (True, self.status_answer('sent'), 'pending', 'sent'),
            (False, self.status_answer('delivered'), 'sent', 'delivered'),
            (False, self.status_answer('unconfirmed', unconfirmed=True), 'pending', 'unconfirmed'),
        ]:
            with self.subTest(status=answer[1]['data']['deliveryStatus']):
                notification = self._send(queued=queued)
                tracker = notification.sms_tracker_ids
                with self.mock_smstunnel(answer):
                    self.env['sms.tracker']._cron_smstunnel_update_status()
                request = self.smstunnel_requests[0]
                self.assertEqual(request['method'], 'GET')
                self.assertEqual(request['path'], '/api/v1/sms/status/%s' % tracker.smstunnel_message_id)
                self.assertEqual(notification.notification_status, notification_status)
                self.assertEqual(tracker.smstunnel_status, smstunnel_status)

    def test_failed_on_the_phone(self):
        notification = self._send()
        with self.mock_smstunnel(self.status_answer('failed', error_message='Generic failure (no service)')):
            self.env['sms.tracker']._cron_smstunnel_update_status()
        self.assertEqual(notification.notification_status, 'exception')
        self.assertEqual(notification.failure_type, 'sms_not_delivered')
        self.assertEqual(notification.failure_reason, 'Generic failure (no service)')

    def test_checks_again_later_only(self):
        self._send()
        with self.mock_smstunnel(self.status_answer('sent')):
            self.env['sms.tracker']._cron_smstunnel_update_status()
            self.env['sms.tracker']._cron_smstunnel_update_status()
        self.assertEqual(len(self.smstunnel_requests), 1, 'A text is checked at most every 10 minutes')

    def test_stops_when_smstunnel_refuses(self):
        self._send()
        self._send()
        with self.mock_smstunnel(self.refused(401, 'Invalid or expired API key', 'Unauthorized')):
            self.env['sms.tracker']._cron_smstunnel_update_status()
        self.assertEqual(len(self.smstunnel_requests), 1)


@tagged('post_install', '-at_install', 'sms_smstunnel')
class TestSmsTunnelWizard(SmsTunnelCase):

    def _wizard(self):
        return self.env['sms.smstunnel.account.manage'].create({'test_number': '+40721234567'})

    def test_send_test_text(self):
        with self.mock_smstunnel():
            action = self._wizard().action_send_test()
        self.assertEqual(action['params']['type'], 'success')
        self.assertEqual(self.smstunnel_requests[0]['json']['to'], '+40721234567')

    def test_send_test_text_bad_key(self):
        with self.mock_smstunnel(self.refused(401, 'Invalid or expired API key', 'Unauthorized')):
            action = self._wizard().action_send_test()
        self.assertEqual(action['params']['type'], 'danger')
        self.assertIn('did not accept the API key', action['params']['message'])

    def test_send_test_text_resumes_the_queue(self):
        self.company.write({'smstunnel_retry_at': fields.Datetime.now() + timedelta(minutes=30),
                            'smstunnel_failures': 4})
        with self.mock_smstunnel():
            self._wizard().action_send_test()
        self.assertFalse(self.company.smstunnel_retry_at)
        self.assertEqual(self.company.smstunnel_failures, 0)

    def test_check_connection(self):
        devices = (200, {'success': True, 'data': {'devices': [
            {'id': '6ae660e96609f21a1184a210', 'name': 'Store phone', 'isOnline': True},
            {'id': '6ae660e96609f21a1184a211', 'name': 'Old Samsung', 'isOnline': False},
        ], 'online': 1, 'total': 2}}, {})
        with self.mock_smstunnel(devices):
            action = self._wizard().action_check_connection()
        self.assertEqual(self.smstunnel_requests[0]['path'], '/api/v1/devices')
        self.assertEqual(action['params']['type'], 'success')
        self.assertIn('Store phone (online', action['params']['message'])
        self.assertIn('Old Samsung (offline', action['params']['message'])

    def test_country_code_check(self):
        for value in ('+40', '40', '0040', '1'):
            self.company.smstunnel_country_code = value
        with self.assertRaises(Exception):
            self.company.smstunnel_country_code = '+40 (Romania)'
            self.company.flush_recordset()
