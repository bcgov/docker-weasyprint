---
title: WeasyPrint HTML to PDF Microservice
description: A ready to use, OpenShift compatible, HTML to PDF microservice for your application.
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
  - microservice
---
# WeasyPrint HTML to PDF Microservice

The [docker-weasyprint](https://github.com/BCDevOps/docker-weasyprint) project bundles [Weasyprint](http://weasyprint.org/) into an easy to use, OpenShift compatible, HTML to PDF microservice with a simple REST interface.

# Images

Pre-built images can be found here; [bcgovimages/weasyprint](https://hub.docker.com/r/bcgovimages/weasyprint)

`docker pull bcgovimages/weasyprint`

# Usage - Docker Example

Run the docker image, exposing port 5001

```
docker run -p 5001:5001 bcgovimages/weasyprint
```

A `POST` to `/pdf` on port 5001 with an html body will result in a response containing a PDF. The filename may be set using a query parameter, e.g.:

```
curl -v -X POST -d @test.html -JLO http://127.0.0.1:5001/pdf?filename=result.pdf
```

This example will use the file `test.html` and return a response with `Content-Type: application/pdf` and `Content-Disposition: inline; filename=result.pdf` headers.  The body of the response will be the PDF rendering of the html document.

`POST` to `/pdf` can be used to generate a PDF from a URL. Use the `type=url` query parameter and a url in a text/plain body, call:

```
curl -v -X POST -H 'Content-Type: text/plain' -d 'https://www.google.ca/?client=safari&channel=iphone_bm'-JLO http://127.0.0.1:5001/pdf?filename=result_from_url.pdf&type=url
```

This example will use the url `https://www.google.ca/?client=safari&channel=iphone_bm` and return a response with `Content-Type: application/pdf` and `Content-Disposition: inline; filename=result_from_url.pdf` headers.  The body of the response will be the PDF rendering of the url (renders static html only, not for Single Page Applications).

When `type=url`, additional query parameters can be passed in: `encoding`, `media_type`, `base_url`.  See [Weasyprint HTML api](https://weasyprint.readthedocs.io/en/stable/api.html#weasyprint.HTML).  


In addition `/health` is a health check endpoint and a `GET` returns 'ok'.
