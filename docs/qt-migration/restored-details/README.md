# Hesap ekranlarında geri getirilen ayrıntılar

2026-10-18 · `codex/pyside6-migration`

Qt ekranları önceki `5f01e53` sürümünün arayüz kaynaklarıyla karşılaştırıldı.
Eksilen açıklamalar ve cıvata kullanım çubuğu geri getirildi. Bu klasördeki
görseller gerçek Qt/X11 ekranlarından alınmıştır.

- Cıvata: güvenli/güvensiz/yük yok durumu, kapasite kullanım çubuğu, gerçek
  yüzde, yük marjı ve gerekli en az adet yeniden görünür. Çubuk dolsa da
  %100 üzerindeki gerçek kullanım metinde gösterilir. Geçersiz girişte eski
  güvenlik sonucu temizlenir.
- Cıvata: ölçü ve yük çizimi sekmeleri, son seçilen görünüm, teknik bilgi,
  tek başına ve birleşik yük sınırlarının açıklamaları korunur. Aynı metinler
  kopyalanan ve CSV olarak kaydedilen rapora da eklenir.
- ISO: boşluk/ara/sıkı geçme açıklamaları, sıfır minimum boşluk notu, sıkılık
  aralığı, örnek çaplar, tek taraflı fark ve şema açıklamaları geri getirildi.
  Montaj kesiti/tolerans bölgeleri ve en az/orta/en çok boşluk sekmeleri yeniden
  doğrudan şemanın yanında bulunur.
- Manuel ISO: üç sonuç sekmesi korunur. Tam/yakın eşleşme, eşit uzaklıktaki
  sınıflar, toplam/en büyük limit farkı, referans genişliği aşımı ve montaj
  değerlendirmesi eksiksiz gösterilir. Uzun metinler kaydırılabilir.
- Geometrik tolerans: anlam, ölçüm yöntemi, üretim notu ve ölçüm karşılaştırması
  ayrı kartlarda gösterilir. Datum, boyut toleransı, MMC zarfı ve tam sınırda
  ölçüm notları geri getirildi.

## Görseller

- [Arşiv: Cıvata güvenlik göstergesi](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/bolt-dark.png)
- [Arşiv: Cıvata yük çizimi](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/bolt-load-dark.png)
- [Arşiv: Kapasite aşımı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/bolt-overload-dark.png)
- [Arşiv: Birleşik yük](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/bolt-combined-dark.png)
- [Arşiv: Küçük pencere](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/bolt-compact-dark.png)
- [Arşiv: Açık tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/bolt-light.png)
- [Arşiv: ISO açıklamaları ve sekmeler](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/iso_fits-dark.png)
- [Arşiv: ISO açık tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/iso_fits-light.png)
- [Arşiv: Manuel ISO montaj değerlendirmesi](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/iso-manual-compatibility.png)
- [Arşiv: Manuel ISO ölçü sınırları](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/iso-manual-limits.png)
- [Arşiv: Manuel ISO karşılaştırması](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/iso-manual-comparison.png)
- [Arşiv: Geometrik tolerans açıklamaları](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/geometric_tolerances-dark.png)
- [Arşiv: Geometrik tolerans ölçüm değerlendirmesi](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/qt-migration/restored-details/gdt-assessment.png)

## Doğrulama

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_qt_workflows.py \
  -k 'bolt or iso or gdt or resolution' --timeout=60 --timeout-method=thread
```

60 test geçti; 59 ilgisiz test seçilmedi. 7 uyarı mevcut ezdxf/pyparsing
kullanımından gelir. Yük yok/güvenli/aşırı yük, geçersiz giriş, birimler,
kalite ve adım seçenekleri, manuel ISO referansları, ölçüm sınırı ve dört
pencere boyutu kapsanır. Son kompakt ISO düzeni ayrıca gerçek ekranlarda
görüntülendi. Hesap ve geometri motorları `5f01e53` ile aynı kalır.

Ekran alma sırasında iki tur dokuz menü geçişi de ölçüldü; bu makinenin
sonuçları [checks.json](checks.json) içindedir. Bunlar FPS veya Windows
performansı ölçümü değildir. Canlı SolidWorks bağlantısı kurulmadı.

Bu düzeltmede yeni EXE üretilmedi. Önceki Windows paketi bu arayüz
düzeltmesini içermez; kaynak kod ve güncel görseller bu daldadır.
