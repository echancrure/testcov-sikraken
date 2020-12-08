# This file is part of TestCov,
# a robust test executor with reliable coverage measurement:
# https://gitlab.com/sosy-lab/software/test-suite-validator/
#
# Copyright (C) 2018 - 2020  Dirk Beyer
# SPDX-FileCopyrightText: 2019 Dirk Beyer <https://www.sosy-lab.org>
#
# SPDX-License-Identifier: Apache-2.0

"Module with classes to add labels in C code"

# pylint: disable=C0103
# to disable snake_case error

from typing import Optional, Iterable
import pycparser
from suite_validation import _logger as logging

LABEL_PREFIX = "BRANCH_"
GOTO_PREFIX = "goto " + LABEL_PREFIX


class AbstractLabelAdder(pycparser.c_ast.NodeVisitor):
    def __init__(self):
        self._labels = 0

    def _get_label(self) -> pycparser.c_ast.Label:
        name = LABEL_PREFIX + str(self._labels)
        self._labels += 1
        label = pycparser.c_ast.Label(name, stmt=pycparser.c_ast.EmptyStatement())
        return label

    def insert_label(self, node: Optional[pycparser.c_ast.Node], i: int):
        if not isinstance(node, pycparser.c_ast.Compound):
            return self.insert_label(
                pycparser.c_ast.Compound([node] if node else []), i
            )
        label = self._get_label()
        goto = pycparser.c_ast.Goto(label.name)

        if node.block_items is None:
            node.block_items = list()
        else:
            try:
                curr_stmt, next_stmt = node.block_items[i], node.block_items[i + 1]
                if (
                    isinstance(curr_stmt, pycparser.c_ast.Goto)
                    and isinstance(next_stmt, pycparser.c_ast.Label)
                    and next_stmt.name.startswith(LABEL_PREFIX)
                ):
                    # Skip adding label, there already seems to be one
                    return node
            except IndexError:
                # There's no i+1, so there can't be a goto-label construct yet
                pass

        node.block_items.insert(i, label)
        # make sure that goto is first element of block_items,
        # to avoid endless loop between label and goto
        node.block_items.insert(i, goto)
        return node

    def add_label_at_start(
        self, node: Optional[pycparser.c_ast.Node]
    ) -> pycparser.c_ast.Node:
        return self.insert_label(node, i=0)


class TargetFuncLabelAdder(AbstractLabelAdder):
    def __init__(self, func_name):
        super().__init__()
        self._func_name = func_name

    def visit_Compound(self, node):
        self.generic_visit(node)
        if not node.block_items:
            return

        for i, stmt in enumerate(node.block_items):
            if isinstance(stmt, pycparser.c_ast.FuncCall):
                try:
                    if stmt.name.name == self._func_name:
                        self.insert_label(node, i)
                        break
                except AttributeError:
                    pass

    def visit_If(self, node):
        self.generic_visit(node)
        if self.is_target_call(node.iftrue):
            node.iftrue = self.add_label_at_start(node.iftrue)
        if self.is_target_call(node.iffalse):
            node.iffalse = self.add_label_at_start(node.iffalse)

    def visit_TernaryOp(self, node):
        self.generic_visit(node)
        if self.is_target_call(node.iftrue):
            node.iftrue = self.add_label_at_start(node.iftrue)
        if self.is_target_call(node.iffalse):
            node.iffalse = self.add_label_at_start(node.iffalse)

    def visit_Case(self, node):
        self.generic_visit(node)
        for idx, stmt in enumerate(node.stmts):
            if self.is_target_call(stmt):
                node.stmts[idx] = self.add_label_at_start(stmt)
                break

    def visit_While(self, node):
        self.generic_visit(node)
        # ignoring node.cond for now
        if self.is_target_call(node.stmt):
            node.stmt = self.add_label_at_start(node.stmt)

    def is_target_call(self, i):
        if isinstance(i, pycparser.c_ast.FuncCall):
            try:
                return i.name.name == self._func_name
            except AttributeError:
                pass
        return False


class LabelAdder(AbstractLabelAdder):
    """Add labels at each branch on the visited AST, in-situ."""

    def __init__(self, optimize_labels=True):
        super().__init__()
        self._optimize = optimize_labels

    def visit_If(self, node):
        # Visit children before adding labels to work on original AST
        self.generic_visit(node)

        if self._optimize and self._followed_by_if(node.iftrue):
            pass
        else:
            node.iftrue = self.add_label_at_start(node.iftrue)

        if self._optimize and self._followed_by_if(node.iffalse):
            pass
        else:
            node.iffalse = self.add_label_at_start(node.iffalse)

    @staticmethod
    def _followed_by_if(node) -> bool:
        return isinstance(node, pycparser.c_ast.If) or (
            isinstance(node, pycparser.c_ast.Compound)
            and node.block_items
            and len(node.block_items) == 1
            and isinstance(node.block_items[0], pycparser.c_ast.If)
        )

    @staticmethod
    def _is_terminating_call(node) -> bool:
        try:
            return isinstance(node, pycparser.c_ast.FuncCall) and node.name.name in [
                "abort",
                "exit",
                "__assert_fail",
            ]
        except NameError:
            return False

    def visit_Compound(self, node):
        self.generic_visit(node)
        if node.block_items is None:
            node.block_items = []

        i = 0
        while i < len(node.block_items):
            stmt = node.block_items[i]
            if isinstance(
                stmt,
                (pycparser.c_ast.While, pycparser.c_ast.For, pycparser.c_ast.DoWhile),
            ):
                self.insert_label(node, i + 1)
                i = i + 2
            elif self._is_terminating_call(stmt):
                self.insert_label(node, i)
                i = i + 3
            else:
                i = i + 1

    def visit_While(self, node):
        self.generic_visit(node)
        node.stmt = self.add_label_at_start(node.stmt)

    def visit_DoWhile(self, node):
        self.generic_visit(node)
        node.stmt = self.add_label_at_start(node.stmt)

    def visit_For(self, node):
        self.generic_visit(node)
        node.stmt = self.add_label_at_start(node.stmt)

    def visit_Case(self, node):
        self.generic_visit(node)
        if node.stmts:
            node.stmts[0] = self.add_label_at_start(node.stmts[0])
        # we don't add a label if the case has no own content but 'falls through'

    def visit_Default(self, node):
        self.generic_visit(node)
        node.stmts[0] = self.add_label_at_start(node.stmts[0])

    def visit_FuncDef(self, node):
        self.generic_visit(node)
        if node.body is None:
            logging.debug(
                "Function %s has no body, adding compound statement.", node.decl.name
            )
            node.body = pycparser.c_ast.Compound(list())
        # self._add_label_at_start(node.body)


def _get_abort_call() -> pycparser.c_ast.FuncCall:
    return pycparser.c_ast.FuncCall(pycparser.c_ast.ID("abort"), args=None)


class AbortAdder(pycparser.c_ast.NodeVisitor):
    """Add an abort after each label with a name in the list given in the constructor, in-situ."""

    def __init__(self, labels: Iterable[str], args):
        del args  # not used at the moment
        self._labels = set(labels)

    def visit_Label(self, node):
        if node.name in self._labels:
            assert node.stmt is None or isinstance(
                node.stmt, pycparser.c_ast.EmptyStatement
            )
            node.stmt = _get_abort_call()
        else:
            self.generic_visit(node)
