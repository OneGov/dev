#!/usr/bin/env sh
if [ "$ES_URL" != 'no' ]; then
    mkdir /tmp/elasticsearch
    wget -O - "$ES_URL" | tar xz --directory=/tmp/elasticsearch --strip-components=1
fi

pip install --upgrade pytest

python bootstrap.py
bin/buildout
