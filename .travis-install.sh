#!/usr/bin/env sh
pip install tox==1.9.2

if [ "$ES_URL" != 'no' ]; then
    mkdir /tmp/elasticsearch
    wget -O - "$ES_URL" | tar xz --directory=/tmp/elasticsearch --strip-components=1
fi

python bootstrap.py
bin/buildout
