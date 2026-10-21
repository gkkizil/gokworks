# ISO geçme toleransları

ISO 286 limitleri, delik/mil eşleştirmeleri ve mevcut manuel tolerans hesabı.

- [ui.py](ui.py): ISO ve manuel tolerans ekranı.
- [rules.py](rules.py), [manual.py](manual.py): ISO, manuel limit ve eşleştirme hesapları.
- [tables.json](tables.json): doğrulanmış sınıf/sapma verileri.
- [diagram.py](diagram.py), [selection_diagram.py](selection_diagram.py): çizimler.
- [tests/](tests): ISO, manuel hesap, tablo ve eşleştirme regresyonları.
- [Kullanım ve standart kapsamı](../../docs/iso-fits.md).

Test: `python -m pytest modules/iso_fits/tests`.
