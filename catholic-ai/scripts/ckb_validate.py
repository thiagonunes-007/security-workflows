"""Valida o CKB: registro de fontes e arquivos em ckb/corpus/.

Falha (exit 1) se houver corpus de fonte desconhecida ou sem licença resolvida.
Uso: python -m scripts.ckb_validate
"""
import sys

from ckb.schema import CKB_DIR, load_passages, load_registry


def main() -> int:
    reg = load_registry()
    errors = []
    for f in sorted((CKB_DIR / "corpus").glob("*.jsonl")):
        sid = f.stem
        if sid not in reg:
            errors.append(f"{f.name}: fonte não registrada em sources.yaml")
            continue
        if not reg[sid].ingestable:
            errors.append(f"{f.name}: licença '{reg[sid].license_status}' não permite uso")
            continue
        try:
            n = len(load_passages(sid))
            print(f"OK  {sid}: {n} trechos")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{f.name}: {e}")
    pend = [s.id for s in reg.values() if s.license_status == "verificar"]
    print(f"Fontes com licença a verificar: {', '.join(pend) or '-'}")
    for e in errors:
        print("ERRO", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
