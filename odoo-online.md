# Texts from Odoo Online, without the module (draft)

Odoo Online can't install the `sms_smstunnel` module, but its **automation rules** can call an SMSTunnel **webhook**. That is enough for texts to **your own number**, or to a few numbers of your team, when something happens in Odoo: an order is confirmed, a lead reaches a stage, a ticket comes in. The text can carry the record's fields, such as `New order S00042: 1250`.

What it can't do yet: text **the record's own number**, such as the customer of the order. An SMSTunnel webhook only texts the numbers saved in it, never a number from the request, so a leaked webhook address can't text anyone else. For texts to customers, use the module on Odoo.sh or on your own server ([README](README.md)).

Checked on 5 November 2026 against Odoo's code (the webhook action is the same in 17.0, 18.0, 19.0 and 20.0, and Odoo Online runs Odoo's latest versions) and against SMSTunnel's API, with Odoo's exact request replayed against a local SMSTunnel server ([below](#what-odoo-sends)). Not yet tried on a live Odoo Online database.

## What you need

- An SMSTunnel account with a password (the account of your phone's app) and the SMSTunnel app on your Android phone.
- Odoo Online (or any Odoo 17 or later) and an administrator who can turn on developer mode. Odoo Studio is not needed.

## 1. Make the webhook in SMSTunnel

The dashboard has no page for webhooks yet, so this takes two calls to SMSTunnel's API (macOS or Linux terminal; on Windows, Git Bash or WSL).

Sign in with your SMSTunnel email and password, and keep the sign-in token (sign in again if a call answers 401; a `"` or `\` in the password needs a `\` before it):

```bash
read -r -p "SMSTunnel email: " EMAIL; read -r -s -p "Password: " PASSWORD; echo
TOKEN=$(curl -s https://smstunnel.io/api/v1/auth/login -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}" | sed -n 's/.*"accessToken":"\([^"]*\)".*/\1/p')
unset PASSWORD
```

Make the webhook: the number that gets the texts, and the text, with Odoo's field names in `{{ }}` (step 2 shows where to find them):

```bash
curl -s https://smstunnel.io/api/v1/webhooks -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
  "name": "Odoo: confirmed orders",
  "recipients": ["+40712345678"],
  "messageTemplate": "New order {{name}}: {{amount_total}}",
  "maxPerHour": 20
}'
```

The answer has a `token`. Your webhook address is `https://smstunnel.io/api/v1/webhook/<token>`. Keep it secret: whoever has it can make SMSTunnel text the numbers of this webhook. Each recipient gets its own text; for alerts to yourself, keep one number.

One webhook per kind of text: for leads too, make a second one with its own text.

## 2. Make the automation rule in Odoo

1. **Settings → Activate the developer mode** (at the bottom of the page).
2. **Settings → Technical → Automation → Automation Rules → New.** If the menu isn't there, open **Apps**, remove the *Apps* filter, search for **Automation Rules** and activate it.
3. **Model**: *Sales Order*. **Trigger**: *State is set to*, value *Sales Order* (the order is confirmed).
4. **Actions To Do → Add an action**, type **Send Webhook Notification**:
   - **URL**: your webhook address.
   - **Fields**: the fields your text uses, here *Order Reference* (`name`) and *Total* (`amount_total`). The **Sample Payload** shows the names to write between `{{ }}`.
5. Save, and confirm an order: the text reaches your phone's number.

Good to know about Odoo's side:

- Odoo sends the fields of the rule's own model only. A many-to-one field arrives as a number (`partner_id: 7`), not the customer's name, so use the record's own text fields (on a lead: `contact_name`, `partner_name`).
- Odoo waits 1 second for SMSTunnel and never sends the same call again. When a call fails, only Odoo's server log says so, and Odoo Online doesn't show you that log: check **Messages** in your SMSTunnel dashboard instead.
- Odoo 19 and later call the webhook once the record is saved. Odoo 17 and 18 call it during the save, so a save that fails afterwards may still have texted you.
- A rule on *On save* (17, 18) or *On create and edit* (19 and later) runs at every save of a matching record. Set a **Before Update Domain** so each record texts once.
- Odoo writes the webhook address in its server log.

## What Odoo sends

The request of the rule above, made with the same lines of code as Odoo's *Send Webhook Notification* (`ir.actions.server._run_action_webhook`) and the `requests` library version Odoo uses, captured on its way out (the replay went to a local copy of SMSTunnel's server; `Host` shows the real address):

```http
POST /api/v1/webhook/<token> HTTP/1.1
Host: smstunnel.io
User-Agent: python-requests/2.31.0
Accept-Encoding: gzip, deflate
Accept: */*
Connection: keep-alive
Content-Type: application/json
Content-Length: 202

{"_action": "Text me confirmed orders(#17)", "_id": 42, "_model": "sale.order", "amount_total": 1250.0, "date_order": "2026-11-05 09:30:12", "id": 42, "name": "S00042", "partner_id": 7, "state": "sale"}
```

`_action`, `_id` and `_model` come with every call; the other keys are the fields picked in the rule. There are no other headers: the secret is in the address. SMSTunnel's answer, in 0.05 seconds on the local server:

```json
{"success":true,"sent":1,"total":1,"message":"New order S00042: 1250","results":[{"to":"+40*****5678","success":true,"messageId":"6aecf7fabf34411ef9a4d7e6"}]}
```

In the text, `1250.0` became `1250`; dates and times are UTC, as `2026-11-05 09:30:12`; a field that isn't in the call is left empty.

## Limits

- Texts are cut at 480 characters.
- Each webhook sends at most `maxPerHour` texts an hour (20 unless you set another number, up to 500), and takes 60 calls a minute. Above that it answers 429 and Odoo drops the call.
- Your SMSTunnel plan's daily limits apply, as for any text. If your phone is offline, the texts wait and go out when it is back.

## When nothing arrives

| What you see | What to do |
| --- | --- |
| 404 `Webhook not found or disabled` | The address is wrong, the webhook was deleted, or it was turned off. |
| 429 `Rate limit reached for this webhook (20/hour)` | Wait, or raise `maxPerHour` with `PATCH /api/v1/webhooks/<id>` (with the sign-in token). |
| The text is Odoo's raw data (`{"_action":...}`) | The webhook has no `messageTemplate`; add one with the same `PATCH`. |
| The text has gaps | The names in `{{ }}` don't match the Sample Payload, or the field isn't picked under **Fields**. |

To test without Odoo, send what Odoo would:

```bash
curl -s https://smstunnel.io/api/v1/webhook/<token> -H "Content-Type: application/json" \
  -d '{"_model": "sale.order", "_id": 42, "name": "S00042", "amount_total": 1250.0}'
```

If the address leaks, make a new one with `POST /api/v1/webhooks/<id>/rotate` (the old one stops at once) and put it in the rule.
