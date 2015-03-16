#!/bin/bash

MODULE="${1}"
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"

LIBS="${SCRIPTPATH}/parts/libmemcached/lib"
LIBS="${LIBS}:${SCRIPTPATH}/parts/libxml2/lib"
LIBS="${LIBS}:${SCRIPTPATH}/parts/libxslt/lib"

INCLUDES="${SCRIPTPATH}/parts/libmemcached/include"
INCLUDES="${INCLUDES}:${SCRIPTPATH}/parts/libxml2/include/libxml2"
INCLUDES="${INCLUDES}:${SCRIPTPATH}/parts/libxslt/include"

cd "src/${MODULE}"
PWD=$(pwd)

if ! grep "install_command" tox.ini; then
    echo "Add install_command=pip install {opts} {packages} to ${PWD}/tox.ini, testenv section"
    exit 1
fi

sed "s\
!install_command.*\
!install_command = pip install {opts} \
--global-option=build_ext \
--global-option='-I${INCLUDES}' \
--global-option='-L${LIBS}' \
{packages}!g" tox.ini > tox.temp.ini

tox -c tox.temp.ini "${@:2}"

rm tox.temp.ini

cd -
