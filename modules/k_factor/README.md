# K faktörü / yarıçap

GOKWORKS içindeki manuel K/R ataması ve bağımsız hesap yardımı.

- [ui.py](ui.py): kalınlık satırları, hesap yardımı ve montaj sonuçları.
- [rules.py](rules.py): sayısal veri modelleri ve BA/BD hesapları.
- [apply.py](apply.py): montaj/parça dolaşımı ve işlem yönetimi.
- [sheetmetal_parameters.py](sheetmetal_parameters.py): doğrudan SheetMetal parametre düzenleyicisi.
- [tooling_diagram.py](tooling_diagram.py): abkant üst/alt takım çizimi.
- [tests/](tests): atama, geri okuma, geri alma, COM sözleşmeleri ve Qt testleri.
- [Arşiv: examples/](https://github.com/gkkizil/gokworks/tree/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/modules/k_factor/examples): örnek görseller ve geçmiş doğrulama kayıtları.
- [standalone/](standalone): kullanımdan kaldırılmış denemenin referans arşivi;
  ana uygulamanın çalışması veya EXE paketi için kullanılmaz.

Test: `python -m pytest modules/k_factor/tests`.
[Kullanım](../../docs/manual-k-radius.md) · [Algoritma ve sınırlar](../../docs/k-factor-radius.md).
