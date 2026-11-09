import importlib.util
import pathlib
import unittest

SPEC = importlib.util.spec_from_file_location("entry", pathlib.Path(__file__).parents[1] / "main.py")
entry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(entry)


class ParserTests(unittest.TestCase):
    def test_labelled_digit_names(self):
        self.assertEqual(entry.parse_reply("letter: apple\nnumber: three\nletter: violet\nletter: violet\nnumber: eight\nletter: dog")[0], ["A3VV8D"])

    def test_letter_line_number_word_initial(self):
        self.assertEqual(entry.parse_reply("letter: two\nletter: apple\nletter: cat\nletter: dog\nletter: elm\nletter: flower")[0], ["TACDEF"])

    def test_numbered_nato(self):
        self.assertEqual(entry.parse_reply("1. alpha\n2. three\n3. bravo\n4. charlie\n5. delta\n6. echo")[0], ["A3BCDE"])

    def test_nato_run(self):
        self.assertEqual(entry.parse_reply("alpha bravo charlie delta echo foxtrot")[0], ["ABCDEF"])

    def test_plain_code(self):
        self.assertEqual(entry.parse_reply("The code is AU3VV8.")[0], ["AU3VV8"])

    def test_spaced_characters(self):
        self.assertEqual(entry.parse_reply("A-U-3-V-V-8")[0], ["AU3VV8"])

    def test_unlabeled_lines(self):
        self.assertEqual(entry.parse_reply("apple\numbrella\nthree\nviolet\nviolin\neight")[0], ["AU3VV8"])

    def test_half_handling(self):
        self.assertEqual(entry.parse_reply("letter: apple\nnumber: three\nletter: violet", "first"), ([], ("first", "A3V")))

    def test_half_last_when_requested(self):
        self.assertEqual(entry.parse_reply("letter: violet\nletter: violin\nnumber: eight", "last"), ([], ("last", "VV8")))

    def test_stopword_is_not_code(self):
        self.assertEqual(entry.parse_reply("SECRET"), ([], None))

    def test_bare_all_letter_code_not_trusted_in_chatter(self):
        self.assertEqual(entry.parse_reply("The answer might be ABCDEF today."), ([], None))

    def test_bare_digit_code_trusted(self):
        self.assertEqual(entry.parse_reply("Maybe 123456 is a clue."), (["123456"], None))

    def test_message_initial(self):
        self.assertIn("6 lines", entry.message_for(1, None, None))

    def test_supervisor_message(self):
        self.assertIn("supervisor", entry.message_for(2, None, None))

    def test_missing_tail_adaptive(self):
        self.assertIn("last 3", entry.message_for(3, "A1B", None))

    def test_missing_head_adaptive(self):
        self.assertIn("first 3", entry.message_for(4, None, "C2D"))

    def test_prompt_ladder_plain_retry(self):
        self.assertIn("once more", entry.message_for(6, None, None))

    def test_plain_list_comma_separated(self):
        self.assertEqual(entry.parse_reply("apple, umbrella, three, violet, violin, eight")[0], ["AU3VV8"])

    def test_numbered_lines_not_spaced_code(self):
        self.assertEqual(entry.parse_reply("1. A\n2. U\n3. 3\n4. V\n5. V\n6. 8"), ([], None))

    def test_nato_aliases(self):
        self.assertEqual(entry.parse_reply("alfa x-ray whisky niner zero two")[0], ["AXW902"])

    def test_stopword_after_code_label(self):
        self.assertEqual(entry.parse_reply("The code is SECRET."), ([], None))

    def test_labelled_single_digit(self):
        self.assertEqual(entry.parse_reply("number: 1\nnumber: 2\nnumber: 3\nnumber: 4\nnumber: 5\nnumber: 6")[0], ["123456"])

    def test_different_spaced_separators_rejected(self):
        self.assertEqual(entry.parse_reply("A-U.3-V-V-8"), ([], None))


if __name__ == "__main__":
    unittest.main()
