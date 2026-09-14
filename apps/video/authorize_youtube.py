"""Authorize YouTube locally; never uploads. Tokens are Windows DPAPI protected."""
import argparse
import base64
import ctypes
from ctypes import wintypes
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def protect(data):
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, output = Blob(len(data), buffer), Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    crypt.CryptProtectData.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR,
        ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    crypt.CryptProtectData.restype = wintypes.BOOL
    if not crypt.CryptProtectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ctypes.WinError(ctypes.get_last_error())
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.client.read_text())['installed']
    assert config['token_uri'] == 'https://oauth2.googleapis.com/token'
    args.output.mkdir(parents=True, exist_ok=True)
    # Validate encrypted storage before requesting user consent.
    assert protect(b'YouTube authorization storage check')
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    state = secrets.token_urlsafe(32)
    finished = False
    deadline = time.time() + 1800

    def status(value):
        (args.output / 'status.json').write_text(json.dumps(value, indent=2), encoding='utf-8')

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log authorization codes or callback query strings.

        def reply(self, code, message):
            body = ('<!doctype html><meta charset="utf-8"><title>YouTube authorization</title>'
                    '<body style="font:20px system-ui;max-width:700px;margin:80px auto">'
                    + message + '</body>').encode()
            self.send_response(code)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            nonlocal finished
            parsed = urlparse(self.path)
            if parsed.path != '/':
                self.reply(404, 'Not found.'); return
            query = parse_qs(parsed.query)
            if not hmac.compare_digest(query.get('state', [''])[0], state):
                self.reply(400, 'Authorization state did not match. Please use the original sign-in link.'); return
            if 'error' in query:
                status({'state': 'CONSENT_DECLINED', 'uploaded': False})
                self.reply(400, 'Authorization was not granted. No video was uploaded.')
                finished = True; return
            if not query.get('code'):
                self.reply(400, 'Authorization code missing.'); return
            try:
                body = urlencode({'client_id': config['client_id'], 'client_secret': config['client_secret'],
                    'code': query['code'][0], 'code_verifier': verifier, 'redirect_uri': redirect,
                    'grant_type': 'authorization_code'}).encode()
                with urlopen(Request(config['token_uri'], data=body), timeout=30) as response:
                    token = json.load(response)
                token['obtained_at'] = time.time()
                token['client_file'] = str(args.client.resolve())
                assert token.get('access_token')
                destination = args.output / 'tokens.dpapi'
                temporary = args.output / 'tokens.dpapi.tmp'
                temporary.write_bytes(protect(json.dumps(token).encode()))
                temporary.replace(destination)
                result = {'state': 'AUTHORIZED', 'uploaded': False,
                    'grantedScopes': token.get('scope', ''), 'hasRefreshToken': bool(token.get('refresh_token')),
                    'storage': 'Windows DPAPI, current user; no plaintext token file'}
                try:
                    request = Request('https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true',
                        headers={'Authorization': 'Bearer ' + token['access_token']})
                    with urlopen(request, timeout=30) as response:
                        channels = json.load(response)
                    result['channels'] = [{'id': c['id'], 'title': c['snippet']['title']} for c in channels.get('items', [])]
                except HTTPError as exc:
                    result['channelLookupHttpStatus'] = exc.code
                status(result)
                self.reply(200, '<h1>Authorization complete</h1><p>You can return to Codex. No video has been uploaded.</p>')
            except Exception as exc:
                status({'state': 'AUTHORIZATION_ERROR', 'errorType': type(exc).__name__, 'uploaded': False})
                self.reply(500, 'Authorization could not be completed. Return to Codex; no video was uploaded.')
            finished = True

    server = HTTPServer(('127.0.0.1', 0), Callback)
    server.timeout = 1
    redirect = f'http://127.0.0.1:{server.server_port}/'
    link = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
        'client_id': config['client_id'], 'redirect_uri': redirect, 'response_type': 'code',
        'scope': 'https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly',
        'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256',
        'access_type': 'offline', 'prompt': 'consent select_account'})
    (args.output / 'authorization.json').write_text(json.dumps({'url': link, 'pid': os.getpid(),
        'expiresAt': deadline, 'redirectUri': redirect}, indent=2))
    status({'state': 'WAITING_FOR_CONSENT', 'uploaded': False, 'expiresAt': deadline})
    try:
        while not finished and time.time() < deadline:
            server.handle_request()
        if not finished:
            status({'state': 'EXPIRED', 'uploaded': False})
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
