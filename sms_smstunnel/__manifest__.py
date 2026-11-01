# Part of SMSTunnel SMS for Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'SMSTunnel SMS',
    'version': '18.0.1.0.0',
    'summary': "Send Odoo's texts from your own Android phone and number",
    'description': """
SMSTunnel SMS
=============
Odoo's texts (Send SMS on contacts, delivery confirmations, SMS templates, automated actions) go out
from your own Android phone, from your own number, with the SMSTunnel app. Choose "Send via SMSTunnel"
in Settings → General Settings → Send SMS.
""",
    'author': 'NARBOWEB SRL',
    'maintainer': 'Narcis Bodea <contact@narboweb.ro>',
    'support': 'contact@narboweb.ro',
    'website': 'https://smstunnel.io/integrations/odoo/',
    'category': 'Extra Tools',
    'license': 'LGPL-3',
    'depends': ['sms', 'sms_twilio'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/sms_sms_views.xml',
        'wizard/sms_resend_views.xml',
        'wizard/sms_smstunnel_account_manage_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
