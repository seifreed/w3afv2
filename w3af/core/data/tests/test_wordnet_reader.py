import unittest

from w3af.core.data.wordnet_reader import wn
from w3af.plugins.crawl.wordnet import wordnet


class TestWordNetReader(unittest.TestCase):
    def test_bundled_wordnet_relations(self):
        synset = wn.synsets("blue")[0]
        related = synset.hypernyms()[0].hyponyms()
        names = {item.name().split(".")[0] for item in related}

        self.assertEqual(
            names,
            {
                "orange",
                "brown",
                "green",
                "salmon",
                "pink",
                "red",
                "blue",
                "blond",
                "purple",
                "olive",
                "yellow",
                "pastel",
                "complementary_color",
            },
        )

    def test_search_normalizes_case_and_spaces(self):
        self.assertEqual(
            [synset.name().split(".")[0] for synset in wn.synsets("BLUE")],
            [synset.name().split(".")[0] for synset in wn.synsets("blue")],
        )
        self.assertEqual(wn.synsets("not_a_word"), [])

    def test_lemma_antonyms_and_member_holonyms(self):
        antonyms = {
            lemma.name()
            for synset in wn.synsets("good")
            for lemma in synset.lemmas()[0].antonyms()
        }
        holonyms = {
            holonym.name().split(".")[0]
            for synset in wn.synsets("tree")
            for holonym in synset.member_holonyms()
        }

        self.assertIn("bad", antonyms)
        self.assertIn("forest", holonyms)

    def test_crawler_keeps_wordnet_results(self):
        results = wordnet()._search_wn("blue")

        self.assertEqual(len(results), 5)
        self.assertIn("red", results)
