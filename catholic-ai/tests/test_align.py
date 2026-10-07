from ckb.align import align


def flat(beads):
    return [(len(a), len(b)) for a, b in beads]


def test_identical_sequences_align_one_to_one():
    lens = [40, 90, 25, 60, 33, 75, 50, 44]
    beads = align(lens, [x * 2 for x in lens])
    assert all(a == b and len(a) == 1 for a, b in beads) and len(beads) == len(lens)


def test_split_and_merge_detected():
    a = [40, 90, 100, 25, 60, 33, 75]
    b = [80, 180, 100, 100, 50, 120, 66, 150]  # 3º verso de A partido em 2 de B
    assert (1, 2) in flat(align(a, b))
    assert (2, 1) in flat(align(b, a))


def test_large_insertion_needs_gap_beads():
    a = [60, 80, 50, 70, 90]
    b = a[:2] + [55, 85, 65, 75, 95, 45] * 8 + a[2:]  # bloco longo sem par (acréscimos gregos)
    beads = align(a, b)
    assert len(beads) >= len(a)  # termina sem erro mesmo com |A| << |B|
