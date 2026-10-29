# Delik içlerini kullanma · GOKWORKS NFP 1.3

21 Ekim 2026. Kullanıcının işaretlediği büyük iç delikler artık yerleşim alanı
olarak değerlendiriliyor. Değişiklik mevcut Python/Shapely motoruna ve PySide6
arayüzüne entegredir; yeni bağımlılık veya harici nesting programı gerektirmez.

**Yerleştir** düğmesine basmak yeterlidir: uygun delik içleri otomatik kullanılır.
Kullanıcıya bunu açıp kapatması için bir seçenek sunulmaz. Eski projeler de
ayar/imza değişikliği gerektirmeden açılır; yeniden yerleşim yapıldığında bu
alanlar otomatik değerlendirilir. Kaydedilmiş eski koordinatlar geçerli kalır.

[Arşiv: Deliklere yerleşen küçük parçalar](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/nesting-hole-placement/after.png)

## İncelenen GitHub kaynakları ve lisanslar

| Proje | Okunan kaynak / lisans | Bu değişiklikte kullanım |
| --- | --- | --- |
| [SVGnest](https://github.com/Jack000/SVGnest) | `svgnest.js`, `util/placementworker.js`, `LICENSE.txt`; MIT, Jack Qiao. `useHoles`, delik çocukları ve iç NFP yaklaşımı. | Yaklaşım referans alındı; GOKWORKS için özgün Python yazıldı. Mevcut MIT bildirimi korunur. |
| [Deepnest](https://github.com/deepnest-next/deepnest) | `main/deepnest.js`, `LICENSE`, `LICENSES.md`. Ana lisans MIT; dosya envanteri bu motor dosyasını GPLv3 olarak listeliyor. | İç kontur/çocuk ağaçları incelendi. GPL veya JavaScript kodu kopyalanmadı, Electron/native motor eklenmedi. |
| [libnest2d](https://github.com/tamasmeszaros/libnest2d) | `README.md`, `LICENSE.txt`; LGPL-3.0. README mevcut yaklaşımın delik ve içbükey sınırlarını belirtiyor. | Delik desteği için seçilmedi; C++ bağlama veya yeni derleme zinciri eklenmedi. |

Okunan sekiz dosyanın sabit commit bağlantıları ve SHA256 değerleri
[references.json](references.json) içindedir. Dalın sonradan değişen içeriği
kanıt yerine kullanılmaz. Üçüncü taraf kodu bu değişiklikte projeye kopyalanmadı.

## Motor ve üretim davranışı

- Çarpışma geometrisi her zaman delikleri korur; bağımsız doğrulayıcı da gerçek
  malzeme poligonlarını kullanır. Dolu dış konturlar yalnız sıralama alanıdır.
- Çerçeveler dış alanlarına göre önce işlenir; az net alanlı bir çerçevenin
  içine girecek büyük düz parça önce levhayı kapatmaz.
- Hızlı başlangıçta delik merkez/kenar ve iç örnekleme adayları denenir;
  kalan sürede gerçek malzeme NFP aramasıyla iyileştirilir. Daire/içbükey
  deliğin sınır dikdörtgeni bir parçanın sığdığı kabulü için kullanılmaz.
- Her aday ve sonuç gerçek malzeme kesişimi, mesafe, kerf, iki parçanın eğri/uç
  hata payları, levha payı, stok, adet, malzeme/kalınlık ve hadde yönüyle doğrulanır.
- Aynı delikte birden fazla küçük parça, birden fazla delik, çok katlı iç içe
  çerçeveler ve birden çok fiziksel plaka desteklenir. Çok bileşenli grupların
  delik içindeki gerçek malzeme adaları boşluk sayılmaz.
- Alan/ağırlık: ana parçadan delik alanı düşülür; küçük parçaların gerçek net
  alanı eklenir. Brüt = net + fire korunur, çift malzeme sayılmaz.
- DXF konturları artan çevrelenmiş alana göre yazılır: küçük parça kendi
  deliklerinden sonra, onu çevreleyen büyük delikten önce kesilir. Bu kural
  çok katlı iç içe konturlarda da geçerlidir. Özgün ARC/CIRCLE korunur.
  `KESIM-SIRASI.csv`, plaka/örnek/kontur önceliğini; DXF XDATA ise plaka ve
  kontur sıra numarasını içerir. Kaynak DXF değiştirilmez.

CSV ve DXF sıra bilgisi **CAM takım yolu değildir**. CAM içe alırken sıralamayı
değiştirebilir; delikteki küçük parça kesilmeden çevreleyen delik serbest
bırakılmamalıdır. Kerf telafisi, giriş/çıkış ve bağlama CAM tarafında yapılır.
Motor sezgiseldir; her olası sığmayı bulma veya optimum yerleşim garantisi yoktur.

## Önce/sonra örneği

Bu, kullanıcının gerçek CAD dosyasının kopyası değildir. Tekrar üretilebilir
örnekte iki adet 110×150 mm çerçeve (Ø80 mm delik), on iki adet 12×18 mm parça,
120×320 mm levha, 4 mm kenar payı, 3 mm parça aralığı ve 0,2 mm kerf vardır.

| | Önceki motor (1.2) | Otomatik delik kullanımı (1.3) |
| --- | --- | --- |
| Yerleşen parça | 14 | 14 |
| Kullanılan levha | 2 | 1 |

[Arşiv: Önce](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/nesting-hole-placement/before.png) · [Arşiv: Sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/nesting-hole-placement/after.png) · [Arşiv: Açık tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/nesting-hole-placement/after-light.png) ·
[Arşiv: Ayar](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/nesting-hole-placement/settings.png) · [Sayısal karşılaştırma](comparison.json) ·
[Örnek DXF'ler](source-parts) · [Önceki proje](before.goknest.json) ·
[Yeni proje](after.goknest.json).

Git geçmişi bulunan depo klonunda `python docs/nesting-hole-placement/reproduce.py`
bu örneği, projeleri ve gerçek GOKWORKS ekran görüntülerini yeniden üretir.
Önceki motor yalnız bu karşılaştırma için `a9dd65a` commit'inden geçici
dizine okunur; eski motor mevcut uygulamaya gömülmez ve dal değiştirilmez.

## Doğrulama

`modules/nesting/tests/test_hole_nesting.py`: dairesel ve dikdörtgen delikler,
çoklu parçalar/plakalar, iç içe çerçeveler, net alanı küçük taşıyıcı sıralaması,
90° dönüş/hadde kilidi, duvara taşma, yetersiz mesafe, eğri hata payı,
kalınlık uyuşmazlığı, içbükey delikte yanıltıcı sınır dikdörtgeni, iç malzeme
adası, eski JSON imzası/tahrif kontrolü, ARC/CIRCLE koruma ve CSV/DXF sırası.
Qt testi gerçek arka plan işinde ayrı seçenek bulunmadığını, sonuç iptalini, plaka adedini ve delik
içindeki parçaya tıklamayı doğrular. Paket öz denetimine beş parçanın tek
plakaya delik kullanarak yerleşmesi ve CSV üretimi eklendi.

Son sürümde 107 nesting testi ve 165 ortak arayüz/paketleme regresyon testi
geçti (toplam 272; hata ve atlanan test yok). Nesting testleri mevcut paketleme
test çalıştırıcısıyla en fazla 32 testlik dört ayrı süreçte çalıştırıldı.
12 modül, iki tema ve dört çözünürlük için kaynak paket öz denetimi de geçti.
[Çalıştırılan komutlar ve kapsam](checks.json) · [Öz denetim sonucu](selfcheck.json).

Yeni kod Linux/Qt offscreen üzerinde test edildi. Bu değişiklik için yeni
Windows EXE henüz üretilmedi; gerçek tezgâh/CAM kesimi çalıştırılmadı.
