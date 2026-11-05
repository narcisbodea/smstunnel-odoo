"""Checks each version folder against the Odoo Apps store rules (apps.odoo.com/apps/vendor-guidelines and
apps.odoo.com/apps/faq, read on 5 November 2026). Run it before pushing the version branches:

    python tools/check-store-rules.py            # all of 17.0, 18.0 and 19.0
    python tools/check-store-rules.py 19.0       # one folder, or a branch checked out elsewhere

It reads files only. Exit code 1 when a rule fails.
"""
import ast
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = 'sms_smstunnel'
LICENSES = {'GPL-3', 'AGPL-3', 'LGPL-3', 'OPL-1', 'Other OSI approved licence', 'Other proprietary'}
# Style attributes the store keeps: color, font-*, margin-*, padding-*, border-* (with Bootstrap 4 classes).
STYLE_OK = re.compile(r'^(color|font(-[a-z]+)?|margin(-[a-z]+)?|padding(-[a-z]+)?|border(-[a-z]+)*)$')
# Links the store keeps: files of static/description, canonical YouTube, Microsoft Teams, mailto:, skype:.
LINK_OK = re.compile(r'^(mailto:|skype:|https://www\.youtube\.com/watch\?v=|https://teams\.microsoft\.com/)')
# Our own wording rules for this module's texts. "SMS Marketing" (Odoo's app) and "SMS gateway" (Odoo's label) pass.
WORDS = re.compile(r'\b(gateway|bulk|campaigns?|mass)\b', re.I)
FORMATS = {b'\x89PNG\r\n\x1a\n': 'png', b'GIF87a': 'gif', b'GIF89a': 'gif', b'\xff\xd8\xff': 'jpeg'}


def image_format(path):
    head = path.read_bytes()[:8]
    for magic, name in FORMATS.items():
        if head.startswith(magic):
            return name
    return None


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.problems, self.images, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'style', 'iframe', 'form', 'input', 'button', 'object', 'embed', 'link', 'meta'):
            self.problems.append(f'<{tag}> is not allowed')
        for name in a:
            if name.startswith('on'):
                self.problems.append(f'<{tag} {name}=...>: no JavaScript')
        if 'data-bs-toggle' in a or 'data-toggle' in a:
            self.problems.append(f'<{tag}>: no widgets or modals')
        for rule in filter(None, (r.strip() for r in (a.get('style') or '').split(';'))):
            prop = rule.split(':', 1)[0].strip().lower()
            if not STYLE_OK.match(prop):
                self.problems.append(f'style "{prop}" on <{tag}>: use Bootstrap 4 classes or color, font-*, margin-*, padding-*, border-*')
        href = a.get('href')
        if tag == 'a' and href is not None and not (LINK_OK.match(href) or not re.match(r'^[a-z]+:|^//', href)):
            self.problems.append(f'link {href}: the store invalidates external links')
        if tag == 'img':
            self.images.append(a.get('src') or '')

    def handle_data(self, data):
        self.text.append(data)


def check(version):
    problems = []
    folder = Path(version)
    if not folder.is_absolute() and not folder.exists():
        folder = ROOT / version
    module = folder / MODULE if (folder / MODULE).is_dir() else folder
    series = re.search(r'(\d+\.0)', str(folder.resolve()))
    manifest = ast.literal_eval((module / '__manifest__.py').read_text(encoding='utf-8'))

    name = manifest.get('name', '')
    if not name or len(name) > 25:
        problems.append(f'manifest name "{name}": required, 25 characters at most')
    if series and not re.fullmatch(re.escape(series.group(1)) + r'\.\d+\.\d+\.\d+', manifest.get('version', '')):
        problems.append(f'manifest version "{manifest.get("version")}": must be {series.group(1)}.x.y.z')
    if manifest.get('license') not in LICENSES:
        problems.append(f'manifest license "{manifest.get("license")}": one of {sorted(LICENSES)}')
    if 'depends' not in manifest:
        problems.append('manifest depends: required')
    if 'price' in manifest:
        if float(manifest['price']) < 9 and float(manifest['price']) >= 0:
            problems.append('manifest price: at least 9 (or no price for a free app)')
        if manifest.get('currency', 'EUR') not in ('EUR', 'USD'):
            problems.append('manifest currency: EUR or USD only')
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[a-z]+', manifest.get('support', '')):
        problems.append('manifest support: an email address')
    if not manifest.get('installable', True):
        problems.append('manifest installable is False: the store would not publish it')
    for words in (manifest.get('summary', ''), manifest.get('description', '')):
        for hit in WORDS.findall(words):
            problems.append(f'manifest wording: "{hit}"')

    description = module / 'static' / 'description'
    icon = description / 'icon.png'
    if not icon.exists() or image_format(icon) != 'png':
        problems.append('static/description/icon.png: missing or not a real PNG (the store shows a white cube)')
    images = manifest.get('images') or []
    if not images:
        problems.append('manifest images: no cover image (thumbnail)')
    for image in images:
        if not (module / image).exists() or image_format(module / image) is None:
            problems.append(f'manifest images: {image} missing or not png/gif/jpeg')

    page = description / 'index.html'
    if not page.exists():
        problems.append('static/description/index.html: missing')
    else:
        parser = Page()
        parser.feed(page.read_text(encoding='utf-8'))
        problems += parser.problems
        for src in parser.images:
            target = description / src
            if re.match(r'^[a-z]+:|^//', src) or not target.exists():
                problems.append(f'image {src}: must be a file in static/description')
            elif image_format(target) is None:
                problems.append(f'image {src}: only png, gif and jpeg are allowed')
        text = ' '.join(parser.text)
        for hit in WORDS.findall(text):
            problems.append(f'page wording: "{hit}"')
        if re.search(r'\bmarketing\b', re.sub(r'SMS\s+Marketing', '', text), re.I):
            problems.append('page wording: "marketing" outside Odoo\'s app name "SMS Marketing"')
        if '{{' in text:
            problems.append('page: a template placeholder was not filled in')
    return module, problems


def main():
    versions = sys.argv[1:] or ['17.0', '18.0', '19.0']
    failed = False
    for version in versions:
        module, problems = check(version)
        print(f'{module}: {"OK" if not problems else str(len(problems)) + " problem(s)"}')
        for problem in problems:
            print(f'  - {problem}')
        failed = failed or bool(problems)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
