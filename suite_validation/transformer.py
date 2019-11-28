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
"""
Reducer of C program. Create a residual program from an input program and a set of relevant labels.
"""

# pylint: disable=C0103
# to disable snake_case error

from contextlib import contextmanager
import itertools
import logging
import re
import os
from typing import List, Dict, Tuple, Set, Iterable, Optional
import pycparser
from pycparser import c_generator

from suite_validation import label_adding as la

INSTRUMENTED_PREFIX = "instrumented_"


class ParseError(Exception):
    def __init__(self, msg=None, cause=None):
        super().__init__(msg, cause)
        self.msg = msg
        self.cause = cause


class CfgNode:
    counter = 0

    def __init__(self, ast_node: pycparser.c_ast.Node):
        self.preds: Set[CfgNode] = set()
        self._succs: Set[CfgNode] = set()
        self.asts = [ast_node]
        CfgNode.counter += 1
        self.id = CfgNode.counter

    @property
    def succs(self):
        return self._succs

    @succs.setter
    def succs(self, value):
        self._succs = value

    @property
    def all_succs(self):
        return list(self._succs)

    def __repr__(self):
        return "N" + str(self.id)

    def __str__(self):
        preds = [repr(self.preds)]
        succs = [repr(self.succs)]
        return "CfgNode({}, {}, {})".format(preds, self.asts, succs)


class CfgCall(CfgNode):
    def __init__(self, ast_node: pycparser.c_ast.Node):
        super().__init__(ast_node)
        self.summary_succ = None

    @property
    def all_succs(self):
        return list(self._succs) + [self.summary_succ]


def instrument_program(program: str) -> Tuple[str, List[int]]:
    content = _get_content(program)

    ast = _parse(content)
    logging.debug("Adding program labels")
    adder = la.LabelAdder()
    adder.visit(ast)

    c_code = _to_c(ast)

    branch_label_line_numbers = collect_branch_label_line_numbers(c_code)

    output_prog = os.path.join(
        os.getcwd(), INSTRUMENTED_PREFIX + os.path.basename(program)
    )
    with open(output_prog, "w") as outp:
        outp.write(c_code)
        logging.debug("Wrote transformed C program to %s", output_prog)

    return output_prog, branch_label_line_numbers


def collect_branch_label_line_numbers(c_code: str) -> List[int]:
    line_numbers = []
    line_number = 1
    for line in c_code.splitlines():
        if la.LABEL_PREFIX in line:
            line_numbers.append(line_number)
        line_number += 1
    return line_numbers


def _reduce_program(
    ast: pycparser.c_ast.FileAST,
    all_labels: Iterable[str],
    relevant_labels: Iterable[str],
    args,
) -> None:
    irrelevant_labels = _get_irrelevant(ast, all_labels, relevant_labels, args)
    logging.debug("Irrelevant labels: %s", len(irrelevant_labels))
    _add_aborts(ast, irrelevant_labels, args)


def _get_irrelevant(
    ast: pycparser.c_ast.FileAST,
    all_labels: Iterable[str],
    relevant_labels: Iterable[str],
    args,
) -> Set[str]:
    logging.debug("Building CFG")
    cfg = _build_cfg(ast, args)
    logging.debug("Finished building CFG")
    logging.debug("Computing reachable nodes")
    reaching: List[CfgNode] = list(_get_nodes_reaching(cfg, relevant_labels))
    logging.debug("Finished computing reachable nodes (%s)", len(reaching))
    logging.debug("Computing reachable labels from nodes")
    labels_reaching = list(
        (
            l.name
            for n in reaching
            for l in n.asts
            if isinstance(l, pycparser.c_ast.Label)
        )
    )
    logging.debug(
        "Finished computing reachable labels from nodes (%s)", len(labels_reaching)
    )
    logging.debug("Reachable labels: %s", labels_reaching)
    logging.debug("All labels: %s", all_labels)
    return set(all_labels) - set(labels_reaching)


def _get_nodes_reaching(cfg: CfgNode, labels: Iterable[str]) -> Iterable[CfgNode]:
    logging.debug("Computing target nodes")
    cfg_targets = list(_get_targets(cfg, labels))
    logging.debug("Finished computing target nodes (%s)", len(cfg_targets))
    waitlist: List[CfgNode] = list(cfg_targets)
    visited = set()
    while waitlist:
        next_node = waitlist.pop()
        if next_node in visited:
            continue
        visited.add(next_node)
        waitlist += next_node.preds
        yield next_node


def _get_targets(cfg: CfgNode, labels: Iterable[str]) -> Iterable[pycparser.c_ast.Node]:
    labels = set(labels)
    waitlist: List[CfgNode] = [cfg]
    del cfg  # don't use anymore
    visited: Set[CfgNode] = set()
    while waitlist:
        next_node = waitlist.pop()
        if next_node in visited:
            continue
        visited.add(next_node)
        waitlist += next_node.all_succs
        if any(
            isinstance(a, pycparser.c_ast.Label) and a.name in labels
            for a in next_node.asts
        ):
            yield next_node


def _build_cfg(
    ast: pycparser.c_ast.FileAST, args, entryfunction: str = "main"
) -> CfgNode:
    builder = _CfgBuilder(args)
    builder.visit(ast)
    if entryfunction not in builder.functions or not builder.functions[entryfunction]:
        raise ParseError(
            "Entry function {} not found in program under test".format(entryfunction)
        )

    start = builder.functions[entryfunction][0]
    assert start is not None
    if builder.globals[0] is not None:
        assert builder.globals[1] is not None

        assert not builder.globals[1].all_succs
        builder.globals[1].succs = {start}
        start.preds.add(builder.globals[1])
        start = builder.globals[0]

    if args.debug:
        dot_file = args.get_target("cfg.dot")
        logging.debug("Writing CFG to %s", dot_file)
        dot = _get_dot(start, args)
        with open(dot_file, "w") as outp:
            outp.writelines(dot)
        logging.debug("Finished writing CFG to %s", dot_file)
    return start


def _get_dot(cfg: CfgNode, args) -> Iterable[str]:
    dot = iter(("digraph CFG {\n"))
    dot = itertools.chain(dot, _get_dot_nodes(cfg, args))
    dot = itertools.chain(dot, _get_dot_edges(cfg, args))
    dot = itertools.chain(dot, iter(("}")))

    return dot


def _get_dot_edges(cfg: CfgNode, args) -> Iterable[str]:
    del args  # unused
    waitlist: List[CfgNode] = [cfg]
    del cfg  # don't use again
    visited: Set[CfgNode] = set()
    while waitlist:
        next_node = waitlist.pop()
        if next_node in visited:
            continue
        visited.add(next_node)
        waitlist += next_node.all_succs

        for succ in next_node.all_succs:
            yield "{} -> {}\n".format(next_node.id, succ.id)


def _get_dot_nodes(cfg: CfgNode, args) -> Iterable[str]:
    del args  # unused
    waitlist: List[CfgNode] = [cfg]
    del cfg  # don't use again
    visited: Set[CfgNode] = set()
    while waitlist:
        next_node = waitlist.pop()
        if next_node in visited:
            continue
        visited.add(next_node)
        waitlist += next_node.all_succs

        stmts = "\\n".join(
            ["N" + str(next_node.id)]
            + [
                a.name if isinstance(a, pycparser.c_ast.Label) else str(type(a))
                for a in next_node.asts
            ]
        )
        yield '{} [shape="rectangle" label="{}"]\n'.format(next_node.id, stmts)


def _get_content(program: str) -> str:
    with open(program) as inp:
        return inp.read()


def _add_aborts(ast: pycparser.c_ast.FileAST, labels: Iterable[str], args) -> None:
    logging.debug("Adding aborts")
    la.AbortAdder(labels, args).visit(ast)
    logging.debug("Finished adding aborts")


def _get_parser() -> pycparser.c_parser.CParser:
    # del args  # unused
    return pycparser.c_parser.CParser()


def _parse(content_original: str) -> pycparser.c_ast.FileAST:
    logging.debug("Parsing program")
    try:
        content = _rewrite_cproblems(content_original)

        parser = _get_parser()
        return parser.parse(content)
    finally:
        logging.debug("Finished parsing program")


def _to_c(ast: pycparser.c_ast.Node) -> str:
    generator = CondensingCGenerator()
    return generator.visit(ast)


def _rewrite_cproblems(content: str) -> str:
    need_struct_body = False
    skip_asm = False
    in_attribute = False
    prepared_content = ""
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
        prepared_content += line

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


StartAndEnd = Tuple[Optional[CfgNode], Optional[CfgNode]]


class _CfgBuilder(pycparser.c_ast.NodeVisitor):
    """Build a CFG from the visited AST, separately for each function"""

    def __init__(self, args):
        del args  # not used at the moment
        self.globals: StartAndEnd = (None, None)
        self.functions: Dict[str, StartAndEnd] = dict()
        self._pending_gotos: Dict[str, List[CfgNode]] = dict()
        self._pending_function_calls: Dict[str, List[StartAndEnd]] = dict()
        self._labels: Dict[str, Dict[str, CfgNode]] = dict()
        self._sideeffects: List[StartAndEnd] = list()

        # only write through '_loop' context!
        self._current_loops: List[StartAndEnd] = list()
        # only write through '_func' context!
        self._current_function = None

    @contextmanager
    def _loop(self, entry_node, exit_node):
        self._current_loops.append((entry_node, exit_node))
        yield
        assert self._current_loops[-1] == (entry_node, exit_node)
        self._current_loops.pop()

    @contextmanager
    def _func(self, function_name):
        self._current_function = function_name
        yield
        self._current_function = None

    def visit_FuncDef(self, node):
        function_name = node.decl.name
        assert function_name not in self.functions
        logging.debug("Building CFG for definition of function %s", function_name)

        entry_node = CfgNode(node)
        exit_node = CfgNode(node)
        self.functions[function_name] = (entry_node, exit_node)

        with self._func(function_name):
            body_start, body_end = self.visit(node.body)
        assert body_start is not None

        entry_node.succs = {body_start}
        body_start.preds.add(entry_node)

        if body_end:  # path without return exists
            body_end.succs = {exit_node}
            exit_node.preds.add(body_end)

        if function_name in self._pending_function_calls:
            for start, end in self._pending_function_calls[function_name]:
                start.succs = {entry_node}
                entry_node.preds.add(start)
                exit_node.succs.add(end)
                end.preds.add(exit_node)

            self._pending_function_calls[function_name] = list()

        return entry_node, exit_node

    def generic_visit(self, node):
        if node is None:
            return None, None

        end = CfgNode(node)
        start = end
        for c in node:
            new_start, new_end = self.visit(c)
            if not new_start:
                assert not new_end
                new_start = CfgNode(c)
                new_end = new_start

            new_start = self._add_sideeffects_before(new_start)
            if new_start != new_end:
                end.succs = {new_start}
                new_start.preds.add(end)
                end = new_end
        return start, end

    def visit_FileAST(self, node):
        for child in node:
            start, end = self.visit(child)

            if not isinstance(child, pycparser.c_ast.FuncDef):
                if self.globals[1]:
                    last = self.globals[1]
                    assert not last.succs
                    if start == end:
                        last.asts += start.asts
                    else:
                        last.succs = {start}
                        start.preds.add(last)
                        self.globals = (self.globals[0], end)
                else:
                    self.globals = (start, end)
        return None, None

    def visit_FuncCall(self, node):
        call_start = CfgCall(node)
        call_end = CfgNode(node)

        call_start.summary_succ = call_end
        call_end.preds.add(
            call_start
        )  # Note that we don't differentiate for predecessor relations

        if node.args:
            start_params = None
            current_end = None
            for a in node.args:
                start_arg, end_arg = self.visit(a)
                if not start_arg:
                    assert not end_arg
                    start_arg = CfgNode(a)
                    end_arg = start_arg
                start_arg = self._add_sideeffects_before(start_arg)

                if not start_params:
                    start_params = start_arg

                if current_end:
                    current_end.succs = {start_arg}
                    start_arg.preds.add(current_end)
                current_end = end_arg

            current_end.succs = {call_start}
            call_start.preds.add(current_end)
        else:
            start_params = call_start

        function_name = self._resolve_name(node.name)

        if not function_name:
            return None, None

        if function_name in self.functions:
            func_start = self.functions[function_name][0]
            func_end = self.functions[function_name][1]
            call_start.succs = {func_start}
            func_start.preds.add(call_start)
            func_end.succs.add(call_end)
            call_end.preds.add(func_end)
        else:
            if function_name not in self._pending_function_calls:
                self._pending_function_calls[function_name] = list()
            self._pending_function_calls[function_name].append((call_start, call_end))
        self._sideeffects.append((start_params, call_end))
        return None, None

    @staticmethod
    def _resolve_name(name_expr: pycparser.c_ast.Node) -> Optional[str]:
        try:
            return name_expr.name
        except ValueError:
            logging.warning("Can't resolve function name expression %s", name_expr)
            return None  # signalizes that we don't know

    def _visit_list(self, stmts: Iterable[pycparser.c_ast.Node]) -> StartAndEnd:
        """
        Create CFG for a list of AST nodes
        and returns the start and the end of that CFG.
        Note that if the start is None, this means that the list was empty.
        """
        first = None
        current = None
        if stmts is None:
            return first, current
        for n in stmts:
            start, end = self.visit(n)
            if start is None:
                start = CfgNode(n)
                end = start
            start = self._add_sideeffects_before(start)
            if not first:
                first = start
            if current:
                current.succs = {start}
                start.preds.add(current)
                if (
                    start == end and len(start.preds) == 1 and current in start.preds
                ):  # only one statement; this collapses multi-edges
                    current.asts += start.asts
                    end = current
            current = end
            assert not self._sideeffects
        return first, current

    def visit_Compound(self, node):
        start, end = self._visit_list(node.block_items)
        if start is None:  # empty compound
            replacement = CfgNode(node)
            return replacement, replacement
        return start, end

    def visit_If(self, node):
        start_node = CfgNode(node)

        cond_start, branch_node = self.visit(node.cond)
        if not cond_start:
            cond_start = CfgNode(node.cond)
            branch_node = cond_start
        cond_start = self._add_sideeffects_before(cond_start)

        start_node.succs = {cond_start}
        cond_start.preds.add(start_node)

        end_node = CfgNode(node)

        end_node_used = False
        for branch in (node.iftrue, node.iffalse):
            branch_start, branch_end = self.visit(branch)
            branch_start = self._add_sideeffects_before(branch_start)

            if branch_start is not None:
                branch_node.succs.add(branch_start)
                branch_start.preds.add(branch_node)
            else:
                if not end_node in branch_node.succs:
                    branch_node.succs.add(end_node)
                    end_node.preds.add(branch_node)
                    end_node_used = True

            if branch_end is not None:
                branch_end.succs = {end_node}
                end_node.preds.add(branch_end)
                end_node_used = True

        if not end_node_used:
            end_node = None

        assert not self._sideeffects
        return start_node, end_node

    def visit_TernaryOp(self, node):
        cond_start, cond_end = self.visit(node.cond)
        if not cond_start:
            cond_start = CfgNode(node.cond)
            cond_end = cond_start
        cond_start = self._add_sideeffects_before(cond_start)
        assert cond_end is not None

        true_branch_start, true_branch_end = self.visit(node.iftrue)
        if not true_branch_start:
            assert not true_branch_end
            true_branch_start = CfgNode(node.iftrue)
            true_branch_end = true_branch_start
            true_branch_start = self._add_sideeffects_before(true_branch_start)

        false_branch_start, false_branch_end = self.visit(node.iffalse)
        if not false_branch_start:
            assert not false_branch_end
            false_branch_start = CfgNode(node.iffalse)
            false_branch_end = true_branch_start
            false_branch_start = self._add_sideeffects_before(false_branch_start)

        cond_end.succs.add(true_branch_start)
        true_branch_start.preds.add(cond_end)
        cond_end.succs.add(false_branch_start)
        false_branch_start.preds.add(cond_end)

        end_node = None
        for end in (true_branch_end, false_branch_end):
            if not end_node:
                end_node = CfgNode(node)
            if end:
                end.succs = {end_node}
                end_node.preds.add(end)

        self._sideeffects.append((cond_start, end_node))

        new_decl = CfgNode(node)  # placeholder, for now
        return new_decl, new_decl

    def visit_While(self, node):
        cond_start, loop_head = self.visit(node.cond)
        if cond_start is None:
            cond_start = CfgNode(node.cond)
            loop_head = cond_start
        cond_start = self._add_sideeffects_before(cond_start)

        end_node = CfgNode(node)

        with self._loop(loop_head, end_node):
            body_start, body_end = self.visit(node.stmt)
            assert not self._sideeffects, "Side effects for {}: {}".format(
                node.stmt, self._sideeffects
            )

        loop_head.succs.add(body_start)
        body_start.preds.add(loop_head)
        loop_head.succs.add(end_node)
        end_node.preds.add(loop_head)

        if body_end:
            body_end.succs = {cond_start}
            cond_start.preds.add(body_end)

        assert not self._sideeffects
        return cond_start, end_node

    def visit_DoWhile(self, node):
        cond_start, loop_cond = self.visit(node.cond)
        if cond_start is None:
            cond_start = CfgNode(node.cond)
            loop_cond = cond_start
        cond_start = self._add_sideeffects_before(cond_start)

        end_node = CfgNode(node)

        with self._loop(loop_cond, end_node):
            body_start, body_end = self.visit(node.stmt)
            assert not self._sideeffects

        loop_cond.succs.add(body_start)
        body_start.preds.add(loop_cond)
        loop_cond.succs.add(end_node)
        end_node.preds.add(loop_cond)

        if body_end:
            body_end.succs = {cond_start}
            cond_start.preds.add(body_end)

        assert not self._sideeffects
        return body_start, end_node

    def visit_For(self, node):
        cond_start, loop_head = self.visit(node.cond)
        if cond_start is None:
            assert loop_head is None
            cond_start = CfgNode(node.cond)
            loop_head = cond_start
        cond_start = self._add_sideeffects_before(cond_start)

        if node.init:
            init_start, init_end = self.visit(node.init)
            if init_start is None:
                assert init_end is None
                init_start = CfgNode(node.init)
                init_end = init_start
            init_start = self._add_sideeffects_before(init_start)
            init_end.succs = {cond_start}
            cond_start.preds.add(init_end)
        else:
            init_start = cond_start

        end_node = CfgNode(node)

        with self._loop(cond_start, end_node):
            body_start, body_end = self.visit(node.stmt)
            assert not self._sideeffects

        loop_head.succs.add(body_start)
        body_start.preds.add(loop_head)
        loop_head.succs.add(end_node)
        end_node.preds.add(loop_head)

        if node.next:
            next_start, next_end = self.visit(node.next)
            if next_start is None:
                assert next_end is None
                next_start = CfgNode(node.next)
                next_end = next_start
            next_start = self._add_sideeffects_before(next_start)
            if body_end:
                body_end.succs = {next_start}
                next_start.preds.add(body_end)
        else:
            next_start = None
            next_end = body_end
        assert next_end
        next_end.succs = {cond_start}
        cond_start.preds.add(next_end)

        assert not self._sideeffects
        return init_start, end_node

    def visit_Switch(self, node):
        cond_start, cond_end = self.visit(node.cond)
        cond_start = self._add_sideeffects_before(cond_start)

        start_node = CfgNode(node)
        end_node = CfgNode(node)

        start_node.succs = {cond_start}
        cond_start.preds.add(start_node)

        with self._loop(cond_start, end_node):
            cases_start, cases_end = self.visit(node.stmt)

        cond_end.succs = {cases_start}
        cases_start.preds.add(cond_end)
        if cases_end:
            cases_end.succs = {end_node}
            end_node.preds.add(cases_end)

        assert not self._sideeffects
        return start_node, end_node

    def visit_Case(self, node):
        start_node, branch_node = self.visit(node.expr)
        start_node = self._add_sideeffects_before(start_node)

        end_node = CfgNode(node)

        # stmts are not a Compound, unfortunately, but a list
        branch_start, branch_end = self._visit_list(node.stmts)
        if branch_start is None:
            assert branch_end is None
            branch_start = CfgNode(node)
            branch_end = branch_start

        branch_node.succs.add(branch_start)
        branch_start.preds.add(branch_node)
        branch_node.succs.add(end_node)
        end_node.preds.add(branch_node)

        if branch_end:
            branch_end.succs = {end_node}
            end_node.preds.add(branch_end)

        assert not self._sideeffects
        return start_node, end_node

    def visit_Default(self, node):
        # stmts are not a Compound, unfortunately, but a list
        branch_start, branch_end = self._visit_list(node.stmts)
        if branch_start is None:
            assert branch_end is None
            branch_start = CfgNode(node)
            branch_end = branch_start
        assert not self._sideeffects
        return branch_start, branch_end

    def visit_Break(self, node):
        break_node = CfgNode(node)
        target = self._current_loops[-1][1]  # exit of loop
        break_node.succs = {target}
        target.preds.add(break_node)
        assert not self._sideeffects
        return break_node, None

    def visit_Continue(self, node):
        cont_node = CfgNode(node)
        target = self._current_loops[-1][0]  # entry of loop
        cont_node.succs = {target}
        target.preds.add(cont_node)
        assert not self._sideeffects
        return cont_node, None

    def visit_Goto(self, node):
        goto = CfgNode(node)
        label_name = node.name
        try:
            assert self._current_function
            label = self._labels[self._current_function][label_name]
            goto.succs = {label}
            label.preds.add(goto)
        except KeyError:
            if label_name not in self._pending_gotos:
                self._pending_gotos[label_name] = list()
            self._pending_gotos[label_name].append(goto)
        assert not self._sideeffects
        return goto, None

    def visit_Label(self, node):
        label = CfgNode(node)
        label_name = node.name
        assert self._current_function
        if self._current_function not in self._labels:
            self._labels[self._current_function] = dict()
        assert label_name not in self._labels[self._current_function], (
            "Label exists twice: %s" % label_name
        )
        self._labels[self._current_function][label_name] = label

        if label_name in self._pending_gotos:
            for goto in self._pending_gotos[label_name]:
                goto.succs = {label}
                label.preds.add(goto)
            self._pending_gotos[label_name] = list()
        assert not self._sideeffects

        if node.stmt:
            stmt_start, stmt_end = self.visit(node.stmt)
            if not stmt_start:
                assert not stmt_end
                stmt_start = CfgNode(node.stmt)
                stmt_end = stmt_start
            stmt_start = self._add_sideeffects_before(stmt_start)
            end = stmt_end
            label.succs = {stmt_start}
            stmt_start.preds.add(label)
        else:
            end = label

        return label, end

    def visit_Return(self, node):
        ret_node = CfgNode(node)
        target = self.functions[self._current_function][1]  # exit of function
        ret_node.succs = {target}
        target.preds.add(ret_node)

        start_expr, end_expr = self.visit(node.expr)
        if not start_expr:
            assert not end_expr
            start_expr = CfgNode(node.expr)
            end_expr = start_expr
        start_expr = self._add_sideeffects_before(start_expr)
        end_expr.succs = {ret_node}
        ret_node.preds.add(end_expr)

        assert not self._sideeffects
        return (
            start_expr,
            None,
        )  # control flow doesn't continue after a return, so the second return value is None

    def _add_sideeffects_before(self, start_node: Optional[pycparser.c_ast.Node]):
        current_end = None
        for start, end in self._sideeffects:
            if current_end:
                assert not current_end.succs, str(current_end)
                current_end.succs = {start}
                start.preds.add(current_end)
            current_end = end
        try:
            if current_end:
                sideeffect_start: pycparser.c_ast.Node = self._sideeffects[0][0]

                if start_node is not None:
                    sideeffect_start.preds = start_node.preds
                    for pred in sideeffect_start.preds:
                        pred.succs.remove(start_node)
                        pred.succs.add(sideeffect_start)

                    current_end.succs = {start_node}
                    # overwrite all previous preds ; these are preds of sideeffect_start now
                    start_node.preds = {current_end}
                return sideeffect_start
            return start_node
        finally:
            self._sideeffects = list()


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
