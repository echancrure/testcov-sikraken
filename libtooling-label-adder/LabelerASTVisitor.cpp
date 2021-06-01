// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0



#include "LabelerASTVisitor.hpp"
#include "Includes.hpp"

LabelerASTVisitor::LabelerASTVisitor(Rewriter &R) : labelAddRewriter(R) {}

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
  SourceLocation beginPos;
  SourceLocation endPos;
  // Check if Braces are missing
  if (!isa<CompoundStmt>(processedStatement)) {
    AddBracesAroundStatement(processedStatement);
    beginPos = processedStatement->getBeginLoc();
    endPos = processedStatement->getEndLoc();
  } else {
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

void LabelerASTVisitor::LabelIfStmt(IfStmt *processedStatement) {
  Stmt *thenStatement = processedStatement->getThen();
  LabelStatementAndAddBracesIfMissing(thenStatement, ifLabel, false);
  Stmt *elseStatement = processedStatement->getElse();
  if (elseStatement) {
    LabelStatementAndAddBracesIfMissing(elseStatement, elseLabel, false);
  }
}

void LabelerASTVisitor::LabelCaseStmt(CaseStmt *processedStatement) {
  for (Stmt *child : processedStatement->children()) {
    if (isa<ConstantExpr>(child)) {
      labelAddRewriter.InsertText(GetTrueEndLocation(child), getNextLabel(),
                                  true, true);
    }
  }
}

void LabelerASTVisitor::LabelTernaryStmt(
    ConditionalOperator *ternaryStatement) {
  // TODO
  Expr *condition = ternaryStatement->getCond();
  labelAddRewriter.InsertText(ternaryStatement->getBeginLoc(), "/*cond-begin*/",
                              true, true);
  labelAddRewriter.InsertText(ternaryStatement->getEndLoc(), "/*cond-end*/",
                              true, true);

  Expr *truePart = ternaryStatement->getTrueExpr();
}

bool LabelerASTVisitor::VisitStmt(Stmt *s) {
  if (isa<IfStmt>(s)) {
    LabelIfStmt(cast<IfStmt>(s));
  } else if (isa<BinaryOperator>(s)) {
    Stmt *rightHandSide = cast<BinaryOperator>(s)->getRHS();
    if (isa<ConditionalOperator>(rightHandSide)) {
      LabelTernaryStmt(cast<ConditionalOperator>(s));
    }
  } else if (isa<CaseStmt>(s)) {
    LabelCaseStmt(cast<CaseStmt>(s));
  }

  return true;
}

bool LabelerASTVisitor::VisitFunctionDecl(FunctionDecl *f) {
  // Only function definitions (with bodies), not declarations.
  if (f->hasBody()) {
    LabelStatementAndAddBracesIfMissing(f->getBody(), functionStartLabel,
                                        functionEndLabel);
  }

  return true;
}