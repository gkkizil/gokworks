# Cıvata hesabı

SolidWorks gerektirmeyen statik cıvata gövdesi kontrolü. [Kullanım ve hesap yöntemi](../../docs/bolt-calculator.md).

## GitHub referans incelemesi — 14 Ekim 2026

Projelerin aşağıdaki sürümlerindeki gerçek kaynak dosyaları ve açıklamaları incelendi. Üçüncü taraf kodu veya bağımlılık uygulamaya eklenmedi; mevcut hesap yönteminden türetilen ek sonuçlar özgün olarak yazıldı.

| Proje ve incelenen sürüm | İncelenen konu | GOKWORKS’e etkisi |
| --- | --- | --- |
| [misams/BAT](https://github.com/misams/BAT/tree/6f39c08201bba0f4034c281c5a22f8d9927bc0a9), GPL-3.0 | [ECSS hesapları](https://github.com/misams/BAT/blob/6f39c08201bba0f4034c281c5a22f8d9927bc0a9/BAT/src/Ecss.py): ön sıkma dağılımı, rijitlik, kayma, bağlantının açılması ve ayrı dayanım marjları; [metrik geometri](https://github.com/misams/BAT/blob/6f39c08201bba0f4034c281c5a22f8d9927bc0a9/BAT/db/ISO4014_4017_hex_metric.bolt) | Sonuç cıvata gövdesinin ön kontrolü olarak açıklandı. Ön sıkma ve bağlantının açılması dayanımla karıştırılmadı. Çekme alanı ve temel diş kökü geometrisi karşılaştırıldı. |
| [tpw809/ranf_thread_fast](https://github.com/tpw809/ranf_thread_fast/tree/0f7103b48173d495dc4daf6e22f549606d8ac638), MIT | [NASA-STD-5020B denklemleri](https://github.com/tpw809/ranf_thread_fast/blob/0f7103b48173d495dc4daf6e22f549606d8ac638/src/thread_fast/nasa_std_5020/nasa_std_5020b.py), [malzeme modeli](https://github.com/tpw809/ranf_thread_fast/blob/0f7103b48173d495dc4daf6e22f549606d8ac638/src/thread_fast/materials/material_class.py): kapasite/talep − 1 biçiminde marj ve von Mises ilişkisi | Seçili `Sp/s` sınırına göre yük marjı eklendi. Bu sonuç NASA akma/kopma marjı veya standarda uygunluk iddiası taşımaz. |
| [StephanoisMineur/bolt-analysis](https://github.com/StephanoisMineur/bolt-analysis/tree/1578baacfe0edb34b529179dbfec347a0a05a50d), MPL-2.0 | [Kaynak](https://github.com/StephanoisMineur/bolt-analysis/blob/1578baacfe0edb34b529179dbfec347a0a05a50d/main.py): ön sıkma, tork, sürtünme, sıcaklık ve bağlantı rijitliği girdileri | Bu değerlerin yalnız çap ve kalite seçimiyle belirlenemeyeceği görüldü. Mevcut ekrana tahmini ön sıkma/tork ataması eklenmedi. |

BAT’ın sıkma sırasında kullandığı burulma gerilmesi, ekranımızdaki dış kesme kuvvetinin gerilmesiyle aynı değildir. BAT’taki akma/kopma dayanımları da burada kullanılan ISO deney yükü gerilmesi `Sp` ile değiştirilmedi. Mevcut muhafazakâr `Sp/s` ve von Mises ön kontrolünde, belirtilen kapsam içinde sayısal hata doğrulanmadı.

## Uygulanan sonuçlar

- **Yük marjı:** `1/kullanım − 1`. Pozitif değer, çekme ve kesme birlikte aynı oranda artırıldığında seçili sınırın ne kadar uzakta olduğunu gösterir. Örneğin kullanım %50 ise marj +%100’dür. Negatif değer sınırın aşıldığını gösterir; yük yoksa marj verilmez.
- **Gerekli en az adet:** Tek cıvataya ait eşdeğer gerilmenin `Sp/s` sınırına oranı yukarı yuvarlanır. Tam sayı sınırı, mevcut güvenli/güvensiz hesabıyla tekrar karşılaştırılır. Adet eşit yük paylaşımı içindir; otomatik değiştirilmez. Gereksinim 1000’i aşıyorsa giriş sınırı açıkça bildirilir.
- **Birleşik yük sınırları:** Mevcut kesme sabitken toplam çekme sınırı ve mevcut çekme sabitken toplam kesme sınırı, aynı von Mises etkileşiminden hesaplanır. Bu değerler eklenebilecek yük değildir ve birlikte kullanılacak yeni bir kuvvet çifti oluşturmaz. Diğer kuvvet tek başına sınırı aşıyorsa geçerli sınır yoktur.
- **Pano raporu:** Bu sonuçları, birimleri ve hesap varsayımlarını içerir.

Örnek: M10 / 8.8 / emniyet 2 / tek kesme / dişli kesitte toplam 12 kN çekme ve 8 kN kesme için bir cıvata sınırı aşar. Aynı varsayımlarla gerekli en az adet 2’dir. Bağlantı plakaları, somun/diş sıyırması, ön sıkma, eksantriklik ve yorulma bu öneriyle doğrulanmış sayılmaz.

## Ölçü çizimi için ek karşılaştırma

### İnce diş

`Diş türü` ve `Diş adımı (mm)` seçimi eklendi. M3–M39 için sunulan ince adımlar
[BAT ince diş geometri tablosu](https://github.com/misams/BAT/blob/6f39c08201bba0f4034c281c5a22f8d9927bc0a9/BAT/db/ISO8765_8676_hex_metric_fine.bolt) ile karşılaştırıldı;
M33×2 ve M39×3 ayrıca [FreeCAD ISO 262 tablosunda](https://github.com/shaise/FreeCAD_FastenersWB/blob/fddd07af422b7d3a69098b32333711c5eeae184c/FsData/iso262def.csv) doğrulandı.
Bu seçki bütün adımların ISO 8676 kapsamında piyasada bulunabilir altıgen başlı
cıvatalar olduğu anlamına gelmez. Baş çizimi ince modunda temsili olarak etiketlenir.
Formül ve yaklaşık `d − P` deliği seçili adımı kullanır. Malzeme sınırları,
ince dişe özgü deney yükü tablosu ayrıca doğrulanana kadar mevcut muhafazakâr
sınırlar olarak korunur; ayrıntı [hesap yönteminde](../../docs/bolt-calculator.md).

Adım seçiminde kaba değer **Standart**, ISO 262 tablosunda seçili ince değerler
**ISO 262**, diğer sunulan ince geometriler **İnce diş** etiketi taşır.
Seçilen çapın standart kaba adımı üst satırda her zaman gösterilir.

### Baş ölçüleri

[FreeCAD Fasteners](https://github.com/shaise/FreeCAD_FastenersWB/blob/fddd07af422b7d3a69098b32333711c5eeae184c/FsData/iso4017head.csv) ve [cq_warehouse](https://github.com/gumyr/cq_warehouse/blob/daa46507ecc429c0e2dce11d9d5ffd09b12a42af/src/cq_warehouse/hex_head_parameters.csv) geometri tabloları ayrıca incelendi. Örneğin M8 anahtar ağzı 13 mm, M10 16 mm, M12 18 mm ve M22 34 mm karşılaştırıldı. Kaynaklarda nominal/maksimum baş yüksekliği ve M14 anahtar ağzı için farklar bulunduğundan tablo topluca aktarılmadı; standart sürümü ve üretici çizimi esas alınmalıdır. Baş ölçüleri ve yaklaşık `d − P` kılavuz deliği dayanım hesabını etkilemez.

Güncel görseller [examples](examples) klasöründedir. İnce diş eklemesiyle 26 ilgili kontrol geçti: 15 hesap, 8 gerçek Tk ve 3 ölçü verisi kontrolü. Windows/SolidWorks bu Linux ortamında çalıştırılmadı; yeni EXE üretilmedi.
