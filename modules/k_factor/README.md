# K faktörü / yarıçap

GOKWORKS içindeki manuel K/R ataması ve bağımsız hesap yardımı.

- [ui.py](ui.py): kalınlık satırları, hesap yardımı ve montaj sonuçları.
- [rules.py](rules.py): sayısal veri modelleri ve BA/BD hesapları.
- [apply.py](apply.py): montaj/parça dolaşımı ve işlem yönetimi.
- [sheetmetal_parameters.py](sheetmetal_parameters.py): doğrudan SheetMetal parametre düzenleyicisi.
- [tooling_diagram.py](tooling_diagram.py): abkant üst/alt takım çizimi.
- [tests/](tests): atama, geri okuma, geri alma, COM sözleşmeleri ve Qt testleri.
- [Arşiv: examples/](https://github.com/gkkizil/gokworks/tree/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/modules/k_factor/examples): örnek görseller ve geçmiş doğrulama kayıtları.

Test: `python -m pytest modules/k_factor/tests`.
[Kullanım](../../docs/manual-k-radius.md) · [Algoritma ve sınırlar](../../docs/k-factor-radius.md).

## Montajda doğrudan Sac-Levha K/R ataması · konfigürasyon ve yeniden oluşturma

- Sac-Levha unsur verisi SolidWorks'te konfigürasyona özgü değildir. Atamadan önce
  aktif konfigürasyonla **aynı** K/R değerlerine sahip konfigürasyonlar (ör. çizim için
  türetilen `<konfigürasyon>SM-FLAT-PATTERN` / `SM-DÜZ-ÇOĞALTMA`) aynı K/R'yi alır ve
  raporda "ortak" olarak listelenir. Farklı değerli bir konfigürasyon değişirse atama
  geri alınır.
- `EditRebuild3` başarısız dönse bile, parçada atamadan **önce** de var olan unsur
  hataları (ör. kopuk taslak ilişkisi) atamayı engellemez; raporda not edilir. Atamayla
  yeni hata çıkan unsurlar adı ve hata koduyla raporlanır ve değişiklik geri alınır.
