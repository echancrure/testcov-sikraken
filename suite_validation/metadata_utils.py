# testsuite-validator is tool for validation and execution of test suites.
# This file is part of testsuite-validator.
#
# Copyright (C) 2019  Dirk Beyer
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import xml.etree.ElementTree as ET
import zipfile
import datetime
import os
from typing import Optional
from tfbuilder import MetadataBuilder

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
    Return the content of the metadata file in the given test suite,
    if it exists.
    """
    meta_root = _get_metadata_root(test_suite)
    if not meta_root:
        return None

    metadata = {
        ORIGIN_FILE: test_suite,
        LANGUAGE: meta_root.find("sourcecodelang").text,
        PRODUCER: meta_root.find("producer").text,
        SPEC: meta_root.find("specification").text,
        PROGRAM_FILE: meta_root.find("programfile").text,
        PROGRAM_HASH: meta_root.find("programhash").text,
        TESTED_METHOD: meta_root.find("entryfunction").text,
        ARCHITECTURE: meta_root.find("architecture").text,
        CREATION_TIME: meta_root.find("creationtime").text,
    }
    return metadata


def create_for_reduced(
    origin_suite: str, producer: str, program_file: str, coverage_goal: str
) -> str:
    """
    Create metadata for reduced test suite.
    """
    m = get_metadata(origin_suite)

    language = m[LANGUAGE]
    entryfunction = m[TESTED_METHOD]
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
