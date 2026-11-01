# Publishing SMSTunnel SMS (`sms_smstunnel`)

Two ways people get the module: from **GitHub** (Odoo.sh submodule, or a copy on their own server) and from the **Odoo Apps store** (apps.odoo.com), which reads the same GitHub repository. Both need the repository to be public, with one branch per Odoo version that has `sms_smstunnel/` at its root. Nothing has been pushed or published yet.

## 1. GitHub: the repository and the version branches

Locally, `main` holds everything (the three version folders, tests, docs). The branches `17.0`, `18.0` and `19.0` are made from the folders of the same name, with their history:

```bash
cd D:/ANDROID/integrari/smstunnel-odoo
gh repo create narcisbodea/smstunnel-odoo --public --description "SMSTunnel SMS for Odoo: Odoo's texts from your own Android phone and number" --source . --remote origin
tools/make-release-branches.sh
git push -u origin main 17.0 18.0 19.0
```

(Without `gh`: create the empty public repository `narcisbodea/smstunnel-odoo` on github.com, then `git remote add origin git@github.com:narcisbodea/smstunnel-odoo.git` and the last two commands.)

Check on GitHub that the branch `17.0` shows `sms_smstunnel/` and a short README at its root.

## 2. Odoo Apps store: account and repository (once per version)

1. Sign in at <https://apps.odoo.com> with an odoo.com account (create one for NARBOWEB SRL, e.g. with contact@narboweb.ro).
2. Open <https://apps.odoo.com/apps/upload> (**Register your Git repository**) and register each branch with its SSH URL:

   ```
   ssh://git@github.com/narcisbodea/smstunnel-odoo.git#17.0
   ssh://git@github.com/narcisbodea/smstunnel-odoo.git#18.0
   ssh://git@github.com/narcisbodea/smstunnel-odoo.git#19.0
   ```

   The part after `#` is the branch, which must match the Odoo series of the modules in it.
3. A public repository needs nothing else. If the repository is ever private, give the GitHub user `online-odoo` read access to this repository (not to the whole account), or the store can't read it.
4. The store scans each branch and creates the app page, for example `https://apps.odoo.com/apps/modules/17.0/sms_smstunnel`. Odoo doesn't review every app before it goes live; it acts on reports. The app is free because the manifest has no `price`.

## 3. What the store reads and checks

| What | Where | State |
| --- | --- | --- |
| Name (25 characters at most), version `<series>.x.y.z`, license, dependencies | `__manifest__.py` | `SMSTunnel SMS`, `17.0.1.0.0` / `18.0.1.0.0` / `19.0.1.0.0`, `LGPL-3`, `sms` + `sms_twilio` (both in Odoo) |
| Icon (a real PNG) | `static/description/icon.png` | 128×128 PNG of the SMSTunnel icon |
| Cover (thumbnail) | manifest `images` | `static/description/banner.png` (1120×560) |
| Page | `static/description/index.html` | Bootstrap 4 classes, no scripts, English; links only to files in `static/description` and `mailto:` (the store drops other external links, so Google Play and smstunnel.io are named as text) |
| Big screenshot | the first image whose name ends with `_screenshot` | `configure_screenshot.png`, from that version's Odoo |
| License text | `LICENSE` at the module root | LGPL-3 |

Store rules this module follows: the external service is stated at the top of the page (an SMSTunnel account and the Android app are needed); the data sent (each text and its number) is explained in the manifest, on the page and in the app's setup dialog, with the privacy policy (`https://smstunnel.io/privacy`); installation is a plain copy into the addons path; no activation key for the module itself (the SMSTunnel API key is the service's own credential, like Twilio's).

A mistake in a manifest unpublishes **every** module of the repository, so after a change run the tests (README → Tests) before pushing.

## 4. New versions

1. Change the code in the version folder(s) on `main`, raise `version` in each changed `__manifest__.py` (e.g. `17.0.1.0.1`), run the tests, commit.
2. `tools/make-release-branches.sh`, then `git push origin main 17.0 18.0 19.0`.
3. The store picks up new commits on the registered branches; if a new version doesn't show after a day, check the repository on your apps.odoo.com account or write to apps@odoo.com.

Screenshots and the store page: `tools/build-descriptions.sh <folder with screenshots>` refills each version's `static/description` from `tools/description-template.html`.

## 5. Where it can't go

- **Odoo Online**: third-party apps can't run there (only Odoo.sh and self-hosted). The README and the store page say so.
- **Odoo's own code**: providers in Odoo core (like `sms_twilio`) are Odoo S.A.'s choice; this module plugs into the same provider choice without needing a change there.

## What stays manual

Creating the GitHub repository and pushing, the odoo.com account, and registering the three branch URLs on apps.odoo.com. Nothing in this repository needs a secret.
