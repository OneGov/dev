# Development Environment for Onegov

About OneGov: http://onegov.readthedocs.org/en/latest

## Install the Development Environment

Requires Python 3.4 (onegov packages are compatible with 2.7 though).

OneGov requires the following packages:

    - libmemcached
    - libxml2
    - libxslt

Those should be downlaoded and built automatically when you run buildout.

For that to work you need the python development files. On OSX those should
be already installed if you installed Python 3 trough homebrew (which you
should).

On other POSIX platforms you might have to install them. On Ubuntu for example,
you need to run:

    sudo apt-get install python3-dev

Having done all that, run buildout:

    git clone https://github.com/onegov/dev onegov
    cd onegov
    virtualenv -p python34 --no-site-packages .
    python bootstrap.py
    bin/buildout

## Run an Application

OneGov supports different applications under different paths. Usually you
probably want to run onegov.town though, the first such application.

To do this, make sure you have Postgres 9.1+ running locally, with a database
designated to running your application.

Once you do, copy `onegov.yml.example` and edit the dns string inside
the resulting `onegov.yml` file:

    cp onegov.yml.example onegov.yml

Then edit the following line in `onegov.yml`:

    dsn: postgres://user:password@localhost:5432/database

Now before you can start your server, you need to define a town. Run the
following command to define a new town (there is currently no way to do it
through the web interface).

    bin/onegov-town --dsn 'postgres://user:password@localhost:5432/database' --schema towns-govikon add Govikon

You also might want to define an admin to manage the site. Run the following
command to define a user with admin role.

    bin/onegov-user --dsn 'postgres://user:password@localhost:5432/database' --schema towns-govikon add admin admin@example.org

Having done that, start the onegov server as follows:

    bin/onegov-server

And point your browser to
[http://localhost:8080/towns/govikon](http://localhost:8080/towns/govikon).

## Run Tests

To run the tests of a specific module:

    bin/py.test src/onegov.core
    bin/py.test src/onegov.town
    bin/py.test src/onegov.user

And so on.

    bin/py.test src/onegov.*

Doesn't really work because pytest gets confused.

To run a specific test:

    bin/py.test src/onegov.core -k test_my_test

To debug a specific test (xdist does not support PDB at the moment), disable
the additional ops in pytest.ini and run the test with '-p no:xdist'

    bin/py.test src/onegov.core -p no:xdist -k test_my_test

## Run Tests with Tox

To run the tests with tox:

    pip install tox
    bash tox.sh onegov.core
    bash tox.sh onegov.town
    bash tox.sh onegov.user

And so on.

To run a specific test:

    bash tox.sh onegov.core -- -k test_my_test

## Internationalization (i18n)

To use i18n, gettext must be installed. On most linux distros this is a given.
On OSX it is recommended to install gettext with homebrew:

    brew install gettext

### Add a language to a module:

    bash i18n.sh onegov.town de

### Extract the messages from a module (update the translation files)

    bash i18n.sh onegov.town

### SCSS Linting

We use https://github.com/brigade/scss-lint to lint our scss files. The linter
configuration is found in the local directory (`./.scss-lint.yml`).

In Sublime Text the linter should pick this file up when using the
`onegov.sublime-project` file. Though it might require a restart.

In Atom the https://atom.io/packages/linter-scss-lint will pick up the right
configuration file per default.

Other editors are not directly supported, so you are on your own.

### Buildout Build Status

Travis tests if this buildout actually works. Current status:

[![Build Status](https://travis-ci.org/OneGov/dev.svg?branch=master)](https://travis-ci.org/OneGov/dev)
