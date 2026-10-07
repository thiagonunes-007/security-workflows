import pytest

from app import rag
from app.config import Settings
from ckb.languages import LANGUAGES, normalize_for_search
from ckb.schema import Source, load_registry


def test_nine_languages():
    assert set(LANGUAGES) == {"grc", "hbo", "la", "pt", "en", "it", "de", "es", "fr"}


def test_normalize_hebrew_and_greek():
    assert normalize_for_search("בְּרֵאשִׁ֖ית בָּרָ֣א", "hbo") == "בראשית ברא"
    assert normalize_for_search("Ἐν ἀρχῇ ἦν ὁ λόγος", "grc") == "εν αρχη ην ο λογοσ"
    assert normalize_for_search("In  principio\n erat", "la") == "In principio erat"


def test_registry_covers_every_language_and_rejects_unknown():
    reg = load_registry()
    assert {s.language for s in reg.values()} >= set(LANGUAGES)
    with pytest.raises(Exception):
        Source(id="x", title="x", authority="escritura", language="xx", license_status="livre")


class FakeCol:
    def get(self, where, limit):
        assert "John.3.16" in where["$and"][0]["canon_ref"]["$in"]
        return {
            "documents": ["εν αρχη", "dup"],
            "metadatas": [
                {"ref": "Jo 3,16", "source": "SBLGNT", "authority": "escritura",
                 "language": "grc", "canon_ref": "John.3.16", "original": "Ἐν ἀρχῇ"},
                {"ref": "Jo 3,16", "source": "DR", "canon_ref": "John.3.16", "language": "en"},
            ],
        }


def test_expand_aligned_adds_original_and_skips_duplicates():
    base = rag.Passage("For God so loved", "Jo 3,16", "DR", "escritura", 0.8, "John.3.16", "en")
    out = rag.expand_aligned(FakeCol(), [base], ["grc", "la"])
    assert len(out) == 1 and out[0].text == "Ἐν ἀρχῇ" and out[0].aligned
    assert "alinhado" in rag.format_sources([base, *out])
    assert rag.expand_aligned(FakeCol(), [base], []) == []
