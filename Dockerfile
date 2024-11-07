FROM python:3.13-alpine

# Install upgrades and dependancies for WeasyPrint
RUN apk update && \
    apk upgrade && \
    apk add gcc \
            musl-dev \
            pango \
            zlib-dev \
            jpeg-dev \
            openjpeg-dev \
            g++ \
            libffi-dev \
            harfbuzz-subset

# Install fonts
RUN apk add font-terminus \
            font-inconsolata \
            font-dejavu \
            font-noto \
            font-noto-cjk \
            font-awesome \
            font-noto-extra \
            font-vollkorn \
            font-misc-cyrillic \
            font-mutt-misc \
            font-screen-cyrillic \
            font-winitzki-cyrillic \
            font-cronyx-cyrillic \
            font-noto-thai \
            font-noto-tibetan \
            font-ipa \
            font-sony-misc \
            font-jis-misc \
            font-isas-misc

# Install custom fonts including BCSans
ADD fonts /usr/share/fonts
ADD fonts.py /app/fonts.py
ADD app.py /app/app.py

ADD requirements.txt /app/requirements.txt
WORKDIR /app

RUN python3 -m pip install -U setuptools
RUN python3 -m pip install -r requirements.txt

EXPOSE 5001

ENV NUM_WORKERS=3
ENV TIMEOUT=120

CMD gunicorn --bind 0.0.0.0:5001 --timeout $TIMEOUT --workers $NUM_WORKERS  app:app
