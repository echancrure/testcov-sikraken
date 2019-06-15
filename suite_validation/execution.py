# tbf-testsuite-validator is tool for validation and execution of test suites.
# This file is part of tbf-testsuite-validator.
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
import xml.etree.ElementTree as ET
import re
import os
import zipfile

from lxml import etree

from suite_validation import execution_utils as eu

HARNESS_FILE_NAME = "harness.c"
ARCHITECTURE_TAG = "architecture"

COVERS = "false"
UNKNOWN = "unknown"
ERROR = "error"
ABORTED = "abort"


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
        cmd = ["gcc"]
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
                [executable],
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

    @staticmethod
    def _get_gcov_val(gcov_line):
        if ":" in gcov_line:
            stat = gcov_line.split(":")[1]
            measure_end = stat.find("of ")
            return stat[:measure_end] + "(" + stat[measure_end:] + ")"
        return None

    def run(self, program_file, test_vector):
        result = super().run(program_file, test_vector)
        if result == ABORTED:
            logging.info("Aborted test run is not considered for coverage")
        return result

    def get_coverage(self, program_file):
        lines_executed = None
        branches_executed = None
        branches_taken = None

        if self.harness_file:
            assert self.harness_file.endswith(".c")
            data_file = self.harness_file[:-1] + "gcda"
            data_file = os.path.basename(data_file)  # data file is in cwd

            if os.path.exists(data_file):
                cmd = ["gcov", "-nbc", data_file]
                res = eu.execute(cmd, quiet=True)
                full_cov = res.stdout.splitlines()

                program_name = os.path.basename(program_file)
                for number, line in enumerate(full_cov):
                    if line.startswith("File") and program_name in line:
                        lines_executed = self._get_gcov_val(full_cov[number + 1])
                        branches_executed = self._get_gcov_val(full_cov[number + 2])
                        branches_taken = self._get_gcov_val(full_cov[number + 3])
                        break
        else:
            logging.debug(
                "Coverage requested without any execution. Returning defaults."
            )

        if not lines_executed:
            lines_executed = "0%"
        if not branches_executed:
            branches_executed = "0%"
        if not branches_taken:
            branches_taken = "0%"

        return lines_executed, branches_executed, branches_taken


class SuiteExecutor:
    """Provides methods to execute a full test suite in the XML format."""

    def __init__(
        self,
        stop_after_found_error,
        timelimit_per_run,
        harness_file_target="harness.c",
        compile_target="a.out",
        compute_sequence=False,
        overwrite_files=True,
    ):
        self._stop_after_success = stop_after_found_error
        self._timelimit = timelimit_per_run

        self._harness_file_target = harness_file_target
        self._compile_target = compile_target
        self._compute_sequence = compute_sequence
        self._overwrite_files = overwrite_files

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

        executor = CoverageMeasuringExecutionRunner(
            machine_model,
            self._timelimit,
            self._harness_file_target,
            self._compile_target,
            self._overwrite_files,
        )

        metadata = self._get_metadata(test_suite)
        if metadata is None:
            raise ExecutionError("No %s found" % eu.METADATA_XML_NAME)

        architecture = metadata.find(ARCHITECTURE_TAG)
        if architecture is not None:
            if ("32" in architecture.text) != ("32" in machine_model):
                logging.warning(
                    "Architecture in metadata.xml different from expected: '%s' vs. '%s'",
                    architecture.text,
                    machine_model,
                )

        # this method call raises an ExecutionError if the given test suite is invalid
        test_vectors = self._get_described_vectors(test_suite)

        self._execute_tests(program_file, test_vectors, executor, result_target)

        return result_target

    @staticmethod
    def _get_metadata(test_suite):
        """Return the metadata of the given test suite."""
        with zipfile.ZipFile(test_suite) as zip_inp:
            for name in zip_inp.namelist():
                if os.path.basename(name) == eu.METADATA_XML_NAME:
                    with zip_inp.open(name) as metadata_inp:
                        return ET.parse(metadata_inp)
            return None

    @staticmethod
    def _get_described_vectors(test_suite):
        """Return a generator that produces the test vectors described by the given test suite.

            :raises ExecutionError: if given test suite is invalid.
        """
        logging.debug("Looking for tests in %s", test_suite)
        with zipfile.ZipFile(test_suite) as zip_inp:
            if not any(
                os.path.basename(f) == eu.METADATA_XML_NAME for f in zip_inp.namelist()
            ):
                raise ExecutionError("No %s in %s" % (eu.METADATA_XML_NAME, test_suite))

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

    def _execute_tests(self, program_file, test_vectors, executor, result_target):
        """Executes all test vectors on the given program using the given executor
        and puts the results into result_target."""

        try:
            for tv in test_vectors:
                next_result = executor.run(program_file, tv)

                if self._compute_sequence:
                    result_target.lines_executed, result_target.branches_executed, result_target.branches_taken = executor.get_coverage(
                        program_file
                    )

                    result_target.coverage_sequence.append(
                        float(result_target.branches_taken.split("%")[0])
                    )

                result_target.results.append(next_result)

                if next_result == COVERS:
                    result_target.successful_test = tv
                    if self._stop_after_success:
                        logging.info("Stopping. Error found for test %s", tv)
                        break

        finally:
            if not self._compute_sequence:
                result_target.lines_executed, result_target.branches_executed, result_target.branches_taken = executor.get_coverage(
                    program_file
                )


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
