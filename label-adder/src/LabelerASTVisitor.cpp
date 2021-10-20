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
  if (isa<NullStmt>(fromStatement)) {
    return fromStatement->getEndLoc().getLocWithOffset(1);
  }
  if (isa<IfStmt>(fromStatement)) {
    IfStmt *ifStmt = cast<IfStmt>(fromStatement);
    if (ifStmt->getElse()) {
      fromStatement = ifStmt->getElse();
    } else {
      fromStatement = ifStmt->getThen();
    }
  } else if (isa<WhileStmt>(fromStatement)) {
    fromStatement = cast<WhileStmt>(fromStatement)->getBody();
  } else if (isa<ForStmt>(fromStatement)) {
    fromStatement = cast<ForStmt>(fromStatement)->getBody();
  }
  if (isa<CompoundStmt>(fromStatement)) {
    // the final decision of the if-statement is a compound statement with
    // curly braces, so we return the location at its closing }. Example 1: if
    // (p) {
    //  x++;
    // }
    // ^ this is returned
    //
    // Example 2:
    // if (p) {
    //  x++;
    // } else {
    //  y++;
    // }
    // ^ this is returned
    Optional<Token> nextToken = getNextToken(fromStatement->getEndLoc());
    assert(nextToken->is(tok::r_brace));
    return nextToken->getLocation();
  }
  Optional<Token> nextToken = getNextToken(fromStatement->getEndLoc());
  if (nextToken->is(tok::semi)) {
    return nextToken->getEndLoc();
  }
  return fromStatement->getEndLoc();
}

Optional<Token> LabelerASTVisitor::getNextToken(SourceLocation fromLocation) {
  return Lexer::findNextToken(fromLocation, labelAddRewriter.getSourceMgr(),
                              labelAddRewriter.getLangOpts());
}

void LabelerASTVisitor::AddBracesAroundStatement(Stmt *processedStatement) {
  if (isa<CompoundStmt>(processedStatement))
    return;
  // We have to use InsertTextBefore so in case
  // other code was written at the same location already,
  // the braces will be put around that written code
  labelAddRewriter.InsertTextBefore(processedStatement->getBeginLoc(), "{\n");
  // We need to add the closing brace after the semicolon, therefore we need
  // to calculate the semicolons position.
  SourceLocation afterSemicolonLocation =
      GetTrueEndLocation(processedStatement);
  labelAddRewriter.InsertTextAfter(afterSemicolonLocation, "\n}\n");
}

void LabelerASTVisitor::LabelStatement(Stmt *processedStatement,
                                       bool beginLabel, bool endLabel) {
  // Return instantly, if no labels to add
  if (!(beginLabel || endLabel)) {
    return;
  }
  if (isa<NullStmt>(processedStatement)) {
    labelAddRewriter.RemoveText(SourceRange(processedStatement->getBeginLoc(),
                                            processedStatement->getEndLoc()));
    labelAddRewriter.InsertTextAfter(processedStatement->getBeginLoc(),
                                     getNextLabel());
    return;
  }
  SourceLocation beginPos;
  SourceLocation endPos;
  // Check if Braces are missing
  if (isa<CompoundStmt>(processedStatement)) {
    // If braces are already there, beginLoc leaves us with the position
    // before the brace, so we have to offset by 1
    // The reverse applies to the closing brace, so we offset by -1
    beginPos = processedStatement->getBeginLoc().getLocWithOffset(1);
    endPos = processedStatement->getEndLoc().getLocWithOffset(-1);
  } else {
    beginPos = processedStatement->getBeginLoc();
    endPos = processedStatement->getEndLoc();
  }
  if (beginLabel) {
    labelAddRewriter.InsertTextAfter(beginPos, getNextLabel());
  }
  if (endLabel) {
    labelAddRewriter.InsertTextAfter(endPos, getNextLabel());
  }
}

void LabelerASTVisitor::LabelStatementAndAddBracesIfMissing(
    Stmt *processedStatement, bool beginLabel, bool endLabel) {
  LabelStatement(processedStatement, beginLabel, endLabel);
  if (!isa<CompoundStmt>(processedStatement) &&
      !isa<NullStmt>(processedStatement)) {
    AddBracesAroundStatement(processedStatement);
  }
}

bool LabelerASTVisitor::VisitIfStmt(IfStmt *S) {
  Stmt *thenStatement = S->getThen();
  LabelStatementAndAddBracesIfMissing(thenStatement, options.ifLabel, false);
  Stmt *elseStatement = S->getElse();
  if (elseStatement) {
    if (isa<IfStmt>(elseStatement) ||
        (isa<LabelStmt>(elseStatement) &&
         isa<IfStmt>(cast<LabelStmt>(elseStatement)->getSubStmt()))) {
      return true;
    }
    LabelStatementAndAddBracesIfMissing(elseStatement, options.elseLabel,
                                        false);
  } else if (options.elseLabel) {
    SourceLocation endLoc = GetTrueEndLocation(S);
    labelAddRewriter.InsertTextAfter(endLoc, " else { " + getNextLabel() + "}");
  }
  return true;
}

bool LabelerASTVisitor::VisitWhileStmt(WhileStmt *S) {
  LabelStatementAndAddBracesIfMissing(S->getBody(), options.ifLabel, false);
  SourceLocation afterLoop = GetTrueEndLocation(S->getBody());
  if (options.elseLabel) {
    labelAddRewriter.InsertTextAfter(afterLoop, getNextLabel());
  }
  return true;
}

bool LabelerASTVisitor::VisitDoStmt(DoStmt *S) {
  SourceLocation afterLoop = GetTrueEndLocation(S);
  if (options.elseLabel) {
    labelAddRewriter.InsertTextAfter(afterLoop, getNextLabel());
  }
  return true;
}

bool LabelerASTVisitor::VisitForStmt(ForStmt *S) {
  LabelStatementAndAddBracesIfMissing(S->getBody(), options.ifLabel, false);
  SourceLocation afterLoop = GetTrueEndLocation(S->getBody());
  if (options.elseLabel) {
    labelAddRewriter.InsertTextAfter(afterLoop, getNextLabel());
  }
  return true;
}

bool LabelerASTVisitor::VisitCaseStmt(CaseStmt *S) {
  if (options.caseLabel) {
    LabelStatement(S->getSubStmt(), true, false);
  }
  return true;
}

bool LabelerASTVisitor::VisitConditionalOperator(ConditionalOperator *S) {
  if (!(options.ternaryTrueLabel || options.ternaryFalseLabel)) {
    return true;
  }

  {
    SourceLocation beginOfTrueExpr = S->getTrueExpr()->getBeginLoc();
    labelAddRewriter.InsertTextBefore(beginOfTrueExpr, "({" + getNextLabel());
    SourceLocation endOfTrueExpr = S->getTrueExpr()->getEndLoc();
    labelAddRewriter.InsertTextAfterToken(endOfTrueExpr, ";})");
  }
  {
    SourceLocation beginOfFalseExpr = S->getFalseExpr()->getBeginLoc();
    labelAddRewriter.InsertTextBefore(beginOfFalseExpr, "({" + getNextLabel());
    SourceLocation endOfFalseExpr = S->getFalseExpr()->getEndLoc();
    labelAddRewriter.InsertTextAfterToken(endOfFalseExpr, ";})");
  }
  return true;
}

bool LabelerASTVisitor::VisitDefaultStmt(DefaultStmt *S) {
  if (options.defaultLabel) {
    LabelStatement(S->getSubStmt(), true, false);
  }

  return true;
}

bool LabelerASTVisitor::VisitFunctionDecl(FunctionDecl *f) {
  // Only function with bodies should get labeled, not declarations.
  // maybe we have to replace this check for hashBody() with a check for
  // isThisDeclarationADefinition() in the future. But this would mean that we
  // have to do more special handling for function definitions without a body.
  if (f->hasBody()) {
    bool labelFunctionStart = options.functionStartLabel;
    if (!options.functionCall.empty()) {
      labelFunctionStart |= options.functionCall == f->getName().str();
    }
    LabelStatementAndAddBracesIfMissing(f->getBody(), labelFunctionStart,
                                        false);
  }

  return true;
}