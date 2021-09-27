# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# Copyright (C) 2018 - 2020 Dirk Beyer
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Module with functionality to write test-suite execution results to disk."""

import csv
import json
import os
import zipfile
import shutil
from typing import List
from suite_validation import _tool_info
from suite_validation import metadata_utils
from suite_validation import execution
from suite_validation import _logger as logging

# Constants for csv output
DELIMITER_TEST_COVERAGES = ";"
HEADER_ID = "id"
HEADER_TEST = "Test"
HEADER_COVERAGE_INDIVIDUAL = "Coverage (individual)"
HEADER_COVERAGE_SEQUENCE = "Coverage (accumulated)"
HEADER_COVERAGE_REDUCED = "Part of reduced suite"
HEADER_RESULT = "Execution success"
HEADER_RETURNCODE = "Returncode"
HEADER_CPUTIME = "CPU-Time (s)"
HEADER_WALLTIME = "Wall-Time (s)"
HEADER_MEMORY = "Memory used (byte)"

SUCCESSFUL_TESTSUITE_FOLDER = "test-suite"
SUCCESSFUL_TEST_NAME = "covering-test.xml"
"""Name of the file a successful test will be written to."""
SUCCESSFUL_HARNESS_NAME = "covering-test.c"
"""Name of the file the executable harness of a successful test will be written to."""


def write_tests_to_suite(
    program_file, origin_suite, tests, coverage_goal, output_suite
):
    """
    Writes the given tests from the given test suite to a new suite.

    :param str origin_suite: Path to the zip-file that contains the original test suite
    :param List[utils.TestVector] tests: Test vector to create files for.
    :param str output_suite: Zip-file or directory to write to.
    """
    if os.path.exists(output_suite):
        logging.debug("File %s already exists - removing it.", output_suite)
        if os.path.isdir(output_suite):
            shutil.rmtree(output_suite, ignore_errors=True)
        else:
            os.remove(output_suite)

    output_metadata = _create_metadata(origin_suite, program_file, coverage_goal)
    if output_suite.endswith(".zip"):
        with zipfile.ZipFile(output_suite, "a") as outp_zip:
            outp_zip.writestr(metadata_utils.METADATA_XML_NAME, output_metadata)
    else:
        os.makedirs(output_suite, exist_ok=True)
        metadata_file = os.path.join(output_suite, metadata_utils.METADATA_XML_NAME)
        with open(metadata_file, "bw") as metadata_outp:
            metadata_outp.write(output_metadata)

    test_names = [t.origin for t in tests]
    with zipfile.ZipFile(origin_suite) as inp_zip:
        for test in inp_zip.namelist():
            if test in test_names:
                _copy_file(test, origin_suite, output_suite, test)


def _create_metadata(origin_suite: str, program_file: str, coverage_goal: str) -> str:
    producer = " ".join([_tool_info.__NAME__, _tool_info.__VERSION__])
    return metadata_utils.create_for_reduced(
        origin_suite, producer, program_file, coverage_goal
    )


def write_harness(program_file, test_vector, output_dir):
    """
    Writes, for the given test, an executable harness to the output folder.

    :param str program_file: Path to the program file.
    :param eu.TestVector test_vector: test vector to create harness for.
    :param str output_dir: Output directory to write into.
    """

    test_c_file = os.path.join(output_dir, SUCCESSFUL_HARNESS_NAME)
    harness_content = execution.HarnessCreator().convert(program_file, test_vector)
    with open(program_file, encoding="UTF-8") as progr_inp:
        harness_content = progr_inp.read() + harness_content
    with open(test_c_file, "w+", encoding="UTF-8") as outp:
        outp.write(harness_content)
    logging.info("Function-covering test case written to %s", test_c_file)


def _copy_file(relative_file_path, origin_container, dest_container, dest_name):
    logging.debug(
        "Copying %s from %s to %s/%s",
        relative_file_path,
        origin_container,
        dest_container,
        dest_name,
    )
    try:
        if dest_container.endswith(".zip"):
            with zipfile.ZipFile(dest_container, "a") as outp_zip:
                if dest_name in outp_zip.namelist():
                    logging.info(
                        "%s already exists in %s - not adding, as it would be a duplicate",
                        dest_name,
                        dest_container,
                    )
                else:
                    with zipfile.ZipFile(origin_container) as inp_zip:
                        content = inp_zip.read(relative_file_path)
                    outp_zip.writestr(dest_name, content)

        else:
            dest_file = os.path.join(dest_container, dest_name)
            if os.path.exists(dest_file):
                logging.info(
                    "%s already exists in %s - not adding, as it would be a duplicate",
                    dest_name,
                    dest_container,
                )
            else:
                parent_dir = os.path.dirname(dest_file)
                os.makedirs(parent_dir, exist_ok=True)
                with zipfile.ZipFile(origin_container) as inp_zip:
                    content = inp_zip.read(relative_file_path)
                with open(dest_file, "wb") as outp:
                    outp.write(content)

    except KeyError:
        logging.warning("No file %s in %s", relative_file_path, origin_container)


def write_results(output_file, exec_results, output_format) -> None:
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    if os.path.exists(output_file):
        os.remove(output_file)

    header, data = _collect_data(exec_results)
    if output_format == "json":
        _write_results_json(output_file, header, data)
    elif output_format == "csv":
        _write_results_csv(output_file, header, data)
    else:
        assert False


def _write_results_json(output_file, header, data) -> None:
    json_data = []
    for table_row in data:
        single_data = {}
        for idx, key in enumerate(header):
            assert key not in single_data
            single_data[key] = table_row[idx]
        json_data.append(single_data)

    with open(output_file, mode="w", encoding="UTF-8") as outp:
        # don't sort keys so we have same order as header specifies
        json.dump(json_data, outp, indent=2, sort_keys=False)


def _write_results_csv(output_file, header, data) -> None:
    with open(output_file, mode="w", encoding="UTF-8") as individual_test_cov_file:
        writer = csv.writer(
            individual_test_cov_file, delimiter=DELIMITER_TEST_COVERAGES
        )
        writer.writerow(header)
        for row in data:
            writer.writerow(row)


def _transpose(data: List[list]):
    return list(map(list, zip(*data)))


def _collect_data(exec_results):
    test_coverages = exec_results.coverage_tests
    coverage_sequence = exec_results.coverage_sequence
    reduced_test_coverages = exec_results.reduced_coverage_tests

    header = [HEADER_ID]
    data = []
    # add ids for executions, starting from 1 to match plot
    data.append(list(range(1, len(exec_results.results) + 1)))
    if test_coverages:
        header += [HEADER_TEST, HEADER_COVERAGE_INDIVIDUAL]
        data.append([tc.test_vectors_as_string() for tc in test_coverages])
        data.append([tc.hits_percent for tc in test_coverages])
    if coverage_sequence:
        header.append(HEADER_COVERAGE_SEQUENCE)
        data.append(coverage_sequence)
    if reduced_test_coverages:
        header.append(HEADER_COVERAGE_REDUCED)
        assert (
            test_coverages
        ), "Reduced test coverage can only be used with individual test coverage"
        test_names = [tc.test_vectors_as_string() for tc in test_coverages]
        reduced_tests = [tc.test_vectors_as_string() for tc in reduced_test_coverages]
        data.append([test in reduced_tests for test in test_names])

    header += [
        HEADER_RESULT,
        HEADER_RETURNCODE,
        HEADER_CPUTIME,
        HEADER_WALLTIME,
        HEADER_MEMORY,
    ]
    data.append([not r.execution_info.got_aborted for r in exec_results.results])
    data.append([r.execution_info.returncode for r in exec_results.results])
    data.append(
        [
            r.execution_info.cpu_time if r.execution_info.cpu_time else ""
            for r in exec_results.results
        ]
    )
    data.append(
        [
            r.execution_info.wall_time if r.execution_info.wall_time else ""
            for r in exec_results.results
        ]
    )
    data.append(
        [
            r.execution_info.memory_used if r.execution_info.memory_used else ""
            for r in exec_results.results
        ]
    )

    table = _transpose(data)

    return header, table
