// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

#include <sstream>
#include <string>

#include "clang/AST/AST.h"
#include "clang/AST/ASTConsumer.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/Frontend/ASTConsumers.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendActions.h"
#include "clang/Rewrite/Core/Rewriter.h"
#include "clang/Tooling/CommonOptionsParser.h"
#include "clang/Tooling/Tooling.h"
#include "llvm/Support/raw_ostream.h"

using namespace clang;
using namespace clang::driver;
using namespace clang::tooling;

static llvm::cl::OptionCategory ToolingSampleCategory("Tooling Sample");

class MyASTVisitor : public RecursiveASTVisitor<MyASTVisitor> {
public:
  MyASTVisitor(Rewriter &R) : labelAddRewriter(R) {}

  SourceLocation GetLastSemicolonLocation(Stmt *fromStatement) {
    // The getEndLoc Method leaves us with the position of the first character
    // from the last token before the semicolon of a Statement. As it is
    // currently implemented in Libtooling, the semicolon itself is defined as
    // not being a part of a statement. Might be source for failure, if that
    // gets changed in later LLVM releases
    return Lexer::findNextToken(fromStatement->getEndLoc(),
                                labelAddRewriter.getSourceMgr(),
                                labelAddRewriter.getLangOpts())
        ->getEndLoc();
  }

  void AddBracesAroundStatement(Stmt *processedStatement) {
    if (isa<CompoundStmt>(processedStatement))
      return;
    labelAddRewriter.InsertText(processedStatement->getBeginLoc(), "{", true,
                                true);
    // We need to add the closing brace after the semicolon, therefore we need
    // to calculate the semicolons position.
    SourceLocation semicolonLocation =
        GetLastSemicolonLocation(processedStatement);
    labelAddRewriter.InsertText(semicolonLocation, "\n}\n", true, true);
  }

  void LabelStatementAndAddBracesIfMissing(Stmt *processedStatement,
                                           std::string labelToAdd) {
    SourceLocation labelPos;
    // Check if Braces are missing
    if (!isa<CompoundStmt>(processedStatement)) {
      AddBracesAroundStatement(processedStatement);
      labelPos = processedStatement->getBeginLoc();
    } else {
      // If braces are already there, beginLoc leaves us with the position
      // before the brace, so we have to offset by 1
      labelPos = processedStatement->getBeginLoc().getLocWithOffset(1);
    }
    // Add Label after opening Brace
    labelAddRewriter.InsertText(labelPos, "\n" + labelToAdd + "\n", true, true);
  }

  void LabelIfStmt(IfStmt *processedStatement) {
    Stmt *thenStatement = processedStatement->getThen();
    LabelStatementAndAddBracesIfMissing(thenStatement, "//if-Label");
    Stmt *elseStatement = processedStatement->getElse();
    if (elseStatement) {
      LabelStatementAndAddBracesIfMissing(elseStatement, "//else-Label");
    }
  }

  void RefactorWriteAndLabelTernary(ConditionalOperator *ternaryStatement,
                                    SourceLocation writePos,
                                    std::string ifLabelToAdd,
                                    std::string elseLabelToAdd) {
    Expr *condition = ternaryStatement->getCond();
    llvm::StringRef conditionText = Lexer::getSourceText(
        CharSourceRange::getCharRange(
            ternaryStatement->getCond()->getSourceRange()),
        labelAddRewriter.getSourceMgr(), labelAddRewriter.getLangOpts());
//    Expr *trueExpr = ternaryStatement->getTrueExpr();
//    llvm::StringRef ifContentText = Lexer::getSourceText(
//        CharSourceRange::getCharRange(
//            trueExpr->getSourceRange()),
//        labelAddRewriter.getSourceMgr(), labelAddRewriter.getLangOpts());
//    Expr *falseExpr = ternaryStatement->getFalseExpr();
//    llvm::StringRef elseContentText = Lexer::getSourceText(
//        CharSourceRange::getCharRange(
//            falseExpr->getSourceRange()),
//        labelAddRewriter.getSourceMgr(), labelAddRewriter.getLangOpts());
    labelAddRewriter.InsertText(writePos, "\nif (", true, true);
    labelAddRewriter.InsertText(writePos, conditionText, true, true);
    labelAddRewriter.InsertText(writePos, ") {\n" + ifLabelToAdd + "\n", true, true);
//    labelAddRewriter.InsertText(writePos, ifContentText, true, true);
    labelAddRewriter.InsertText(writePos, ";\n}else{\n" + elseLabelToAdd + "\n", true, true);
//    labelAddRewriter.InsertText(writePos, elseContentText, true, true);
    labelAddRewriter.InsertText(writePos, ";\n}\n", true, true);
  }

  bool VisitStmt(Stmt *s) {
    if (isa<IfStmt>(s)) {
      LabelIfStmt(cast<IfStmt>(s));
    } else if (isa<BinaryOperator>(s)) {
      Stmt *rightHandSide = cast<BinaryOperator>(s)->getRHS();
      if (isa<ConditionalOperator>(rightHandSide)) {
        labelAddRewriter.InsertText(s->getBeginLoc(), "/*", true, true);
        SourceLocation semicolonLocation = GetLastSemicolonLocation(s);
        labelAddRewriter.InsertText(semicolonLocation, "*/", true, true);
        RefactorWriteAndLabelTernary(cast<ConditionalOperator>(s),
                                     semicolonLocation, "//ternary-If-Label",
                                     "//ternary-Else-Label");
      }
    }

    return true;
  }

  bool VisitFunctionDecl(FunctionDecl *f) {
    // Only function definitions (with bodies), not declarations.
    if (f->hasBody()) {
      Stmt *FuncBody = f->getBody();

      // Type name as string
      QualType QT = f->getReturnType();
      std::string TypeStr = QT.getAsString();

      // Function name
      DeclarationName DeclName = f->getNameInfo().getName();
      std::string FuncName = DeclName.getAsString();

      // Add comment before
      std::stringstream SSBefore;
      SSBefore << "// Begin function " << FuncName << " returning " << TypeStr
               << "\n";
      SourceLocation ST = f->getSourceRange().getBegin();
      labelAddRewriter.InsertText(ST, SSBefore.str(), true, true);

      // And after
      std::stringstream SSAfter;
      SSAfter << "\n// End function " << FuncName;
      ST = FuncBody->getEndLoc().getLocWithOffset(1);
      labelAddRewriter.InsertText(ST, SSAfter.str(), true, true);
    }

    return true;
  }

private:
  Rewriter &labelAddRewriter;
};

// Implementation of the ASTConsumer interface for reading an AST produced
// by the Clang parser.
class MyASTConsumer : public ASTConsumer {
public:
  MyASTConsumer(Rewriter &R) : Visitor(R) {}

  // Override the method that gets called for each parsed top-level
  // declaration.
  bool HandleTopLevelDecl(DeclGroupRef DR) override {
    for (DeclGroupRef::iterator b = DR.begin(), e = DR.end(); b != e; ++b) {
      // Traverse the declaration using our AST visitor.
      Visitor.TraverseDecl(*b);
      (*b)->dump();
    }
    return true;
  }

private:
  MyASTVisitor Visitor;
};

// For each source file provided to the tool, a new FrontendAction is created.
class MyFrontendAction : public ASTFrontendAction {
public:
  MyFrontendAction() {}
  void EndSourceFileAction() override {
    SourceManager &SM = labelAddRewriter.getSourceMgr();
    llvm::errs() << "** EndSourceFileAction for: "
                 << SM.getFileEntryForID(SM.getMainFileID())->getName() << "\n";

    // Now emit the rewritten buffer.
    labelAddRewriter.getEditBuffer(SM.getMainFileID()).write(llvm::outs());
  }

  std::unique_ptr<ASTConsumer> CreateASTConsumer(CompilerInstance &CI,
                                                 StringRef file) override {
    llvm::errs() << "** Creating AST consumer for: " << file << "\n";
    labelAddRewriter.setSourceMgr(CI.getSourceManager(), CI.getLangOpts());
    return std::make_unique<MyASTConsumer>(labelAddRewriter);
  }

private:
  Rewriter labelAddRewriter;
};

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

  return Tool.run(newFrontendActionFactory<MyFrontendAction>().get());
}
