import os

UNREACHED_LINE = "#####"
NO_COUNTABLE_PROGRAM_LINE = "-"


class TestCoverage:
    def __init__(self, file_name, test_vector, hit_counter_dic, lines_executed, branches_executed, branches_taken):
        self.filename = file_name
        self.test_vector = test_vector
        self.hit_counter_dic = hit_counter_dic
        self.lines_executed = lines_executed
        self.branches_executed = branches_executed
        self.branches_taken = branches_taken


def get_hit_counter_dic_from_gcov_file(filename):
    hit_counter_dic = {}
    with open(filename) as file:
        for line in file:
            line = line.strip()
            line = line.replace(" ", "")
            chunks = line.split(":")
            if len(chunks) == 1:
                continue
            hit_counter = chunks[0]
            countable_program_line = True
            if hit_counter == NO_COUNTABLE_PROGRAM_LINE:
                hit_counter = 0
                countable_program_line = False
            if hit_counter == UNREACHED_LINE:
                hit_counter = 0
            program_line = chunks[1]
            if program_line.isdigit() and int(program_line) > 0:
                if countable_program_line:
                    hit_counter_dic[int(program_line)] = int(hit_counter)
    return hit_counter_dic


def write_individual_test_coverages_to_output(outputdir, program, exec_results):
    hit_counter_file = os.path.join(outputdir, "individual-test-coverage")
    with open(hit_counter_file, "w") as outp:
        outp.write("Program: " + program + "\n\n")
        for test_coverage in exec_results.coverage_tests:
            outp.write(str(test_coverage.test_vector) + "\n")
            outp.write("Hit counter:" + "\n")
            for program_line, hit_counter in test_coverage.hit_counter_dic.items():
                outp.write(str(program_line) + ": " + str(hit_counter) + "\n")
            outp.write("Lines covered:" + test_coverage.lines_executed + "\n")
            outp.write("Branch conditions executed:" + test_coverage.branches_executed + "\n")
            outp.write("Branches covered:" + test_coverage.branches_taken + "\n\n")

        test_suite_hit_counter_dic = {}

        for test_coverage in exec_results.coverage_tests:
            for program_line in test_coverage.hit_counter_dic.keys():
                if not program_line in test_suite_hit_counter_dic:
                    test_suite_hit_counter_dic[program_line] = 0
                test_suite_hit_counter_dic[program_line] += test_coverage.hit_counter_dic[program_line]

        outp.write("Total Coverage" + "\n")
        outp.write("Hit counter:" + "\n")
        lines = 0
        covered_lines = 0
        for program_line, hit_counter in test_suite_hit_counter_dic.items():
            outp.write(str(program_line) + ": " + str(hit_counter) + "\n")
            lines += 1
            if hit_counter > 0:
                covered_lines += 1
        covered = 0
        if lines != 0:
            covered = 100 * float(covered_lines) / float(lines)
        outp.write("Lines covered:" + str(covered) + "%" + " (of " + str(lines) + ")")
        outp.close()
