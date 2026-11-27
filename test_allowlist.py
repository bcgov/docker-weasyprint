import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from app import app, load_resource_allowlist, parse_resource_allowlist


GIF = bytes.fromhex('47494638396101000100800000000000ffffff21f90401000000002c'
                    '00000000010001000002024401003b')


class TestResourceAllowlistConfiguration(unittest.TestCase):
    def test_file_takes_precedence_at_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'allowlist.json'
            path.write_text('{"urls": ["https://example.com/image.png"]}', encoding='utf-8')
            env = os.environ.copy()
            env.update(RESOURCE_ALLOWLIST_FILE=str(path), RESOURCE_ALLOWLIST='invalid JSON')
            result = subprocess.run(
                [sys.executable, '-c',
                 'import json, app; print(json.dumps(app.app.config["RESOURCE_ALLOWLIST"]))'],
                env=env, capture_output=True, text=True, check=True)
            self.assertEqual(
                json.loads(result.stdout),
                {'origins': [], 'urls': [[['https', 'example.com', 443], '/image.png', '']],
                 'prefixes': []})

    def test_file_errors_do_not_fall_back_to_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'allowlist.json'
            with patch.dict(os.environ, {
                    'RESOURCE_ALLOWLIST_FILE': str(path),
                    'RESOURCE_ALLOWLIST': '{"origins": ["https://example.com"]}'}):
                with self.assertRaises(FileNotFoundError):
                    load_resource_allowlist()
                path.write_text('not json', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'RESOURCE_ALLOWLIST_FILE'):
                    load_resource_allowlist()
                path.write_text('{"origins": ["file:///etc/passwd"]}', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'RESOURCE_ALLOWLIST_FILE'):
                    load_resource_allowlist()
                path.write_bytes(b'\xff')
                with self.assertRaisesRegex(ValueError, 'RESOURCE_ALLOWLIST_FILE'):
                    load_resource_allowlist()

    def test_environment_still_works_without_file(self):
        with patch.dict(
                os.environ, {'RESOURCE_ALLOWLIST': '{"origins": ["https://example.com"]}'}, clear=True):
            self.assertEqual(
                load_resource_allowlist(),
                parse_resource_allowlist('{"origins": ["https://example.com"]}'))
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_resource_allowlist(), parse_resource_allowlist('{}'))


class ResourceHandler(BaseHTTPRequestHandler):
    requests = []

    def do_GET(self):
        self.requests.append(self.path)
        if self.path == '/redirect':
            self.send_response(302)
            self.send_header('Location', '/secret')
            self.end_headers()
            return
        self.send_response(200)
        if self.path == '/style.css':
            self.send_header('Content-Type', 'text/css')
            body = b'body { background-image: url("/images/test.gif"); }'
        else:
            self.send_header('Content-Type', 'image/gif')
            body = GIF
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class TestResourceAllowlist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), ResourceHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = 'http://127.0.0.1:%s' % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def setUp(self):
        self.previous_rules = app.config['RESOURCE_ALLOWLIST']
        app.config['RESOURCE_ALLOWLIST'] = parse_resource_allowlist('{}')
        ResourceHandler.requests = []
        self.client = app.test_client()

    def tearDown(self):
        app.config['RESOURCE_ALLOWLIST'] = self.previous_rules

    def allow(self, **rules):
        app.config['RESOURCE_ALLOWLIST'] = parse_resource_allowlist(json.dumps(rules))

    def pdf(self, url, endpoint='/pdf'):
        html = '<img src="%s">' % url
        if endpoint == '/multiple':
            return self.client.post(endpoint, json=['<p>First</p>', html])
        return self.client.post(endpoint, data=html)

    def test_default_blocks_http_and_file_but_allows_data(self):
        for url in (self.origin + '/image.gif', 'file:///etc/passwd'):
            with self.subTest(url=url):
                self.assertEqual(self.pdf(url).status_code, 400)
        self.assertEqual(self.pdf('data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==').status_code, 200)
        self.assertEqual(ResourceHandler.requests, [])

    def test_exact_url_requires_exact_path_and_query_on_both_endpoints(self):
        self.allow(urls=[self.origin + '/image.gif?size=1'])
        for endpoint in ('/pdf', '/multiple'):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.pdf(self.origin + '/image.gif?size=1', endpoint).status_code, 200)
                self.assertEqual(self.pdf(self.origin + '/image.gif?size=2', endpoint).status_code, 400)
                self.assertEqual(self.pdf(self.origin + '/other.gif?size=1', endpoint).status_code, 400)
        self.assertEqual(ResourceHandler.requests, ['/image.gif?size=1'] * 2)

    def test_origin_matches_only_same_scheme_host_and_port(self):
        self.allow(origins=[self.origin])
        self.assertEqual(self.pdf(self.origin + '/anything').status_code, 200)
        self.assertEqual(self.pdf(self.origin.replace('127.0.0.1', 'localhost') + '/anything').status_code, 400)
        self.assertEqual(self.pdf(self.origin.replace('http:', 'https:') + '/anything').status_code, 400)
        other_port = self.server.server_port - 1
        self.assertEqual(self.pdf('http://127.0.0.1:%s/anything' % other_port).status_code, 400)

    def test_prefix_rejects_traversal_and_similar_paths(self):
        self.allow(prefixes=[self.origin + '/images/'])
        self.assertEqual(self.pdf(self.origin + '/images/test.gif').status_code, 200)
        for path in ('/images-other/test.gif', '/images/../secret', '/images/%2e%2e/secret',
                     '/images/%252e%252e/secret', '/images/..;x/secret', '/images\\..\\secret'):
            with self.subTest(path=path):
                self.assertEqual(self.pdf(self.origin + path).status_code, 400)
        self.assertEqual(ResourceHandler.requests, ['/images/test.gif'])

    def test_stylesheet_nested_resources_are_also_checked(self):
        self.allow(urls=[self.origin + '/style.css'])
        html = '<link rel="stylesheet" href="%s/style.css">' % self.origin
        self.assertEqual(self.client.post('/pdf', data=html).status_code, 400)
        self.assertEqual(ResourceHandler.requests, ['/style.css'])
        self.allow(urls=[self.origin + '/style.css'], prefixes=[self.origin + '/images/'])
        self.assertEqual(self.client.post('/pdf', data=html).status_code, 200)
        self.assertEqual(ResourceHandler.requests[-2:], ['/style.css', '/images/test.gif'])

    def test_redirect_is_not_followed_even_when_origin_is_allowed(self):
        self.allow(origins=[self.origin])
        self.assertEqual(self.pdf(self.origin + '/redirect').status_code, 400)
        self.assertEqual(ResourceHandler.requests, ['/redirect'])

    def test_invalid_configuration_fails(self):
        for value in ('not json', '[]', '{"unknown": []}', '{"urls": "http://example.com"}',
                      '{"urls": ["file:///etc/passwd"]}', '{"urls": ["http://user@example.com/"]}',
                      '{"origins": ["http://example.com/path"]}',
                      '{"prefixes": ["http://example.com/api"]}',
                      '{"prefixes": ["http://example.com/api/%2e%2e/"]}',
                      '{"urls": ["http://example.com/a#fragment"]}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_resource_allowlist(value)


if __name__ == '__main__':
    unittest.main()
