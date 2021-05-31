#include "Includes.hpp"
#include "LabelerASTConsumer.hpp"

LabelerASTConsumer::LabelerASTConsumer(Rewriter &R) : Visitor(R) {}

bool LabelerASTConsumer::HandleTopLevelDecl(DeclGroupRef DR) {
  for (DeclGroupRef::iterator b = DR.begin(), e = DR.end(); b != e; ++b) {
    // Traverse the declaration using our AST visitor.
    Visitor.TraverseDecl(*b);
    (*b)->dump();
  }
  return true;
}