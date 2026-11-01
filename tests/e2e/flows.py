# Real Odoo flows against a local SMSTunnel server. Run inside `odoo shell` (see run-flows.sh), which
# provides `env`. Each step prints PASS/FAIL; the last line is a JSON summary with the texts to look for
# in the SMSTunnel test database (check-mongo.mjs).
#
# Environment: SMSTUNNEL_E2E_URL, SMSTUNNEL_E2E_KEY (never printed), SMSTUNNEL_E2E_NUMBER,
# SMSTUNNEL_E2E_OFFLINE_DEVICE (optional: a phone of the account that is offline).
import json
import os
import time

from odoo import fields

URL = os.environ['SMSTUNNEL_E2E_URL'].rstrip('/')
KEY = os.environ['SMSTUNNEL_E2E_KEY']
NUMBER = os.environ.get('SMSTUNNEL_E2E_NUMBER', '+14155550123')
OFFLINE_DEVICE = os.environ.get('SMSTUNNEL_E2E_OFFLINE_DEVICE', '')
DOWN_URL = 'http://127.0.0.1:9'  # inside the Odoo container nothing listens there: "SMSTunnel is down"
TAG = 'odoo%s' % env.cr.dbname[-2:]  # noqa: F821 - env comes from odoo shell
VERSION = int(TAG[-2:])

# Accepted by SMSTunnel: "Sent" (pending), "Delivered" (sent), or "Processing" (process) when the phone is
# offline and SMSTunnel keeps the text until it is back.
ACCEPTED = ('pending', 'sent', 'process')
results = []
texts = []


def check(name, ok, detail=''):
    results.append({'step': name, 'ok': bool(ok), 'detail': str(detail)[:300]})
    print('%s  %s  %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def commit():
    env.cr.commit()  # noqa: F821
    env.invalidate_all()  # noqa: F821


company = env.company  # noqa: F821
ICP = env['ir.config_parameter'].sudo()  # noqa: F821
SmsSms = env['sms.sms'].sudo()  # noqa: F821
queue_cron = env.ref('sms.ir_cron_sms_scheduler_action')  # noqa: F821
status_cron = env.ref('sms_smstunnel.ir_cron_smstunnel_status')  # noqa: F821


def configure(**values):
    vals = {
        'sms_provider': 'smstunnel', 'smstunnel_api_key': KEY, 'smstunnel_device_id': False,
        'smstunnel_country_code': False, 'smstunnel_retry_at': False, 'smstunnel_failures': 0,
    }
    vals.update(values)
    company.write(vals)
    commit()


def run_queue():
    """What the "SMS: SMS Queue Manager" cron does, run now."""
    queue_cron.method_direct_trigger()
    commit()


def drain(sms_records, max_wait=200):
    """Run the queue until these texts left it, waiting while SMSTunnel asked to wait (shared 30/min limit)."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        env.invalidate_all()  # noqa: F821
        if not sms_records.exists().filtered(lambda s: s.state == 'outgoing'):
            return True
        retry_at = company.smstunnel_retry_at
        if retry_at and retry_at > fields.Datetime.now():
            time.sleep(min((retry_at - fields.Datetime.now()).total_seconds() + 1, 65))
        run_queue()
    return False


def contact(name, phone):
    return env['res.partner'].create({'name': name, 'phone': phone, 'country_id': env.ref('base.us').id})  # noqa: F821


def send_sms_from_contact(partner, body):
    """The "Send SMS" button of a contact: the composer in comment mode, posted in the chatter."""
    composer = env['sms.composer'].with_context(active_model='res.partner', active_id=partner.id).create({'body': body})  # noqa: F821
    message = composer._action_send_sms()
    commit()
    return message


def notification_of(message):
    return message.notification_ids.filtered(lambda n: n.notification_type == 'sms')


def sms_of(message):
    return SmsSms.with_context(active_test=False).search([('mail_message_id', '=', message.id)])


# ---------------------------------------------------------------------------------------------------------
ICP.set_param('sms_smstunnel.server_url', URL)
company.write({'country_id': env.ref('base.us').id})  # noqa: F821
configure()
check('provider', company._get_sms_api_class().__name__ == 'SmsApiSmsTunnel', company.sms_provider)

# 1. A contact's "Send SMS" -------------------------------------------------------------------------------
ana = contact('Ana Pop (%s)' % TAG, NUMBER)
body = '[%s] Hello Ana, your appointment is confirmed for tomorrow at 10:00.' % TAG
message = send_sms_from_contact(ana, body)
drain(sms_of(message))
notif = notification_of(message)
tracker = notif.sms_tracker_ids
check('contact Send SMS', notif.notification_status in ACCEPTED and tracker.smstunnel_message_id,
      '%s / %s' % (notif.notification_status, tracker.smstunnel_message_id))
texts.append({'flow': 'contact', 'body': body, 'messageId': tracker.smstunnel_message_id})

# 2. Sale order -> delivery validated -> the delivery SMS template ----------------------------------------
if 'sale.order' in env and 'stock.picking' in env:  # noqa: F821
    if VERSION >= 19:
        company.write({'stock_text_confirmation': True, 'stock_confirmation_type': 'sms',
                       'has_received_warning_stock_sms': True})
    else:
        company.write({'stock_move_sms_validation': True, 'has_received_warning_stock_sms': True})
    product_vals = {'name': 'Desk lamp (%s)' % TAG, 'list_price': 40}
    if 'is_storable' in env['product.template']._fields:  # noqa: F821
        product_vals.update(type='consu', is_storable=True)
    else:
        product_vals.update(detailed_type='product')
    product = env['product.product'].create(product_vals)  # noqa: F821
    warehouse = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)  # noqa: F821
    env['stock.quant']._update_available_quantity(product, warehouse.lot_stock_id, 5)  # noqa: F821
    customer = contact('Mihai Ionescu (%s)' % TAG, NUMBER)
    order = env['sale.order'].create({  # noqa: F821
        'partner_id': customer.id,
        'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1})],
    })
    order.action_confirm()
    picking = order.picking_ids
    picking.action_assign()
    for move in picking.move_ids:
        move.quantity = move.product_uom_qty
        if 'picked' in move._fields:
            move.picked = True
    result = picking.button_validate()
    commit()
    if isinstance(result, dict):
        check('delivery validated', False, 'a wizard opened: %s' % result.get('res_model'))
    sms_message = picking.message_ids.filtered(lambda m: m.message_type == 'sms')[:1]
    drain(sms_of(sms_message)) if sms_message else None
    notif = notification_of(sms_message)
    check('delivery SMS template', picking.state == 'done' and notif.notification_status in ACCEPTED,
          '%s / %s / %s' % (order.name, picking.state, notif.notification_status))
    texts.append({'flow': 'delivery', 'body': '%s has been shipped' % order.name,
                  'messageId': notif.sms_tracker_ids.smstunnel_message_id})

# 3. Automated action: a new contact gets a welcome text (queued, sent by the SMS queue cron) --------------
if 'base.automation' in env:  # noqa: F821
    partner_model = env['ir.model']._get('res.partner')  # noqa: F821
    template = env['sms.template'].create({  # noqa: F821
        'name': 'Welcome (%s)' % TAG, 'model_id': partner_model.id,
        'body': '[%s] Welcome {{ object.name }}! You can reply to this number anytime.' % TAG,
    })
    automation = env['base.automation'].create({  # noqa: F821
        'name': 'Welcome text (%s)' % TAG, 'model_id': partner_model.id,
        'trigger': 'on_create_or_write',
        # Fires once: when a contact starts matching (without the "before" filter, every later save of a
        # matching contact would send the text again).
        'filter_pre_domain': "[('comment', 'not ilike', 'welcome-%s')]" % TAG,
        'filter_domain': "[('comment', 'ilike', 'welcome-%s')]" % TAG,
    })
    env['ir.actions.server'].create({  # noqa: F821
        'name': 'Send the welcome text', 'model_id': partner_model.id, 'state': 'sms',
        'sms_template_id': template.id, 'sms_method': 'sms', 'base_automation_id': automation.id,
    })
    commit()
    newcomer = env['res.partner'].create({  # noqa: F821
        'name': 'Elena Radu (%s)' % TAG, 'phone': NUMBER, 'country_id': env.ref('base.us').id,  # noqa: F821
        'comment': 'welcome-%s' % TAG,
    })
    commit()
    queued = SmsSms.search([('partner_id', '=', newcomer.id)])
    check('automated action queued the text', len(queued) == 1 and queued.state in ('outgoing', 'pending', 'process'),
          queued.mapped('state'))
    drain(queued)
    env.invalidate_all()  # noqa: F821
    states = queued.exists().mapped('state')
    check('queue cron sent it', queued and not queued.exists().filtered(lambda s: s.state in ('outgoing', 'error')),
          states or 'sent and cleaned up')
    texts.append({'flow': 'automated action', 'body': '[%s] Welcome Elena Radu' % TAG})

# 4. SMS Marketing: refused ---------------------------------------------------------------------------------
if 'mailing.mailing' in env:  # noqa: F821
    target = contact('Ioana Marin (%s)' % TAG, NUMBER)
    mailing = env['mailing.mailing'].create({  # noqa: F821
        'subject': 'Weekend offer (%s)' % TAG, 'mailing_type': 'sms',
        'body_plaintext': '[%s] Weekend offer: 20%% off' % TAG,
        'mailing_model_id': env['ir.model']._get_id('res.partner'),  # noqa: F821
        'mailing_domain': repr([('id', '=', target.id)]), 'sms_force_send': True,
    })
    mailing.action_send_sms()
    commit()
    trace = mailing.mailing_trace_ids
    check('SMS Marketing send refused', trace and set(trace.mapped('trace_status')) == {'error'}
          and 'not SMS marketing' in (trace.failure_reason or ''), '%s: %s' % (trace.mapped('trace_status'), trace.failure_reason))
    wizard = env['mailing.sms.test'].with_context(default_mailing_id=mailing.id).create(  # noqa: F821
        {'mailing_id': mailing.id, 'numbers': NUMBER})
    wizard.action_send_sms()
    commit()
    run_queue()
    log = mailing.message_ids[:1].body or ''
    left = SmsSms.search([('body', 'ilike', 'Weekend offer'), ('state', '=', 'outgoing')])
    check('SMS Marketing test refused', 'not SMS marketing' in log and not left, log[:160])
    texts.append({'flow': 'marketing (must be absent)', 'body': '[%s] Weekend offer' % TAG})

# 5. Bad key ------------------------------------------------------------------------------------------------
configure(smstunnel_api_key='sk_live_this_is_not_a_real_key_00000000')
message = send_sms_from_contact(ana, '[%s] This text uses a wrong key.' % TAG)
drain(sms_of(message))
notif = notification_of(message)
check('bad key', notif.notification_status == 'exception' and notif.failure_type == 'sms_acc',
      '%s / %s' % (notif.failure_type, notif.failure_reason))
configure()

# 6. A number Odoo accepts but SMSTunnel refuses (satellite phones are blocked) ------------------------------
# (A malformed number such as 12345 never reaches the provider: Odoo's own composer refuses it.)
wrong = contact('Satellite phone (%s)' % TAG, '+881631234567')
message = send_sms_from_contact(wrong, '[%s] This number is refused by SMSTunnel.' % TAG)
drain(sms_of(message))
notif = notification_of(message)
check('invalid number', notif.notification_status == 'exception' and notif.failure_type == 'sms_number_format',
      '%s / %s' % (notif.failure_type, notif.failure_reason))

# 7. SMSTunnel down: the text waits in the queue, then goes out ---------------------------------------------
ICP.set_param('sms_smstunnel.server_url', DOWN_URL)
commit()
body = '[%s] Sent after SMSTunnel came back.' % TAG
message = send_sms_from_contact(ana, body)
sms = sms_of(message)
notif = notification_of(message)
check('SMSTunnel down: kept in the queue', sms.state == 'outgoing' and notif.notification_status == 'ready'
      and company.smstunnel_retry_at, '%s / tries %s / retry at %s' % (sms.state, sms.smstunnel_tries, company.smstunnel_retry_at))
run_queue()  # still waiting: nothing is sent, nothing crashes
check('SMSTunnel down: queue run while waiting', sms.state == 'outgoing', sms.state)
ICP.set_param('sms_smstunnel.server_url', URL)
commit()
drain(sms)
env.invalidate_all()  # noqa: F821
check('SMSTunnel back: sent from the queue', notif.notification_status in ACCEPTED,
      '%s / failures %s' % (notif.notification_status, company.smstunnel_failures))
texts.append({'flow': 'down then back', 'body': body, 'messageId': notif.sms_tracker_ids.smstunnel_message_id})

# 8. Phone offline: SMSTunnel keeps the text; Odoo shows "Processing" ----------------------------------------
if OFFLINE_DEVICE:
    configure(smstunnel_device_id=OFFLINE_DEVICE)
    body = '[%s] Waits for the phone to come back online.' % TAG
    message = send_sms_from_contact(ana, body)
    drain(sms_of(message))
    notif = notification_of(message)
    check('phone offline: Processing', notif.notification_status == 'process'
          and notif.sms_tracker_ids.smstunnel_status == 'pending', notif.notification_status)
    texts.append({'flow': 'phone offline (pending)', 'body': body})
    configure()

# 9. The status cron follows accepted texts -----------------------------------------------------------------
status_cron.method_direct_trigger()
commit()
followed = env['sms.tracker'].search([('smstunnel_message_id', '!=', False), ('smstunnel_checked_at', '!=', False)])  # noqa: F821
check('status cron', followed, '%s tracker(s) checked: %s' % (len(followed), sorted(set(followed.mapped('smstunnel_status')))))

# 10. A sign-in code from custom code (/send-2fa) -----------------------------------------------------------
body = '[%s] Your sign-in code is 482913' % TAG
code_sms = SmsSms.create({'number': NUMBER, 'body': body, 'smstunnel_sign_in_code': True})
code_sms.send()
commit()
drain(code_sms)
check('sign-in code', code_sms.state in ('pending', 'process'), '%s / %s' % (code_sms.state, code_sms.smstunnel_message_id))
texts.append({'flow': 'sign-in code', 'body': body, 'messageId': code_sms.smstunnel_message_id})

passed = sum(1 for r in results if r['ok'])
print('SUMMARY ' + json.dumps({'version': VERSION, 'passed': passed, 'total': len(results), 'texts': texts}), flush=True)
