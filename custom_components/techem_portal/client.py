"""Experimental Techem client. Only Python standard library; no browser session reuse."""
import http.cookiejar
import json
import math
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

PORTAL = 'https://mieter.techem.de'
IDENTITY = 'https://techemtenantportal.b2clogin.com'

class TechemError(Exception):
    pass

class TechemAuthError(TechemError):
    pass

class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.scripts, self.forms = [], []
        self.script = None
        self.form = None
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'script': self.script = ''
        if tag == 'form':
            self.form = {'action': a.get('action', ''), 'method': a.get('method', 'get').lower(), 'fields': {}}
            self.forms.append(self.form)
        if tag == 'input' and self.form is not None and a.get('name'):
            self.form['fields'][a['name']] = a.get('value', '')
    def handle_data(self, data):
        if self.script is not None: self.script += data
    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            self.scripts.append(self.script)
            self.script = None
        if tag == 'form': self.form = None

def walk(value):
    yield value
    if isinstance(value, dict):
        for v in value.values(): yield from walk(v)
    elif isinstance(value, list):
        for v in value: yield from walk(v)

def objects(html):
    """Decode data, never execute embedded JavaScript."""
    chunks = []
    for script in Document(html).scripts:
        for match in re.finditer(r'self\.__next_f\.push\(', script):
            try:
                item, _ = json.JSONDecoder().raw_decode(script[match.end():].lstrip())
                if item[0] == 1 and isinstance(item[1], str): chunks.append(item[1])
            except (ValueError, IndexError, TypeError): continue
    for line in ''.join(chunks).splitlines():
        _, sep, body = line.partition(':')
        if not sep: continue
        try: value = json.loads(body)
        except ValueError: continue
        yield from walk(value)

def units(html):
    result = {}
    for obj in objects(html):
        if not isinstance(obj, dict): continue
        for entry in obj.get('rentalAgreements', []):
            if isinstance(entry, dict) and entry.get('residentialUnitId'):
                result.setdefault(entry['residentialUnitId'], {})
        if isinstance(obj.get('address'), dict) and obj.get('residentialUnitId'):
            result[obj['residentialUnitId']] = {k: obj['address'].get(k) for k in ('street', 'zip', 'city', 'floor')}
    if not result: raise TechemError('Keine Verbrauchsstelle gefunden; Sitzung oder Seitenformat prüfen.')
    return result

def consumption(html, period, unit_id=None):
    if unit_id and not any(isinstance(o, list) and len(o)>1 and o[0]=='unitid' and urllib.parse.unquote(str(o[1]))==unit_id for o in objects(html)):
        raise TechemError('Verbrauchsstelle der Antwort stimmt nicht überein.')
    matches = []
    for obj in objects(html):
        if not isinstance(obj, dict) or obj.get('serviceType') != 'HEATING': continue
        c = obj.get('consumption')
        if not isinstance(c, dict) or c.get('period') != period or c.get('service') != 'HEATING': continue
        if c.get('status') != 'OK': raise TechemError('Monatsdaten sind nicht als OK gekennzeichnet.')
        amount = c.get('amount')
        if c.get('unitOfMeasure') != 'KWH' or isinstance(amount, bool) or not isinstance(amount, (int,float)) or not math.isfinite(amount) or amount < 0:
            raise TechemError('Ungültiger Verbrauch oder unbekannte Einheit.')
        original = obj.get('original', {})
        result = {'period': period, 'heating_kwh': amount, 'status': c['status'], 'revision': c.get('revision'), 'source_created_at': c.get('createdAt')}
        if isinstance(original, dict) and original.get('period') == period and original.get('service') == 'HEATING' and original.get('status') == 'OK':
            v = original.get('amount')
            if not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v) and v >= 0:
                result.update(original_amount=v, original_unit=original.get('unitOfMeasure'))
        if result not in matches: matches.append(result)
    if len(matches) != 1: raise TechemError('Keine eindeutigen Heizungsdaten für den angeforderten Monat gefunden.')
    return matches[0]

def safe_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.netloc not in ('mieter.techem.de','techemtenantportal.b2clogin.com'):
        raise TechemError('Unerwartetes Weiterleitungsziel; Abruf abgebrochen.')
    return url

class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

class Client:
    def __init__(self):
        # macOS framework Python may lack a configured CA bundle; use system bundle.
        ca = '/etc/ssl/cert.pem'
        context = ssl.create_default_context(cafile=ca if Path(ca).is_file() else None)
        self.cookies = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(Redirects(), urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(self.cookies))
        self.http.addheaders = [('User-Agent','Mozilla/5.0 (compatible; TechemLocalPrototype/0.1)')]
        self.settings = None
    def request(self, url, data=None, headers=None):
        safe_url(url)
        payload = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=payload, headers=headers or {})
        try:
            with self.http.open(req, timeout=40) as response:
                safe_url(response.url)
                body = response.read(10_000_001)
                if len(body)>10_000_000: raise TechemError('Antwort zu groß.')
                return body.decode('utf-8'), response.url
        except urllib.error.HTTPError as e:
            raise TechemError(f'HTTP-Fehler {e.code}; keine automatische Passwort-Wiederholung.') from None
        except (urllib.error.URLError, TimeoutError):
            raise TechemError('Verbindung oder Zertifikatsprüfung fehlgeschlagen.') from None
    def prepare(self):
        csrf = json.loads(self.request(PORTAL+'/api/auth/csrf')[0])['csrfToken']
        response = json.loads(self.request(PORTAL+'/api/auth/signin/azure-b2c', {'csrfToken':csrf,'callbackUrl':PORTAL+'/de/auth','json':'true'})[0])
        html, url = self.request(response['url'])
        if urllib.parse.urlsplit(url).netloc != 'techemtenantportal.b2clogin.com': raise TechemError('Erwartete Anmeldeseite fehlt.')
        m = re.search(r'var SETTINGS\s*=\s*', html)
        if not m: raise TechemError('Unbekanntes Anmeldeformat.')
        s, _ = json.JSONDecoder().raw_decode(html[m.end():])
        if s.get('api') != 'CombinedSigninAndSignup' or s['hosts']['tenant'] != '/techemtenantportal.onmicrosoft.com/B2C_1A_signin':
            raise TechemError('Unerwartete Anmeldekonfiguration.')
        self.settings = s
    def login(self, email, password):
        if self.settings is None: self.prepare()
        s = self.settings
        root = IDENTITY+s['hosts']['tenant']
        query = urllib.parse.urlencode({'tx':s['transId'],'p':s['hosts']['policy']})
        body, _ = self.request(root+'/SelfAsserted?'+query, {'request_type':'RESPONSE','signInName':email,'password':password}, {'X-CSRF-TOKEN':s['csrf']})
        if str(json.loads(body).get('status')) != '200':
            raise TechemAuthError('Anmeldung abgelehnt oder zusätzlicher Anmeldeschritt erforderlich.')
        query = urllib.parse.urlencode({'rememberMe':'false','csrf_token':s['csrf'],'tx':s['transId'],'p':s['hosts']['policy']})
        html, url = self.request(root+'/api/'+s['api']+'/confirmed?'+query)
        forms = [f for f in Document(html).forms if f['method']=='post' and urllib.parse.urljoin(url,f['action']) == PORTAL+'/api/auth/callback/azure-b2c' and 'code' in f['fields'] and 'state' in f['fields']]
        if len(forms)!=1: raise TechemError('Erwartete OAuth-Rückgabe fehlt; zusätzlicher Anmeldeschritt möglich.')
        self.request(PORTAL+'/api/auth/callback/azure-b2c', forms[0]['fields'])
        html, _ = self.request(PORTAL+'/de')
        return self.complete_addresses(units(html))
    def complete_addresses(self, available):
        """The landing page may expose rental IDs without tenantDetails."""
        result = {key: dict(address) for key, address in available.items()}
        for key, address in result.items():
            if all(address.get(field) for field in ('street', 'zip', 'city', 'floor')):
                continue
            path = '/de/'+urllib.parse.quote(key, safe='')+'/consumptions'
            html, _ = self.request(PORTAL+path)
            details = units(html)
            if key not in details:
                raise TechemError('Verbrauchsstelle der Übersicht stimmt nicht überein.')
            address.update({k:v for k,v in details[key].items() if v is not None})
        return result
    def read(self, unit_id, period):
        path = '/de/'+urllib.parse.quote(unit_id,safe='')+'/consumptions/heating/'+period
        html, _ = self.request(PORTAL+path)
        return consumption(html, period, unit_id)


def validate_credentials(email, password):
    """Run entirely in HA's executor, including SSL setup and HTTP calls."""
    return Client().login(email, password)


def fetch_month(email, password, unit_id, period):
    client = Client()
    available = client.login(email, password)
    if unit_id not in available:
        raise TechemError('Die konfigurierte Verbrauchsstelle ist im Konto nicht verfügbar.')
    return {'address': available[unit_id], 'reading': client.read(unit_id, period)}
