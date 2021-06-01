// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0



#include "Includes.hpp"
#include "LabelerFrontendActionFactory.hpp"
#include "LabelerFrontendAction.hpp"

std::unique_ptr<FrontendActionFactory> newLabelerFrontendActionFactory(std::string options) {
  class LabelerFrontendActionFactory : public FrontendActionFactory {
  public:
    LabelerFrontendActionFactory(std::string optionstring) : mOptions(optionstring) {}

    std::unique_ptr<FrontendAction> create() override {
      llvm::errs() << "** Options: " << mOptions << "\n";
      return std::make_unique<LabelerFrontendAction>(mOptions);
    }

  private:
    std::string mOptions;
  };

  return std::unique_ptr<FrontendActionFactory>(
      new LabelerFrontendActionFactory(options));
}