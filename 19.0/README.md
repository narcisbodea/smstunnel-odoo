# SMSTunnel SMS for Odoo 19.0

The Odoo 19.0 version of `sms_smstunnel`: Odoo's texts go out from your own Android phone and your own number, with [SMSTunnel](https://smstunnel.io).

1. Copy `sms_smstunnel` into your addons path (on Odoo.sh: add this branch as a submodule), then **Apps → Update Apps List → SMSTunnel → Activate**. Needs an Odoo 19.0 build from September 2025 or later (with the core `sms_twilio` module); Odoo Online can't install it.
2. Install the [SMSTunnel app from Google Play](https://play.google.com/store/apps/details?id=io.smstunnel.app) on your Android phone and sign in; in your [SMSTunnel dashboard](https://dashboard.smstunnel.io/apps) open **Apps → Add an app**, pick **Odoo**, click **Create the key** and copy it.
3. In Odoo: **Settings → General Settings → Send SMS → Send via SMSTunnel → Configure SMSTunnel**, paste the key and send a test text to your own number.

Full documentation, statuses, limits and the prompt for AI assistants: [README on the main branch](https://github.com/narcisbodea/smstunnel-odoo#readme).

License: LGPL-3. SMSTunnel for Odoo is made by NARBOWEB SRL. It is not affiliated with, endorsed by, or sponsored by Odoo S.A. Odoo is a trademark of Odoo S.A.
