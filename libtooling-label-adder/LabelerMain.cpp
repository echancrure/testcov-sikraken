// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

#include "Includes.hpp"

#include "LabelerASTConsumer.hpp"
#include "LabelerASTVisitor.hpp"
#include "LabelerFrontendAction.hpp"
#include "LabelerFrontendActionFactory.hpp"

static llvm::cl::OptionCategory
    InstrumentationOptions("Instrumentation Options");
static llvm::cl::opt<bool>
    NoIfLabel("no-labels-if",
              llvm::cl::desc("Do not create Labels in if-branches"),
              llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool>
    NoElseLabel("no-labels-else",
              llvm::cl::desc("Do not create Labels in else-branches"),
              llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool>
    NoSwitchLabel("no-labels-switch",
              llvm::cl::desc("Do not create Labels in switch cases"),
              llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool>
    NoFunctionStartLabel("no-labels-function-start",
              llvm::cl::desc("Do not create Labels at the begin of a function"),
              llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool>
    NoFunctionEndLabel("no-labels-function-end",
              llvm::cl::desc("Do not create Labels at the end of a function"),
              llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool>
    NoTernaryLabel("no-labels-ternary",
                       llvm::cl::desc("Do not refactor ternary Statements to if statements and add Labels inside them"),
                       llvm::cl::cat(InstrumentationOptions));

int main(int argc, const char **argv) {
  auto ExpectedParser =
      CommonOptionsParser::create(argc, argv, InstrumentationOptions);
  if (!ExpectedParser) {
    // Fail gracefully for unsupported options.
    llvm::errs() << ExpectedParser.takeError();
    return 1;
  }
  CommonOptionsParser &op = ExpectedParser.get();
  ClangTool Tool(op.getCompilations(), op.getSourcePathList());

  LabelOptions labelOptions;
  labelOptions.ifLabel = !NoIfLabel.getValue();
  labelOptions.elseLabel = !NoElseLabel.getValue();
  labelOptions.caseLabel = !NoSwitchLabel.getValue();
  labelOptions.functionStartLabel = !NoFunctionStartLabel.getValue();
  labelOptions.functionEndLabel = !NoFunctionEndLabel.getValue();
  labelOptions.ternaryTrueLabel = !NoTernaryLabel.getValue();
  labelOptions.ternaryFalseLabel = !NoTernaryLabel.getValue();

  return Tool.run(newLabelerFrontendActionFactory(labelOptions).get());
}
