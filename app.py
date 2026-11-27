#!/usr/bin/env python

import json
import logging
import os
from urllib.error import HTTPError
from urllib.parse import urlsplit

from flask import Flask, request, make_response
from weasyprint import HTML
from weasyprint.urls import FatalURLFetchingError, URLFetcher
from weasyprint.text.fonts import FontConfiguration
from fonts import css_for_extra_fonts

app = Flask('pdf')
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get('MAX_REQUEST_BYTES', 2 * 1024 * 1024))


def parse_http_url(url):
    if not isinstance(url, str) or any(ord(char) <= 32 or ord(char) == 127 for char in url):
        raise ValueError('Invalid HTTP resource URL')
    try:
        parts = urlsplit(url)
        if (parts.scheme not in ('http', 'https') or not parts.hostname or
                parts.username is not None or parts.password is not None or
                '\\' in parts.netloc):
            raise ValueError('Invalid HTTP resource URL')
        port = parts.port
    except ValueError as error:
        raise ValueError('Invalid HTTP resource URL: %r' % url) from error
    origin = (parts.scheme, parts.hostname.lower(),
              port if port is not None else (443 if parts.scheme == 'https' else 80))
    return origin, parts


def parse_resource_allowlist(value):
    try:
        rules = json.loads(value)
    except (TypeError, ValueError) as error:
        raise ValueError('RESOURCE_ALLOWLIST must be a JSON object') from error
    if not isinstance(rules, dict) or set(rules) - {'origins', 'urls', 'prefixes'}:
        raise ValueError('RESOURCE_ALLOWLIST must contain only origins, urls, and prefixes')
    parsed = {}
    for kind in ('origins', 'urls', 'prefixes'):
        entries = rules.get(kind, [])
        if not isinstance(entries, list):
            raise ValueError('RESOURCE_ALLOWLIST %s must be a list' % kind)
        parsed[kind] = []
        for entry in entries:
            origin, parts = parse_http_url(entry)
            if parts.fragment:
                raise ValueError('Allow-list entries cannot contain fragments')
            if kind == 'origins' and (parts.path not in ('', '/') or parts.query):
                raise ValueError('Allow-list origins cannot contain a path or query')
            if kind == 'prefixes' and (
                    not parts.path.startswith('/') or not parts.path.endswith('/') or
                    parts.query or not safe_prefix_path(parts.path)):
                raise ValueError('Allow-list prefixes must be safe directory URLs ending in /')
            parsed[kind].append((origin, parts.path or '/', parts.query))
    return parsed


def safe_prefix_path(path):
    return (not any(char in path for char in ('%', '\\', ';')) and
            all(segment not in ('.', '..') for segment in path.split('/')))


def load_resource_allowlist():
    if 'RESOURCE_ALLOWLIST_FILE' not in os.environ:
        return parse_resource_allowlist(os.environ.get('RESOURCE_ALLOWLIST', '{}'))
    path = os.environ['RESOURCE_ALLOWLIST_FILE']
    try:
        with open(path, encoding='utf-8') as config_file:
            return parse_resource_allowlist(config_file.read())
    except (UnicodeError, ValueError) as error:
        raise ValueError('Invalid RESOURCE_ALLOWLIST_FILE %r: %s' % (path, error)) from error


app.config['RESOURCE_ALLOWLIST'] = load_resource_allowlist()


class BlockExternalFetcher(URLFetcher):
    def __init__(self):
        super().__init__(
            allowed_protocols=('data', 'http', 'https'),
            allow_redirects=False, fail_on_errors=True)

    def fetch(self, url, headers=None):
        if urlsplit(url).scheme.lower() != 'data':
            origin, parts = parse_http_url(url)
            path = parts.path or '/'
            rules = app.config['RESOURCE_ALLOWLIST']
            if not (any(origin == rule[0] for rule in rules['origins']) or
                    (origin, path, parts.query) in rules['urls'] or
                    (safe_prefix_path(path) and any(
                        origin == rule[0] and path.startswith(rule[1])
                        for rule in rules['prefixes']))):
                raise ValueError('Resource URL is not allow-listed: %s' % url)
        try:
            return super().fetch(url, headers)
        except HTTPError as error:
            error.close()
            raise


with app.app_context():
    logging.addLevelName(logging.DEBUG, "\033[1;36m%s\033[1;0m" % logging.getLevelName(logging.DEBUG))
    logging.addLevelName(logging.INFO, "\033[1;32m%s\033[1;0m" % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR))

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    ))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.DEBUG)


@app.route('/health')
def index():
    return 'ok'


@app.route('/')
def home():
    return '''
        <h1>PDF Generator</h1>
        <p>The following endpoints are available:</p>
        <ul>
            <li>POST to <code>/pdf?filename=myfile.pdf</code>. The body should
                contain html</li>
            <li>POST to <code>/multiple?filename=myfile.pdf</code>. The body
                should contain a JSON list of html strings. They will each
                be rendered and combined into a single pdf</li>
        </ul>
    '''


@app.route('/pdf', methods=['POST'])
def generate():
    name = request.args.get('filename', 'unnamed.pdf')
    app.logger.info('POST  /pdf?filename=%s' % name)
    #print ( request.get_data(as_text=True) )
    try:
        html = HTML(string=request.get_data(as_text=True), url_fetcher=BlockExternalFetcher())
        css, font_config = css_for_extra_fonts()
        pdf = html.write_pdf(stylesheets=[css], font_config=font_config)
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline;filename=%s' % name
        app.logger.info(' ==> POST  /pdf?filename=%s  ok' % name)
        return response
    except FatalURLFetchingError as e:
        app.logger.error('Failed to fetch URL: %s', e)
        return 'Bad Request', 400


@app.route('/multiple', methods=['POST'])
def multiple():
    name = request.args.get('filename', 'unnamed.pdf')
    app.logger.info('POST  /multiple?filename=%s' % name)
    try:
        htmls = json.loads(request.data.decode('utf-8'))
        css, font_config = css_for_extra_fonts()
        documents = [HTML(string=html, url_fetcher=BlockExternalFetcher()).render(
            stylesheets=[css], font_config=font_config) for html in htmls]
        pdf = documents[0].copy([page for doc in documents for page in doc.pages]).write_pdf()
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline;filename=%s' % name
        app.logger.info(' ==> POST  /multiple?filename=%s  ok' % name)
        return response
    except FatalURLFetchingError as e:
        app.logger.error('Failed to fetch URL: %s', e)
        return 'Bad Request', 400


if __name__ == '__main__':
    app.run()
