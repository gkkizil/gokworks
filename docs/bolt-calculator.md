# Cıvata hesabı

**Mühendislik hesapları → Cıvata hesabı**. SolidWorks bağlantısı gerektirmez. Metrik ölçü, kalite sınıfı, yük türü ve kuvvet girildiğinde sonuç canlı güncellenir. Yeşil **Güvenli**, kırmızı **Güvensiz** ve yük girilmediğinde **Yük yok** gösterilir. Hatalı girişte önceki sonuç kaldırılır.

- M3–M39 arasındaki 18 kaba diş ölçüsü; 4.6, 5.6, 8.8, 10.9 ve 12.9 çelik cıvata sınıfları.
- Çekme, kesme veya eşzamanlı birleşik yük. N, kN ve kgf arasında geçiş girilmiş kuvveti dönüştürür; kgf kütle değildir.
- Cıvata adedi, tek/çift kesme düzlemi, dişli/dişsiz kesit ve 1–10 arasında emniyet katsayısı. Varsayılan katsayı 2; tüm cıvatalar ve çift kesmedeki düzlemler eşit yük taşır.
- Yük okları, kapasite kullanımı, eşdeğer/izin verilen gerilme, mevcut emniyet ve çekme alanı. Hesap varsayımlarıyla panoya kopyalanabilir. Seçimler kaydedilir.

## Hesap yöntemi

`d` nominal çap, `P` adım (mm); kuvvetler N, alanlar mm², gerilmeler MPa (= N/mm²). `n` cıvata adedi, `m` kesme düzlemi adedi, `s` hedef emniyet katsayısıdır.

```text
Çekme alanı As = π/4 × (d − 0,938194P)²
Dişli kesmede Ak = π/4 × (d − 1,226869P)²
Dişsiz kesmede Ak = πd²/4
σ = Ft / (n As)
τ = Fv / (n m Ak)
σeş = √(σ² + 3τ²)
İzin verilen gerilme = Sp / s
Kullanım = σeş / (Sp / s)
Mevcut emniyet = Sp / σeş
Güvenli koşulu: kullanım ≤ 1
```

Deney yükü gerilmesi `Sp`:

| Sınıf | Sp (MPa) |
| --- | ---: |
| 4.6 | 225 |
| 5.6 | 280 |
| 8.8, d ≤ 16 mm | 580 |
| 8.8, d > 16 mm | 600 |
| 10.9 | 830 |
| 12.9 | 970 |

Malzeme değerlerinin dayanağı ISO 898-1:2013 deney yükü gerilmesi tablosu; kaba diş adımları ISO 261, temel diş geometrisi ISO 68-1 / ISO 724'tür. Sp kopma dayanımı değildir. Von Mises gerilmesinin Sp/s ile karşılaştırılması bu uygulamanın ihtiyatlı statik ön kontrol yöntemidir; ISO 898-1 bir bağlantı tasarım standardı değildir. Dişli kesmede çekme alanından daha küçük olan temel diş kök alanı kullanılır; imalat toleransları ayrıca modellenmez.

Referans erişimleri: [ISO 898-1](https://www.iso.org/obp/ui/#iso:std:iso:898:-1:ed-5:v1:en), [ISO 261](https://www.iso.org/obp/ui/#iso:std:iso:261:ed-2:v1:en), [ISO 724](https://www.iso.org/obp/ui/#iso:std:iso:724:ed-2:v1:en). Standartların tam metni depoya dahil değildir. Bu oturumda dış teknik tablo sitelerine erişim ağ tarafından reddedildi; canlı kaynak karşılaştırması yapıldığı iddia edilmez.

## Kapsam

Bu ekran **cıvata gövdesinin statik ön kontrolünü** yapar. Tam yük taşıma kapasitesine sahip, ilgili sınıfa uygun karbon/alaşımlı çelik cıvata ve oda sıcaklığı kabul edilir. Paslanmaz A2/A4, ince diş, azaltılmış baş/gövde ve özel bağlantı elemanları kapsam dışıdır.

Girilen çekme kuvveti cıvataların taşıdığı toplam kuvvettir. Ön sıkmalı bağlantıda dış kuvvet doğrudan bu alana girilmemelidir; ön yük ve bağlantı rijitliği ayrıca hesaplanır. Ön sıkma, diş sıyırması, plaka ezilmesi, kenar yırtılması, kayma/sürtünme, eğilme, eksantriklik, yorulma, darbe ve sıcaklık etkileri hesaplanmaz. Güvenli sonucu bağlantının bütün bu kontrolleri geçtiği anlamına gelmez. Seçilen emniyet katsayısı uygulama gereksinimine göre belirlenmelidir.

Ekrandaki çekme/kesme kapasiteleri tek başına etkiyen kuvvetler içindir; birleşik yükte ikisi aynı anda sınır değerlerinde kullanılamaz. Kuvvet dağılımı ve kapasiteye esas kesit **Hesap yöntemi** penceresinde açıklanır.

## Kontrol örnekleri ve görseller

M10 × 1,5 / 8.8 / 1 cıvata / s=2: As ≈ 57,99 mm², Sp=580 MPa, izin verilen gerilme=290 MPa. Yalnız 10 kN çekmede σ ≈ 172,44 MPa ve sonuç güvenlidir; yalnız çekme kapasitesi ≈ 16,82 kN'dir. Diş kökü alanı ≈ 52,29 mm²; tek kesmede 10 kN güvensiz, çift kesmede güvenlidir. 12 kN çekme ve 8 kN kesme ayrı ayrı güvenliyken birlikte σeş ≈ 336,21 MPa ile güvensizdir.

14 hedefli kontrol: 8 hesap testi, 3 gerçek Tk arayüz testi ve 3 sayfa ön yükleme/tema/ölçek testi. Birim dönüşümü, sınırın iki tarafı, geçersiz/sıfır yükler, yeniden açılış, seçimlerin korunması, küçük pencere, tema ve %125 ölçek kapsandı. Linux/Python 3.13/Tk 8.6 kullanıldı; Windows/SolidWorks çalıştırılmadı. [Test çıktısı](reports/bolt/test-run.log).

[Açık tema](reports/bolt/screenshots/tension-light.png) · [Birleşik yük, koyu tema](reports/bolt/screenshots/combined-dark.png) · [1000×690, güvensiz sonuç](reports/bolt/screenshots/unsafe-dark-small.png)

![Cıvata hesabı, birleşik yük](reports/bolt/screenshots/combined-dark.png)

Görseller çalışan Tk uygulamasından `docs/report-tools/capture_bolt_gui.py` ile alınır; hesaplar örnek girdilerle çalışır. Ek bağımlılık kurulması gerekmez.
