#include "Includes.hpp"

#ifndef LABELER_FRONTEND_ACTION_HPP
#define LABELER_FRONTEND_ACTION_HPP
// For each source file provided to the tool, a new FrontendAction is created.
class LabelerFrontendAction : public ASTFrontendAction {
public:
  LabelerFrontendAction(std::string options);
  void EndSourceFileAction() override;

  std::unique_ptr<ASTConsumer> CreateASTConsumer(CompilerInstance &CI,
                                                 StringRef file) override ;

private:
  Rewriter labelAddRewriter;
};
#endif