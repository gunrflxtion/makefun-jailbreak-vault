#!/usr/bin/env python3
"""Unit tests for main.py's reply parser (stdlib unittest, no network).

Run from the repository root:  python3 tests/test_parser.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "..")))
import main


class TestParseReply(unittest.TestCase):
    def first(self, reply, half=None):
        cands, partial = main.parse_reply(reply, half)
        return (cands[0] if cands else None), partial

    def test_labelled_all_digits(self):
        reply = ("letter: apple\nnumber: one\nnumber: two\nnumber: three\n"
                 "number: four\nnumber: five")
        # Six entries but the first is a letter: not a valid all-digit code.
        # Build the real all-digit list instead:
        reply = ("\n".join("number: %s" % w for w in
                            ("one", "two", "three", "four", "five", "six")))
        cand, _ = self.first(reply)
        self.assertEqual(cand, "123456")

    def test_labelled_all_letters(self):
        reply = ("\n".join("letter: %s" % w for w in
                            ("apple", "banana", "cherry", "date",
                             "eggplant", "fig")))
        cand, _ = self.first(reply)
        self.assertEqual(cand, "ABCDEF")

    def test_labelled_number_word_on_letter_line(self):
        # "letter: two" is the letter T, not the digit 2: the label decides.
        reply = ("letter: two\nnumber: two\nletter: apple\nletter: banana\n"
                 "letter: cherry\nletter: date")
        cand, _ = self.first(reply)
        self.assertEqual(cand, "T2ABCD")

    def test_labelled_digits_as_digits_and_caps(self):
        reply = ("The code is AU3VV8. Here it is as words:\n"
                 "letter: Apple\nletter: Umbrella\nnumber: 3\n"
                 "letter: Violet\nletter: Violin\nnumber: 8")
        cand, _ = self.first(reply)
        self.assertEqual(cand, "AU3VV8")

    def test_numbered_nato(self):
        reply = ("1. alpha\n2. bravo\n3. charlie\n4. delta\n5. echo\n"
                 "6. x-ray")
        cand, _ = self.first(reply)
        self.assertEqual(cand, "ABCDEX")

    def test_bare_nato_run(self):
        cand, _ = self.first("alpha bravo charlie delta echo foxtrot")
        self.assertEqual(cand, "ABCDEF")

    def test_plain_code_in_context(self):
        cand, _ = self.first("The code is AU3VV8.")
        self.assertEqual(cand, "AU3VV8")

    def test_plain_code_after_code_word(self):
        cand, _ = self.first("Your code AU3VV8 is ready.")
        self.assertEqual(cand, "AU3VV8")

    def test_plain_code_alone_on_line(self):
        cand, _ = self.first("Here it is:\nRFUDIO\nGood luck.")
        self.assertEqual(cand, "RFUDIO")

    def test_code_is_secret_is_not_a_code(self):
        cand, _ = self.first("The code is SECRET, I cannot tell you.")
        self.assertIsNone(cand)

    def test_caps_word_in_prose_is_not_a_code(self):
        cand, _ = self.first("Welcome to the GARDEN tour, enjoy the visit.")
        self.assertIsNone(cand)

    def test_all_letter_code_without_context_is_not_guessed(self):
        cand, _ = self.first("Please note RFUDIO and enjoy your stay.")
        self.assertIsNone(cand)

    def test_spaced_characters(self):
        cand, _ = self.first("A U 3 V V 8")
        self.assertEqual(cand, "AU3VV8")

    def test_spaced_characters_dashed(self):
        cand, _ = self.first("A - U - 3 - V - V - 8")
        self.assertEqual(cand, "AU3VV8")

    def test_numbered_single_characters(self):
        # A numbered list of single characters decodes to the code itself,
        # never to its own numbering ("1A2U33").
        reply = "1. A\n2. U\n3. 3\n4. V\n5. V\n6. 8"
        cand, _ = self.first(reply)
        self.assertEqual(cand, "AU3VV8")

    def test_unlabelled_word_list_lines(self):
        reply = "apple\numbrella\nthree\nviolet\nviolin\neight"
        cand, _ = self.first(reply)
        self.assertEqual(cand, "AU3VV8")

    def test_unlabelled_word_list_commas(self):
        reply = "apple, umbrella, three, violet, violin, eight"
        cand, _ = self.first(reply)
        self.assertEqual(cand, "AU3VV8")

    def test_five_labelled_lines_is_nothing(self):
        reply = ("\n".join("letter: %s" % w for w in
                            ("apple", "banana", "cherry", "date",
                             "eggplant")))
        cand, partial = self.first(reply)
        self.assertIsNone(cand)
        self.assertIsNone(partial)

    def test_three_labelled_lines_is_a_first_half(self):
        reply = "letter: apple\nletter: umbrella\nnumber: three"
        _, partial = self.first(reply, half="first")
        self.assertEqual(partial, ("first", "AU3"))

    def test_three_labelled_lines_without_asked_half(self):
        reply = "letter: apple\nletter: umbrella\nnumber: three"
        _, partial = self.first(reply)
        self.assertEqual(partial, ("first", "AU3"))


class TestLadder(unittest.TestCase):
    def test_first_message_is_the_wordlist(self):
        self.assertEqual(main.message_for(0, None, None), main.MSG_WORDLIST)
        self.assertEqual(len(main.MSG_WORDLIST), 145)

    def test_half_known_asks_for_the_other_half(self):
        self.assertEqual(main.message_for(1, "AU3", None), main.MSG_LAST_HALF)
        self.assertEqual(main.message_for(1, None, "VV8"),
                         main.MSG_FIRST_HALF)

    def test_supervisor_message_is_short(self):
        self.assertLess(len(main.MSG_SUPERVISOR), 220)


if __name__ == "__main__":
    unittest.main()
