"""Read the bundled WordNet 3.0 database for the crawl plugin."""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from zipfile import ZipFile

from w3af import ROOT_PATH


@dataclass(frozen=True)
class _Pointer:
    symbol: str
    target: tuple[str, int]
    source_word: int
    target_word: int


class _Lemma:
    def __init__(self, synset, index):
        self.synset = synset
        self.index = index

    def name(self):
        return self.synset.words[self.index]

    def antonyms(self):
        return [
            lemma
            for pointer in self.synset.pointers
            if pointer.symbol == "!" and pointer.source_word in (0, self.index + 1)
            for lemma in self.synset.reader._synsets[pointer.target].lemmas()
            if pointer.target_word in (0, lemma.index + 1)
        ]


class _Synset:
    def __init__(self, reader, key, words, pointers):
        self.reader = reader
        self.key = key
        self.words = words
        self.pointers = pointers

    def name(self):
        return f"{self.words[0]}.{self.key[0]}.{self.key[1]}"

    def lemmas(self):
        return [_Lemma(self, index) for index in range(len(self.words))]

    def hypernyms(self):
        return self._related("@")

    def hyponyms(self):
        return self._related("~")

    def member_holonyms(self):
        return self._related("#m")

    def _related(self, *symbols):
        return [
            self.reader._synsets[pointer.target]
            for pointer in self.pointers
            if pointer.symbol in symbols
        ]


class WordNetReader:
    """Expose the WordNet relations consumed by the crawl plugin."""

    def __init__(self, database=None):
        self.database = database or (
            Path(ROOT_PATH) / "plugins" / "crawl" / "wordnet" / "wordnet.zip"
        )
        self._index = {}

    @cached_property
    def _synsets(self):
        records: dict[tuple[str, int], tuple[tuple[str, ...], tuple[_Pointer, ...]]] = (
            {}
        )
        indexes: dict[str, list[tuple[str, int]]] = {}
        with ZipFile(self.database) as archive:
            for pos, filename in (
                ("n", "noun"),
                ("v", "verb"),
                ("a", "adj"),
                ("r", "adv"),
            ):
                for line in (
                    archive.read(f"wordnet/index.{filename}").decode().splitlines()
                ):
                    if not line or line.startswith(" "):
                        continue
                    fields = line.split()
                    pointer_count = int(fields[3])
                    first_offset = 6 + pointer_count
                    indexes.setdefault(fields[0], []).extend(
                        (pos, int(offset)) for offset in fields[first_offset:]
                    )

                for line in (
                    archive.read(f"wordnet/data.{filename}").decode().splitlines()
                ):
                    if not line or line.startswith(" "):
                        continue
                    fields = line.partition("|")[0].split()
                    offset = int(fields[0])
                    word_count = int(fields[3], 16)
                    words = tuple(fields[4 + index * 2] for index in range(word_count))
                    pointer_start = 4 + word_count * 2
                    pointer_count = int(fields[pointer_start])
                    pointers: list[_Pointer] = []
                    for index in range(pointer_count):
                        start = pointer_start + 1 + index * 4
                        symbol, target_offset, target_pos, word_indexes = fields[
                            start : start + 4
                        ]
                        pointers.append(
                            _Pointer(
                                symbol,
                                (
                                    "a" if target_pos == "s" else target_pos,
                                    int(target_offset),
                                ),
                                int(f"0x{word_indexes[:2]}", base=0),
                                int(f"0x{word_indexes[2:]}", base=0),
                            )
                        )
                    records[(pos, offset)] = (words, tuple(pointers))

        synsets = {
            key: _Synset(self, key, words, pointers)
            for key, (words, pointers) in records.items()
        }
        self._index = indexes
        return synsets

    def synsets(self, word):
        normalized = word.lower().replace(" ", "_")
        synsets = self._synsets
        return [
            synsets[(pos, offset)] for pos, offset in self._index.get(normalized, ())
        ]


wn = WordNetReader()
