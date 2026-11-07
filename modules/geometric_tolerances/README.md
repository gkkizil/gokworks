# Geometrik toleranslar

GD&T eğitim kataloğu, datum ilişkileri, belirtim kontrolleri ve bölge şemaları.

- [ui.py](ui.py): Qt ekranı (tür → çerçeve → isteğe bağlı ölçüm kontrolü).
- [catalog_view.py](catalog_view.py): sembollü, gruplu tür listesi; semboller `diagram.symbol` çiziminden.
- [catalog.py](catalog.py): açıklamalar, kullanım ve ölçüm notları.
- [rules.py](rules.py): belirtim/doğrulama kuralları.
- [diagram.py](diagram.py): tolerans bölgesi çizimleri.
- [tests/](tests): katalog, hesap ve çizim regresyonları.
- [Kullanım ve ASME/ISO sınırları](../../docs/geometric-tolerances.md).

Test: `python -m pytest modules/geometric_tolerances/tests` (`test_gdt_gui.py`: sayfa düzeni, alan hataları, çerçeve).
