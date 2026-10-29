# Ayrıntılı konturlarda boş levhaya rağmen eksik yerleşim

NFP 1.1, ilk geçişte ikinci parçayı denemeden önce ayrıntılı konturların
Minkowski/konveks ayrıştırma hesabını yapıyordu. Bu hesap zaman sınırını
tükettiğinde yalnızca ilk parça korunuyor; açıkça kullanılabilir alan olsa
bile kalan parçalar yerleşmemiş görünüyordu.

NFP 1.2 önce bütün parçaları kapsayan hızlı bir başlangıç yerleşimi dener.
Kenar/köşe koordinatları yalnız aday üretir; kabul kararı özgün konturun
kesişim, mesafe, kenar payı ve dönüş kontrolleriyle verilir. Kalan sürede
ayrıntılı NFP araması iyileştirmeye devam eder. Daha sonraki deneme süreye
takılsa da önceki en iyi doğrulanmış çözüm kaybolmaz.

Süre sınırı ile kullanıcı iptali ayrı kaydedilir. Eksik sonuçta arayüz bunları
stok/ölçü kısıtından ayıran bir açıklama gösterir. Eski proje dosyaları yeni
süre alanı olmadan da açılır; eksik yerleşimde üretim çıktısı kapalı kalır.

## Tekrar üretim

Sentetik örnek: altı adet 204 köşeli, yaklaşık 1800 × 600 mm parça;
2000 × 4000 mm levha, stok 1, 5 mm kenar payı ve 0,6 saniye süre sınırı.

| Sonuç | Önce | Sonra |
| --- | --- | --- |
| Yerleşen parça | 1 | 6 |
| Yerleşmeyen parça | 5 | 0 |
| Kullanılan levha | 1 | 1 |

[Arşiv: Çalışan arayüz](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/nesting-contour-fill/after.png) · [Ölçüm kaydı](reproduction.json).

[Doğrulama özeti](checks.json): genel grupta 921 test ve 878 alt senaryo geçti;
7 Windows/canlı CAD testi atlandı. Son NFP iyileştirmesinden sonra nesting'in
90 testi ayrıca geçti. [Uygulama öz denetimi](selfcheck.json) de tamamlandı.

Görsel ve ölçüm Linux / Qt offscreen ortamında sentetik konturlarla alınmıştır;
kullanıcının ekran görüntüsündeki DXF dosyaları bu testin girdisi değildir.
Bu düzeltme, her geometri için en iyi yerleşimin bulunacağı garantisi vermez.

Regresyonlar; karmaşık konturlarda 6/6 ve iki plakada 9/9 yerleşimi, iyileştirme
sırasında zaman aşımında başlangıcın korunmasını, gerçek bir C konturunun
içbükey boşluğuna yerleşimi, eski proje uyumunu ve iptal/stok/süre açıklamalarını
kapsar. NFP içbükey geometriyi dikdörtgenle değiştirmez; delik içine yerleştirme
ve aynalama kapalı kalır.

```bash
QT_QPA_PLATFORM=offscreen python -m pytest modules/nesting/tests
```
