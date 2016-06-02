# Development Environment for Onegov

About OneGov: http://onegov.readthedocs.org/en/latest

## Install the Development Environment

Requires Python 3.4+.

OneGov requires the following packages:

    - libxml2
    - libxslt

Those should be downloaded and built automatically when you run buildout.

For that to work you need the python development files. On OSX those should
be already installed if you installed Python 3 trough homebrew.

On other POSIX platforms you might have to install them. On Ubuntu for example,
you need to run:

    sudo apt-get install git python3-dev python-virtualenv

You also need to have the following header files installed:

    sudo apt-get install libcurl4-openssl-dev libffi-dev libjpeg-dev libpq-dev libxml2-dev libxslt1-dev zlib1g-dev

Having done all that, run buildout:

    git clone https://github.com/onegov/dev onegov
    cd onegov
    virtualenv -p python3.4 --no-site-packages .
    bin/python bootstrap.py
    bin/buildout

## Setup Database

OneGov supports different applications under different paths. Usually you
probably want to run onegov.town though, the first such application. You can
have different applications run on the same database though.

To prepare a database, make sure you have Postgres 9.3+ running locally,
with a database designated to running your application.

Once you do, copy `onegov.yml.example` and edit the dns string inside
the resulting `onegov.yml` file:

    cp onegov.yml.example onegov.yml

Then edit the following line in `onegov.yml`:

    dsn: postgres://user:password@localhost:5432/database

## Setup OneGov Town

To use OneGov Town you need to define a town first. Run the
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

## Setup OneGov Election Day

To use OneGov Election Day you need to define a so called principal. That's
basically the canton using the application.

To do this for the canton of zg for example you create the following directory:

    mkdir -p file-storage/election_day-zg

Then you create a file containing the information about the canton:

    touch file-storage/election_day-zg/principal.yml

Inside you configure the principal (example content):

    name: Kanton Zug
    logo: logo.svg
    canton: zg
    color: '#234B85'

The logo points to a file in the same directory as the yml file.

You also want to add a user, which you can do as follows:

    bin/onegov-user --select '/election_day/zg' add admin admin@example.org

Having done that, start the onegov server as follows:

    bin/onegov-server

And point your browser to
[http://localhost:8080/wahlen/zg](http://localhost:8080/wahlen/zg).

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

To run tests in parallel (for faster execution):

    bin/py.test src/onegov.core --tx='4*popen//python=bin/py' --dist=load

## Run Tests with Tox

To run the tests with tox:

    pip install tox
    bash tox.sh onegov.core
    bash tox.sh onegov.town
    bash tox.sh onegov.user

And so on.

To run a specific test:

    bash tox.sh onegov.core -- -k test_my_test

## Profiling

To profile all requests, set `profile` in the onegov.yml to `true`. This will
result in a timestamp profile file in the profiles folder for each request.

You may then use the pstats profile browser as described here:
http://stefaanlippens.net/python_profiling_with_pstats_interactive_mode

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
