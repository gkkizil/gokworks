# Nesting & Sac Maliyet Analizi

GOKWORKS → **Mühendislik Hesapları → Nesting · Sac maliyeti**.
Mevcut PySide6 uygulamasının modülüdür; SolidWorks veya bulut bağlantısı gerekmez.

1. **1 · Parçalar → DXF ekle**: birden fazla dosya seçin. Malzeme, kalınlık,
   adet ve eğri toleransını belirtin. `$INSUNITS` yoksa mm/cm/inch seçimini
   açıkça yapın. Yardımcı katmanları adlarıyla `;` kullanarak dışlayın.
   Seçilen her dosya hemen listede görünür; okunamayanlar hata açıklamasıyla
   kalır. Dosyaya çift tıklayıp ayarlarını düzeltip yeniden okuyabilirsiniz.
2. Parçaya çift tıklayarak kod, açıklama, adet, kalınlık ve malzemeyi düzenleyin.
   Alan, sınır ölçüleri ve dış/iç çevreler aynı pencerede gösterilir. Ctrl/Shift
   ile birden fazla satırı seçip birlikte kaldırabilirsiniz. Dosya yolu ve
   hata açıklaması satır üzerinde bekleyince, bütün okuma kayıtları
   **Yükleme ayrıntıları** içinde görünür.
3. **2 · Sac ve ayarlar**: özel ölçü veya 1000×2000, 1250×2500,
   1500×3000, 2000×4000 şablonunu seçin. Stok adedini ve TL/kg ya da
   TL/levha fiyatını sac satırına çift tıklayarak girin. **Malzeme kütüphanesi**
   penceresinde özel malzeme ve yoğunluk eklenebilir.
4. Aynı sekmede kenar payı, parça aralığı, döndürme ve kaliteyi ayarlayın.
   Kerf, açı/adım, hadde yönü, **Yerleşim hesaplama süresi** ve **Deneme sırası kodu**
   (seed) **Gelişmiş ayarları göster** içinde. Süre, hesabın en uzun çalışma
   süresidir; daha erken bitebilir. Deneme sırası kodu varsayılan 42 olarak
   bırakılabilir; farklı yerleşimlerin denenme sırasını belirler.
   Operasyon giderleri, kâr ve KDV **Kesim ve ek maliyetler** içindedir.
   Bu bölümleri kapatmak girilen değerleri sıfırlamaz.
5. **Yerleştir → 3 · Yerleşim**: yerleşim hesabı arka planda çalışır.
   AutoCAD benzeri **1. plaka / 2. plaka / 3. plaka** sekmelerine tıklayın;
   çok sayıda plaka varsa sekme çubuğunu kaydırın. Odak sekmedeyken
   klavyenin sol/sağ oklarıyla da geçilebilir.
   tekerlekle yakınlaştırın, sürükleyerek kaydırın, **Sığdır** ile görünümü sıfırlayın.
   **Durdur**, o ana kadar bulunan doğrulanmış sonucu korur.
   **Parça adlarını göster** ile çizim üzerindeki adları açıp kapatın;
   tam ad ve koordinatlar, parça üzerinde bekleyince görünür. Üç adım hem
   dar hem geniş pencerede aynı yerde kalır; yerleşim özeti görünümün altındadır.
6. **Ayrıntılar**: maliyet dökümü ve yeniden doğrulama.
   **Dışa aktar**: DXF / Excel / PDF; tüm parçalar yerleşmeden açılmaz.
   **Proje**: kaydet, aç ve yeni proje. Kaydedilen analizler mevcut geometriyi kullanır.

Ekrandaki toplam, sac ve operasyon giderleri ile kâr/KDV'yi içerir.
Malzeme bedeli ayrıca gösterilir; kullanılan bir sacın fiyatı sıfırsa
**Sac fiyatı eksik** yazılır. Eksik yerleşimin maliyeti **Kısmi hesap** olarak
işaretlenir. Yalnız fiyat değişikliği aynı koordinatları yeniden kullanır ve
seçili fiziksel plakayı korur.

Fiyat/yoğunluk/operasyon gideri değişikliği aynı koordinatları arka planda
yeniden doğrulayarak maliyeti günceller. Kontur, adet, kalınlık, stok/ölçü veya
yerleşim payları değişirse eski sonuç kapatılır ve yeniden yerleşim istenir.

## Hesap ve algoritma

Motor adı **GOKWORKS NFP 1.1**. Gerçek kontur çarpışma alanı,
`A ⊕ (−B)` Minkowski toplamıdır. İçbükey poligonlar kısıtlı Delaunay
üçgenlemesine ayrılır; yalnız dışbükey kalan birleşimler birleştirilir.
Dışbükey parçaların Minkowski toplamları birleştirilerek No-Fit Polygon
elde edilir. Bu işlem parçayı sınır dikdörtgeniyle değiştirmez.
NFP engellerinin levha içi uygun öteleme bölgesinden çıkarılmasıyla
aday koordinatlar bulunur; her aday ayrıca gerçek konturla kontrol edilir.

Alan/boyut sıralamaları, tekrarlanabilir rastgele sıra değişimleri,
izinli dönüşler ve farklı levha boyutu seçimleri denenir.
Her fiziksel plaka, kalan uygun parçalarla doldurulduktan sonra sonraki
plaka açılır. Ekrandaki ve rapordaki numaralar 1 → 2 → 3 olarak ilerler.
Skor sırasıyla yerleşmeyen adet, kullanılan levha adedi, satın alınan alan
ve yerleşimin yüksekliğidir. Hızlı/Dengeli/Yüksek en fazla 3/12/40 yerleşim
denemesidir; zaman sınırı daha erken durdurabilir. Genetik algoritma
veya kanıtlanmış matematiksel optimum olduğu iddia edilmez.

Bağımsız doğrulayıcı, NFP önbelleğini kullanmadan gerçek dönüşümler,
STRtree komşu araması, kesişim alanı, Öklid mesafesi, levha sınırı,
malzeme/kalınlık, stok, izinli açılar ve örnek/adet tutarlılığını kontrol eder.
İptal, süre sınırı veya stok yetersizliğinde eksik yerleşim gösterilir;
eksik proje üretim DXF/PDF/Excel çıktısına gönderilemez, JSON kaydedilebilir.

`kg = net alan (mm²) × t (mm) × yoğunluk (kg/m³) / 10⁹`.
Delikler net alandan düşülür ve fireye dahildir. `1250×2500×2×7850/10⁹`
sonucu **49,0625 kg**'dır. Fire = brüt − net; verim = net/brüt alan × 100.
Levha maliyeti TL/kg × brüt kg veya doğrudan TL/levhadır.
Her levhanın maliyeti kendi parçalarının net alanlarına dağıtılır; kuruş
yuvarlama kalanı son örnekte dengelenir. Malzeme/operasyon/kâr/KDV ayrıdır.
Kesim bedeli nominal dış+iç çevreden; piercing bedeli kapalı kontur
adedinden gelir. Tezgâh süresi, giriş/çıkış yolu ve ortak kesim uydurulmaz.

## Geometri ve üretim sınırları

- LINE, ARC, CIRCLE, LWPOLYLINE/POLYLINE (bulge dahil), SPLINE,
  ELLIPSE, döndürülmüş/ölçeklenmiş ve iç içe INSERT desteklenir.
- ARC/CIRCLE doğrudan dairesel değerlendiriciyle düzleştirilir;
  ara Bezier yaklaşımının ek hatası kullanılmaz. Kontur hesabı kullanıcı
  toleransına göre yaklaşık poligonaldir. Eğri toleransı ve uç birleştirme
  toleransı projede/raporda saklanır. Varsayılanlar 0,02 / 0,001 mm.
- Açık, dallanan, kendi kendini kesen, üst üste binen, 3B veya tanımsız
  kesim nesneleri reddedilir. Kritik geometriler `buffer(0)` ile onarılmaz.
  Kapalı/dondurulmuş katmanlar ve metin/ölçülendirme/tarama dışlanır.
- Düz konturlarda başlangıç birleştirme toleransı ayrıca belgelidir.
  Eğri çarpışma güvenliği iki parçanın kiriş hata paylarını mesafeye ekler.
  Kapalı konturların koordinatları ızgaraya yuvarlanmaz. Yakın açık uçlar
  birleştirildiyse gerçekleşen en büyük hareket ayrıca kaydedilir ve hem
  parça aralığına hem kenar payına eklenir.
- Hadde yönü kaynak DXF'in X doğrultusudur; kilit yalnız 0°/180° kabul eder.
  Aynalama ve delik içine parça yerleştirme kapalıdır. İç içe adalar ayrı
  parçalar ya da dosya bazında rijit bir grup olarak içe alınabilir.
- Kerf ve bitmiş parça mesafesi farklı ayarlardır. Çarpışma aralığı
  `max(mesafe, kerf) + eğri hata payları`; kenar güvenliği
  `kenar payı + kerf/2 + eğri hata payı`dır. Mitre engel genişletmesi
  bazı dar köşelerde konservatif yer kaybına neden olabilir.
- DXF **nominal bitmiş parça konturudur**, telafili CAM takım yolu değildir.
  Makinede kerf telafisi uygulanmalıdır. Özgün ARC/CIRCLE korunur;
  `PART_OUTER/PART_INNER` kesim, diğer üç katman operatör bilgisidir.
  Çıkışla birlikte `KESIM-NOTLARI.txt` yazılır. Kaynak dosyaya dokunulmaz.
- Büyük tekrar kullanılabilir kalıntı sınıflandırması/hurda kredisi bu
  sürümde yoktur. Bütün artık alan raporlanır, maliyetten düşülmez.
- En fazla 100 MB giriş/proje, 20.000 içe aktarılmış kontur noktası,
  10.000 parça örneği ve 600 saniye hesaplama sınırı vardır. Karmaşık konturlarda
  GEOS işlemi tamamlanana kadar iptal isteği kısa süre bekleyebilir.

## Proje ve katmanlar

`.goknest.json`, sürümlü mm geometriyi, normalize özgün DXF nesnelerini,
kaynak yol/SHA256 bilgilerini, malzemeleri, levhaları, stok/fiyatları,
ayarları, motor sürümünü, koordinatları ve hesaplanan maliyetleri içerir.
Kaynak DXF taşınsa da açılabilir. Kaynak dosyanın sonraki değişiklikleri
projeye otomatik aktarılmaz; yeniden içe alınmalıdır. Girdi imzası değişmiş
bir sonuç güncel kabul edilmez. Bozuk proje/yerleşim reddedilir.
JSON/Excel/PDF atomik; çok levhalı DXF klasörü tüm levhalar hazır olunca
yayımlanır. Mevcut DXF klasörünün üstüne yazılmaz.

Paketler: `models`, `materials`, `geometry`, `dxf_import`, `engine`,
`validation`, `accounting`, `dxf_export`, `storage`, `report`, `render`.
Qt sayfası `gui_qt/pages/nesting.py`; editör/kanvas `nesting_widgets.py`.
Mevcut JobManager, tablo modeli, tema, lisans ve atomik dosya altyapısı kullanılır.

## Çalıştırma ve doğrulama

Python 3.13: `python -m pip install -r requirements-dev.txt`, ardından
`python main.py`. Testler: `QT_QPA_PLATFORM=offscreen python -m pytest
tests/test_nesting.py tests/test_nesting_gui.py -q` (Windows'ta ortam değişkenini
PowerShell üzerinden ayarlayın veya standart Qt platformunu kullanın).
`packaging/build_windows.py` Shapely ve GEOS DLL'lerini toplar; mevcut tek
EXE dağıtımı korunur. Paket açılış kontrolünde gerçek DXF içe alma/NFP/
ağırlık/Excel/PDF/DXF denemesi eklendi. Bu değişiklik için EXE üretilmedi;
gerçek Windows paket kontrolü sonraki istenen EXE derlemesinde çalışacak.

Referanslar ve lisans değerlendirmesi: [teknik rapor](../docs/nesting.md).
[Toplu yükleme ve plaka sırası düzeltmesi](../docs/nesting-bulk/README.md).
[Sade arayüz incelemesi ve plaka sekmeleri](../docs/nesting-usability/README.md).
