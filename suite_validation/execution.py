# testcov is tool for validation and execution of test suites.
# This file is part of testcov.
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
import sys
import tempfile
import zipfile

import xml.etree.ElementTree as etree

from suite_validation import execution_utils as eu
from suite_validation import coverage as cov
from suite_validation import metadata_utils as mu
from suite_validation import reduction_strategy as rs

HARNESS_FILE_NAME = "harness.c"
HARNESS_GCDA_FILE = "harness.gcda"

GCOV_FILE_END = ".gcov"
GCDA_FILE_END = ".gcda"
GCNO_FILE_END = ".gcno"

# Contains the extractable coverage data and is stored in the cwd
LCOV_TRACE_FILE = "current_test.info"


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
        preprocessed = True
        with open(program_file) as inp:
            for line in inp.readlines():
                # This loop may produce strange results if an include-statement
                # comes after the declaration of one of the required declarations;
                # it is common to put include-statements at the top of C programs,
                # though.
                if line.startswith("#include"):
                    preprocessed = False
                    break
                for name, _, _ in eu.EXTERNAL_DECLARATIONS:
                    if name in to_declare and re.search(
                        r"\s+" + name + r"([^a-zA-Z]+|$)", line
                    ):
                        to_declare.remove(name)
        if preprocessed:
            return "\n".join(
                l[1] for l in eu.EXTERNAL_DECLARATIONS if l[0] in to_declare
            )
        to_declare = set(l[2] for l in eu.EXTERNAL_DECLARATIONS)
        with open(program_file) as inp:
            for line in inp.readlines():
                for _, _, decl in eu.EXTERNAL_DECLARATIONS:
                    if line.startswith(decl):
                        to_declare.remove(decl)
        return "\n".join(to_declare)

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
        compiler="gcc",
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
        self._compiler = compiler

    def _get_compile_cmd(
        self, program_file, harness_file, output_file, c_version="gnu11"
    ):
        mm_arg = "-m64" if self.machine_model == eu.MACHINE_MODEL_64 else "-m32"
        cmd = [self._compiler]
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
        harness_content = self.harness_generator.convert(program_file)

        with open(harness_file, "w+") as outp:
            outp.write(harness_content)
        self.harness_file = (
            harness_file  # set this only after successfully writing the harness
        )

        output_file = self._compile_target
        return self.compile(program_file, harness_file, output_file)

    def run(self, program_file, test_vector):
        executable = self.get_executable_harness(program_file)
        input_vector = self._get_input_vector(test_vector)

        run_result = None
        if executable and os.path.exists(executable):
            run_result = eu.execute(
                self._get_execute_cmd(executable),
                quiet=True,
                input_str=input_vector,
                timelimit=self.timelimit,
            )
            if eu.found_err(run_result.stderr):
                logging.debug("Error found for test %s", test_vector)
                return eu.TestResult(eu.COVERS, run_result)
            if run_result.got_aborted:
                logging.info("Aborted execution for test %s", test_vector)
                return eu.TestResult(eu.ABORTED, run_result)
            if run_result.returncode != 0:
                logging.debug("Non-0 return code for test %s", test_vector)
            return eu.TestResult(eu.UNKNOWN, run_result)
        return eu.TestResult(eu.ERROR, run_result)

    def _get_execute_cmd(self, executable):
        # pylint: disable=no-self-use
        # `self` may be used by children
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
    def __init__(
        self,
        machine_model,
        timelimit_per_run,
        goal,
        harness_file_target="harness.c",
        compile_target="a.out",
        compiler="gcc",
    ):
        super().__init__(
            machine_model,
            timelimit_per_run,
            harness_file_target,
            compile_target,
            compiler,
        )
        self._goal = goal
        self._data_file = self._get_data_file()

    @staticmethod
    def _get_data_file():
        return "harness.gcda"

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
        for f in gcov_files:
            if os.path.exists(f):
                logging.info("Removing existing file %s", f)
                os.remove(f)

        return_value = super().compile(program_file, harness_file, output_file)

        return return_value

    def run(self, program_file, test_vector: eu.TestVector) -> eu.TestResult:
        result = super().run(program_file, test_vector)
        result.coverage = self.compute_coverage(
            program_file, test_vector, result, self._goal
        )
        return result

    def compute_coverage(
        self, program_file, test_vector, next_result, coverage_goal
    ) -> cov.TestCoverage:
        program_name = _get_program_name(program_file)
        if self.harness_file and os.path.exists(self._get_data_file()):
            data_file = self._get_data_file()
            return cov.compute_test_coverage(
                program_name,
                data_file,
                LCOV_TRACE_FILE,
                test_vector,
                next_result,
                coverage_goal,
            )

        logging.info(
            "Coverage requested without any valid execution. Returning empty test coverage."
        )
        return None


class IsolatingRunner(CoverageMeasuringExecutionRunner):
    def __init__(
        self,
        machine_model,
        timelimit_per_run,
        goal,
        harness_file_target="harness.c",
        compile_target="a.out",
        memlimit=None,
        cores=None,
        use_runexec=True,
    ):
        super().__init__(
            machine_model,
            timelimit_per_run if not use_runexec else None,
            goal,
            harness_file_target,
            compile_target,
        )
        self._memlimit = memlimit
        self._timelimit = timelimit_per_run
        self._cpu_cores = cores
        self._use_runexec = use_runexec
        tempdir = tempfile.mkdtemp(prefix="testcov-")
        self._output_log = os.path.join(tempdir, "output.log")
        self._output_dir = "."  # necessary to be cwd for coverage computation to work

    def _get_execute_cmd(self, executable):
        # At the moment, this does not consider executables provided through PATH
        if self._use_runexec:
            # always try to limit processes
            resource_options = ["--set-cgroup-value", "pids.max=5000"]
            if self._memlimit:
                resource_options += ["--memlimit", self._memlimit]
            if self._timelimit:
                resource_options += ["--timelimit", str(self._timelimit)]
            if self._cpu_cores:
                resource_options += ["--cores", str(self._cpu_cores)]
            cmd = [
                "runexec",
                "--container",
                "--input",
                "-",
                "--output",
                self._output_log,
            ] + resource_options
        else:
            cmd = ["containerexec"]
        return cmd + [
            "--overlay-dir",
            os.getcwd(),
            "--hidden-dir",
            "/sys/kernel/debug",
            "--result-files",
            "harness.gcda",
            "--output-dir",
            self._output_dir,
            "--",
            os.path.join(".", os.path.relpath(executable, start="./")),
        ]

    def run(self, program_file, test_vector: eu.TestVector) -> eu.TestResult:
        result = super().run(program_file, test_vector)
        if self._use_runexec:
            with open(self._output_log) as outp:
                if eu.found_err(outp.read()):
                    logging.debug("Error found for test %s", test_vector)
                    result.verdict = eu.COVERS
        if self._use_runexec:
            result.execution_info.cpu_time = self._get_cputime(result.execution_info)
            result.execution_info.wall_time = self._get_walltime(result.execution_info)
            result.execution_info.memory_used = self._get_memory(result.execution_info)
            result.execution_info.returncode = self._get_returncode(
                result.execution_info
            )
            result.execution_info.got_aborted = self._was_aborted(result.execution_info)
        return result

    @staticmethod
    def _get_cputime(execution_info) -> float:
        for line in reversed(execution_info.stdout.split("\n")):
            match = re.match(r"cputime=([0-9]+\.[0-9]+)s", line)
            if match:
                return float(match.group(1))
        return execution_info.cpu_time

    @staticmethod
    def _get_walltime(execution_info) -> float:
        for line in reversed(execution_info.stdout.split("\n")):
            match = re.match(r"walltime=([0-9]+\.[0-9]+)s", line)
            if match:
                return float(match.group(1))
        return execution_info.wall_time

    @staticmethod
    def _get_memory(execution_info) -> float:
        for line in reversed(execution_info.stdout.split("\n")):
            match = re.match("memory=([0-9]+)B", line)
            if match:
                return int(match.group(1))
        return execution_info.memory_used

    @staticmethod
    def _get_returncode(execution_info) -> float:
        for line in reversed(execution_info.stdout.split("\n")):
            match = re.match("returnvalue=((-)?[0-9]+)", line)
            if match:
                return int(match.group(1))
            match = re.match("exitsignal=([0-9]+)", line)
            if match:
                # runexec returns exitsignals as positive numbers.
                # Negate to be consistent with C return code, which uses
                # negative numbers to reference signals
                return -int(match.group(1))
            assert not re.match("exitsignal=(-[0-9]+)", line)
        return execution_info.returncode

    @staticmethod
    def _was_aborted(execution_info) -> float:
        for line in reversed(execution_info.stdout.split("\n")):
            if line.startswith("terminationreason=") or re.match("exitsignal=", line):
                return True
        return execution_info.got_aborted


class SuiteExecutor:
    """Provides methods to execute a full test suite in the XML format."""

    def __init__(
        self,
        goal,
        timelimit_per_run,
        harness_file_target="harness.c",
        compile_target="a.out",
        compute_sequence=False,
        reduce_tests=rs.BYORDER_REDUCTION,
        isolate_tests=True,
        compute_individuals=True,
        memlimit=None,
        cores=None,
        use_runexec=True,
        info_output=False,
    ):
        self._check_for_error = goal == eu.COVER_ERRORS
        self._goal = goal
        self._timelimit = timelimit_per_run

        self._harness_file_target = harness_file_target
        self._compile_target = compile_target
        self._compute_sequence = compute_sequence
        self._reduce_tests = reduce_tests
        self._isolate_tests = isolate_tests
        self._compute_individual_test_coverages = compute_individuals
        self._memlimit = memlimit
        self._cpu_cores = cores
        self._use_runexec = use_runexec
        assert (
            not self._use_runexec or self._isolate_tests
        ), "Conflicting arguments: Can't use runexec without isolating runs"

        self._info_target = sys.stderr if info_output else None

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
                self._goal,
                self._harness_file_target,
                self._compile_target,
                self._memlimit,
                self._cpu_cores,
                self._use_runexec,
            )
        else:
            executor = CoverageMeasuringExecutionRunner(
                machine_model,
                self._timelimit,
                self._goal,
                self._harness_file_target,
                self._compile_target,
            )

        try:
            metadata = mu.get_metadata(test_suite)
        except etree.ParseError as e:
            raise ExecutionError("Test-suite metadata not valid: {}".format(e.msg))
        self._check_metadata(metadata, machine_model)

        # this method call raises an ExecutionError if the given test suite is invalid
        test_vectors = self._get_described_vectors(test_suite)

        # old gcda, gcno or gcov files might exist
        _remove_coverages_files_in_working_directory()

        self._execute_tests(program_file, test_vectors, executor, result_target)

        return result_target

    @staticmethod
    def _check_metadata(metadata, machine_model) -> None:
        architecture = metadata[mu.ARCHITECTURE]
        if architecture is not None:
            if ("32" in architecture) != ("32" in machine_model):
                logging.warning(
                    "Architecture in metadata.xml different from expected: '%s' vs. '%s'",
                    architecture,
                    machine_model,
                )

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

            for xml_file in (
                l
                for l in zip_inp.namelist()
                if l.endswith(".xml") and not os.path.basename(l) == "metadata.xml"
            ):
                logging.debug("Considering %s", xml_file)
                with zip_inp.open(xml_file) as xml_inp:
                    xml_lines = xml_inp.readlines()
                    maybe_vector = convert_to_vector_if_testcase(xml_file, xml_lines)
                    if maybe_vector is not None:
                        logging.debug("File %s is valid testcase", xml_file)
                        yield maybe_vector
                    else:
                        logging.debug("File %s is no valid testcase", xml_file)

    def _record_coverage(
        self,
        result_target: eu.SuiteExecutionResult,
        next_result: eu.TestResult,
        program_file: str,
        tv: eu.TestVector,
    ):
        if next_result.coverage:
            current_coverage = next_result.coverage

            if self._compute_individual_test_coverages:
                # Since we delete the gcda file merging the new coverage with the old one is necessary
                result_target.coverage_tests.append(current_coverage)
                if result_target.coverage_total:
                    result_target.coverage_total = cov.TestCoverage.merge(
                        current_coverage, result_target.coverage_total
                    )
                else:
                    result_target.coverage_total = current_coverage
                _remove_harness_gcda_file()
                _remove_lcov_trace_file()
            else:
                # No merging necessary because we never delete the gcda file.
                # The gcda file always contains the coverage from all tests.
                result_target.coverage_total = current_coverage

            if self._compute_sequence:
                new_coverage = float(result_target.coverage_total.hits_percent)

                result_target.coverage_sequence.append(new_coverage)
        else:
            # Make sure that every test gets a coverage
            if self._compute_individual_test_coverages:
                result_target.coverage_tests.append(
                    cov.TestCoverage(_get_program_name(program_file), {tv: next_result})
                )
            if self._compute_sequence:
                if result_target.coverage_sequence:
                    result_target.coverage_sequence.append(
                        result_target.coverage_sequence[-1]
                    )
                else:
                    result_target.coverage_sequence = [0]
        if result_target.coverage_total:
            logging.debug(
                "Accumulated coverage: %s%%", result_target.coverage_total.hits_percent
            )

    def _execute_tests(self, program_file, test_vectors, executor, result_target):
        """Executes all test vectors on the given program using the given executor
        and puts the results into result_target."""

        try:
            print("⏳ Executing tests.", file=self._info_target, end="", flush=True)
            for tv in test_vectors:
                result_target.tests.append(tv)
                next_result = executor.run(program_file, tv)
                result_target.results.append(next_result)

                self._record_coverage(result_target, next_result, program_file, tv)

                if next_result == eu.COVERS and self._check_for_error:
                    result_target.successful_tests.append(tv)
                    logging.info("Stopping. Error found for test %s", tv)
                    break
                print(".", file=self._info_target, end="", flush=True)
        finally:
            print("\n✔️  Done!", file=self._info_target, flush=True)  # print newline
            if result_target.coverage_tests and result_target.coverage_total:
                result_target.reduced_coverage_tests = rs.execute(
                    self._reduce_tests, result_target.coverage_tests[:]
                )
                if not self._check_for_error:
                    for tc in result_target.reduced_coverage_tests:
                        result_target.successful_tests.extend(tc.test_vectors)


def _remove_lcov_trace_file():
    if os.path.exists(LCOV_TRACE_FILE):
        os.remove(LCOV_TRACE_FILE)


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
    except etree.ParseError as e:
        logging.warning("Couldn't parse file %s: %s", test_xml_file, e.msg)
        xml = None

    if xml is None:
        return None

    # test name is file name without suffix '.xml'
    test_name = os.path.basename(test_xml_file)[:-4]
    vector = eu.TestVector(test_name, test_xml_file)
    for input_tag in xml:
        vector.add(input_tag.text.strip())
    return vector


def _get_program_name(program_file: str) -> str:
    return os.path.basename(program_file)
