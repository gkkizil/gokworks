# Dişli türleri — ortak çalışma ekranı, 28 Ekim 2026

final result: passed

## Kaynak, durum ve kanıt

Kullanıcının mevcut düz dişli ekranı referans alındı. Bu çalışma mevcut
PySide6 masaüstü uygulamasındadır. Tarayıcı/web arayüzü üretilmedi.
Başlangıç kaynak commit'i `8e95713`; ortak yerleşim
`modules/gear_calculator/workspace.py`, tür ekranı
`modules/gear_calculator/families/ui.py` içindedir.

- Yerel kaynak görüntü: `/workspace/artifacts/gear-layout/reference-spur.png`.
  1920×1080, koyu tema, daraltılmış gezgin, 2D, duraklatılmış hareket;
  m=3, z₁/z₂=20/40, b=20, delikler 20/60, n₁=1602, P=5.
- Son uygulama: [helisel ekran](docs/screenshots/gear-workspace.png),
  1920×1080; aynı pencere/tema/gezgin, helisel türün varsayılanları
  mₙ=2, β=20°, b=15, delikler 8/12, n₁=1500, P=1,5.
  Türe ve girdilere bağlı ölçü farkları beklenir; sayısal eşitlik aranmadı.
- Tam görünüm, iki kaynak aynı karşılaştırma görüntüsünde:
  `/workspace/artifacts/gear-layout/comparison-wide.png`, 2560×720;
  iki 1920×1080 kaynak eşit olarak 1280×720'ye küçültüldü.
- Sonuç/CAD yakın incelemesi:
  `/workspace/artifacts/gear-layout/comparison-results.png`, 700×920;
  giriş yakın incelemesi: `comparison-inputs.png`, 680×700, aynı klasörde.
  Bu kırpmalar kaynak ve uygulamayı yerel piksel yoğunluğunda birlikte gösterir.
- Dar ekran: [görünüm ve sonuç/CAD](docs/screenshots/gear-workspace-compact.png),
  iki ayrı 820×560 gerçek pencere görüntüsü yan yana, toplam 1640×560;
  açık tema, sonuçlar sekmesinde CAD düğmelerine kaydırılmış durum.
- Diğer dokuz tür: `/workspace/artifacts/gear-layout/verified-<tür>.png`.
  Hipoid dahil hesap türlerinin boş durumları da incelendi.

Qt mantıksal boyutu ve ekran görüntüsü piksel boyutu eşit, ölçek 1.
CSS boyutu uygulanamaz. Kullanıcının Windows görüntüsünün font rasterizasyonu
Linux/Qt ile birebir karşılaştırılmadı; mevcut tema ve font ayarları korundu.
Aynı Linux ortamında önceki ve sonraki düz dişli görüntülerinin piksel farkı
yoktur (`reference-spur.png` / `final-spur.png`, ImageChops fark sınırı `None`).

## Bulgular, düzeltmeler ve yeniden kontrol

1. **P1 — Diğer türlerde giriş, görüntü ve CAD dört ayrı sekmedeydi.**
   Kanıt: `comparison-initial.png` içinde düz dişli kaynağı ve önceki helisel
   ekran birlikte. Girdiler düzenlenirken sonuçlar görülemiyordu.
   Düzeltme: ortak üç kolon; yalnız dar alanda üç ana sekme.
   Son kanıt: `comparison-wide.png` ve yukarıdaki dar ekran görüntüsü.
2. **P2 — İlk uyarlamada özet birimi ikinci satıra taşıyordu; eksen ölçüsü
   şeklin üstünde, açıklaması altında kalıyordu.** İlk kanıt:
   `/workspace/artifacts/gear-layout/after-helical.png`.
   Düzeltme: özet için dört anlamlı basamak, ayrıntılı tabloda önceki sayı
   sunumu; ölçü çizgisi ve metni birlikte şeklin altına taşındı.
   Son kanıt: `verified-helical.png` ve `comparison-results.png`.
3. **P2 — Ortak etiketler türün normal/eksenel modülünü ve parça adını
   ayırt etmiyordu.** Düzeltme: helisel normal modül/açı, sonsuz vida eksenel
   modülü, güneş/planet/halka ve sikloid disk/pim adları; sonuçlarda devir
   büyüklüğü ile taşıyıcı devri açık yazıldı. Desteklenmeyen DXF bölüm
   dairesi seçeneği kapatıldı. Son kanıt: tür görüntüleri ve gerçek DXF testi.

Son karşılaştırmada açık P0/P1/P2 bulgu kalmadı.

## Beş görsel kontrol yüzeyi

- **Font ve hiyerarşi:** mevcut Qt fontu/token'ları; bölüm başlıkları,
  büyük sonuç özeti, tablo ve yardımcı metinler kaynak hiyerarşisini korur.
  Türkçe adlar ve mühendislik sembolleri yakın incelemede okunuyor.
- **Boşluk ve yerleşim:** 1920 genişlikte kolonlar 290/1226/310 piksel;
  ortadaki alan büyür. 1100 piksel altındaki çalışma alanı sekmelere dönüşür.
  Dar/geniş dönüşte üç panel geri görünür; CAD, kaydırma ile erişilebilir.
- **Renk ve durumlar:** mevcut `COLORS` açık/koyu temaları, mavi ilk parça,
  sarı diğer parçalar, kesik yardımcı çizgiler ve kapalı düğmeler kullanılır.
  Hesap türlerinde hareket/CAD eksikliği görünür; sahte model gösterilmez.
- **Görsel/varlık kalitesi:** logo ve mevcut ikonlar korundu. Dişliler gerçek
  parametrik vektör konturudur; ekran resmi/temsili çokgen ile değiştirilmedi.
  3D önizleme mevcut B-Rep katı akışını kullanır.
- **Metin ve içerik:** türe özgü etiketler, birimler, hesap kapsamı ve
  imalat/dayanım sınırlamaları korunur. Tabloda bütün mekanizmanın adlandırılmış
  sonuçları bulunur; seçili parça satırı ve CAD hedefi ayrıca gösterilir.

## İşlevsel kontrol ve sınırlar

- On ek türün tamamında kolonlar, dar/geniş geçişler, görünür sonuç/CAD
  kontrolleri ve destek durumları otomatik test edildi; düz dişli testleri korundu.
- Açık/koyu tema, yardımcı daireler, parça/halka/planet seçimi ve CAD hedefi,
  türler arasında girişlerin korunması, güç/tork birincil girdisi test edildi.
- Gerçek worker ile STEP, B-Rep 3D, hareket başlat/durdur ve seçili tek parçanın
  yardımcı çizgili/çizgisiz DXF dosyası okunarak doğrulandı.
- Linux doğrulaması: 182 testlik dişli/entegrasyon/yapı koşusunda 181 başarılı;
  tek yapı kontrolü eski kök modül dizinlerinde kalan `.pyc` önbelleği nedeniyle
  başarısızdı. Yalnız bytecode içeren yedi dizin `/tmp/gokworks-stale-bytecode-*`
  altına taşındı; yapı paketinin beş testi yeniden başarılı. Son tür ekranı
  paketinin yedi testi de başarılı. Kanıtlar `/tmp/gear-layout-final.xml`,
  `/tmp/gear-layout-structure-final.xml`, `/tmp/gear-layout-ui-final.xml`.
- Kaynaktan `main.py --self-check` başarılı: 16 modül, iki tema, çözünürlük
  matrisi ve gerçek dişli STEP/DXF alt süreçleri. Kanıt:
  `/tmp/gear-layout-source-smoke.json`. Tüm uygulamanın test paketi çalıştırılmadı.
- Qt yerel çalıştırmada beklenmeyen uygulama hatası görülmedi. Linux font ve
  ezdxf önbellek uyarıları kaydedildi; web konsolu uygulanamaz.
- Bu görsel rapor yeni konik/hipoid/sonsuz vida CAD desteği veya SOLIDWORKS
  üzerinde canlı import doğrulaması iddia etmez. Mühendislik motorları değişmedi.

Kontrol listesi tamamlandı: ortak yerleşim, doğru etiketler, destek durumları,
dar ekran erişimi, gerçek CAD seçeneği bağlantısı ve son görüntü karşılaştırması.
