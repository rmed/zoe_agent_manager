#!/bin/bash

# Build locales to ../locale
# Must be run from the zam/ directory
# Requires 'msgfmt' command. Only for development!

# Generate original English .mo
echo "Building 'en'..."
mkdir -p ../locale/en/LC_MESSAGES
msgfmt -o ../locale/en/LC_MESSAGES/zam.mo locale/zam.pot

# Generate rest of .mo files
for po in locale/*.po
do
    file=${po##*/}
    lang=${file%.*}
    echo "Building '$lang'..."

    mkdir -p ../locale/$lang/LC_MESSAGES
    msgfmt -o ../locale/$lang/LC_MESSAGES/zam.mo $po
done

echo "Done!"
