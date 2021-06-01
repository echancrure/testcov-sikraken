// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0



#include "Includes.hpp"

#include "LabelerASTVisitor.hpp"
#include "LabelerFrontendAction.hpp"
#include "LabelerASTConsumer.hpp"
#include "LabelerFrontendActionFactory.hpp"

int main(int argc, const char **argv) {
  auto ExpectedParser =
      CommonOptionsParser::create(argc, argv, ToolingSampleCategory);
  if (!ExpectedParser) {
    // Fail gracefully for unsupported options.
    llvm::errs() << ExpectedParser.takeError();
    return 1;
  }
  CommonOptionsParser &op = ExpectedParser.get();
  ClangTool Tool(op.getCompilations(), op.getSourcePathList());
  return Tool.run(newLabelerFrontendActionFactory("test").get());
}
