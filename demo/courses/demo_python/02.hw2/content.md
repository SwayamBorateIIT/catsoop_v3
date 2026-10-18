<question number>
csq_name = "range_len"
csq_display_name = "Length of a range"
csq_prompt = "How many numbers does `range(2, 10, 2)` produce?"
csq_soln = "4"
csq_npoints = 1
</question>

<question number>
csq_name = "loop_sum"
csq_display_name = "Loop accumulator"
csq_prompt = "After `t = 0` and `for i in range(5): t += i`, what is `t`?"
csq_soln = "10"
csq_npoints = 2
</question>

<question multiplechoice>
csq_name = "break_kw"
csq_display_name = "Leaving a loop early"
csq_prompt = "Which keyword exits a loop immediately?"
csq_options = ["continue", "pass", "break", "return"]
csq_soln = "break"
csq_npoints = 1
</question>

<question number>
csq_name = "nested"
csq_display_name = "Nested loops"
csq_prompt = "How many times does the body of `for i in range(3): for j in range(i): ...` run?"
csq_soln = "3"
csq_npoints = 3
</question>

<question bigbox>
csq_name = "reflection"
csq_display_name = "Reflection (manually graded)"
csq_prompt = "In a few sentences, explain when you would use a `while` loop instead of a `for` loop."
csq_grading_mode = "manual"
csq_npoints = 2
</question>
