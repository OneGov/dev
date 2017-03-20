""" Replacement for zc.buildout's bootstrap script.

This version is simpler and usually works better than bootstrap.py, which
builds on stale assumptions about the state of Python packaging.

"""

import os
import sys


def is_venv():
    if hasattr(sys, 'real_prefix'):
        return True

    if hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix:
        return True

    return False


if __name__ == '__main__':

    if not is_venv():
        print("Please make sure you created a virtualenv and activated it")
        sys.exit(1)

    os.system('pip install --upgrade pip')
    os.system('pip install --upgrade setuptools')
    os.system('pip install --upgrade zc.buildout')

    if not os.path.exists('./bin'):
        os.system('mkdir ./bin')

    if not os.path.exists('./bin/buildout'):
        os.system('ln -s $VIRTUAL_ENV/bin/buildout ./bin/buildout')
