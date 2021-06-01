// This file is part of TestCov,
// a robust test executor with reliable coverage measurement:
// https://gitlab.com/sosy-lab/software/test-suite-validator/
//
// SPDX-FileCopyrightText: 2021 Dirk Beyer <https://www.sosy-lab.org>
//
// SPDX-License-Identifier: Apache-2.0



#include "Includes.hpp"

#ifndef LABELER_AST_VISITOR_HPP
#define LABELER_AST_VISITOR_HPP

class LabelerASTVisitor : public RecursiveASTVisitor<LabelerASTVisitor> {
private:
  int goalCounter = 0;

public:
  LabelerASTVisitor(Rewriter &R);

  bool ternaryTrueLabel, ternaryFalseLabel, functionStartLabel,
      functionEndLabel, caseLabel, ifLabel, elseLabel = true;

  std::string getNextLabel();

  // The getEndLoc Method leaves us with the position of the first character
  // from the last token before the semicolon or normal colon of a Statement.
  // As it is currently implemented in Libtooling, the (semi)colon itself is
  // not being part of a statement. Might be source for failure,
  // if that gets changed in later LLVM releases. This Method returns the
  // SourceLocation, where the Statement really ends.
  SourceLocation GetTrueEndLocation(Stmt *fromStatement);

  // This Method transforms a Statement to a compound statement, if it is not
  // one already.
  void AddBracesAroundStatement(Stmt *processedStatement);

  // This Method adds a Label at the begin of a statement, if beginLabel is set.
  // And a Label at the end if endLabel is set. It also transforms a statement,
  // to a compound statement, if it is a one-liner with missing braces.
  void LabelStatementAndAddBracesIfMissing(Stmt *processedStatement,
                                           bool beginLabel, bool endLabel);


  void LabelIfStmt(IfStmt *processedStatement);

  void LabelCaseStmt(CaseStmt *processedStatement);

  void LabelTernaryStmt(ConditionalOperator *ternaryStatement);

  bool VisitStmt(Stmt *s);

  bool VisitFunctionDecl(FunctionDecl *f);

private:
  Rewriter &labelAddRewriter;
};

#endif