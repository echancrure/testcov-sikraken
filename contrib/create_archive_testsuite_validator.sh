#!/bin/bash
set -eao pipefail
IFS=$'\t\n'

DIRNAME="$(dirname "$(readlink -f "$0")")/.."
VERSION=$(git describe --always --dirty)
TMPDIR=$(mktemp -d)
pushd "$TMPDIR" > /dev/null
ln -s "$DIRNAME" testcov
find testcov -name '*.py' -exec sed -i "s/\(__VERSION__\s*=\s*\).*/\1\"$VERSION\"/" '{}' +
zip --exclude="*/lib/PyYAML-3.13.dist-info/*" --exclude="*/lib/yaml*" --exclude="*/test/*" --exclude="*/a.out" --exclude="*/.idea/*" --exclude="*/__pycache__/*" -r testcov.zip testcov/{bin/testcov,suite_validation,lib,LICENSE.txt,README.md}
popd
mv "$TMPDIR/testcov.zip" ./
echo "Wrote testcov.zip, version $VERSION"
