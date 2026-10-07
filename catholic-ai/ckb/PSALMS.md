# Numeração dos Salmos — mapeamento hebraico ↔ Vulgata

`canon_ref` usa a numeração da **Vulgata/LXX** (`Ps.22.1` = "Dominus pascit me"). Fontes hebraicas e a
maioria das traduções modernas usam a numeração hebraica (Sl 23). Código: `ckb/psalms.py`.

## Capítulos (exato, verificado)
| Hebraico | Vulgata |
|---|---|
| 1–8 | 1–8 |
| 9–10 | 9 (fundidos; Heb 10,1 = Vul 9,22) |
| 11–113 | 10–112 (Vul = Heb − 1) |
| 114–115 | 113 (Heb 115,1 = Vul 113,9) |
| 116 | 114 (v.1-9) e 115 (v.10-19) |
| 117–146 | 116–145 (Vul = Heb − 1) |
| 147 | 146 (v.1-11) e 147 (v.12-20) |
| 148–150 | 148–150 |

## Versículos
- **exato**: salmos 9–10, 114–115, 116, 147 — contagens fecham e as fronteiras foram conferidas no texto latino.
- **verificado** (lendo hebraico OSHB e latim): Vulgata 2, 4, 10, 12, 43 e 55, onde a divisão interna difere
  (título fundido ao v.1, versículos partidos ao meio, 1 hebraico ↔ 2 latinos). Podem ser 1→N ou N→1.
- **capitulo**: demais salmos. O capítulo está certo; o versículo é assumido igual e passou no teste de
  deslocamento. A heurística sinalizou Vulgata 13, 69, 94, 117 e 148; **li os cinco e são falsos
  positivos** (título latino mais longo; inserção longa de Sl 13,3 na Vulgata).

## Como foi verificado (reproduzível)
```bash
curl -sSLO https://raw.githubusercontent.com/openscriptures/morphhb/master/wlc/Ps.xml
python -m scripts.psalms_audit Ps.xml
```
Resultado: 2.527 versículos hebraicos, todos mapeados; nenhum versículo latino fica sem par; único
buraco é Vul 15,11 (vazio na fonte latina). Os testes cobrem cobertura nos dois sentidos e ida e volta.

## Limites (leia antes de confiar)
- A heurística de comprimento **pode deixar passar** deslocamentos pequenos em salmos "capitulo". Se um
  teólogo ou filólogo revisar o restante, acrescente em `OVERRIDES`.
- Divisões por meio-versículo são representadas como versículo → versículos (sobreposição), não como
  fronteira exata.
- A Vulgata Clementina tem acréscimos (ex.: Sl 13,3, de Rm 3) sem par no hebraico; o mapeamento os trata como o
  mesmo versículo.
- Outras tradições (Nova Vulgata, LXX de Rahlfs, traduções modernas) têm divisões próprias; cada nova fonte
  deve ser reauditada com `psalms_audit`.
