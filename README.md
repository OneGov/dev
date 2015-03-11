# Development Environment for Onegov

About OneGov: http://onegov.readthedocs.org/en/latest

## Install the Development Environment

Requires Python 3.4 (onegov packages are compatible with 2.7 though).

Before you can proceed, you have to make sure the following packages are
installed:

    - libmemcached

On OSX this can be done thusly (if you are using homebrew, which you should):

    brew install libmemcached

Having done that, proceed like this:

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

Once you do, copy `onegov.yml.example` and edit the dns string inside the
the resulting `onegov.yml` file:

    cp onegov.yml.example onegov.yml

Then edit the following line in `onegov.yml`:

    dsn: postgres://user:password@localhost:5432/database

Now before you can start your server, you need to define a town. Run the
following to define a new town, as there is currently no way to do it through
the web interface.

    bin/onegov-town --dsn 'postgres://user:password@localhost:5432/database' --schema towns-govikon add Govikon 

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


## Internationalization (i18n)

To use i18n, gettext must be installed. On most linux distros this is a given.
On OSX it is recommended to install gettext with homebrew:

    brew install gettext

### Add a language to a module:

    bash i18n.sh onegov.town de

### Extract the messages from a module (update the translation files)

    bash i18n.sh onegov.town
