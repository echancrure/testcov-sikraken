#!/bin/bash
set -eao pipefail
IFS=$'\t\n'

DIRNAME="$(dirname "$(readlink -f "$0")")/.."
VERSION=$(git describe --always --dirty)
TMPDIR=$(mktemp -d)
pushd "$TMPDIR" > /dev/null
ln -s "$DIRNAME" tbf-testsuite-validator 
find tbf-testsuite-validator -name '*.py' -exec sed -i "s/\(__VERSION__\s*=\s*\).*/\1\"$VERSION\"/" '{}' +
zip --exclude="*/lib/PyYAML-3.13.dist-info/*" --exclude="*/lib/yaml*" --exclude="*/test/*" --exclude="*/a.out" --exclude="*/.idea/*" --exclude="*/__pycache__/*" -r tbf-testsuite-validator.zip tbf-testsuite-validator/{bin/tbf-testsuite-validator,suite_validation,lib,LICENSE.txt,README.md}
popd
mv "$TMPDIR/tbf-testsuite-validator.zip" ./
echo "Wrote tbf-testsuite-validator.zip, version $VERSION"
