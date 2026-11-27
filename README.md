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

Pre-built images can be found here; [ghcr.io/bcgov/weasyprint:63.1.0](https://github.com/bcgov/docker-weasyprint/pkgs/container/weasyprint)

`docker pull ghcr.io/bcgov/weasyprint:63.1.0`

Release images receive semantic-version tags and a seven-character commit SHA tag. Manual workflow runs require an image tag and can optionally specify a branch, tag, or commit to build; they also receive a tag for the checked-out commit's short SHA.

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

This example will use the file `test.html` and return a response with `Content-Type: application/pdf` and `Content-Disposition: inline; filename=result.pdf` headers.  The body of the response will be the PDF rendering of the html document.

In addition `/health` is a health check endpoint and a `GET` returns 'ok'.

## Resource allow list

By default, the service permits embedded `data:` resources only. External
resources, including local files, are blocked. The recommended approach is to
provide complete HTML with embedded resources and avoid external fetching.
Use an allow list only when external resources are absolutely necessary.

To permit trusted HTTP(S) resources, provide a JSON object with any of these
lists:

- `origins`: allow every path and query on the specified scheme, host, and port.
  Subdomains are not included.
- `urls`: allow only the specified URL and query string.
- `prefixes`: allow paths under a directory URL ending in `/`, with any query
  string. Prefix matching rejects paths containing percent escapes, backslashes,
  semicolons, or `.` and `..` path segments.

Scheme and host are case-insensitive; an omitted port matches its scheme's
default port. URL fragments are ignored for resource matching and cannot be
specified in rules. Rules must use HTTP or HTTPS and cannot include credentials.
Invalid configuration prevents the service from starting. Redirects are not
followed, even to another allowed URL. Stylesheets, images, fonts, and nested
resources are all checked; a blocked or failed fetch returns HTTP 400.

For example, the following configuration allows all resources from one origin,
a specific stylesheet, and resources under selected directory paths:

```json
{
  "origins": [
    "https://assets.example.com"
  ],
  "urls": [
    "https://app.example.com/static/css/print.css"
  ],
  "prefixes": [
    "https://app.example.com/static/fonts/",
    "https://app.example.com/api/documents/"
  ]
}
```

The preferred configuration is a UTF-8 JSON file mounted read-only into the
container. Set `RESOURCE_ALLOWLIST_FILE` to its path inside the container. For
example, from a POSIX shell, with the JSON above saved as `allowlist.json` in
the current directory:

```sh
docker run -p 5001:5001 \
  --mount type=bind,source="$(pwd)/allowlist.json",target=/config/allowlist.json,readonly \
  -e RESOURCE_ALLOWLIST_FILE=/config/allowlist.json \
  ghcr.io/bcgov/weasyprint
```

For smaller configurations, `RESOURCE_ALLOWLIST` can instead contain the JSON
object directly. If both variables are set, `RESOURCE_ALLOWLIST_FILE` takes
precedence and `RESOURCE_ALLOWLIST` is ignored. A missing, unreadable, or invalid
configured file prevents startup; there is no fallback to the environment
variable. Configuration is read at process startup, so restart the service after
changing it. An empty JSON object or no configuration preserves the default
data-only policy.

### Overlapping rules

**Rules are additive:** a resource is allowed if it matches any rule. More
specific rules do not restrict a broader rule for the same origin. For example:

```json
{
  "origins": ["https://app.example.com"],
  "urls": ["https://app.example.com/static/css/print.css"],
  "prefixes": ["https://app.example.com/static/fonts/"]
}
```

The origin rule allows every path and query on `https://app.example.com`,
including `https://app.example.com/api/documents/`. Remove the origin rule to
limit access to the listed URL and prefix.

An allow-list rule grants **every caller** access to matching resources via the
PDF service; it is not user authorization. In particular, a document endpoint
prefix may expose other users' documents if the endpoint does not independently
authorize requests. Use the narrowest rules possible, protect the PDF service,
and restrict its network access. Trusted hostnames must remain under your
control, including their DNS resolution.
