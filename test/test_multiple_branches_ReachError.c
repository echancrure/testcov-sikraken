extern char __VERIFIER_nondet_char();

void reach_error() {}

int main() {
  char a = __VERIFIER_nondet_char();
  char b = __VERIFIER_nondet_char();
  char c = __VERIFIER_nondet_char();
  if (c == 16) {
    c = __VERIFIER_nondet_char();
    if (a == 'a' && b == 5) {
        reach_error();
    }
  }

}