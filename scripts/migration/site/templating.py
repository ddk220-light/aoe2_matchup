"""Standalone Jinja rendering of the verbatim snippets in ``templates/``.

Configured like Flask 3's template environment, so the published text is
byte-identical: autoescaping by file extension (``.html`` and friends, and
always for strings) and ``tojson`` using Flask's JSON provider defaults
(``ensure_ascii``, Flask's ``default`` hook) with Jinja's ``sort_keys`` policy
and HTML-safe escaping of ``<``, ``>``, ``&`` and ``'``. No Flask app or request
context is involved.
"""
import dataclasses
import decimal
from datetime import date
import json
from pathlib import Path
import re
import uuid

import jinja2
from werkzeug.http import http_date

TEMPLATES = Path(__file__).resolve().parent / 'templates'
_JSON_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def _flask_default(value):
    """flask.json.provider._default"""
    if isinstance(value, date):
        return http_date(value)
    if isinstance(value, (decimal.Decimal, uuid.UUID)):
        return str(value)
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, '__html__'):
        return str(value.__html__())
    raise TypeError(f'Object of type {type(value).__name__} is not JSON serializable')


def _flask_dumps(value, **kwargs):
    """flask.json.provider.DefaultJSONProvider.dumps (the API sets sort_keys=False)."""
    kwargs.setdefault('default', _flask_default)
    kwargs.setdefault('ensure_ascii', True)
    kwargs.setdefault('sort_keys', False)
    return json.dumps(value, **kwargs)


def _autoescape(name):
    """flask.Flask.select_jinja_autoescape"""
    if name is None:
        return True
    return name.endswith(('.html', '.htm', '.xml', '.xhtml', '.svg'))


environment = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)), autoescape=_autoescape)
environment.policies['json.dumps_function'] = _flask_dumps


def render(name, **context):
    return environment.get_template(name).render(**context)


def render_string(source, **context):
    return environment.from_string(source).render(**context)


def json_ld(name, **context):
    """The inner text of every JSON-LD block a snippet renders, in document order."""
    blocks = _JSON_LD.findall(render(name, **context))
    for block in blocks:
        json.loads(block)
    return blocks
