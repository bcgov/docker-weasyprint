---
title: WeasyPrint HTML to PDF/PNG Microservice
description: A ready to use, OpenShift compatible, HTML to PDF/PNG microservice for your application.
author: WadeBarnes
resourceType: Components
personas:
  - Developer
  - Product Owner
  - Designer
labels:
  - weasyprint
  - html
  - pdf
  - png
  - microservice
---
# WeasyPrint HTML to PDF/PNG Microservice

The [docker-weasyprint](https://github.com/BCDevOps/docker-weasyprint) project bundles [Weasyprint](http://weasyprint.org/) into an easy to use, OpenShift compatible, HTML to PDF/PNG microservice with a simple REST interface.

# Images

Pre-built images can be found here; [ghcr.io/bcgov/weasyprint:63.1.0](https://github.com/bcgov/docker-weasyprint/pkgs/container/weasyprint)

`docker pull ghcr.io/bcgov/weasyprint:63.1.0`

# Usage - Docker Example

Build the docker image

```
docker build --no-cache -f Dockerfile -t ghcr.io/bcgov/weasyprint .
```

Run the docker image, exposing port 5001

```
docker run -p 5001:5001 ghcr.io/bcgov/weasyprint
```

A `POST` to `/pdf` on port 5001 with an html body will result in a response containing a PDF. The filename may be set using a query parameter, e.g.:

```
curl -v -X POST -d @test.html -JLO http://127.0.0.1:5001/pdf?filename=result.pdf
```

This example will use the file `test.html` and return a response with `Content-Type: application/pdf` and `Content-Disposition: inline; filename=result.pdf` headers.  The body of the response will be the PDF rendering of the html document. To generate a png, make a call to `/png` instead

In addition `/health` is a health check endpoint and a `GET` returns 'ok'.
