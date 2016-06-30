#!/bin/bash
#
# This script helps to add and update gettext translations to onegov modules.
#

SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"

MODULE="${1}"
LANGUAGE="${2}"
DOMAIN="${MODULE}"
MODULE_PATH="${SCRIPTPATH}/src/${1}"

SEARCH_PATH="${MODULE_PATH}/"$(echo "${MODULE}" | sed 's:\.:/:g')
LOCALE_PATH="${SEARCH_PATH}/locale"
POT_FILE="${LOCALE_PATH}/${DOMAIN}.pot"

POT_CREATE="${SCRIPTPATH}/bin/pot-create"
POJSON=$(which pojson)

if [ "${LANGUAGE}" != "" ]; then
    if echo "${LANGUAGE}" | egrep -v '^[a-z]{2}(_[A-Z]{2})?$' > /dev/null; then
        echo "Invalid language code, format like this: de_CH, en_GB, en, de, ..."
        echo "the language code is lowercased, the optional country code is uppercased"
        exit 1
    fi
fi

function show_usage() {
    echo "Usage: bash i18n.sh module-name [language]"
    echo ""
    echo "Example adding a language to a module:"
    echo "bash i18n.sh onegov.town fr"
    echo ""
    echo "Example updating the pofiles in a module:"
    echo "bash i18n.sh onegov.town"
    echo ""
    exit 1
}

function die() {
    echo "${1}"
    exit 1
}

command_exists () {
    type "$1" &> /dev/null;
}

if [ "${MODULE}" = "" ]; then
    show_usage
fi

# try to find the gettext tools we need - on linux they should be available,
# on osx we try to get them from homebrew
if command_exists brew; then
    if brew list | grep gettext -q; then
        BREW_PREFIX=$(brew --prefix)
        GETTEXT_PATH=$(brew info gettext | grep "${BREW_PREFIX}" | awk '{print $1; exit}')

        MSGINIT="${GETTEXT_PATH}/bin/msginit"
        MSGMERGE="${GETTEXT_PATH}/bin/msgmerge"
        MSGFMT="${GETTEXT_PATH}/bin/msgfmt"
        XGETTEXT="${GETTEXT_PATH}/bin/xgettext"
    else
        echo "Homebrew was found but gettext is not installed"
        die  "Install gettext using 'brew install gettext'"
    fi
else
    MSGINIT=$(which msginit)
    MSGMERGE=$(which msgmerge)
    MSGFMT=$(which msgfmt)
    XGETTEXT=$(which xgettext)
fi

if [ ! -e "${MSGINIT}" ]; then
    die "msginit command could not be found, be sure to install gettext"
fi

if [ ! -e "${MSGMERGE}" ]; then
    die "msgmerge command could not be found, be sure to install gettext"
fi

if [ ! -e "${MSGFMT}" ]; then
    die "msgfmt command could not be found, be sure to install gettext"
fi

if [ ! -e "${XGETTEXT}" ]; then
    die "xgettext command could not be found, be sure to install gettext"
fi

if [ ! -d "${MODULE_PATH}" ]; then
    die "${MODULE_PATH} does not exist"
fi

if [ ! -d "${SEARCH_PATH}" ]; then
    die "${SEARCH_PATH} does not exist"
fi

if [ ! -e "${POT_CREATE}" ]; then
    die "${POT_CREATE} does not exist"
fi

if [ ! -e "${LOCALE_PATH}" ]; then
    echo "${LOCALE_PATH} does not exist, creating..."
    mkdir "${LOCALE_PATH}"
fi

if [ ! -e "${POT_FILE}" ]; then
    echo "${POT_FILE} does not exist, creating..."
    touch "${POT_FILE}"
fi

# language given, create catalog
if [ -n "${LANGUAGE}" ]; then
    echo "Creating language ${LANGUAGE}"

    if [ -e "${LOCALE_PATH}/${LANGUAGE}/LC_MESSAGES" ]; then
        die "Cannot initialize language '${LANGUAGE}', it exists already!"
    fi

    cd "${LOCALE_PATH}"
    mkdir -p "${LANGUAGE}/LC_MESSAGES"

    domainfile="${LANGUAGE}/LC_MESSAGES/${DOMAIN}.po"

    $MSGINIT -i "${DOMAIN}.pot" -o "${domainfile}" -l "${LANGUAGE}"
fi

echo "Extract messages"
$POT_CREATE "${SEARCH_PATH}" -o "${POT_FILE}"
find ${SEARCH_PATH} -name "*.js" | xargs $XGETTEXT --from-code=UTF-8 --keyword --keyword=_l --join-existing -o "${POT_FILE}"

echo "Update translations"
for po in "${LOCALE_PATH}"/*/LC_MESSAGES/$DOMAIN.po; do
    $MSGMERGE --no-location --no-fuzzy-matching -o "${po}" "${po}" "${POT_FILE}"
done

echo "Compile message catalogs"
for po in "${LOCALE_PATH}"/*/LC_MESSAGES/*.po; do
    $MSGFMT -o "${po%.*}.mo" "$po"
done

echo "Compile message catalogs"
for po in "${LOCALE_PATH}"/*/LC_MESSAGES/*.po; do
    $POJSON -e UTF-8 -p "$po" > "${po%.*}.json"
done
