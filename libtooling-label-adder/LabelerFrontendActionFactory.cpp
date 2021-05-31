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