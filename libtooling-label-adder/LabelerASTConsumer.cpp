// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

#include "LabelerASTConsumer.hpp"
#include "Includes.hpp"

LabelerASTConsumer::LabelerASTConsumer(Rewriter &R, LabelOptions labelOptions)
    : Visitor(R, labelOptions) {}

bool LabelerASTConsumer::HandleTopLevelDecl(DeclGroupRef DR) {
  for (DeclGroupRef::iterator b = DR.begin(), e = DR.end(); b != e; ++b) {
    // Traverse the declaration using our AST visitor.
    Visitor.TraverseDecl(*b);
    (*b)->dump();
  }
  return true;
}