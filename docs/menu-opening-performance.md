# Menü ve sekme geçişleri — 15 Ekim 2026

> Eski Tk arayüzü için verilen görsel/rapor komutları tarihîdir. Bu betikler ve
> üretilmiş görseller güncel daldan kaldırılmıştır; yeniden incelemek için
> [temizlik öncesi sürümü](https://github.com/gkkizil/gokworks/tree/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9) kullanın.

16 Ekim'de pencere boyutlandırma akışı da düzenlendi: saklanan sayfalar artık son boyutlarında kalıyor, yalnız açık sayfa esniyor. Mimari ve önce/sonra ölçümü için [pencere boyutlandırma notu](window-resizing.md).

## Güncel mimari: gezinmeden önce hazırlık

Normal uygulama açılışında dokuz çalışma alanı sade bir ilerleme göstergesi altında ana Tk iş parçacığında kurulup gerçek pencere boyutunda çiziliyor. Hazırlık tamamlanınca PDF sayfası açılıyor. Böylece kullanıcı menüler arasında dolaşırken yeni sayfa kurulumu veya 700 ms aralıklarla çalışan ağır arka plan hazırlığı devreye girmiyor. Kurulum maliyeti kaldırılmadı; başlangıca taşındı.

Ziyaret edilmiş sayfaların native pencereleri artık kaldırılıp yeniden eşlenmiyor; aynı alanda birbirinin altında hazır tutuluyor. Pencere boyutu, DPI ve tema değişmediyse geçiş yalnız hazır sayfayı öne alıyor; yeniden yerleşim ve global `update_idletasks()` çağrısı yapmıyor. Geometri veya tema değiştiğinde gereken yerleşim yenileniyor. Form değerleri korunuyor, menü vurgusu tıklamada hemen değişiyor ve klavye odağı aktif sayfa ile yan menüde tutuluyor. Dokuz sayfanın bellekte tutulması bu yaklaşımın maliyetidir.

## Normal açılış ve olay döngüsü ölçümü

Aynı [Arşiv: ölçüm betiği](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/report-tools/benchmark_navigation_ready.py), önce `b79f585` kodunun temiz arşiv kopyasında, ardından yeni kodda birer tur çalıştırıldı. Python 3.13.5, Tk 8.6.16, CustomTkinter 6.0.0 ve Linux/Xvfb `:99` kullanıldı; iki tarafta da font dosyaları yüklenemediği için `circle_shapes` çizimi kullanıldı.

Bu ölçüm normal açılış yolunu kullanır. Başlangıçtan sonra tam Tk olay döngüsüyle 950 ms beklenir, ardından sekiz menüye 100 ms aralıkla tıklanır. Eski sürümün arka plan hazırlığı açık bırakılır. Olay döngüsünün yanıt vermesini izlemek için her 16 ms'de bir kontrol çağrısı istenir; aşağıdaki aralık, bu çağrılar arasında gözlenen en uzun süredir ve kare hızı ölçümü değildir.

| İşlem | Önce | Sonra |
| --- | ---: | ---: |
| Etkileşime hazır açılış | 327,90 ms | 1240,95 ms |
| Açılış sonunda hazır sayfa | 1 | 9 |
| Açılış sonrası oluşturulan sayfa | 8 | 0 |
| Tıklama ve olay işleme süresi, medyan | 150,58 ms | 25,87 ms |
| Tıklama ve olay işleme süresi, en yüksek | 246,98 ms | 31,84 ms |
| Olay döngüsü kontrol aralığı, en yüksek | 248,35 ms | 30,38 ms |

Açılış bu koşuda yaklaşık 0,33 saniyeden 1,24 saniyeye çıktı; karşılığında gezinme sırasında sayfa kurulumları ortadan kalktı. Tıklama süresi düğmenin çağrılmasını ve ardından bir tam `update()` çağrısını içerir. Birer tur değişkenliği belirlemeye yetmez. Bu sayılar Windows görüntü birleştiricisinin karelerini veya SolidWorks çalışmasını ölçmez; gerçek Windows akıcılığı için kesin garanti değildir.

Önceki yaklaşık 3 ms hazır sayfa sonucu farklı bir yöntemden geliyordu: o betik arka plan hazırlığını iptal ediyor, varsayılan tembel kurucuyu kullanıyor ve çizimde ağırlıklı olarak idle olaylarını işliyordu. Normal açılıştan hemen sonra görülen hazırlık takılmalarını kapsamıyordu. Yeni 25,87 ms değeriyle eşdeğer değildir. [Ham normal-gezinme sonuçları](test-results/navigation-ready.json) sayfa bazındaki ölçümleri içerir.

27 ilgili gezinme ve sekme GUI kontrolü geçti. Başlangıç hazırlığı, hazır sayfa geçişinde yeniden kurulum/yerleşim yapılmaması, durumun korunması, hızlı seçimler, hata dönüşü, yeniden boyutlandırma, tema ve DPI davranışları denetlendi. Bu rapor tam test paketi veya yeni EXE doğrulaması iddiası içermez.

## Tarihsel çalışma: ilk geçiş düzeltmeleri — 15 Ekim 2026

Aşağıdaki kod davranışı ve ölçümler önceki çalışmaya aittir. Bu bölümdeki eski sayfayı gizleme yaklaşımı güncel kalıcı sayfa katmanlarıyla değiştirilmiştir; aşağıdaki sayılar normal açılış ölçümüyle birleştirilmemelidir.

### Önceki değişiklikler

Ana menüde yeni sayfa mevcut ekranın arkasında görünür duruma getiriliyor, gerçek pencere boyutuna yerleştiriliyor ve çiziliyor. Sonra öne alınıyor; önceki sayfa ancak bundan sonra gizleniyor. Sayfalar ve girilmiş değerler önbellekte korunuyor. Kurulum ya da çizim hatasında önceki ekran geri yükleniyor.

CustomTkinter 6.0.0'ın sonuç sekmelerindeki iki geçiş davranışı değiştirildi: tıklamada eski sekmenin yeni sekme çizilmeden gizlenmesi ve programlı geçişte 100 ms sonra eski seçime göre çalışan temizleme. İkincisi hızlı geçişlerde güncel sekmeyi de gizleyebiliyordu. Artık yeni sekme çizildikten sonra diğerleri hemen gizleniyor; gecikmiş sekme temizleme görevi bırakılmıyor. K/R'nin manuel, hesap yardımı ve sonuç görünümleri de aynı çizim sırasını kullanıyor.

Menüdeki 140 ms renk animasyonu kaldırıldı; yalnız eski ve yeni seçili düğme hemen güncelleniyor. Biriken menü seçimleri `after(0)` ile son seçime indirgeniyor; kontrol oluşturulurken çağrılan `update_idletasks()` yeni bir geçişi başlatmıyor. Ağırlık hesabında sayı, adet, malzeme veya birim değişince alanlar kaldırılıp yeniden yerleştirilmiyor; yerleşim yalnız kesit türü veya hesap yöntemi değişince yenileniyor.

### Önceki ölçüm

Başlangıç: `e3ada75` kodunun temiz `git archive` kopyası. Aynı güncel ölçüm betiğiyle önce başlangıç, ardından son kod birer tur çalıştırıldı. Ortam: Python 3.13.5, Tk 8.6.16, CustomTkinter 6.0.0, Linux/Xvfb `:99`. Font dosyaları salt okunur olduğundan iki tarafta da `circle_shapes` çizimi kullanıldı.

Dokuz sayfa kapsandı: PDF başlangıç sayfası, sekiz sayfanın ilk açılışı, 45 hazır sayfa geçişi ve dokuz tamamlanma ölçümü. Kuyruk ölçümünde sekiz düğme olay döngüsüne dönmeden çağrıldı; her iki sürüm de yalnız son seçilen sayfayı oluşturdu. Bu, aralıklı kullanıcı tıklamalarının süresi değildir.

| İşlem | Önce | Sonra |
| --- | ---: | ---: |
| İlk sayfa çizimi, medyan | 141,26 ms | 116,05 ms |
| Hazır sayfa çizimi, medyan | 5,05 ms | 3,29 ms |
| Hazır sayfa çizimi, en yüksek | 9,20 ms | 4,87 ms |
| Gecikmeli yerleşim ve menü animasyonu tamamlanması, medyan | 146,26 ms | 40,47 ms |
| Aynı tamamlanma ölçümü, en yüksek | 553,44 ms | 777,56 ms |
| Gizli sayfa hazırlama, medyan | 71,04 ms | 91,85 ms |
| Sekiz tıklamalık kuyruk | 185,71 ms | 171,04 ms |
| Kuyrukta oluşturulan yeni sayfa | 1 | 1 |

Çizim süreleri `update_idletasks()` içerir. Tamamlanma ölçümü ayrıca gecikmeli yerleşim görevlerini ve önceki sürümdeki menü animasyonunu bekler; 140 ms animasyonun kaldırılması bu medyanı doğrudan azaltır. Bu değer sayfanın ilk görünme süresi veya bütün uygulamanın hızlanma oranı değildir. İlk açılışlar da tek kare süresine inmiyor: son kodda ISO yaklaşık 184 ms, ağırlık 200 ms. Ağırlığın ilk açılışı 178 → 200 ms, adlandırmanınki 86 → 94 ms oldu.

En yüksek tamamlanma süresi ve gizli hazırlama medyanı bu ölçümde arttı. Birer turla değişkenliğin büyüklüğü belirlenemez; tüm işlemlerin hızlandığı sonucu çıkarılamaz. Ayrı, hedefli profil çalışmasında ilk tamamlanma ölçümü olan PDF geçişi 820 ms sürerken diğer sekiz geçiş 40–42 ms sürdü. PDF geçiş fonksiyonu yaklaşık 4 ms, ilk tam `update()` çağrısı 815 ms aldı; Python callback'leri yaklaşık 1 ms tuttu. Sürenin çoğu native Tcl/Tk çağrısında kaldı. Betik önceki çizim geçişlerinde yalnız idle olaylarını işler; ilk tam `update()` diğer hazır olayları da çalıştırır. Profil, native çağrının iç nedenini kesinleştirmedi. Bu ayrı tanı sayıları yukarıdaki önce/sonra tablosuna dahil edilmedi.

[Ham güncel sonuçlar](test-results/menu-transitions.json) sayfa bazındaki değerleri ve ölçüm sınırlarını içerir. Windows görüntü birleştiricisi veya SolidWorks ölçülmedi; Linux görünürlük kontrolleri Windows'ta siyah karelerin tamamen giderildiğini kanıtlamaz.

### Önceki kontrol

26 benzersiz ilgili GUI kontrolü doğrulandı. İlk çalışmada 25 geçti; sonuçlardan manuel K/R görünümüne dönüşte eski panel gizlenirken hedef alanın henüz görünür olmadığını denetleyen bir kontrol başarısız oldu. Eski hesap formunun kaldırılması kaydırılabilir alanın geometrisini yeniden değiştiriyordu. Sonuç paneli gizlenmeden önce bu yerleşimin tamamlanması sağlandı; assertion değiştirilmeden ilgili dört sekme kontrolü yeniden çalıştırıldı ve geçti.

Kontroller sayfa/sekme değiştirme sırasını, hızlı seçimleri, gizli hazırlamayı, veri ve ayarların korunmasını, hata dönüşünü, işlem/kapanış korumalarını, ağırlık alanlarının yerleşimini, tema ve DPI değişikliklerini kapsıyor. Tüm test paketi çalıştırılmadı; EXE üretilmedi.

## Önceki çalışma — 14 Ekim 2026

Aşağıdaki ölçümler önceki optimizasyona aittir. Güncel çalışmayla sayfa kapsamı ve ölçüm turu farklıdır; iki tablo aynı hız karşılaştırması olarak kullanılmamalıdır.

Yeni sayfalar, bütün kontrolleri hazırlandıktan sonra görünür oluyor. Kurulum sırasında mevcut ekran açık kalıyor; arka planda hazırlanan sayfalar hiç görünür yapılmıyor. Böylece CustomTkinter'ın kurulum sırasında çalıştırdığı yerleşim işlemleri, yarım sayfayı tekrar tekrar pencereye yerleştirmiyor.

Aynı olay kuyruğunda biriken menü tıklamaları son seçime birleştiriliyor. Hazır sayfalar ve girilmiş değerler korunuyor. İşlem başladığında veya pencere kapandığında bekleyen geçiş uygulanmıyor. Sayfa oluşturulamazsa mevcut ekranın verileri ve yerleşimi geri yükleniyor. Kapanış sırasında yeni yerleşim zamanlayıcıları oluşturulması da engellendi.

### Önceki ölçüm

Başlangıç: `7ffd15d`. Python 3.13.5, Tk 8.6.16, CustomTkinter 6.0.0 ve Linux/Xvfb üzerinde üç tur, aynı bağımlılıklar ve ekran kullanıldı. SolidWorks çalıştırılmadı. Font yüklenemediği için her iki ölçümde de CTk'nin `circle_shapes` çizimi kullanıldı. Windows süreleri farklı olabilir.

| İşlem | Önce | Sonra |
| --- | ---: | ---: |
| İlk sayfa çizimi, medyan | 121,33 ms | 108,35 ms |
| Gizli sayfa hazırlama, medyan | 105,49 ms | 72,92 ms |
| Hazır sayfalar arası geçiş, medyan | 4,55 ms | 4,24 ms |
| Altı tıklamalık kuyruk, medyan | 825,82 ms | 120,55 ms |
| Bu kuyrukta oluşturulan yeni sayfa | 6 | 1 |

Çizim ölçümleri `update_idletasks()` içerir; gecikmeli yerleşim çağrılarının ve menü renk animasyonunun tamamlanmasını içermez. Kuyruk ölçümünde altı düğme, olay döngüsüne dönmeden art arda çağrılır. Bu sonuç, kullanıcının aralıklı altı tıklamasının süresi değildir; bekleyen tıklamaların gereksiz sayfa kurulumlarına dönüşmesini ölçer.

İlk açılış kazanımı sayfaya göre değişiyor: K/R 181 → 146 ms, BOM 113 → 94 ms; geometrik toleranslar 104 → 110 ms. Sayfa kurulumu hâlâ Tk ana iş parçacığında; tüm ilk açılışlar tek çizim karesine sığmıyor. [Ham sonuçlar](test-results/menu-opening.json) bütün sayfaları içerir.

### Önceki kontrol

19 ilgili GUI kontrolü geçti: biriken tıklamalar, mevcut sayfaya geri dönüş, doğrudan geçiş, işlem/kapanış sırasında bekleyen geçiş, sayfa oluşturma hatasından dönüş, gizli hazırlama, veri ve ayarların korunması, menü vurgusu, diyagramlar, tema, DPI ve çalışma alanı boyutları. İlk çalışmadaki test sınıfı adı ve CTk yerine doğrudan Tk olay bağlama düzeltildi; ilgili üç kontrol tekrar geçti. Tüm test paketi çalıştırılmadı.

Ölçümü çalıştırmak için, Tk bağımlılıkları ve sanal ekran hazırken:

```bash
DISPLAY=:99 python docs/report-tools/benchmark_menu_opening.py /tmp/menu-opening.json
```
