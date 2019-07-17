#!/usr/bin/env sh
sudo update-java-alternatives --jre-headless --jre --set java-1.8.0-openjdk-amd64

if [ "$ES_URL" != 'no' ]; then
    mkdir /tmp/elasticsearch
    wget -O - "$ES_URL" | tar xz --directory=/tmp/elasticsearch --strip-components=1
fi

pip install --upgrade pip setuptools pytest
make install
