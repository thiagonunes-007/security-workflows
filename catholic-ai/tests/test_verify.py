from ckb.verify import agrees, filter_alignments, greek_key, latin_key


def test_name_skeletons_match_across_scripts():
    assert greek_key("Ἰσραήλ") == latin_key("Israël") == "srl"
    assert greek_key("Ἱερουσαλήμ")[:3] == latin_key("Jerusalem")[:3]
    assert greek_key("Ἀβραάμ")[:3] == latin_key("Abraham")[:3]


def test_agrees_uses_names_and_ignores_sentence_starts_and_theology_words():
    assert agrees("ὁ Ἰησοῦς εἰς Ἱερουσαλήμ", "Ascendit Jesus in Jerusalem.") is True
    assert agrees("ὁ Ἰησοῦς εἰς Ἱερουσαλήμ", "Et ibat Paulus in Antiochiam.") is False
    assert agrees("καὶ ὁ κύριος", "Dominus dixit. Deus et Spiritus") is None  # sem nomes próprios
    assert agrees("Jérusalem et Israël", "Et venit in Jerusalem et Israel", script="latin") is True


def _row(i, ref, text, label="identico"):
    return {"canon_ref": ref, "canon_ref_2": "", "align": label, "text": text, "ref": str(i)}


def test_filter_drops_unsupported_labels_and_failing_books():
    lat = {}
    rows = []
    for i in range(12):  # livro bom: 'identico' concorda; 'deslocado' falha
        lat[f"Gen.1.{i}"] = "Venit Abraham in Aegyptum."
        rows.append(_row(i, f"Gen.1.{i}", "ὁ Ἀβραὰμ εἰς Αἴγυπτον"))
        lat[f"Gen.2.{i}"] = "Venit Abraham in Aegyptum."
        rows.append(_row(i, f"Gen.2.{i}", "ὁ Μωϋσῆς εἰς Μαδιάμ", "deslocado"))
    for i in range(12):  # livro ruim: 'identico' não concorda
        lat[f"Job.1.{i}"] = "Venit Abraham in Aegyptum."
        rows.append(_row(i, f"Job.1.{i}", "ὁ Μωϋσῆς εἰς Μαδιάμ"))
    out, rep = filter_alignments(rows, lat)
    kept = {r["canon_ref"] for r in out if r["canon_ref"]}
    assert all(f"Gen.1.{i}" in kept for i in range(12))
    assert not any(k.startswith(("Gen.2", "Job")) for k in kept)
    assert rep["dropped"] == 24
