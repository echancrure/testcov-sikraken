// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0

#include "LabelerASTVisitor.hpp"
#include "Includes.hpp"

LabelerASTVisitor::LabelerASTVisitor(Rewriter &R, LabelOptions labelOptions)
    : labelAddRewriter(R), options(labelOptions) {}

std::string LabelerASTVisitor::getNextLabel() {
  goalCounter++;
  return "\nGoal_" + std::to_string(goalCounter) + ":;\n";
}

SourceLocation LabelerASTVisitor::GetTrueEndLocation(Stmt *fromStatement) {
  return Lexer::findNextToken(fromStatement->getEndLoc(),
                              labelAddRewriter.getSourceMgr(),
                              labelAddRewriter.getLangOpts())
      ->getEndLoc();
}

void LabelerASTVisitor::AddBracesAroundStatement(Stmt *processedStatement) {
  if (isa<CompoundStmt>(processedStatement))
    return;
  labelAddRewriter.InsertText(processedStatement->getBeginLoc(), "{", true,
                              true);
  // We need to add the closing brace after the semicolon, therefore we need
  // to calculate the semicolons position.
  SourceLocation semicolonLocation = GetTrueEndLocation(processedStatement);
  labelAddRewriter.InsertText(semicolonLocation, "\n}\n", true, true);
}

void LabelerASTVisitor::LabelStatementAndAddBracesIfMissing(
    Stmt *processedStatement, bool beginLabel, bool endLabel) {
  // Return instantly, if no labels to add
  if (!(beginLabel || endLabel))
    return;
  // If there is no code (a Null-Statement), remove semicolon and add brackets and Label
  if(isa<NullStmt>(processedStatement)){
    labelAddRewriter.ReplaceText(processedStatement->getSourceRange(), "{" + getNextLabel() + "}");
    return;
  }
  SourceLocation beginPos;
  SourceLocation endPos;
  // Check if Braces are missing
  if (!isa<CompoundStmt>(processedStatement)) {
    AddBracesAroundStatement(processedStatement);
    beginPos = processedStatement->getBeginLoc();
    endPos = processedStatement->getEndLoc();
  } else {
    if(cast<CompoundStmt>(processedStatement)->body_empty()){
      labelAddRewriter.ReplaceText(processedStatement->getSourceRange(), "{" + getNextLabel() + "}");
      return;
    }
    // If braces are already there, beginLoc leaves us with the position
    // before the brace, so we have to offset by 1
    // The reverse applies to the closing brace, so we offset by -1
    beginPos = processedStatement->getBeginLoc().getLocWithOffset(1);
    endPos = processedStatement->getEndLoc().getLocWithOffset(-1);
  }
  // Add Label after opening Brace, if present
  if (beginLabel) {
    labelAddRewriter.InsertText(beginPos, getNextLabel(), true, true);
  }
  // Add Label after closing Brace, if present
  if (endLabel) {
    labelAddRewriter.InsertText(endPos, getNextLabel(), true, true);
  }
}

bool LabelerASTVisitor::VisitIfStmt(IfStmt *S) {
  Stmt *thenStatement = S->getThen();
  LabelStatementAndAddBracesIfMissing(thenStatement, options.ifLabel, false);
  Stmt *elseStatement = S->getElse();
  if (elseStatement) {
    LabelStatementAndAddBracesIfMissing(elseStatement, options.elseLabel,
                                        false);
  }
  return true;
}

bool LabelerASTVisitor::VisitCaseStmt(CaseStmt *S) {
  if (options.caseLabel)
    for (Stmt *child : S->children()) {
      if (isa<ConstantExpr>(child)) {
        labelAddRewriter.InsertText(GetTrueEndLocation(child), getNextLabel(),
                                    true, true);
      }
    }
  return true;
}

bool LabelerASTVisitor::VisitBinaryOperator(BinaryOperator *S) {
  if(!(options.ternaryTrueLabel || options.ternaryFalseLabel)) return true;
  Stmt *rightHandSide = S->getRHS();
  Stmt *leftHandSide = S->getLHS();
  std::string leftHandString =
      Lexer::getSourceText(
          CharSourceRange::getCharRange(leftHandSide->getBeginLoc(),
                                        GetTrueEndLocation(leftHandSide)),
          labelAddRewriter.getSourceMgr(), labelAddRewriter.getLangOpts())
          .str();
  if (isa<ConditionalOperator>(rightHandSide)) {
    labelAddRewriter.RemoveText(SourceRange(leftHandSide->getBeginLoc(),
                                            GetTrueEndLocation(leftHandSide)));
    LabelTernaryStmt(cast<ConditionalOperator>(rightHandSide), leftHandString);
  } else if (isa<ImplicitCastExpr>(rightHandSide)) {
    for (Stmt *child : rightHandSide->children()) {
      if (isa<ConditionalOperator>(child)) {
        labelAddRewriter.RemoveText(SourceRange(
            leftHandSide->getBeginLoc(), GetTrueEndLocation(leftHandSide)));
        LabelTernaryStmt(cast<ConditionalOperator>(child), leftHandString);
      }
    }
  }
  return true;
}

bool LabelerASTVisitor::VisitCompoundStmt(CompoundStmt *S) {
  if(!(options.ternaryTrueLabel || options.ternaryFalseLabel)) return true;
  for (Stmt *child : S->children()){
    if(isa<ConditionalOperator>(child)){
      LabelTernaryStmt(cast<ConditionalOperator>(child), std::string(""));
    }
  }
  return true;
}

bool LabelerASTVisitor::VisitDefaultStmt(DefaultStmt *S) {
  if (options.defaultLabel)
    labelAddRewriter.InsertText(S->getSubStmt()->getBeginLoc(), getNextLabel(), true,
                                true);
  return true;
}

void LabelerASTVisitor::LabelTernaryStmt(ConditionalOperator *ternaryStatement,
                                         std::string leftHandString) {
  labelAddRewriter.InsertText(ternaryStatement->getBeginLoc(), "if(", true,
                              true);
  labelAddRewriter.RemoveText(ternaryStatement->getQuestionLoc(), 1);
  labelAddRewriter.InsertText(ternaryStatement->getQuestionLoc(),
                              "){" + getNextLabel() + leftHandString, true,
                              true);
  labelAddRewriter.RemoveText(ternaryStatement->getColonLoc(), 1);
  labelAddRewriter.InsertText(ternaryStatement->getColonLoc(),
                              ";\n}else{" + getNextLabel() + leftHandString,
                              true, true);
  labelAddRewriter.InsertText(GetTrueEndLocation(ternaryStatement), "\n}", false,
                              true);
}

bool LabelerASTVisitor::VisitFunctionDecl(FunctionDecl *f) {
  // Only function with bodies should get labeled, not declarations.
  if (f->hasBody()) {
    LabelStatementAndAddBracesIfMissing(
        f->getBody(), options.functionStartLabel, options.functionEndLabel);
  }

  return true;
}