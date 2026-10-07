from scripts.convert_allioli_german import clean, parse


def test_clean_removes_footnote_marks_and_parallels():
    t = "Im Anfange¹ schuf² Gott³ Himmel und Erde.⁴ [Ps 32,6, Ps 135,5]"
    assert clean(t) == "Im Anfange schuf Gott Himmel und Erde."
    assert clean("Auge um Auge [Lev 24,20]. Ich aber") == "Auge um Auge. Ich aber"
    assert clean("Zahn um Zahn. [Lev 24,20].") == "Zahn um Zahn."
    assert clean("ein [Wort] bleibt") == "ein [Wort] bleibt"  # colchete sem número fica


def test_parse_keeps_only_verse_rows():
    tsv = "\n".join([
        "Genesis\tGen\t1\t1\t0\t\tEingang.\t",  # introdução do capítulo (8 campos)
        "Genesis\tGen\t1\t1\t1\tIn principio\tIm Anfange¹ schuf Gott.",  # versículo
        "Genesis\tGen\t1\t1\t1\t\t1\tNota de rodapé",  # rodapé (8 campos)
        "Psalmen\tPs\t23\t118\t\tAlleluja. ALEPH",  # título de salmo sem versículo numérico
    ])
    assert parse(tsv) == [("Gen", 1, 1, "Im Anfange schuf Gott.")]
