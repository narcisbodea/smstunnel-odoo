# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
import itertools
import json
from contextlib import contextmanager

import requests

from odoo.tests.common import TransactionCase


class SmsTunnelCase(TransactionCase):
    """Base class: the main company sends through SMSTunnel, and SMSTunnel answers from canned responses.

    Every request to ``SERVER`` is recorded in ``self.smstunnel_requests`` as ``{'method', 'path', 'headers',
    'json'}``. Answers come from ``mock_smstunnel(*answers)`` in order (then "accepted"); an answer is a
    ``(status, body, headers)`` tuple from the helpers below, or an exception to raise (SMSTunnel down).
    """

    SERVER = 'https://smstunnel.test'
    API_KEY = 'sk_test_odoo_0123456789'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('sms_smstunnel.server_url', cls.SERVER)
        cls.company = cls.env.company
        cls.company.write({
            'country_id': cls.env.ref('base.ro').id,
            'sms_provider': 'smstunnel',
            'smstunnel_api_key': cls.API_KEY,
            'smstunnel_device_id': False,
            'smstunnel_country_code': False,
            'smstunnel_retry_at': False,
            'smstunnel_failures': 0,
        })
        cls._smstunnel_answers = []
        cls._smstunnel_requests = []
        cls._smstunnel_ids = itertools.count(1)

    # ------------------------------------------------------------
    # Mocked SMSTunnel
    # ------------------------------------------------------------

    @classmethod
    def _request_handler(cls, session, request, **kwargs):
        if not request.url.startswith(cls.SERVER):
            return super()._request_handler(session, request, **kwargs)
        cls._smstunnel_requests.append({
            'method': request.method,
            'path': request.url[len(cls.SERVER):],
            'headers': dict(request.headers),
            'json': json.loads(request.body) if request.body else None,
        })
        answer = cls._smstunnel_answers.pop(0) if cls._smstunnel_answers else cls.accepted()
        if isinstance(answer, Exception):
            raise answer
        status, body, headers = answer
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(body).encode() if body is not None else b''
        response.headers.update(headers or {})
        response.url = request.url
        response.request = request
        return response

    @contextmanager
    def mock_smstunnel(self, *answers):
        type(self)._smstunnel_answers = list(answers)
        type(self)._smstunnel_requests = []
        try:
            yield
        finally:
            type(self)._smstunnel_answers = []

    @property
    def smstunnel_requests(self):
        return type(self)._smstunnel_requests

    @classmethod
    def accepted(cls, queued=False):
        message_id = '6b%022x' % next(cls._smstunnel_ids)
        return 200, {
            'success': True,
            'messageId': message_id,
            'queued': True if queued else None,
            'data': {'messageId': message_id, 'branded': False, 'queued': True if queued else None,
                     'remaining': {'clean': -1, 'total': 'unlimited'}},
        }, {}

    @staticmethod
    def refused(status, message, error=None, code=None, headers=None):
        body = {'message': message, 'error': error or 'Error', 'statusCode': status}
        if code:
            body['code'] = code
        return status, body, headers or {}

    @staticmethod
    def unreachable():
        return requests.exceptions.ConnectionError('Connection refused')

    @staticmethod
    def status_answer(status, error_message=None, unconfirmed=False):
        data = {'id': 'x', 'phoneNumber': '+40721234567', 'status': 'failed' if unconfirmed else status,
                'deliveryStatus': status, 'errorMessage': error_message}
        if unconfirmed:
            data['unconfirmed'] = True
        return 200, {'success': True, 'data': data}, {}

    # ------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------

    def send_to_number(self, number, body='Your order SO042 is ready for pickup.'):
        """Odoo's "Send SMS" to a number (composer in numbers mode); returns the sms.sms records."""
        composer = self.env['sms.composer'].create({
            'body': body,
            'composition_mode': 'numbers',
            'numbers': number,
        })
        return composer._action_send_sms()

    def send_to_partner(self, partner, body='Hello, your delivery arrives today.'):
        """Odoo's "Send SMS" on a contact (composer in comment mode); returns the chatter message."""
        composer = self.env['sms.composer'].with_context(
            active_model='res.partner', active_id=partner.id,
        ).create({'body': body})
        return composer._action_send_sms()

    def process_queue(self):
        """Run what the SMS queue cron runs (in a test, without reporting progress to the cron, which commits)."""
        self.patch(self.registry['ir.cron'], '_commit_progress',
                   lambda cron_model, processed=0, remaining=None, **kwargs: 1)
        self.env['sms.sms'].sudo()._process_queue()

    def sms_notification(self, message):
        return message.notification_ids.filtered(lambda n: n.notification_type == 'sms')
