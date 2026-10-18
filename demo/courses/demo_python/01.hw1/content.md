<question number>
csq_name = "int_div"
csq_display_name = "Integer division"
csq_prompt = "What does `7 // 2` evaluate to?"
csq_soln = "3"
csq_npoints = 1
</question>

<question multiplechoice>
csq_name = "type_of"
csq_display_name = "Type of a literal"
csq_prompt = "What is the type of `3.0`?"
csq_options = ["int", "float", "str", "bool"]
csq_soln = "float"
csq_npoints = 1
</question>

<question smallbox>
csq_name = "concat"
csq_display_name = "String concatenation"
csq_prompt = "What does `'ab' + 'cd'` evaluate to? (no quotes)"
csq_soln = "abcd"
csq_check_function = lambda sub, sol: sub.strip().strip("'\"") == sol
csq_npoints = 2
</question>

<question number>
csq_name = "modulo"
csq_display_name = "Modulo"
csq_prompt = "What does `17 % 5` evaluate to?"
csq_soln = "2"
csq_npoints = 1
</question>
