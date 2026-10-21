# BOM · Ürün ağacı

Aktif SolidWorks montajını okuyarak parça adetlerini, hiyerarşiyi ve ağırlıkları
çıkarır. Üretim dosyalarını değiştirmeden Excel çıktısı oluşturur.

- [exporter.py](exporter.py): montaj okuma, adet/ağırlık ve Excel motoru.
- [ui.py](ui.py): GOKWORKS içindeki Qt ekranı.
- [tests/](tests): motor ve SolidWorks sınırlarının regresyon testleri.
- [Ayrıntılı kullanım ve API sınırları](../../docs/bom.md).

Test: `python -m pytest modules/bom/tests`.
