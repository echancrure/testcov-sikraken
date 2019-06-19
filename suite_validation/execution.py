# testsuite-validator is tool for validation and execution of test suites.
# This file is part of testsuite-validator.
#
# Copyright (C) 2018  Dirk Beyer
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
"""Module for creation and execution of test harnesses from test-format XML files."""

import logging
import re
import os
import tempfile
import zipfile
import shutil

from lxml import etree

from suite_validation import execution_utils as eu
from suite_validation import coverage as cov
from suite_validation import metadata_utils as mu

HARNESS_FILE_NAME = "harness.c"

COVERS = "false"
UNKNOWN = "unknown"
ERROR = "error"
ABORTED = "abort"

HARNESS_GCDA_FILE = "harness.gcda"

GCOV_FILE_END = ".gcov"
GCDA_FILE_END = ".gcda"
GCNO_FILE_END = ".gcno"

LCOV_SUBFOLDER_TRACE_FILE = "tracefiles"
LCOV_SUMMARY_TRACE_FILE = "tracefile_summary.info"
LCOV_CURRENT_TRACE_FILE = "current_test.info"


class ExecutionError(Exception):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg


class HarnessCreator:
    """Provides methods to create a harness.

    The harness can either read test input values from standard input or provide fixed values
    in the code.
    """

    @staticmethod
    def _get_vector_read_method(test_vector):
        if test_vector:
            definition = ["unsigned int access_counter = 0;"]
            definition += [""]
            definition += ["char * get_input() {"]
            definition += ["    char * inp_var;"]
            definition += ["    switch(access_counter) {"]
            for idx, item in enumerate(test_vector.vector):
                # If there's quotes in the value, escape them for our C code
                value = item["value"].replace(r'"', r"\"r")
                definition += ["    case " + str(idx) + ":"]
                definition += ['        inp_var = "' + value + '";']
                definition += ["        break;"]
            definition += ["    default:"]
            definition += [
                '        fprintf(stderr, "Incomplete test vector, aborting\\n");'
            ]
            definition += ["        abort();"]
            definition += ["    }"]
            definition += ["    access_counter++;"]
            definition += ["    return inp_var;"]
            definition += ["}"]
            return "\n".join(definition)

        return """char * get_input() {
    char * inp_var = malloc(MAX_INPUT_SIZE);
    char * result = fgets(inp_var, MAX_INPUT_SIZE, stdin);
    if (result == 0) {
        fprintf(stderr, "No more test inputs available, exiting\\n");
        exit(1);
    }
    unsigned int input_length = strlen(inp_var)-1;
    /* Remove '\\n' at end of input */
    if (inp_var[input_length] == '\\n') {
        inp_var[input_length] = '\\0';
    }
    return inp_var;
}
"""

    @staticmethod
    def _get_declarations(program_file):
        to_declare = set(l[0] for l in eu.EXTERNAL_DECLARATIONS)
        with open(program_file) as inp:
            for line in inp.readlines():
                for name, _ in eu.EXTERNAL_DECLARATIONS:
                    if name in to_declare and re.search(
                        r"\s+" + name + r"([^a-zA-Z]+|$)", line
                    ):
                        to_declare.remove(name)
        return "\n".join(l[1] for l in eu.EXTERNAL_DECLARATIONS if l[0] in to_declare)

    @staticmethod
    def _get_harness_skeleton():
        harness_skeleton = os.path.join(os.path.dirname(__file__), HARNESS_FILE_NAME)
        with open(harness_skeleton) as inp:
            return inp.read()

    def convert(self, program_file, test_vector=None) -> str:
        """Create a harness that reads tests values for nondet methods.
        If no test vector is given, the harness reads test values from standard input.
        Otherwise, the values of the test_vector are coded into the harness.

        The created harness can be compiled with the original program to create
        a testing environment.
        Example compilation with gcc, with harness content written to a file 'harness.c':
        ```
            gcc -include program_file.c harness.c
        ```

        :param Optional[eu.TestVector] test_vector: Test vector to use for harness creation
        :return str: Content of the harness.
        """

        testsuite = [self._get_declarations(program_file)]
        testsuite += [self._get_harness_skeleton()]
        testsuite += [self._get_vector_read_method(test_vector)]

        return "\n".join(testsuite)


class ExecutionRunner:
    def __init__(
        self,
        machine_model,
        timelimit_per_run,
        harness_file_target="harness.c",
        compile_target="a.out",
        overwrite_files=True,
    ):
        """Create new ExecutionRunner.

        :param str machine_model: Machine model to use
        :param int timelimit_per_run: Time limit for each execution, in seconds
        """

        self.machine_model = machine_model
        self.harness = None
        self._compile_target = compile_target
        self.harness_generator = HarnessCreator()
        self.harness_file = None
        self._harness_file_target = harness_file_target
        self.timelimit = timelimit_per_run
        self._overwrite = overwrite_files

    def _get_compile_cmd(
        self, program_file, harness_file, output_file, c_version="gnu11"
    ):
        mm_arg = "-m64" if self.machine_model == eu.MACHINE_MODEL_64 else "-m32"
        cmd = ["clang"]
        cmd += [
            "-std={}".format(c_version),
            mm_arg,
            "-D__alias__(x)=",
            "-o",
            output_file,
            "-include",
            program_file,
            harness_file,
            "-lm",
        ]

        return cmd

    def compile(self, program_file, harness_file, output_file):
        if not self._overwrite and os.path.exists(output_file):
            logging.info("Not overwriting %s", output_file)
            return output_file

        logging.debug(
            "Compiling %s and %s into %s", program_file, harness_file, output_file
        )
        compile_cmd = self._get_compile_cmd(program_file, harness_file, output_file)
        compile_result = eu.execute(compile_cmd, quiet=True)

        if compile_result.returncode != 0:
            raise ExecutionError(
                "Compilation failed for harness {}:\n".format(harness_file)
                + "\n".join(
                    "    " + l for l in compile_result.stderr.decode().split("\n")
                )
            )

        return output_file

    def get_executable_harness(self, program_file):
        if not self.harness:
            self.harness = os.path.abspath(
                self._create_executable_harness(program_file)
            )
        return self.harness

    def _create_executable_harness(self, program_file):
        harness_file = self._harness_file_target
        if not self._overwrite and os.path.exists(harness_file):
            logging.info("Not overwriting %s", harness_file)
        else:
            harness_content = self.harness_generator.convert(program_file)

            with open(harness_file, "w+") as outp:
                outp.write(harness_content)
        self.harness_file = (
            harness_file
        )  # set this only after successfully writing the harness

        output_file = self._compile_target
        return self.compile(program_file, harness_file, output_file)

    def run(self, program_file, test_vector):
        executable = self.get_executable_harness(program_file)
        input_vector = self._get_input_vector(test_vector)

        if executable and os.path.exists(executable):
            run_result = eu.execute(
                self._get_execute_cmd(executable),
                quiet=True,
                input_str=input_vector,
                timelimit=self.timelimit,
            )
            if eu.found_err(run_result):
                logging.debug("Error found for test %s", test_vector)
                return COVERS
            if run_result.got_aborted:
                logging.info("Aborted execution for test %s", test_vector)
                return ABORTED
            if run_result.returncode != 0:
                logging.debug("Non-0 return code for test %s", test_vector)
            return UNKNOWN
        return ERROR

    @staticmethod
    def _get_execute_cmd(executable):
        return [executable]

    @staticmethod
    def _get_input_vector(test_vector, escape_newline=False):
        input_vector = ""
        if escape_newline:
            newline = "\\n"
        else:
            newline = "\n"
            input_vector = newline.join([i["value"] for i in test_vector.vector])

        logging.debug("Input for %s:", test_vector.name)
        logging.debug(input_vector)
        return input_vector


class CoverageMeasuringExecutionRunner(ExecutionRunner):
    def _get_compile_cmd(
        self, program_file, harness_file, output_file, c_version="gnu11"
    ):
        cmd = super()._get_compile_cmd(
            program_file, harness_file, output_file, c_version
        )
        cmd += ["-fprofile-arcs", "-ftest-coverage", "-DGCOV"]

        return cmd

    def compile(self, program_file, harness_file, output_file):
        harness_name = ".".join(harness_file.split("/")[-1].split(".")[:-1])
        gcov_files = [harness_name + suffix for suffix in (".gcda", ".gcno")]
        if self._overwrite:
            for f in gcov_files:
                if os.path.exists(f):
                    logging.info("Removing existing file %s", f)
                    os.remove(f)

        return_value = super().compile(program_file, harness_file, output_file)

        return return_value

    def run(self, program_file, test_vector):
        result = super().run(program_file, test_vector)
        if result == ABORTED:
            logging.info("Aborted test run is not considered for coverage")
        return result

    def compute_test_coverage(self, program_file, output_tracefile):
        program_name = os.path.basename(program_file)
        if self.harness_file:
            assert self.harness_file.endswith(".c")
            data_file = self.harness_file[:-1] + "gcda"
            data_file = os.path.basename(data_file)  # data file is in cwd
            return cov.get_test_coverage_from_data_file(
                program_name, data_file, output_tracefile
            )
        logging.warning(
            "Coverage requested without any execution. Returning empty test coverage."
        )
        return cov.TestCoverage(program_name)

    def get_coverage(self, program_file, target_tracefile):

        if os.path.exists(target_tracefile):
            program_name = os.path.basename(program_file)
            return cov.get_test_coverage_from_lcov_file(program_name, target_tracefile)

        return self.compute_test_coverage(program_file, target_tracefile)


class IsolatingRunner(CoverageMeasuringExecutionRunner):
    @staticmethod
    def _get_execute_cmd(executable):
        # At the moment, this does not consider executables provided through PATH
        return [
            "runexec",
            "--overlay-dir",
            os.getcwd(),
            "--hidden-dir",
            "/sys/kernel/debug",
            "--result-files",
            "harness.gcda",
            "--output-dir",
            ".",
            "--",
            os.path.join(".", os.path.relpath(executable, start="./")),
        ]


class SuiteExecutor:
    """Provides methods to execute a full test suite in the XML format."""

    def __init__(
        self,
        goal,
        timelimit_per_run,
        harness_file_target="harness.c",
        compile_target="a.out",
        compute_sequence=False,
        reduce_tests=False,
        overwrite_files=True,
        isolate_tests=True,
        compute_individuals=True,
    ):
        self._check_for_error = goal == eu.COVER_ERRORS
        self._goal = goal
        self._timelimit = timelimit_per_run

        self._harness_file_target = harness_file_target
        self._compile_target = compile_target
        self._compute_sequence = compute_sequence
        self._reduce_tests = reduce_tests
        self._overwrite_files = overwrite_files
        self._isolate_tests = isolate_tests
        self._compute_individual_test_coverages = compute_individuals

    def run(self, program_file, test_suite, machine_model, result_target=None):
        """Execute the given tests on the given program.

        If a test covering an error is found, the XML file describing the test is written
        to a file in the current working directory.
        In addition, a C file that contains the program-file content
        and a harness with the covering test values is written to the current working directory.
        This file is standalone can be compiled to execute the covering test on the program.

        Example command line to compile a created harness:
        (in the example, the program requires math libraries (-lm))
        ```
            gcc -D'__alias__(x)=' covering-test.c -lm
        ```

        :param str program_file: Path to program file
        :param str test_suite: Path to zip file that contains test files.
        :param Optional[eu.SuiteExecutionResult] result_target: if set, execution results will be
            written into the given object. This allows easy access to intermediate results.

        :raises ExecutionError: if given test suite is invalid.
        """

        if result_target is None:
            result_target = eu.SuiteExecutionResult()

        if self._isolate_tests:
            executor = IsolatingRunner(
                machine_model,
                self._timelimit,
                self._harness_file_target,
                self._compile_target,
                self._overwrite_files,
            )
        else:
            executor = CoverageMeasuringExecutionRunner(
                machine_model,
                self._timelimit,
                self._harness_file_target,
                self._compile_target,
                self._overwrite_files,
            )

        metadata = mu.get_metadata(test_suite)
        if metadata is None:
            raise ExecutionError("No %s found" % mu.METADATA_XML_NAME)

        architecture = metadata[mu.ARCHITECTURE]
        if architecture is not None:
            if ("32" in architecture) != ("32" in machine_model):
                logging.warning(
                    "Architecture in metadata.xml different from expected: '%s' vs. '%s'",
                    architecture,
                    machine_model,
                )

        # this method call raises an ExecutionError if the given test suite is invalid
        test_vectors = self._get_described_vectors(test_suite)

        if self._overwrite_files:
            # old gcda, gcno or gcov files might exist
            _remove_coverages_files_in_working_directory()

        self._execute_tests(program_file, test_vectors, executor, result_target)

        return result_target

    @staticmethod
    def _get_described_vectors(test_suite):
        """Return a generator that produces the test vectors described by the given test suite.

            :raises ExecutionError: if given test suite is invalid.
        """
        logging.debug("Looking for tests in %s", test_suite)
        with zipfile.ZipFile(test_suite) as zip_inp:
            if not any(
                os.path.basename(f) == mu.METADATA_XML_NAME for f in zip_inp.namelist()
            ):
                raise ExecutionError("No %s in %s" % (mu.METADATA_XML_NAME, test_suite))

            for xml_file in (l for l in zip_inp.namelist() if l.endswith(".xml")):
                logging.debug("Considering %s", xml_file)
                with zip_inp.open(xml_file) as xml_inp:
                    xml_lines = xml_inp.readlines()
                    maybe_vector = convert_to_vector_if_testcase(xml_file, xml_lines)
                    if maybe_vector is not None:
                        logging.debug("File %s is valid testcase", xml_file)
                        yield maybe_vector
                    else:
                        logging.debug("File %s is no valid testcase", xml_file)

    def _get_coverage_for_goal(self, result_target):
        if self._goal == eu.COVER_BRANCHES:
            return result_target.branches_taken
        if self._goal == eu.COVER_CONDITIONS:
            return result_target.branches_executed
        if self._goal == eu.COVER_LINES:
            return result_target.lines_executed
        if self._goal == eu.COVER_ERRORS:
            return result_target.branches_taken
        assert False, "Unhandled coverage goal: {}".format(self._goal)
        return None

    @staticmethod
    def create_tracefile_folder():
        return tempfile.mkdtemp(prefix="testval")

    @staticmethod
    def get_tracefile_path(tracefile_folder):
        return os.path.join(tracefile_folder, LCOV_CURRENT_TRACE_FILE)

    def _execute_tests(self, program_file, test_vectors, executor, result_target):
        """Executes all test vectors on the given program using the given executor
        and puts the results into result_target."""

        tracefile_folder = self.create_tracefile_folder()
        output_tracefile = self.get_tracefile_path(tracefile_folder)
        summary_file = os.path.join(tracefile_folder, LCOV_SUMMARY_TRACE_FILE)
        try:
            for tv in test_vectors:
                next_result = executor.run(program_file, tv)

                if self._compute_individual_test_coverages:

                    coverage_test = executor.compute_test_coverage(
                        program_file, output_tracefile
                    )
                    coverage_test.set_result(next_result)
                    coverage_test.set_test_vector(tv)
                    result_target.coverage_tests.append(coverage_test)

                    # Create the summary for final output
                    if os.path.exists(output_tracefile):
                        cov.combine_tracefile_with_previous(
                            output_tracefile, summary_file
                        )
                        _remove_current_tracefile(output_tracefile)
                    _remove_harness_gcda_file()
                    del (
                        coverage_test
                    )  # not needed anymore after being stored in result_target

                if self._compute_sequence or self._reduce_tests:
                    if os.path.exists(summary_file):
                        coverage_summary = executor.get_coverage(
                            program_file, summary_file
                        )
                    else:
                        # if we have no summary file, we compute the info from the gcda
                        coverage_summary = executor.compute_test_coverage(
                            program_file, output_tracefile
                        )

                    result_target.lines_executed, result_target.branches_executed, result_target.branches_taken = (
                        coverage_summary.get_coverage_ratios_as_percent_expressions()
                    )

                    del coverage_summary  # not needed anymore after computation

                    new_coverage = float(
                        self._get_coverage_for_goal(result_target).split("%")[0]
                    )
                    if self._reduce_tests:
                        if result_target.coverage_sequence:
                            old_coverage = result_target.coverage_sequence[-1]
                        else:
                            old_coverage = 0
                        if not self._check_for_error and old_coverage < new_coverage:
                            logging.debug(
                                "Test %s increased coverage from %s%% to %s%%",
                                tv.origin,
                                old_coverage,
                                new_coverage,
                            )
                            result_target.successful_tests.append(tv)

                    result_target.coverage_sequence.append(new_coverage)

                result_target.results.append(next_result)

                if next_result == COVERS and self._check_for_error:
                    result_target.successful_tests.append(tv)
                    logging.info("Stopping. Error found for test %s", tv)
                    break

        finally:
            if os.path.exists(summary_file):
                coverage_summary = executor.get_coverage(program_file, summary_file)
            else:
                # if we have no summary file, we compute the info from the gcda
                coverage_summary = executor.get_coverage(program_file, output_tracefile)
            result_target.lines_executed, result_target.branches_executed, result_target.branches_taken = (
                coverage_summary.get_coverage_ratios_as_percent_expressions()
            )

            _remove_tracefile_folder(tracefile_folder)


def _remove_tracefile_folder(folder):
    shutil.rmtree(folder, ignore_errors=True)


def _remove_current_tracefile(tracefile):
    if os.path.exists(tracefile):
        os.remove(tracefile)


def _remove_harness_gcda_file():
    if os.path.exists(HARNESS_GCDA_FILE):
        os.remove(HARNESS_GCDA_FILE)


def _remove_coverages_files_in_working_directory():
    extensions = (GCOV_FILE_END, GCDA_FILE_END, GCNO_FILE_END)
    files = [
        f for f in os.listdir(os.curdir) if os.path.isfile(f) and f.endswith(extensions)
    ]
    for file in files:
        os.remove(file)


def _parse_xml_if_testcase(xml_lines):
    curr_content = []
    for line_number, line in enumerate(xml_lines):
        if line_number == 0 and not line.startswith(b"<?xml "):
            return None
        if line_number == 1 and not line.startswith(b"<!DOCTYPE testcase "):
            return None
        curr_content.append(line)
    return etree.fromstringlist(curr_content)


def convert_to_vector_if_testcase(test_xml_file, xml_lines):
    """Return test vector represented by given test-case XML.

    :param str test_xml_file: Path to xml file to convert.
    :return Optional[eu.TestVector]: TestVector representation of the test case described by
        the given XML, if XML is test-case XML. None, otherwise.
    """
    try:
        xml = _parse_xml_if_testcase(xml_lines)
    except etree.XMLSyntaxError as e:
        logging.warning("Couldn't parse file %s: %s", test_xml_file, e.msg)
        xml = None

    if xml is None:
        return None

    # test name is file name without suffix '.xml'
    test_name = os.path.basename(test_xml_file)[:-4]
    vector = eu.TestVector(test_name, test_xml_file)
    for input_tag in xml:
        logging.debug("Input: %s", input_tag.text)
        vector.add(input_tag.text.strip())
    return vector
