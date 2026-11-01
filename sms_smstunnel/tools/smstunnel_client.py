# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
"""A small client for the SMSTunnel HTTP API (https://smstunnel.io/api-reference).

Each call sends one text to one number. The client never logs the API key.
"""
import logging
import re
from urllib.parse import quote

import requests

_logger = logging.getLogger(__name__)

DEFAULT_SERVER_URL = 'https://smstunnel.io'
USER_AGENT = 'SMSTunnel-Odoo/%s (+https://smstunnel.io)'
# (connect, read) in seconds. SMSTunnel answers as soon as it has the text: it does not wait for the phone.
TIMEOUT = (5, 20)
# The longest text SMSTunnel takes (10 joined SMS), and the longest sign-in code text.
MAX_TEXT_LENGTH = 1600
MAX_CODE_TEXT_LENGTH = 320
# A 429 without Retry-After: SMSTunnel counts send requests per minute.
DEFAULT_RETRY_AFTER = 60

_NUMBER_ERROR = re.compile(r'phone number|number format|premium|satellite|e\.164', re.IGNORECASE)


class SmsTunnelError(Exception):
    """SMSTunnel refused the call, or could not be reached.

    :param message: what went wrong, in words (SMSTunnel's own message when there is one);
    :param status: the HTTP status, or None when SMSTunnel could not be reached;
    :param code: SMSTunnel's error code when it sends one (e.g. ``PERMISSION_REQUIRED``);
    :param transient: True when trying again later can work (no answer, 429, 5xx);
    :param retry_after: seconds to wait, from a 429 answer.
    """

    def __init__(self, message, status=None, code=None, transient=False, retry_after=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.transient = transient
        self.retry_after = retry_after

    @property
    def is_number_error(self):
        return self.status == 400 and bool(_NUMBER_ERROR.search(self.message or ''))


def error_message_of(body, status):
    """The words of an error body, whatever its shape (same rules as the official SDK)."""
    if isinstance(body, str):
        return body.strip()[:300] or 'SMSTunnel returned error: %s' % status
    fields = body if isinstance(body, dict) else {}
    message = fields.get('message')
    if isinstance(message, list):
        message = '; '.join(str(part) for part in message)
    return message or fields.get('error') or 'SMSTunnel returned error: %s' % status


def _retry_after(response):
    value = response.headers.get('Retry-After')
    try:
        return max(1, int(float(value)))
    except (TypeError, ValueError):
        return DEFAULT_RETRY_AFTER


class SmsTunnelClient:
    """Calls the SMSTunnel API with one API key.

    :param api_key: the key from the SMSTunnel dashboard (Apps → Add an app);
    :param server_url: https://smstunnel.io unless testing against another SMSTunnel server;
    :param version: the module version, for the User-Agent header.
    """

    def __init__(self, api_key, server_url=None, version='1.0'):
        if not api_key:
            raise ValueError('An SMSTunnel API key is required')
        self._api_key = api_key
        self.server_url = (server_url or DEFAULT_SERVER_URL).strip().rstrip('/')
        self._user_agent = USER_AGENT % version
        self._session = None

    def __repr__(self):
        # Never show the key, not even in a traceback.
        return '<SmsTunnelClient %s>' % self.server_url

    # ------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------

    def send(self, to, message, device_id=None, country_code=None, sign_in_code=False):
        """Send one text to one number.

        :param to: the number, in international format (+ and the country code) when possible;
        :param message: the text;
        :param device_id: which of the account's phones sends it (empty: the main phone);
        :param country_code: completes numbers written without + or 00 (e.g. ``40`` or ``+40``);
        :param sign_in_code: True for a text that carries a sign-in code (4 to 10 digits): it goes
            through ``/send-2fa`` and counts against the separate allowance for codes;
        :return: SMSTunnel's answer: ``{'success': True, 'messageId': ..., 'queued': bool, 'data': {...}}``.
        """
        body = {'to': to, 'message': message}
        if device_id:
            body['deviceId'] = device_id
        if country_code:
            body['defaultCountryCode'] = country_code
        path = '/api/v1/sms/send-2fa' if sign_in_code else '/api/v1/sms/send'
        answer = self._request('POST', path, body)
        if not isinstance(answer, dict) or not answer.get('success') or not self.message_id_of(answer):
            message_text = error_message_of(answer, 200) if isinstance(answer, (dict, str)) else ''
            raise SmsTunnelError(message_text or 'SMSTunnel did not confirm the text', status=200)
        return answer

    def devices(self):
        """The phones of the account: ``{'devices': [{'id', 'name', 'isOnline', 'lastSeenAt'}], 'online', 'total'}``."""
        answer = self._request('GET', '/api/v1/devices')
        return (answer or {}).get('data') or {'devices': [], 'online': 0, 'total': 0}

    def message_status(self, message_id):
        """Where a text is now: ``{'status', 'deliveryStatus', 'unconfirmed', 'errorMessage', ...}``."""
        answer = self._request('GET', '/api/v1/sms/status/%s' % quote(str(message_id), safe=''))
        return (answer or {}).get('data') or {}

    @staticmethod
    def message_id_of(answer):
        return answer.get('messageId') or (answer.get('data') or {}).get('messageId')

    @staticmethod
    def is_queued(answer):
        """True when the phone is offline: the text waits on SMSTunnel and goes out when it is back."""
        return bool(answer.get('queued') or (answer.get('data') or {}).get('queued'))

    # ------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------

    def _request(self, method, path, json_body=None):
        if self._session is None:
            self._session = requests.Session()
        headers = {
            'X-API-Key': self._api_key,
            'Accept': 'application/json',
            'User-Agent': self._user_agent,
        }
        if json_body is not None:
            headers['Content-Type'] = 'application/json'
        url = self.server_url + path
        try:
            response = self._session.request(method, url, json=json_body, headers=headers, timeout=TIMEOUT)
        except requests.exceptions.Timeout:
            raise SmsTunnelError('SMSTunnel did not answer in time', transient=True) from None
        except requests.exceptions.RequestException as error:
            # The message of a connection error carries the URL only, never the headers.
            _logger.info('SMSTunnel could not be reached at %s: %s', self.server_url, error)
            raise SmsTunnelError('SMSTunnel could not be reached (%s)' % self.server_url, transient=True) from None

        try:
            body = response.json() if response.content else None
        except ValueError:
            body = response.text

        if response.status_code >= 400:
            message = error_message_of(body, response.status_code)
            code = body.get('code') if isinstance(body, dict) else None
            if response.status_code == 429:
                raise SmsTunnelError(message, status=429, code=code, transient=True, retry_after=_retry_after(response))
            raise SmsTunnelError(message, status=response.status_code, code=code, transient=response.status_code >= 500)
        return body
