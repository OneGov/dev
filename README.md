# Development Environment for Onegov

Run this to get started:

    git clone https://github.com/onegov/dev onegov
    cd onegov
    virtualenv -p python34 --no-site-packages .
    python bootstrap.py
    bin/buildout

Requires Python 3.4 (onegov packages are compatible with 2.7 though).

More info: http://onegov.readthedocs.org/en/latest
