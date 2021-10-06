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
// If Options
static llvm::cl::opt<bool>
    NoIfStmtLabel("no-labels-if-stmt",
                  llvm::cl::desc("Do not create Labels in if-statements."),
                  llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool>
    NoIfLabel("no-labels-if-case",
              llvm::cl::desc("Do not create Labels in if-branches"),
              llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool>
    NoElseLabel("no-labels-else-case",
                llvm::cl::desc("Do not create Labels in else-branches"),
                llvm::cl::cat(InstrumentationOptions));
// Switch Options
static llvm::cl::opt<bool> NoSwitchLabel(
    "no-labels-switch",
    llvm::cl::desc("Do not create Labels in switch cases and default case"),
    llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool>
    NoSwitchCaseLabel("no-labels-switch-case",
                      llvm::cl::desc("Do not create Labels in switch cases"),
                      llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool> NoSwitchDefaultLabel(
    "no-labels-switch-default",
    llvm::cl::desc("Do not create Labels in default cases"),
    llvm::cl::cat(InstrumentationOptions));
// Function Options
static llvm::cl::opt<bool> NoFunctionLabel(
    "no-labels-function",
    llvm::cl::desc("Do not create Labels at the begin or end of a function"),
    llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool> NoFunctionStartLabel(
    "no-labels-function-start",
    llvm::cl::desc("Do not create Labels at the begin of a function"),
    llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool> NoFunctionEndLabel(
    "no-labels-function-end",
    llvm::cl::desc("Do not create Labels at the end of a function"),
    llvm::cl::cat(InstrumentationOptions));
// Ternary Options
static llvm::cl::opt<bool>
    NoTernaryLabel("no-labels-ternary",
                   llvm::cl::desc("Do not refactor ternary Statements to if "
                                  "statements and add Labels inside them"),
                   llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool> NoTernaryTrueLabel(
    "no-labels-ternary-true",
    llvm::cl::desc("Do not add labels to refactored ternary true cases"),
    llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool> NoTernaryFalseLabel(
    "no-labels-ternary-false",
    llvm::cl::desc("Do not add labels to refactored ternary false cases"),
    llvm::cl::cat(InstrumentationOptions));
// Output Options
static llvm::cl::opt<bool> InPlace(
    "in-place",
     llvm::cl::desc("Overwrite files"),
     llvm::cl::cat(InstrumentationOptions));
static llvm::cl::opt<bool> NoInfo(
    "no-info",
    llvm::cl::desc("Do not print information to stderr"),
    llvm::cl::cat(InstrumentationOptions));

LabelOptions generateLabelOptions() {
  LabelOptions labelOptions;
  if (NoIfStmtLabel) {
    labelOptions.ifLabel = false;
    labelOptions.elseLabel = false;
  } else {
    labelOptions.ifLabel = !NoIfLabel.getValue();
    labelOptions.elseLabel = !NoElseLabel.getValue();
  }

  if (NoSwitchLabel) {
    labelOptions.caseLabel = false;
    labelOptions.defaultLabel = false;
  } else {
    labelOptions.caseLabel = !NoSwitchCaseLabel.getValue();
    labelOptions.defaultLabel = !NoSwitchDefaultLabel.getValue();
  }

  if (NoFunctionLabel) {
    labelOptions.functionStartLabel = false;
    labelOptions.functionEndLabel = false;
  } else {
    labelOptions.functionStartLabel = !NoFunctionStartLabel.getValue();
    labelOptions.functionEndLabel = !NoFunctionEndLabel.getValue();
  }

  if (NoTernaryLabel) {
    labelOptions.ternaryTrueLabel = false;
    labelOptions.ternaryFalseLabel = false;
  } else {
    labelOptions.ternaryTrueLabel = !NoTernaryTrueLabel.getValue();
    labelOptions.ternaryFalseLabel = !NoTernaryFalseLabel.getValue();
  }

  labelOptions.inPlace = InPlace.getValue();
  labelOptions.noInfo = NoInfo.getValue();

  return labelOptions;
}

int main(int argc, const char **argv) {
  auto ExpectedParser =
      CommonOptionsParser::create(argc, argv, InstrumentationOptions, llvm::cl::NumOccurrencesFlag(llvm::cl::OneOrMore), NULL);
  if (!ExpectedParser) {
    // Fail gracefully for unsupported options.
    llvm::errs() << ExpectedParser.takeError();
    return 1;
  }
  CommonOptionsParser &op = ExpectedParser.get();
  ClangTool Tool(op.getCompilations(), op.getSourcePathList());

  return Tool.run(
      newLabelerFrontendActionFactory(generateLabelOptions()).get());
}
