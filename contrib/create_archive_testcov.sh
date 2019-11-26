#!/bin/bash
set -eao pipefail
IFS=$'\t\n'

if ! git diff --quiet; then
  echo "Archive directory is dirty. Please commit pending changes and then re-run this script."
  false
fi
DIRNAME="$(dirname "$(readlink -f "$0")")/.."
VERSION=$(git describe --always --dirty)
TMPDIR=$(mktemp -d)
pushd "$TMPDIR" > /dev/null
ln -s "$DIRNAME" testcov
# Install dependencies
(
cd testcov
EGGDIR=$(mktemp -d)
python3 setup.py egg_info -e "$EGGDIR"
pip install --target lib -r "$EGGDIR/testcov.egg-info/requires.txt"
rm -r "$EGGDIR"
mkdir -p testcov/lib/bin
cp $(which lcov) testcov/lib/bin
)
# Set version number
find testcov/suite_validation -name '*.py' -exec sed -i "s/\(__VERSION__\s*=\s*\).*/\1\"$VERSION\"/" '{}' +
zip --exclude="*/lib/PyYAML-3.13.dist-info/*" --exclude="*/lib/yaml*" --exclude="*/test/*" --exclude="*/a.out" --exclude="*/.idea/*" --exclude="*/__pycache__/*" -r testcov.zip testcov/{bin,suite_validation,lib,LICENSE.txt,README.md}
popd
mv "$TMPDIR/testcov.zip" ./
echo "Wrote testcov.zip, version $VERSION"
