# ISO geçme toleransları

ISO 286 limitleri, delik/mil eşleştirmeleri ve mevcut manuel tolerans hesabı.

- [ui.py](ui.py): ISO ve manuel tolerans ekranı.
- [rules.py](rules.py), [manual.py](manual.py): ISO, manuel limit ve eşleştirme hesapları.
- [tables.json](tables.json): doğrulanmış sınıf/sapma verileri.
- [diagram.py](diagram.py): ISO ve manuel kontrolde ortak montaj kesiti ve tolerans bölgeleri.
  Önceki sade çizim [selection_diagram.py](selection_diagram.py) güncel arayüzde kullanılmaz.
- [tests/](tests): ISO, manuel hesap, tablo ve eşleştirme regresyonları.
- [Kullanım ve standart kapsamı](../../docs/iso-fits.md).

Test: `python -m pytest modules/iso_fits/tests`.

ISO seçimi ve manuel kontrol aynı çizimi kullanır: D/d çap okları, tek taraflı
g oku, boşluk/çakışma alanları ve seçilen örneğin sonuçları. Sınıf adları ve
sayısal değerler geçerli girdilerden alınır. Her iki yöntemde **Montaj kesiti /
Tolerans bölgeleri** ve **En az boşluk / Orta değer / En çok boşluk** korunur.
[Ekranlar ve arayüz doğrulaması](../../docs/ui-source-and-fit/README.md).
