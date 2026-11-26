#!/usr/bin/env python3

import json
import io
import subprocess
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pypdf import PdfReader

html_data = '''
<!DOCTYPE html>
<html>
<head>
    <title>Test File</title>
</head>
<body>
    <h1>Hello World</h1>
</body>
</html>
'''


def request_factory(path='/'):
    url = 'http://127.0.0.1:5001%s' % path
    headers = {
        'Content-Type': 'application/html'
    }
    return Request(url, data=html_data.encode('utf-8'), headers=headers, method='POST')


class TestPdf(unittest.TestCase):

    def setUp(self):
        request = request_factory('/pdf?filename=sample.pdf')
        self.response = urlopen(request)

    def tearDown(self):
        self.response.close()

    def test_response_code(self):
        self.assertEqual(self.response.getcode(), 200)

    def test_headers(self):
        headers = dict(self.response.info())
        self.assertEqual(headers['Content-Type'], 'application/pdf')
        self.assertEqual(headers['Content-Disposition'], 'inline;filename=sample.pdf')

    def test_body(self):
        self.assertEqual(self.response.read()[:4], b'%PDF')


class TestMultiple(unittest.TestCase):

    def setUp(self):
        url = 'http://127.0.0.1:5001/multiple?filename=sample.pdf'
        headers = {
            'Content-Type': 'application/json'
        }
        data = json.dumps([html_data, html_data]).encode('utf-8')
        request = Request(url, data=data, headers=headers, method='POST')
        self.response = urlopen(request)

    def tearDown(self):
        self.response.close()

    def test_response_code(self):
        self.assertEqual(self.response.getcode(), 200)

    def test_headers(self):
        headers = dict(self.response.info())
        self.assertEqual(headers['Content-Type'], 'application/pdf')
        self.assertEqual(headers['Content-Disposition'], 'inline;filename=sample.pdf')

    def test_body(self):
        data = self.response.read()
        self.assertEqual(len(PdfReader(io.BytesIO(data)).pages), 2)


class TestResourceProtection(unittest.TestCase):
    def post(self, path, data, content_type='text/html'):
        request = Request(
            'http://127.0.0.1:5001' + path, data=data,
            headers={'Content-Type': content_type}, method='POST')
        return urlopen(request)
    def test_pdf_rejects_external_and_local_resources(self):
        for url in ('http://127.0.0.1:1/image.svg', 'file:///etc/passwd'):
            with self.subTest(url=url):
                html = ('<img src="%s">' % url).encode('utf-8')
                with self.assertRaises(HTTPError) as error:
                    self.post('/pdf', html)
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(error.exception.read(), b'Bad Request')
    def test_pdf_accepts_embedded_image(self):
        html = (b'<img src="data:image/gif;base64,'
                b'R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==">')
        with self.post('/pdf', html) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(4), b'%PDF')
    def test_multiple_rejects_resource_in_any_document(self):
        data = json.dumps([html_data, '<img src="file:///etc/passwd">']).encode('utf-8')
        with self.assertRaises(HTTPError) as error:
            self.post('/multiple', data, 'application/json')
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(error.exception.read(), b'Bad Request')
    def test_request_larger_than_default_limit_is_rejected(self):
        with self.assertRaises(HTTPError) as error:
            self.post('/pdf', b'x' * (2 * 1024 * 1024 + 1))
        self.assertEqual(error.exception.code, 413)
if __name__ == '__main__':
    unittest.main()
