#!/bin/bash
set -eao pipefail
IFS=$'\t\n'

DIRNAME="$(dirname "$(readlink -f "$0")")/.."
VERSION=$(git describe --always --dirty)
TMPDIR=$(mktemp -d)
pushd "$TMPDIR" > /dev/null
ln -s "$DIRNAME" testsuite-validator 
find testsuite-validator -name '*.py' -exec sed -i "s/\(__VERSION__\s*=\s*\).*/\1\"$VERSION\"/" '{}' +
zip --exclude="*/lib/PyYAML-3.13.dist-info/*" --exclude="*/lib/yaml*" --exclude="*/test/*" --exclude="*/a.out" --exclude="*/.idea/*" --exclude="*/__pycache__/*" -r testsuite-validator.zip testsuite-validator/{bin/testsuite-validator,suite_validation,lib,LICENSE.txt,README.md}
popd
mv "$TMPDIR/testsuite-validator.zip" ./
echo "Wrote testsuite-validator.zip, version $VERSION"
