# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# Copyright (C) 2019 - 2020  Dirk Beyer
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

import xml.etree.ElementTree as ET
import zipfile
import datetime
import os
from typing import Optional
from tsbuilder import MetadataBuilder

LANGUAGE = "sourcecodelang"
PRODUCER = "producer"
SPEC = "specification"
PROGRAM_FILE = "programfile"
PROGRAM_HASH = "programhash"
TESTED_METHOD = "entryfunction"
ARCHITECTURE = "architecture"
CREATION_TIME = "creationtime"
ORIGIN_FILE = "inputwitnessfile"

METADATA_XML_NAME = "metadata.xml"


def _get_metadata_root(test_suite: str) -> Optional[ET.Element]:
    with zipfile.ZipFile(test_suite) as zip_inp:
        for name in zip_inp.namelist():
            if os.path.basename(name) == METADATA_XML_NAME:
                with zip_inp.open(name) as metadata_inp:
                    return ET.parse(metadata_inp).getroot()
        return None


def get_metadata(test_suite: str) -> Optional[dict]:
    """
    Return the content of the metadata file in the given test suite.
    Raises an xml.etree.ElementTree.ParseError if no metadata file exists
    or a required field is missing.
    """
    meta_root = _get_metadata_root(test_suite)
    if not meta_root:
        raise ET.ParseError("No metadata.xml found")

    def get_field_text(field_name: str) -> Optional[str]:
        field = meta_root.find(field_name)
        if field is None:
            raise ET.ParseError(f"Undefined field '<{field_name}>'")
        return field.text

    metadata = {
        ORIGIN_FILE: test_suite,
        LANGUAGE: get_field_text("sourcecodelang"),
        PRODUCER: get_field_text("producer"),
        SPEC: get_field_text("specification"),
        PROGRAM_FILE: get_field_text("programfile"),
        PROGRAM_HASH: get_field_text("programhash"),
        TESTED_METHOD: get_field_text("entryfunction"),
        ARCHITECTURE: get_field_text("architecture"),
        CREATION_TIME: get_field_text("creationtime"),
    }
    return metadata


def create_for_reduced(
    origin_suite: str, producer: str, program_file: str, coverage_goal: str
) -> str:
    """
    Create metadata for reduced test suite.
    """
    m = get_metadata(origin_suite)

    language = "C"
    entryfunction = m[TESTED_METHOD] or "main"
    architecture = m[ARCHITECTURE]
    creation_time = datetime.datetime.now()

    return MetadataBuilder(
        language,
        producer,
        coverage_goal,
        program_file,
        entryfunction,
        architecture,
        creation_time,
        origin_suite,
    ).build()
