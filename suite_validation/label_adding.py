# testcov is tool for validation and execution of test suites.
# This file is part of testcov.
#
# Copyright (C) 2018 - 2020  Dirk Beyer
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
"Module with classes to add labels in C code"

# pylint: disable=C0103
# to disable snake_case error

import logging
from typing import Optional, Iterable
import pycparser

LABEL_PREFIX = "BRANCH_"
GOTO_PREFIX = "goto " + LABEL_PREFIX

class LabelAdder(pycparser.c_ast.NodeVisitor):
    """Add labels at each branch on the visited AST, in-situ."""

    def __init__(self, optimize_labels=True):
        # del args  # not used at the moment
        self._labels = 0
        self._optimize = optimize_labels

    def _get_label(self) -> pycparser.c_ast.Label:
        name = LABEL_PREFIX + str(self._labels)
        self._labels += 1
        label = pycparser.c_ast.Label(name, stmt=pycparser.c_ast.EmptyStatement())
        return label

    def _add_label_at_start(
        self, node: Optional[pycparser.c_ast.Node]
    ) -> pycparser.c_ast.Node:
        if isinstance(node, pycparser.c_ast.Compound):
            if node.block_items is None:
                node.block_items = list()
            label = self._get_label()
            goto = pycparser.c_ast.Goto(label.name)

            node.block_items.insert(0, label)
            # make sure that goto is first element of block_items,
            # to avoid endless loop between label and goto
            node.block_items.insert(0, goto)
            return node

        return self._add_label_at_start(
            pycparser.c_ast.Compound([node] if node else [])
        )

    def visit_If(self, node):
        # Visit children before adding labels to work on original AST
        self.generic_visit(node)

        if self._optimize and self._followed_by_if(node.iftrue):
            pass
        else:
            node.iftrue = self._add_label_at_start(node.iftrue)

        if self._optimize and self._followed_by_if(node.iffalse):
            pass
        else:
            node.iffalse = self._add_label_at_start(node.iffalse)

    @staticmethod
    def _followed_by_if(node) -> bool:
        return isinstance(node, pycparser.c_ast.If) or (
            isinstance(node, pycparser.c_ast.Compound)
            and node.block_items
            and len(node.block_items) == 1
            and isinstance(node.block_items[0], pycparser.c_ast.If)
        )

    def visit_Compound(self, node):
        self.generic_visit(node)
        if not node.block_items:
            return

        i = 0
        while i < len(node.block_items):
            stmt = node.block_items[i]
            if isinstance(
                stmt,
                (pycparser.c_ast.While, pycparser.c_ast.For, pycparser.c_ast.DoWhile),
            ):
                node.block_items.insert(i + 1, self._get_label())
                i = i + 2
            else:
                i = i + 1

    def visit_While(self, node):
        self.generic_visit(node)
        node.stmt = self._add_label_at_start(node.stmt)

    def visit_DoWhile(self, node):
        self.generic_visit(node)
        node.stmt = self._add_label_at_start(node.stmt)

    def visit_For(self, node):
        self.generic_visit(node)
        node.stmt = self._add_label_at_start(node.stmt)

    def visit_Case(self, node):
        self.generic_visit(node)
        if node.stmts:
            node.stmts[0] = self._add_label_at_start(node.stmts[0])
        # we don't add a label if the case has no own content but 'falls through'

    def visit_Default(self, node):
        self.generic_visit(node)
        node.stmts[0] = self._add_label_at_start(node.stmts[0])

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
