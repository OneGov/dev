#!/usr/bin/env sh
pip install tox
pip install --upgrade pip
pip install --upgrade setuptools

if [ "$ES_URL" != 'no' ]; then
    mkdir /tmp/elasticsearch
    wget -O - "$ES_URL" | tar xz --directory=/tmp/elasticsearch --strip-components=1
fi

python bootstrap.py
bin/buildout
