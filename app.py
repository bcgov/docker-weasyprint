#!/usr/bin/env python

import json
import logging
import os

from flask import Flask, request, make_response
from weasyprint import HTML
from weasyprint.urls import FatalURLFetchingError, URLFetcher
from weasyprint.text.fonts import FontConfiguration
from fonts import css_for_extra_fonts

app = Flask('pdf')
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get('MAX_REQUEST_BYTES', 2 * 1024 * 1024))

class BlockExternalFetcher(URLFetcher):
    def __init__(self):
        super().__init__(allowed_protocols=('data'), fail_on_errors=True)


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
