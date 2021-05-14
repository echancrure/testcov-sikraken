set(LLVM_LINK_COMPONENTS support)

add_clang_executable(if-tool
  IfTool.cpp
  )
target_link_libraries(if-tool
  PRIVATE
  clangTooling
  clangBasic
  clangASTMatchers
  )
