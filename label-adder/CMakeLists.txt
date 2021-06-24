set(LLVM_LINK_COMPONENTS support)

add_clang_tool(labeler
    LabelerMain.cpp

    LabelerASTConsumer.cpp
    LabelerASTVisitor.cpp
    LabelerFrontendAction.cpp
    LabelerFrontendActionFactory.cpp

    LabelerASTConsumer.hpp
    LabelerASTVisitor.hpp
    LabelerFrontendAction.hpp
    LabelerFrontendActionFactory.hpp
  )
target_link_libraries(labeler
  PRIVATE
  clangTooling
  clangBasic
  clangASTMatchers
  )
