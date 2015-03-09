# Development Environment for Onegov

About OneGov: http://onegov.readthedocs.org/en/latest

## Install the Development Environment

Requires Python 3.4 (onegov packages are compatible with 2.7 though).

To install do this:

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

    bin/onegov-town --dns 'postgres://user:password@localhost:5432/database' --scheme towns-govikon add Govikon 

Having done that, start the onegov server as follows:

    bin/onegov-server

And point your browser to
[https://localhost:8080/towns/govikon](https://localhost:8080/towns/govikon).
