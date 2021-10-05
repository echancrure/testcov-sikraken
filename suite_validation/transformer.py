# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# Copyright (C) 2018 - 2020  Dirk Beyer
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"""
Reducer of C program. Create a residual program from an input program and a set of relevant labels.
"""

# pylint: disable=C0103
# to disable snake_case error

import re
from typing import List, Sequence
import pycparser
from pycparser import c_generator

from suite_validation import label_adding as la
from suite_validation import execution_utils as eu
from suite_validation import _logger as logging


def _preprocess(input_program: str, machine_model: str) -> str:
    """
    Pre-processes the given program.

    :param input_program: program to pre-process
    :param machine_model: machine-model to use for pre-processing
    :return: name of new, pre-processed program file
    """
    preprocessed_file = input_program + ".i"
    cmd = [eu.COMPILER, machine_model, "-E", input_program, "-o", preprocessed_file]
    eu.execute(cmd, quiet=True)

    return preprocessed_file


def _get_label_adder(coverage_goal):
    if isinstance(coverage_goal, eu.CoverFunc):
        return la.TargetFuncLabelAdder(coverage_goal.target_method)
    if eu.uses_branch_coverage(coverage_goal):
        return la.LabelAdder()
    return None


def instrument_program(
    input_program: str, machine_model: str, output_program: str, coverage_goal
) -> List[int]:
    if not input_program.endswith(
        ".i"
    ):  # very simple heuristic to decide whether program is preprocessed
        input_program = _preprocess(input_program, machine_model)
    c_code = _get_content(input_program)

    logging.debug("Adding program labels")
    adder = _get_label_adder(coverage_goal)

    if adder:
        ast = _parse(c_code)
        adder.visit(ast)
        c_code = _to_c(ast)

    lines = c_code.split("\n")
    lines = add_gcov_flushes(lines)
    # If we keep preprocessor comments, gcov and lcov may use these to deduce the original file name.
    # While this is nice in general, we already manage the original file name separately, for all goal types.
    # So we remove the comments here to avoid the additional special case where the file name
    # in the gcov file does not match the file name of the transformed file used for compilation.
    lines = remove_preprocessor_comments(lines)
    c_code = "\n".join(lines)

    branch_label_line_numbers = collect_branch_label_line_numbers(c_code)

    with open(output_program, "w", encoding="UTF-8") as outp:
        outp.write(c_code)
        logging.debug("Wrote transformed C program to %s", output_program)

    return branch_label_line_numbers


def collect_branch_label_line_numbers(c_code: str) -> List[int]:
    line_numbers = []
    line_number = 1
    for line in c_code.splitlines():
        if la.GOTO_PREFIX in line:
            line_numbers.append(line_number)
        line_number += 1
    return line_numbers


def _get_content(program: str) -> str:
    with open(program, encoding="UTF-8") as inp:
        return inp.read()


def _get_parser() -> pycparser.c_parser.CParser:
    # del args  # unused
    return pycparser.c_parser.CParser()


def _parse(content_original: str) -> pycparser.c_ast.FileAST:
    logging.debug("Parsing program")
    try:
        content = _rewrite_cproblems(content_original)

        parser = _get_parser()
        return parser.parse(content)
    except pycparser.plyparser.ParseError as e:
        print(content)
        raise eu.ParseError("Parsing failed") from e
    finally:
        logging.debug("Finished parsing program")


def _to_c(ast: pycparser.c_ast.Node) -> str:
    generator = CondensingCGenerator()
    return generator.visit(ast)


def _rewrite_cproblems(content: str) -> str:
    need_struct_body = False
    skip_asm = False
    in_attribute = False
    prepared_content = []
    for line in [c + "\n" for c in content.split("\n")]:
        line = re.sub(r"/\*.*?\*/", "", line)
        # remove __attribute__
        line = re.sub(r"__attribute__\s*\(\(\s*[a-z_, ]+\s*\)\)\s*", "", line)
        # line = re.sub(r'__attribute__\s*\(\(\s*[a-z_, ]+\s*\(\s*[a-zA-Z0-9_, "\.]+\s*\)\s*\)\)\s*', '', line)
        # line = re.sub(r'__attribute__\s*\(\(\s*[a-z_, ]+\s*\(\s*sizeof\s*\([a-z ]+\)\s*\)\s*\)\)\s*', '', line)
        # line = re.sub(r'__attribute__\s*\(\(\s*[a-z_, ]+\s*\(\s*\([0-9]+\)\s*<<\s*\([0-9]+\)\s*\)\s*\)\)\s*', '', line)
        line = re.sub(r"__attribute__\s*\(\(.*\)\)\s*", "", line)
        if re.search(r"__attribute__\s*\(\(", line):
            line = re.sub(r"__attribute__\s*\(\(.*", "", line)
            in_attribute = True
        elif in_attribute:
            line = re.sub(r".*\)\)", "", line)
            in_attribute = False
        # rewrite some GCC extensions
        line = re.sub(r"__extension__", "", line)
        line = re.sub(r"__PRETTY_FUNCTION__", '"func_name"', line)
        line = re.sub(r"__restrict", "", line)
        line = re.sub(r"__restrict__", "", line)
        line = re.sub(r"__inline__", "", line)
        line = re.sub(r"__inline", "", line)
        line = re.sub(r"__const", "const", line)
        line = re.sub(r"__signed__", "signed", line)
        line = re.sub(r"__builtin_va_list", "int", line)
        # a hack for some C-standards violating code in LDV benchmarks
        if need_struct_body and re.match(r"^\s*}\s*;\s*$", line):
            line = "int __dummy; " + line
            need_struct_body = False
        elif need_struct_body:
            need_struct_body = re.match(r"^\s*$", line) is not None
        elif re.match(r"^\s*struct\s+[a-zA-Z0-9_]+\s*{\s*$", line):
            need_struct_body = True
        # remove inline asm
        line = re.sub(
            r'(^|\s)\s*__asm__(\s+volatile)?\s*\("([^"]|\\")*"[^;]*\)\s*;$', ";", line
        )
        if re.match(r'^\s*__asm__(\s+volatile)?\s*\("([^"]|\\")*"[^;]*$', line):
            skip_asm = True
        elif skip_asm and re.search(r"\)\s*;\s*$", line):
            skip_asm = False
            line = "\n"
        if skip_asm or re.match(
            r'^\s*__asm__(\s+volatile)?\s*\("([^"]|\\")*"[^;]*\)\s*;\s*$', line
        ):
            line = "\n"
        # remove asm renaming
        line = re.sub(r'__asm__\s*\(""\s+"[a-zA-Z0-9_]+"\)', "", line)
        prepared_content.append(line)

    prepared_content = replace_reach_error(prepared_content)

    prepared_content = "".join(prepared_content)

    def replacer(match):
        s = match.group(0)
        if s.startswith("/"):
            return ""
        return s

    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE,
    )
    return re.sub(pattern, replacer, prepared_content)


def replace_reach_error(content: Sequence[str]) -> Sequence[str]:
    new_content = []
    in_reach_error = False
    contains_reach_error = re.compile(r".*void reach_error.*")
    single_line_reach_error = re.compile(r"^\s*void reach_error\s*\(.*\)\s*{.*}\s*$")
    multiline_reach_error = re.compile(r"^\s*void reach_error.*{\s*$")
    idx = None
    for idx, line in enumerate(content):
        if in_reach_error:
            if re.match(r"^\s*}\s*$", line):
                break
        elif contains_reach_error.match(line):
            new_content.append("extern void exit (int __status);\n")
            new_content.append("void reach_error() { exit(1); }\n")
            if single_line_reach_error.match(line):
                break
            if multiline_reach_error.match(line):
                in_reach_error = True
            else:
                logging.warning("Unmatched occurence of reach_error: %s", line)
        else:
            new_content.append(line)

    if idx is not None:
        new_content += content[(idx + 1) :]

    return new_content


def add_gcov_flushes(content: Sequence[str]) -> Sequence[str]:
    new_content = ["#ifdef GCOV", "extern void __gcov_dump(void);", "#endif"]
    for line in content:
        if " abort();" in line:
            line = re.sub(
                r"(\s+)abort\(\);",
                r"\1{\n\1#ifdef GCOV\n\1__gcov_dump();\n\1#endif\n\1abort();\n\1}",
                line,
            )
        if " __assert_fail" in line and not re.search(r"void.*__assert_fail", line):
            line = re.sub(
                r"(\s+)__assert_fail",
                r"\1#ifdef GCOV\n\1__gcov_dump();\n\1#endif\n\1__assert_fail",
                line,
            )

        new_content.append(line)
    return new_content


def remove_preprocessor_comments(content: Sequence[str]) -> Sequence[str]:
    return [line for line in content if not line.strip().startswith("# ")]


class CondensingCGenerator(c_generator.CGenerator):
    def visit_Label(self, n):
        if isinstance(n.stmt, pycparser.c_ast.EmptyStatement):
            separator = ""
        else:
            separator = "\n"
        return n.name + ":" + separator + self._generate_stmt(n.stmt).strip()

    def visit_If(self, n):
        s = "if ("
        if n.cond:
            s += self.visit(n.cond)
        s += ") "
        s += self._generate_stmt(n.iftrue, add_indent=True)
        if n.iffalse:
            s += self._make_indent() + "else"
            s += self._generate_stmt(n.iffalse, add_indent=True)
        return s

    def visit_While(self, n):
        s = "while ("
        if n.cond:
            s += self.visit(n.cond)
        s += ") "
        s += self._generate_stmt(n.stmt, add_indent=True)
        return s

    def visit_DoWhile(self, n):
        s = "do "
        s += self._generate_stmt(n.stmt, add_indent=True)
        s += self._make_indent() + "while ("
        if n.cond:
            s += self.visit(n.cond)
        s += ");"
        return s

    def visit_For(self, n):
        s = "for ("
        if n.init:
            s += self.visit(n.init)
        s += ";"
        if n.cond:
            s += " " + self.visit(n.cond)
        s += ";"
        if n.next:
            s += " " + self.visit(n.next)
        s += ") "
        s += self._generate_stmt(n.stmt, add_indent=True)
        return s
