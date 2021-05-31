#include "Includes.hpp"
#include "LabelerFrontendAction.hpp"
#include "LabelerASTConsumer.hpp"

LabelerFrontendAction::LabelerFrontendAction(std::string options) {}
void LabelerFrontendAction::EndSourceFileAction() {
  SourceManager &SM = labelAddRewriter.getSourceMgr();
  llvm::errs() << "** EndSourceFileAction for: "
               << SM.getFileEntryForID(SM.getMainFileID())->getName() << "\n";

  // Now emit the rewritten buffer.
  labelAddRewriter.getEditBuffer(SM.getMainFileID()).write(llvm::outs());
}

std::unique_ptr<ASTConsumer> LabelerFrontendAction::CreateASTConsumer(CompilerInstance &CI,
                                               StringRef file) {
  llvm::errs() << "** Creating AST consumer for: " << file << "\n";
  labelAddRewriter.setSourceMgr(CI.getSourceManager(), CI.getLangOpts());
  return std::make_unique<LabelerASTConsumer>(labelAddRewriter);
}
