#!/bin/bash

# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

set -eao pipefail
IFS=$'\t\n'

if ! git diff --quiet; then
  echo "Archive directory is dirty. Please commit pending changes and then re-run this script."
  false
fi
LCOV_LOC=$(which lcov)
GENINFO_LOC=$(which geninfo)
[ -z $LCOV_LOC ] && echo "lcov missing on system. Please install LCOV or add it to your PATH" && false
[ -z $GENINFO_LOC ] && echo "geninfo missing on system. Please install LCOV or add it to your PATH" && false

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
python3 -m pip install --target lib -r "$EGGDIR/testcov.egg-info/requires.txt"
rm -r "$EGGDIR"
mkdir -p "${DIRNAME}"/lib/bin
cp $(which lcov) "${DIRNAME}"/lib/bin
cp $(which geninfo) "${DIRNAME}"/lib/bin
)
# Set version number
find testcov/suite_validation -name '*.py' -exec sed -i "s/\(__VERSION__\s*=\s*\).*/\1\"$VERSION\"/" '{}' +
zip --exclude="*/lib/PyYAML-*.dist-info/*" --exclude="*/lib/yaml*" --exclude="*/test/*" --exclude="*/a.out" --exclude="*/.idea/*" --exclude="*/__pycache__/*" -r testcov.zip testcov/{bin,suite_validation,lib,LICENSE.txt,README.md}
popd
mv "$TMPDIR/testcov.zip" ./
echo "Wrote testcov.zip, version $VERSION"
git reset --hard
