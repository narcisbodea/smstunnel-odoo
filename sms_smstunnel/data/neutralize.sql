-- A neutralized copy of the database (Odoo.sh staging, odoo-bin neutralize) must not text real customers:
-- without a key, SMSTunnel texts fail with "SMSTunnel isn't set up yet" until a key is added again.
UPDATE res_company
   SET smstunnel_api_key = NULL;
