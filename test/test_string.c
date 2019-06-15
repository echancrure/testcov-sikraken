extern const char * __VERIFIER_nondet_string();
extern void __VERIFIER_error();

int main() {
  char * s = __VERIFIER_nondet_string();
  printf("%s\n", s);
  if (strcmp(s, "Required value") == 0) {
    __VERIFIER_error();
  }
}
