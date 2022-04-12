# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# Copyright (C) 2018 - 2020  Dirk Beyer
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Module for creation and execution of test harnesses from test-format XML files."""

import re
import os
import sys
import tempfile
import glob
from typing import Optional, Iterable
import zipfile

import xml.etree.ElementTree as etree

from suite_validation import _gcov_coverage
from suite_validation import execution_utils as eu
from suite_validation import coverage as cov
from suite_validation import metadata_utils as mu
from suite_validation import transformer as tr
from suite_validation import _logger as logging

HARNESS_FILE_NAME = "harness.c"


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
        with open(program_file, encoding="UTF-8") as inp:
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
                        r"\s+\*?" + name + r"([^a-zA-Z0-9_]+|$)", line
                    ):
                        logging.debug(
                            "Removing %s from explicit declaration. Exists in line: %s",
                            name,
                            line.strip(),
                        )
                        to_declare.remove(name)
        if preprocessed:
            return "\n".join(
                l[1] for l in eu.EXTERNAL_DECLARATIONS if l[0] in to_declare
            )
        to_declare = set(l[2] for l in eu.EXTERNAL_DECLARATIONS)
        with open(program_file, encoding="UTF-8") as inp:
            for line in inp.readlines():
                for _, _, decl in eu.EXTERNAL_DECLARATIONS:
                    if line.startswith(decl):
                        to_declare.remove(decl)
        return "\n".join(to_declare)

    @staticmethod
    def _get_harness_skeleton():
        harness_skeleton = os.path.join(os.path.dirname(__file__), HARNESS_FILE_NAME)
        with open(harness_skeleton, encoding="UTF-8") as inp:
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
            f"-std={c_version}",
            mm_arg,
            "-Wno-attributes",
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
                f"Compilation failed for harness {harness_file}:\n"
                + "\n".join(
                    "    " + l for l in compile_result.stderr.decode().split("\n")
                )
            )

        return output_file

    def get_executable_harness(self, program_file):
        if not self.harness:
            self.harness = self._create_executable_harness(program_file)
        return self.harness

    def _create_executable_harness(self, program_file):
        harness_file = self._harness_file_target
        harness_content = self.harness_generator.convert(program_file)

        with open(harness_file, "w+", encoding="UTF-8") as outp:
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
        if not os.path.isabs(executable):
            executable = "./" + executable
        return [executable]

    @staticmethod
    def _get_input_vector(test_vector, escape_newline=False):
        input_vector = ""
        if escape_newline:
            newline = "\\n"
        else:
            newline = "\n"
        input_vector = newline.join([i["value"] for i in test_vector.vector])

        def get_log_repr(test_vec):
            input_values = [i["value"] for i in test_vec.vector]
            number_inputs = len(input_values)
            threshold = 12  # random number for snipping the output
            if number_inputs > threshold:
                number_snipped = number_inputs - threshold
                head_stop = int(threshold / 2) + 1  # int() always rounds down
                tail_start = threshold - head_stop
                input_values = (
                    input_values[:head_stop]
                    + [f"..(snip {number_snipped} values).."]
                    + input_values[-tail_start:]
                )

            return ", ".join(input_values)

        logging.debug("Input for %s: %s", test_vector.name, get_log_repr(test_vector))
        return input_vector


class GcovCoverageMeasurer(ExecutionRunner):
    TEMPORARY_FILE_SUFFIXES = (".gcda", ".gcno", ".gcov")

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
        self.harness_file = None

    def _get_compile_cmd(
        self, program_file, harness_file, output_file, c_version="gnu11"
    ):
        cmd = super()._get_compile_cmd(
            program_file, harness_file, output_file, c_version
        )
        cmd += ["--coverage", "-DGCOV"]

        return cmd

    @staticmethod
    def _get_temporary_data_files(harness_file):
        harness_name = ".".join(harness_file.split("/")[-1].split(".")[:-1])
        return [
            harness_name + suffix
            for suffix in LcovCoverageMeasurer.TEMPORARY_FILE_SUFFIXES
        ]

    def _remove_existing_data_files(self, harness_file):
        gcov_files = self._get_temporary_data_files(harness_file)
        for f in gcov_files:
            if os.path.exists(f):
                logging.info("Removing existing file %s", f)
                os.remove(f)

    def _compute_coverage_with_gcov(self, program_name, data_file) -> Optional[float]:
        try:
            _, execution_result = _gcov_coverage.create_gcov_file(
                program_name, data_file
            )
        except FileNotFoundError:
            return None
        return _gcov_coverage.parse_gcov_output(
            program_name, execution_result.stdout, self._goal
        )

    def run(self, program_file, test_vector: eu.TestVector) -> eu.TestResult:
        result = super().run(program_file, test_vector)
        if eu.is_failed_run(result):
            return result

        program_name = _get_program_name(program_file)
        try:
            data_file = self._get_data_file()
            result.coverage = self._compute_coverage_with_gcov(program_name, data_file)
        except (_gcov_coverage.GcovError, FileNotFoundError) as e:
            logging.info("GCov coverage could not be computed: %s", e)
            result.coverage = None
        return result

    def _get_data_file(self):
        # According to the gcc documentation,
        # "The .gcno files are placed in the same directory as the object file" and
        # "the .gcda files are also stored in the same directory as the object file".
        # -- https://gcc.gnu.org/onlinedocs/gcc/Gcov-Data-Files.html
        #
        # So we look in the directory of our compile target first.
        # Unfortunately, older versions of GCC (before GCC-11, and even some versions of GCC 11, e.g. on Ubuntu)
        # place the .gcda file in the current working directory.
        # So as a fallback, we also look there.

        def _get_gcda(directory):
            candidate = list(glob.glob(directory + "/*.gcda"))
            if len(candidate) == 1:
                gcda_file = candidate[0]
                logging.debug("Using .gcda file: %s", gcda_file)
                return gcda_file
            if len(candidate) > 1:
                raise ValueError(
                    f"Multiple GCOV data files found in directory: {candidate}"
                )
            raise FileNotFoundError(
                f"No GCOV data file with known name found in directory: {os.listdir(directory)}"
            )

        build_directory = os.path.dirname(self._compile_target)
        if build_directory:
            try:
                return _get_gcda(build_directory)
            except FileNotFoundError as e:
                logging.debug(e)

            logging.debug("Falling back to look in current directory for GCDA file.")
        return _get_gcda(".")


class LcovCoverageMeasurer(GcovCoverageMeasurer):
    TEMPORARY_FILE_SUFFIXES = (".gcda", ".gcno", ".gcov", ".info")

    def __init__(
        self,
        machine_model,
        timelimit_per_run,
        goal,
        harness_file_target="harness.c",
        compile_target="a.out",
        compiler="gcc",
        output_dir="output",
        info_files_dir="info_files",
        individual_runs=True,
    ):
        super().__init__(
            machine_model,
            timelimit_per_run,
            goal,
            harness_file_target,
            compile_target,
            compiler,
        )
        self._goal = goal
        self._output_dir = output_dir
        self._output_dir_info = os.path.join(output_dir, info_files_dir)
        self.harness_file = None
        self._individual_runs = individual_runs
        self._instrumented_programs_cache = {}
        os.makedirs(self._output_dir_info, exist_ok=True)

    @staticmethod
    def _get_info_file(harness_file):
        harness_name = ".".join(harness_file.split("/")[-1].split(".")[:-1])
        return harness_name + ".info"

    def _remove_existing_data_files(self, harness_file):
        super()._remove_existing_data_files(harness_file)
        info_file = self._get_info_file(harness_file)
        os.remove(info_file)

    def _get_instrumented_file_name(self, original_file) -> str:
        filename = os.path.basename(original_file)
        return os.path.join(self._output_dir, "instrumented_" + filename)

    def _prepare_program(self, program_file):
        if eu.uses_line_coverage(self._goal):
            return (
                program_file,
                None,
            )  # no modifications possible without changing line count
        if program_file not in self._instrumented_programs_cache:
            prepared_program = self._get_instrumented_file_name(program_file)

            label_lines = tr.instrument_program(
                program_file, self.machine_model, prepared_program, self._goal
            )
            self._instrumented_programs_cache[program_file] = (
                prepared_program,
                label_lines,
            )

        # Beware! Overwrites program_file parameter
        program_file, label_line_numbers = self._instrumented_programs_cache[
            program_file
        ]
        if not (
            isinstance(self._goal, eu.CoverFunc) or eu.uses_branch_coverage(self._goal)
        ):
            label_line_numbers = None  # for condition coverage and line coverage we use existing measurements
        return program_file, label_line_numbers

    def run(self, program_file, test_vector: eu.TestVector) -> eu.TestResult:
        original_program = program_file
        program_file, label_line_numbers = self._prepare_program(program_file)

        result = super().run(program_file, test_vector)

        try:
            result.coverage = self._compute_coverage(
                program_file,
                test_vector,
                result,
                self._goal,
                label_line_numbers,
            )
        except FileNotFoundError as e:
            logging.warning("Could not compute coverage for last test run: %s", e)
            return result

        if result.coverage:
            # To hide the information that lcov measurement actually works on an instrumented program,
            # set the filename to the original program before returning the coverage
            result.coverage.filename = _get_program_name(original_program)

        if isinstance(self._goal, eu.CoverFunc) and self._hit_target_function(
            result.coverage
        ):
            result.verdict = eu.COVERS
        return result

    @staticmethod
    def _hit_target_function(coverage: cov.TestCoverage):
        return coverage and coverage.count_total > 0 and coverage.hits > 0

    def _compute_coverage(
        self,
        program_file,
        test_vector,
        next_result,
        coverage_goal,
        branch_label_line_numbers=None,
    ) -> Optional[cov.TestCoverage]:
        program_name = _get_program_name(program_file)
        data_file = self._get_data_file()
        try:
            coverage = cov.compute_test_coverage(
                program_name,
                data_file,
                test_vector,
                next_result,
                coverage_goal,
                branch_label_line_numbers,
                output_dir=self._output_dir_info,
            )
            return coverage
        except FileNotFoundError as e:
            logging.info(
                "Coverage computation failed. No coverage recorded for run %s. Reason is a missing file: %s",
                test_vector,
                e,
            )
            return None
        finally:
            if self._individual_runs:
                self._remove_data_file(data_file)

    @staticmethod
    def _remove_data_file(data_file):
        try:
            os.remove(data_file)
        except FileNotFoundError:
            pass


class IsolatingRunner(LcovCoverageMeasurer):
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
        output_dir="output",
        info_files_dir="info_files",
        individual_runs=True,
    ):
        super().__init__(
            machine_model,
            timelimit_per_run if not use_runexec else None,
            goal,
            harness_file_target,
            compile_target,
            output_dir=output_dir,
            info_files_dir=info_files_dir,
            individual_runs=individual_runs,
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
        isolation_cmd = cmd + [
            "--read-only-dir",
            "/",
            "--overlay-dir",
            os.getcwd(),
            "--hidden-dir",
            "/home",
            "--hidden-dir",
            "/sys/kernel/debug",
            "--result-files",
            "harness.gcda",
            "--output-dir",
            self._output_dir,
            "--",
        ]

        return isolation_cmd + super()._get_execute_cmd(executable)

    def run(self, program_file, test_vector: eu.TestVector) -> eu.TestResult:
        result = super().run(program_file, test_vector)
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
        isolate_tests=True,
        compute_individuals=True,
        memlimit=None,
        cores=None,
        use_runexec=True,
        use_gcov_only=False,
        info_output=False,
        stop_on_success=False,
        output_dir="output",
    ):
        self._check_for_error = isinstance(goal, eu.CoverFunc)
        self._stop_on_success = stop_on_success
        self._goal = goal
        self._timelimit = timelimit_per_run

        self._harness_file_target = harness_file_target
        self._compile_target = compile_target
        self._isolate_tests = isolate_tests and not use_gcov_only
        self._compute_individual_test_coverages = (
            compute_individuals and not use_gcov_only
        )
        self._memlimit = memlimit
        self._cpu_cores = cores
        self._use_runexec = use_runexec and not use_gcov_only
        self._use_gcov_only = use_gcov_only
        assert (
            not self._use_gcov_only or not self._isolate_tests
        ), "Conflicting arguments: Can't use gcov-only measurement with test isolation"
        assert (
            not self._use_runexec or self._isolate_tests
        ), "Conflicting arguments: Can't use runexec without isolating runs"

        self._info_target = sys.stderr if info_output else None

        self._output_dir = output_dir

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
        :param machine_model: machine model to use. Should be
            either execution_utils.MACHINE_MODEL_32 or execution_utils.MACHINE_MODEL_64
        :param Optional[eu.SuiteExecutionResult] result_target: if set, execution results will be
            written into the given object. This allows easy access to intermediate results.

        :raises ExecutionError: if given test suite is invalid.
        """

        if result_target is None:
            # add dummy result target that is never used by the caller
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
                output_dir=self._output_dir,
                individual_runs=self._compute_individual_test_coverages,
            )
        elif self._use_gcov_only:
            executor = GcovCoverageMeasurer(
                machine_model,
                self._timelimit,
                self._goal,
                self._harness_file_target,
                self._compile_target,
            )

        else:
            executor = LcovCoverageMeasurer(
                machine_model,
                self._timelimit,
                self._goal,
                self._harness_file_target,
                self._compile_target,
                output_dir=self._output_dir,
                individual_runs=self._compute_individual_test_coverages,
            )

        try:
            metadata = mu.get_metadata(test_suite)
        except etree.ParseError as e:
            raise ExecutionError("Test-suite metadata not valid") from e
        self._check_metadata(metadata, machine_model)

        # this method call raises an ExecutionError if the given test suite is invalid
        test_vectors = list(self._get_described_vectors(test_suite))
        logging.debug("Tests in suite: %s", len(test_vectors))
        result_target.all_tests = test_vectors
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
    def _get_described_vectors(test_suite) -> Iterable[eu.TestVector]:
        """Return a generator that produces the test vectors described by the given test suite.

        :raises ExecutionError: if given test suite is invalid.
        """
        logging.debug("Looking for tests in %s", test_suite)
        with zipfile.ZipFile(test_suite) as zip_inp:
            if not any(
                os.path.basename(f) == mu.METADATA_XML_NAME for f in zip_inp.namelist()
            ):
                raise ExecutionError(f"No {mu.METADATA_XML_NAME} in {test_suite}")

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

    @staticmethod
    def _merge_coverages(coverage1, coverage2):
        if coverage1 is not None and coverage2 is not None:
            return coverage1 + coverage2
        if coverage1 is not None:
            return coverage1
        if coverage2 is not None:
            return coverage2
        return None

    def _record_coverage(
        self,
        result_target: eu.SuiteExecutionResult,
        next_result: eu.TestResult,
        program_file: str,
        tv: eu.TestVector,
    ):
        if next_result.coverage:
            current_coverage = next_result.coverage
        else:
            current_coverage = cov.TestCoverage(
                _get_program_name(program_file), {tv: next_result}
            )

        if self._compute_individual_test_coverages:
            result_target.coverage_tests.append(current_coverage)
            result_target.coverage_total = self._merge_coverages(
                result_target.coverage_total, current_coverage
            )
        else:
            result_target.coverage_total = current_coverage

        try:
            accumulated_coverage_in_percent = float(
                result_target.coverage_total.hits_percent
            )
        except ValueError:
            pass
        else:
            logging.debug("Accumulated coverage: %s%%", accumulated_coverage_in_percent)
            if not result_target.coverage_sequence:
                result_target.coverage_sequence = []
            result_target.coverage_sequence.append(accumulated_coverage_in_percent)

    def _execute_tests(self, program_file, test_vectors, executor, result_target):
        """Executes all test vectors on the given program using the given executor
        and puts the results into result_target."""

        total_test_count = len(test_vectors)
        for tv in test_vectors:
            result_target.tests.append(tv)
            executed_test_count = len(result_target.tests)
            logging.print_progress(
                count=executed_test_count,
                total=total_test_count,
                target=self._info_target,
            )
            next_result = executor.run(program_file, tv)
            result_target.results.append(next_result)

            self._record_coverage(result_target, next_result, program_file, tv)

            if not self._check_for_error:
                # if we do not try to reach an error, every test is successful, by default
                result_target.successful_tests.append(tv)
            if self._check_for_error and next_result == eu.COVERS:
                result_target.successful_tests.append(tv)
                if self._stop_on_success:
                    logging.info("Stopping. Error found for test %s", tv)
                    break
            if (
                self._stop_on_success
                and float(result_target.coverage_total.hits_percent) >= 100
                and executed_test_count < total_test_count
            ):
                logging.info("Stopping. Achieved full coverage")
                break
        logging.print_done(target=self._info_target)


def _parse_xml_if_testcase(xml_lines):
    curr_content = []
    for line_number, line in enumerate(xml_lines):
        if line_number == 0 and not line.startswith(b"<?xml "):
            return None
        if line_number == 1 and not line.startswith(b"<!DOCTYPE testcase "):
            return None
        curr_content.append(line)
    return etree.fromstringlist(curr_content)


def convert_to_vector_if_testcase(test_xml_file, xml_lines) -> Optional[eu.TestVector]:
    """Return test vector represented by given test-case XML.

    :param str test_xml_file: Path to xml file to convert.
    :param List[str] xml_lines: content of test_xml_file as list of lines
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
