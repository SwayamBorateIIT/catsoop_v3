<question number>
csq_name = "default_arg"
csq_display_name = "Default arguments"
csq_prompt = "Given `def f(x, y=3): return x * y`, what is `f(4)`?"
csq_soln = "12"
csq_npoints = 2
</question>

<question multiplechoice>
csq_name = "return_none"
csq_display_name = "Implicit return"
csq_prompt = "What does a function without a `return` statement return?"
csq_options = ["0", "None", "False", "an error"]
csq_soln = "None"
csq_npoints = 1
</question>

<question number>
csq_name = "recursion"
csq_display_name = "Recursion"
csq_prompt = "Given `def g(n): return 1 if n <= 1 else n * g(n - 1)`, what is `g(4)`?"
csq_soln = "24"
csq_npoints = 3
</question>
