# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
"""End-to-end tests against a real SMSTunnel server. They run only when these environment variables are set:

- ``SMSTUNNEL_E2E_URL``: the server, e.g. a local test server (never production);
- ``SMSTUNNEL_E2E_KEY``: an API key of that server;
- ``SMSTUNNEL_E2E_NUMBER`` (optional): the recipient, ``+14155550123`` by default.

Run: ``odoo -d <db> --test-tags /sms_smstunnel:TestSmsTunnelLocalApi --stop-after-init``
"""
import os
import time

from odoo import fields
from odoo.addons.sms_smstunnel.tools.smstunnel_client import SmsTunnelClient
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, _super_send

E2E_URL = os.environ.get('SMSTUNNEL_E2E_URL', '').rstrip('/')
E2E_KEY = os.environ.get('SMSTUNNEL_E2E_KEY', '')
E2E_NUMBER = os.environ.get('SMSTUNNEL_E2E_NUMBER', '+14155550123')


@tagged('post_install', '-at_install', 'sms_smstunnel', 'sms_smstunnel_e2e')
class TestSmsTunnelLocalApi(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not (E2E_URL and E2E_KEY):
            return
        cls.env['ir.config_parameter'].sudo().set_param('sms_smstunnel.server_url', E2E_URL)
        cls.env.company.write({
            'country_id': cls.env.ref('base.us').id,
            'sms_provider': 'smstunnel',
            'smstunnel_api_key': E2E_KEY,
            'smstunnel_retry_at': False,
            'smstunnel_failures': 0,
        })

    def setUp(self):
        super().setUp()
        if not (E2E_URL and E2E_KEY):
            self.skipTest('Set SMSTUNNEL_E2E_URL and SMSTUNNEL_E2E_KEY to run the end-to-end tests')

    @classmethod
    def _request_handler(cls, session, request, **kwargs):
        # Odoo's tests block outgoing requests; let the ones to the test server through.
        if E2E_URL and request.url.startswith(E2E_URL + '/'):
            return _super_send(session, request, **kwargs)
        return super()._request_handler(session, request, **kwargs)

    def _send(self, sms):
        """Send, waiting out SMSTunnel's rate limit (30 texts a minute per server; a test server may be shared):
        a 429 leaves the text in the queue until the time SMSTunnel gave."""
        for _attempt in range(5):
            if sms.state != 'outgoing':
                return
            retry_at = self.env.company.sudo().smstunnel_retry_at
            if retry_at:
                time.sleep(min(max((retry_at - fields.Datetime.now()).total_seconds(), 1), 65))
                self.env.company.sudo().smstunnel_retry_at = False
            sms.send()
        self.assertNotEqual(sms.state, 'outgoing', 'SMSTunnel kept asking to wait')

    def test_send_and_follow(self):
        body = 'SMSTunnel for Odoo end-to-end test (%s)' % self.env.cr.dbname
        composer = self.env['sms.composer'].create({'body': body, 'composition_mode': 'numbers', 'numbers': E2E_NUMBER})
        sms = composer._action_send_sms()
        self._send(sms)
        self.assertIn(sms.state, ('pending', 'process'), 'SMSTunnel accepted the text')
        self.assertTrue(sms.smstunnel_message_id)

        client = self.env.company._smstunnel_client()
        status = client.message_status(sms.smstunnel_message_id)
        self.assertEqual(status.get('phoneNumber'), E2E_NUMBER)
        self.assertIn(status.get('status'), ('pending', 'sent', 'delivered'))

    def test_invalid_number(self):
        sms = self.env['sms.sms'].sudo().create({'number': '12', 'body': 'Not a number'})
        self._send(sms)
        self.assertEqual(sms.state, 'error')
        self.assertEqual(sms.failure_type, 'sms_number_format')

    def test_bad_key(self):
        self.env.company.smstunnel_api_key = 'sk_live_not_a_real_key_000000000000000'
        sms = self.env['sms.sms'].sudo().create({'number': E2E_NUMBER, 'body': 'Bad key'})
        self._send(sms)
        self.assertEqual(sms.state, 'error')
        self.assertEqual(sms.failure_type, 'sms_acc')

    def test_list_phones(self):
        devices = SmsTunnelClient(E2E_KEY, server_url=E2E_URL).devices()
        self.assertGreaterEqual(devices.get('total', 0), 1)
