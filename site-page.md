# Content for smstunnel.io/integrations/odoo/

Draft content for an Odoo page on smstunnel.io, in the order the page shows it. It follows the current guide pages (`src/pages/integrations/erpnext.astro`: `GuideHeader`, `GuideKeyStep`, `GuideFields`, `GuideTroubleshooting`, `AiPrompt`, `GuideFooter`). The facts come from this folder's README, which is tested on Odoo 17, 18 and 19; keep the two in step. Unlike most guides, this one installs a module: Odoo has no "custom SMS URL" setting, so the module adds SMSTunnel as an SMS provider next to Odoo's own.

## Page meta

- **Title:** `Odoo SMS from Your Own Phone`
- **Description:** `Send Odoo's texts, from the SMS button of contacts, delivery confirmations, SMS templates and automated actions, through your own Android phone and number. A free module for Odoo 17, 18 and 19 on Odoo.sh or your own server.`
- **Integrations list card** (group "Business apps and automations", after ERPNext): `{ slug: 'odoo', name: 'Odoo', how: 'Send via SMSTunnel module', color: 'bg-purple-700' }`

## Header (`GuideHeader`)

- `title`: SMSTunnel for Odoo
- `subtitle`: Odoo's texts from your own phone and number
- `badge`: Free module · Odoo 17, 18, 19 · Odoo.sh and self-hosted
- `feature`: Send via SMSTunnel
- `link`: the module's README on GitHub once the repository is public (`https://github.com/narcisbodea/smstunnel-odoo`), label `Module on GitHub`; until then, the Odoo Apps page when it is published, or no link.
- `introTitle`: Order, delivery and appointment texts from a number customers know
- Intro paragraph: Odoo can text a customer from any contact or document, confirm deliveries, and send reminders and texts from automated actions. With the SMSTunnel module, you choose **Send via SMSTunnel** next to Odoo's own choices, and Odoo hands each text to your SMSTunnel account; your own Android phone sends it from its own SIM. Customers see your number, can save it and reply, and each text costs what your carrier charges.
- Colors: Odoo's purple, e.g. `bg-purple-700`, bar `bg-purple-50 border-purple-200`, text `text-purple-700`, button `bg-purple-700 hover:bg-purple-800`, gradient `from-purple-700 to-purple-900`, gradient text `text-purple-50`.

## What it texts (four cards)

| Card | From | Example |
| --- | --- | --- |
| A contact or document | The SMS button next to a phone number, or Send SMS on a record | Hi Maria, your order S00042 is ready for pickup at our Main Street shop, open until 18:00. |
| Delivery confirmation | Inventory → Settings → SMS confirmation, when a delivery is validated | My Company: We are glad to inform you that your order n° S00042 has been shipped. |
| Automated action | Settings → Technical → Automation Rules, action "Send SMS" with an SMS template | Welcome Elena! You can reply to this number anytime. |
| Reminders | Calendar and event reminders set to "SMS Text Message" | Reminder: your appointment is tomorrow at 10:00. |

## What you need

- Odoo **17, 18 or 19** on **Odoo.sh** or your **own server**, with an Odoo build from September 2025 or later. Odoo Online can't install modules that aren't Odoo's own.
- An Android phone with the SMSTunnel app from Google Play, signed in to your account. [Google Play badge]

## 1. Get your key (`GuideKeyStep app="Odoo"`)

The shared component as is: Apps → Add an app → Script or server → name it "Odoo" → Create the key.

## 2. Install the module

Text: Pick the folder of your Odoo version (`17.0`, `18.0` or `19.0`) from the module's repository, or download it from the Odoo Apps store once it is published there.

- **Odoo.sh**: add the repository to your project as a submodule, on the branch of your version, and push. When the build is ready: **Apps → Update Apps List**, search for **SMSTunnel**, **Activate**.
- **Your own server**: copy the `sms_smstunnel` folder into your addons path and restart Odoo, then **Apps → Update Apps List** (developer mode) → **SMSTunnel** → **Activate**.

Code block (Odoo.sh):

```bash
git submodule add -b 17.0 https://github.com/narcisbodea/smstunnel-odoo.git smstunnel-odoo
git commit -m "Add SMSTunnel SMS" && git push
```

## 3. Choose SMSTunnel in Settings (`GuideFields`)

Text: In Odoo, open **Settings → General Settings**, find **Send SMS** under *Contacts*, choose **Send via SMSTunnel** and click **Configure SMSTunnel**.

| Field | Value |
| --- | --- |
| SMSTunnel API key | the key from step 1 (only Settings administrators can read it; shown masked) |
| Phone ID | optional: which of your phones sends; empty means your main phone (Phones in the dashboard has a Copy button) |
| Default country code | optional: completes numbers written without + or 00; empty means the company's country |

Screenshot: `19.0/sms_smstunnel/static/description/configure_screenshot.png` (copy it to `public/`, not `public/images/`, which goes to the API).

## 4. Test it with your own number

Text: Type your number under **Test number** and click **Send a test text**. **Check the key and list my phones** shows your phones and whether they are online. Then **Save**: from now on every text Odoo sends for this company goes through your phone.

## Worth knowing (short list)

- One text per number, up to 1600 characters.
- Odoo shows each text's status in the chatter: Sent, Processing while your phone is offline (the text waits up to 3 days and goes out when it's back), Delivered, or an error with SMSTunnel's reason.
- If SMSTunnel can't be reached, texts wait in Odoo's queue and go out later; nothing is lost.
- Each company chooses its own SMS provider.
- Texts of SMS Marketing mailings are refused: SMSTunnel sends texts people expect, one at a time.
- Copies of the database made by Odoo.sh for staging lose the key, so they never text real customers.
- Automation rules on "create and edit" need a "Before update" filter, or each save sends another text.

## Troubleshooting (`GuideTroubleshooting via="api"`, extra items)

- **"Unregistered Account"** on a text: the key is wrong or deleted; paste it again in Configure SMSTunnel, then **Send & Close** in the failure dialog (Odoo 17 and 18) or **Retry** in Settings → Technical → SMS.
- **"Wrong Number Format"**: SMSTunnel refused the number (international format expected; premium-rate and satellite numbers are blocked).
- **The module isn't in the Apps list**: update the list (developer mode); on your own server, check that Odoo has the core `sms_twilio` module, otherwise update Odoo.

## FAQ

- **Does it work on Odoo Online?** No. Odoo Online only runs Odoo's own apps; use Odoo.sh or your own server.
- **Community or Enterprise?** Both: the module only uses Odoo's SMS features.
- **Do I still need Odoo's SMS credits?** Not for the company that sends via SMSTunnel. Your carrier's usual price applies to each text, plus your SMSTunnel plan.
- **Can customers reply?** Yes: replies arrive on your phone like any text.
- **SMS Marketing?** No: those mailings are refused. SMSTunnel is for texts people expect, one at a time.

## Build it with an AI assistant

Use the shared `AiPrompt` component (same shape as `erpnext.astro`):

```ts
import { aiPrompt, SETUP_RULES, GET_A_KEY, TOOL_ERRORS, ONE_NUMBER } from '../../lib/guide-prompts';

const prompt = aiPrompt({
  task: 'Help me make Odoo send its texts from my own phone with SMSTunnel.',
  steps: [
    'The free module "SMSTunnel SMS" (technical name sms_smstunnel, https://github.com/narcisbodea/smstunnel-odoo) for Odoo 17.0, 18.0 and 19.0 on Odoo.sh or self-hosted; Odoo Online cannot install it. Install the folder of my version, then Apps → Update Apps List → SMSTunnel → Activate. It needs Odoo builds from September 2025 or later (Odoo installs the core "Twilio SMS" module, sms_twilio, with it).',
    'Settings → General Settings → Send SMS → "Send via SMSTunnel" → "Configure SMSTunnel": API key, optional Phone ID (which phone sends; empty = my main phone) and Default country code (completes numbers written without + or 00; empty = the company\'s country). "Send a test text" checks it.',
    'Then everything in Odoo that sends texts for that company goes through my phone: the SMS button of a contact or record, SMS templates (Inventory → Settings → SMS confirmation of deliveries), automation rules with the "Send SMS" action and an SMS template, calendar and event reminders. Each company chooses its own provider.',
    'Statuses in the chatter: Sent; Processing while my phone is offline (the text waits up to 3 days); Delivered; Error with SMSTunnel\'s reason. If SMSTunnel can\'t be reached or asks to slow down, texts wait in Odoo\'s queue and the "SMS: SMS Queue Manager" cron sends them later.',
    'SMS Marketing mailings are refused. Automation rules on create and edit need a "Before update" filter so they fire once.',
    'In custom code: create sms.sms records (number, body) and call send(); for a sign-in code (4 to 10 digits, at most 320 characters) also set smstunnel_sign_in_code=True.',
    ONE_NUMBER,
    TOOL_ERRORS,
    GET_A_KEY,
  ],
  rules: [
    ...SETUP_RULES,
    'Keep the key in Odoo\'s SMSTunnel settings; in custom code never put it in source code.',
    'Help me text only the person the record is about (their order, their delivery, their appointment).',
  ],
});
```

## Footer lines (`GuideFooter`)

- `product`: Odoo · `owner`: Odoo S.A. · default trademark line ("Odoo is a trademark of Odoo S.A.").
- `related`: ERPNext (`/integrations/erpnext`, "Texts from SMS Settings"), Zoho CRM (`/integrations/zoho-crm`, "Webhook texts"), n8n (`/integrations/n8n`, "Texts from your workflows").
- Non-affiliation sentence, if the footer has room for it: *SMSTunnel for Odoo is made by NARBOWEB SRL. It is not affiliated with, endorsed by, or sponsored by Odoo S.A.*
