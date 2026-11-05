# Publishing SMSTunnel SMS (`sms_smstunnel`) on the Odoo Apps store

People get the module from **GitHub** (an Odoo.sh submodule, or a copy on their own server) and from the **Odoo Apps store** (apps.odoo.com), which reads this same public repository: one branch per Odoo version (`17.0`, `18.0`, `19.0`), each with `sms_smstunnel/` at its root. The branches are on GitHub. What's left is registering them on apps.odoo.com, which only the owner can do (section 2).

## 1. What the store requires

From Odoo's [vendor guidelines](https://apps.odoo.com/apps/vendor-guidelines), [FAQ](https://apps.odoo.com/apps/faq) and [upload page](https://apps.odoo.com/apps/upload), read on 5 November 2026. `python tools/check-store-rules.py` checks the file rules on each version folder.

| Rule | Here |
| --- | --- |
| Register each branch as `ssh://git@<server>/<path>#<branch>`. A public GitHub repository needs nothing more; a private one needs the GitHub user `online-odoo` (not `odoo-online`) on that repository. | Public; three URLs in section 2. |
| Each module in its own folder at the root of the branch, or the scan finds no module. | `sms_smstunnel/` on each branch. |
| Manifest: `name` (25 characters at most, no adjectives, no company name), `version` with the Odoo series and major.minor.patch, a new number for each release, under 1.0 means beta, `license`, `depends`. A dependency the store doesn't know fails the scan. **Any manifest error unpublishes every module of the repository.** | `SMSTunnel SMS`; `17.0.1.0.0`, `18.0.1.0.0`, `19.0.1.0.0`; `LGPL-3` (the license the store recommends for open source); `sms` and `sms_twilio`, both Odoo's own and in 17.0, 18.0 and 19.0 since September 2025. |
| `price`: none means free (otherwise 9 EUR at least); `currency` EUR or USD only; `support`: an email. | No price, so free; `contact@narboweb.ro`. |
| Icon at `static/description/icon.png`, a real PNG (otherwise the store shows a white cube). | 128 × 128, from `D:\ANDROID\identitate\SMS512.png`. |
| Cover (thumbnail): the first file of `images` in the manifest. The listing shows it in a 2:1 box. | `static/description/banner.png`, 1120 × 560, brand blue #2240ae with the logo. |
| Page `static/description/index.html`, in English: Bootstrap 4 classes, `style` limited to color, font-\*, margin-\*, padding-\*, border-\*; no JavaScript, static tags, widgets or modals. Links only to files of `static/description`, canonical YouTube, Microsoft Teams, `mailto:` and `skype:`: the store turns other links into plain text. Images png, gif or jpeg. | Built from `tools/description-template.html`; smstunnel.io, the dashboard and Google Play are named as plain text, with no links. |
| No promotions, advertising or links to other app stores or platforms, in the page or the manifest. Accurate features, "a full description, a thumbnail, screenshots". | No prices or offers on the page; five screenshots per version, taken from that version's Odoo. |
| An app that needs an external service says so clearly. Data sent to another service is explained in the manifest, the store page and the app itself, with the user's opt-in, ideally with a privacy policy. | The page's first box, the manifest's description and the setup dialog in Odoo all say what goes to SMSTunnel and name smstunnel.io/privacy. Nothing is sent before the admin chooses Send via SMSTunnel and enters a key. |
| No activation key, no downloaded or obfuscated code, no hidden features; installable by copying the folder into the addons path. | The SMSTunnel API key is the service's own credential (like Twilio's); the module is plain Python and XML. |
| Ranking: an icon, a cover, a license, an HTML page and a rating of 3 or more each count. | The first four are in place. |
| Odoo doesn't review each app before it goes live. It acts on reports: the app is unpublished until fixed, by email. | |

Not rules, but good to know: the big screenshot named `*_screenshot` only applies to themes with several `images`; a `LICENSE` file is only shown for licenses that aren't well-known open source ones; `doc/index.rst` in the module would add a documentation tab (not used).

## 2. The owner's steps

### An odoo.com account (once)

Sign up at <https://www.odoo.com/web/signup> (or sign in) with `contact@narboweb.ro`, the module's support address, for NARBOWEB SRL. The same account signs in to apps.odoo.com.

### Register the branches (once per version)

Open <https://apps.odoo.com/apps/upload>, sign in, and register these URLs one at a time:

```
ssh://git@github.com/narcisbodea/smstunnel-odoo.git#17.0
ssh://git@github.com/narcisbodea/smstunnel-odoo.git#18.0
ssh://git@github.com/narcisbodea/smstunnel-odoo.git#19.0
```

Nothing else is needed: the repository is public, so no deploy key and no GitHub collaborator. Keep the same spelling for all three (with `.git`): the store tells repositories apart by their URL.

### After the scan

1. On <https://apps.odoo.com/apps/dashboard/repos> each branch shows one module and no warning. Warnings to look for: an unmet dependency, a license conflict, a name already used in another series, "not installable". "No module found" means the branch has no `sms_smstunnel/` at its root.
2. Each app page opens: <https://apps.odoo.com/apps/modules/17.0/sms_smstunnel>, and the same with `18.0` and `19.0`. Check the name *SMSTunnel SMS*, the icon (not a white cube), **Free**, *LGPL-3*, the version, the five screenshots, the support link, and that the names (smstunnel.io, Google Play) show as plain text.
3. The listing (*Extra Tools*, or search for SMSTunnel) shows the cover.
4. Signed in, the app page shows your score: everything but the rating should be there.
5. Download the zip from one page: it holds the `sms_smstunnel` folder of that branch.

### A new version

1. Change the code in the version folders on `main`, raise `version` in each changed `__manifest__.py` (`17.0.1.0.1`, ...), run `python tools/check-store-rules.py` and the tests (README → Tests), and commit. A change to the store page alone needs no new version.
2. `tools/make-release-branches.sh`, then `git push origin main 17.0 18.0 19.0`.
3. The store scans the registered branches for new commits; **Scan** on <https://apps.odoo.com/apps/dashboard/repos> does it at once. If the new version doesn't show within a day, write to apps@odoo.com.

The page text: edit `tools/description-template.html`, then `tools/build-descriptions.sh` (no argument) writes the three `index.html`. New screenshots: put them in a folder named like `D:\ANDROID\integrari\odoo-screens\store` (`icon.png`, `banner.png`, `odoo<NN>-configure.png`, `-settings`, `-test-text`, `-contact`, `-failure`) and run `tools/build-descriptions.sh <folder>`.

A module deleted from the repository stays on the store; to take it down, write to apps@odoo.com.

## 3. Not covered yet

- **Odoo 20.0** is out (the `20.0` branch of Odoo and apps on the store for it). A port is a `20.0` folder on `main`, a `20.0` branch, and a fourth URL ending in `#20.0`.
- **Odoo Online** can't install third-party modules. [odoo-online.md](odoo-online.md) covers what works there without the module: texts to your own numbers from an automation rule and an SMSTunnel webhook.
