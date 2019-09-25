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
import logging
import subprocess
from enum import Enum
from typing import List

ERROR_STRING = "Error found."

COVER_LINES = "COVER( init(main()), FQL(COVER EDGES(@BASICBLOCKENTRY)) )"
COVER_BRANCHES = "COVER( init(main()), FQL(COVER EDGES(@DECISIONEDGE)) )"
COVER_CONDITIONS = "COVER( init(main()), FQL(COVER EDGES(@CONDITIONEDGE)) )"
COVER_ERRORS = "COVER( init(main()), FQL(COVER EDGES(@CALL(__VERIFIER_error))) )"

COVERAGE_GOALS = {
    "@DECISIONEDGE": COVER_BRANCHES,
    "@CONDITIONEDGE": COVER_CONDITIONS,
    "@BASICBLOCKENTRY": COVER_LINES,
    "@CALL(__VERIFIER_error)": COVER_ERRORS,
}

MACHINE_MODEL_32 = "-m32"
MACHINE_MODEL_64 = "-m64"

EXTERNAL_DECLARATIONS = [
    ("_IO_FILE", "struct _IO_FILE;", "#include<stdio.h>;"),
    ("FILE", "typedef struct _IO_FILE FILE;", "#include<stdio.h>;"),
    ("stdin", "extern struct _IO_FILE *stdin;", "#include<stdio.h>;"),
    ("stderr", "extern struct _IO_FILE *stderr;", "#include<stdio.h>;"),
    ("size_t", "typedef long unsigned int size_t;", "#include<stddef.h>;"),
    (
        "abort",
        "extern void abort (void) __attribute__ ((__nothrow__ , __leaf__))"
        + " __attribute__ ((__noreturn__));",
        "#include<stdlib.h>;",
    ),
    (
        "exit",
        "extern void exit (int __status) __attribute__ ((__nothrow__ , __leaf__))"
        + " __attribute__ ((__noreturn__));",
        "#include<stdlib.h>;",
    ),
    (
        "fgets",
        "extern char *fgets (char *__restrict __s, int __n, FILE *__restrict __stream);",
        "#include<stdio.h>;",
    ),
    (
        "sscanf",
        "extern int sscanf (const char *__restrict __s, const char *__restrict __format, ...)"
        + " __attribute__ ((__nothrow__ , __leaf__));",
        "#include<stdio.h>;",
    ),
    (
        "strlen",
        " extern size_t strlen (const char *__s __attribute__ ((__nothrow__ , __leaf__))"
        + " __attribute__ ((__pure__)) __attribute__ ((__nonnull__ (1))));",
        "#include<string.h>;",
    ),
    (
        "fprintf",
        "extern int fprintf (FILE *__restrict __stream, const char *__restrict __format, ...);",
        "#include<stdio.h>;",
    ),
    (
        "malloc",
        " extern void *malloc (size_t __size __attribute__ ((__nothrow__ , __leaf__))"
        + " __attribute__ ((__malloc__)));",
        "#include<stdlib.h>;",
    ),
    (
        "memcpy",
        " extern void *memcpy (void *__restrict __dest, const void *__restrict __src, size_t __n)"
        + " __attribute__ ((__nothrow__ , __leaf__)) __attribute__ ((__nonnull__ (1, 2)));",
        "#include<stdlib.h>;",
    ),
    (
        "strcpy",
        " extern char *strcpy (char *__restrict __dest, const char *__restrict __src)"
        + " __attribute__ ((__nothrow__ , __leaf__)) __attribute__ ((__nonnull__ (1, 2)));",
        "#include<string.h>;",
    ),
    (
        "strcat",
        " extern char *strcat (char *__restrict __dest, const char *__restrict __src)"
        + " __attribute__ ((__nothrow__ , __leaf__)) __attribute__ ((__nonnull__ (1, 2)));",
        "#include<string.h>;",
    ),
]


class TestVector:
    """Test vector.

    Consists of a unique name, the original file that
    describes the test vector,
    and the vector as a sequence of test inputs.
    Each test input is a dictionary and consists
    of a 'value' and a 'name'.
    """

    def __init__(self, name, origin_file):
        self.name = name
        self.origin = origin_file
        self._vector = list()

    def add(self, value, method=None):
        self._vector.append({"value": value, "name": method})

    @property
    def vector(self):
        """The sequence of test inputs of this test vector.

        Each element of this sequence is a dict
        and consists of two entries: 'value' and 'name'.
        The 'value' entry describes the input value, as it should be given
        to the program as input.
        The 'name' entry describes the program input method
        through which the value is retrieved. The value of this entry may be None.
        """
        return self._vector

    def __len__(self):
        return len(self.vector)

    def __str__(self):
        return self.origin + " " + str(self.vector)


class TestResult(Enum):
    COVERS = "false"
    UNKNOWN = "unknown"
    ERROR = "error"
    ABORTED = "abort"


class SuiteExecutionResult:
    """Results of a full test suite execution."""

    def __init__(self):
        self.results: List[ExecutionResult] = list()
        self.coverage_total = None
        self.successful_tests = list()
        self.coverage_sequence: List[float] = list()
        self.coverage_tests = list()
        self.reduced_coverage_tests = list()
        self.tests = list()


class ExecutionResult:
    """Results of a subprocess execution."""

    def __init__(self, returncode, stdout, stderr, got_aborted):
        self._returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._got_aborted = got_aborted

    @property
    def returncode(self):
        return self._returncode

    @property
    def stdout(self):
        return self._stdout

    @property
    def stderr(self):
        return self._stderr

    @property
    def got_aborted(self):
        return self._got_aborted


def execute(command, quiet=False, input_str=None, timelimit=None):
    def shut_down(process):
        process.kill()
        return process.wait()

    log_cmd = logging.debug if quiet else logging.info
    log_cmd(" ".join(command))

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if input_str else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=False,
    )

    output = None
    err_output = None
    try:
        if input_str and not isinstance(input_str, bytes):
            input_str = input_str.encode()
        output, err_output = process.communicate(
            input=input_str, timeout=timelimit if timelimit else None
        )
        returncode = process.poll()
        got_aborted = False
    except subprocess.TimeoutExpired:
        logging.debug("Timeout of %ss expired. Killing process.", timelimit)
        returncode = shut_down(process)
        got_aborted = True
    # We decode output, but we can't decode error output, since it may contain undecodable bytes.
    output = output.decode() if output else ""

    if output:
        logging.debug("Output of execution:\n%s", output)
    if err_output:
        logging.debug("Error output of execution:\n%s", err_output.decode())

    return ExecutionResult(returncode, output, err_output, got_aborted)


def found_err(run_result):
    return run_result.stderr and ERROR_STRING.encode() in run_result.stderr
