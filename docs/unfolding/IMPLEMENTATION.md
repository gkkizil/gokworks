# Sac Açınımı altyapısı — ilk çalışan teslim

5 Kasım 2026. Taban `ec62f5f`; görev dalı `agent/codex-sheet-unfolding`.

## İncelenen mevcut altyapı

Python 3.13.5, PySide6/Qt Widgets 6.10.3; `gui_qt/app.py` modül kayıt düzeni,
`gui_qt/workers.py` seri JobManager, dişli `service.py/worker.py/cad.py`
ayrı CAD süreci örüntüsü, nesting `models.py/dxf_import.py/dxf_export.py`,
tolerans raporlarının Qt PDF/atomik dosya yaklaşımı, PyInstaller Windows
paketleme ve Agent integration akışı incelendi. `requirements.txt` içindeki
ezdxf 1.4.3, Shapely 2.1.2, cadquery-ocp-novtk 8.0.1.1.0 yeniden kullanılır.
Yeni üçüncü taraf bağımlılık, FreeCAD, LLM, web servisi veya hesap sistemi yok.

## Gerçek çalışan kapsam

5 aile, 7 varyant: düz/eğik kesilmiş silindir; tam/kesik konsantrik koni;
merkezli dört panelli dikdörtgen redüksiyon; merkezli sekiz panelli fasetli
dikdörtgen–yuvarlak; sabit çaplı, serbest toplam açılı segmentli dirsek.
Katalog/boş fonksiyon yerine gerçek 2D konturlar, montaj koordinatında 3D
ağlar, parametre şeması, alan/kesim/kütle/maliyet ve kalite kayıtları üretilir.

Çekirdek dosyaları:

- `models.py`, `registry.py`, `validation.py`, `service.py`: değişmez v1
  sözleşme, gerçek şekil kayıtları, birim/normal offset dönüşümü, cache.
- `geometry.py`, `quality.py`, `shapes/`: eğriler, analitik alan/uzunluk,
  kontur/mesh denetimi, şekle özel geometri.
- `storage.py`: sıkı, yinelenen anahtarları ve bilinmeyen alanları reddeden
  sürümlü JSON; atomik ve no-clobber dosya yayını.
- `dxf.py`, `pdf.py`, `exporting.py`, `batch.py`: gerçek çıktılar, doğrulama,
  ayrı katmanlar, Türkçe PDF ve kısmi hataları gizlemeyen ZIP manifestleri.
- `cad.py`, `cad_process.py`: bağımsız OCCT orta yüzeyleri ve sınırlandırılmış
  headless süreç; tekrar okuma yüzey sayısı/alan/kutu kontrolü ve dosyaya
  bağlı SHA-256 doğrulama kanıtı olmadan başarı kabul edilmez.
- `nesting.py`: mevcut Part modeline gerçek kontur/delik/malzeme/kalınlık/
  adet ve özgün analitik DXF taşıyan adaptör; nesting motoru değiştirilmedi.
- `__main__.py`: GUI olmadan gerçek örnek hesaplama/çıktı CLI'sı.

UI sahibi Claude'dur. Hiçbir ekran, tema, modül menüsü veya controller
dosyası değiştirilmedi. Ortak dosyalar: `main.py` üç satırlık worker yönü;
`packaging/build_windows.py` tek `--collect-submodules core.unfolding` satırı.

## Hesap yöntemleri ve ölçüm konvansiyonları

Silindir orta çapı içten `D+t`, dıştan `D−t`; açınım çevresi πD_mid'dir.
Eğik üst kesim `z=H−r tan(β) cos(θ−azimut)` düzlem kesişimidir. Açınımda
`x=r(θ−θ₀)`; kesim eğrisi ikinci türevden sınırlanan kord hatasıyla örneklenir.
Ekran piksel sayısı kullanılmaz; önizleme mesh toleransı ayrıdır.

Konide `s=hypot(H,R−r)`, sektör yarıçapları `sR/(R−r)`, `sr/(R−r)`, açı
`2π(R−r)/s`'dir. Alan `π(R+r)s`. Uçlar sabit z=0/H ölçüm düzlemleridir;
referans yüzeyden orta yüzeye yarıçap değişimi
`±t/2 sqrt(1+((R−r)/H)²)` olarak normal mesafeden çözülür. Bütün boylara
körlemesine t eklenmez. Tam koninin t>0 inner/outer tepe bitişi reddedilir.
Yakın-eşit çapta kararlı sinüs/alan ifadeleri ve açık raporlanan silindir
limiti kullanılır; çok uzak yay merkezleri nedeniyle kontur gereksiz taşınmaz.

Dikdörtgen redüksiyonda dört düz trapezin gerçek eğik yüksekliği ve
genişliği kullanılır. Normal offset sabit uç düzlemlerinde yan düzlemlerin
normal vektörlerinden çözülür. Dört ayrı kaynaklı paneldir; büküm telafili
tek abkant blank'i gibi sunulmaz.

Dikdörtgen–yuvarlak geçiş dört düz üçgen ve köşe tepesinden üst çembere
kurulan dört üçgen fanıdır. Her üçgenin gerçek 3D kenar uzunluklarıyla 2D
trilaterasyon yapılır. Kord hatası ve kenar uzunluğu korunumu raporlanır.
Faset yapısı tanımlıdır; herhangi bir loft'u düzleştirme iddiası yoktur.
İmalat dönüşleri/büküm planı, köşe radyüsü ve kalınlıklı inner/outer offset
uygulanmaz. Desteklenmeyen istek hata verir.

Dirsekte N toplam segmenttir; iki uç yarım segment dahildir. Birleşim
sayısı N−1, eksen adımı `Δ=toplam_açı/(N−1)`, miter yarım açısı Δ/2'dir.
İlk/son eksen boyu `R tan(Δ/2)`, aradakiler iki katıdır; uç uzatmaları
ayrıca eklenir. Her birleşim yönlerin açıortay düzlemidir; silindire gerçek
düzlem kesişimi uygulanır. Çıkış konumu bağımsız yay uç noktasıyla ve
komşu kesim eğrileri dünya koordinatlarında karşılaştırılarak doğrulanır.

Bindirme yalnız her çevresel parçanın seçili bitiş dikişine şerit ekler;
tüm kontur offset yapılmaz. Net, paylı kesim ve çevreleyen dikdörtgen
alanları ayrıdır. Kütle paylı alan×t×1e−9×ρ; t=0 veya ρ eksikse None'dır.
Kullanıcı kg, m² veya kesim metre fiyatı sağlamadıkça maliyet hesaplanmaz.

## Dosya ve CAD doğrulaması

DXF mm, Z=0, kapalı LWPOLYLINE/CIRCLE; gerçek yaylar bulge ile kalır.
Kesim, yardımcı, dikiş, ölçü ve etiket katmanları ayrıdır. DXF yeniden
okunur; testler ayrıca ezdxf'nin bağımsız path çözücüsüyle alanı karşılaştırır.
Nesting adaptörü aynı bulge eğrilerini yalnız kesim içeren DXF metni olarak
korur; 17° döndürme ve öteleme sonrası nesting DXF'i geri okunarak sınanır.

PDF A4/A3, gerçek metin ve vektör çizim, Türkçe parametreler, ayrı ön/üst
görünüş, açınım, G çizgileri ve gerçek boy listeleri içerir. Sayfaya sığdırma
açıkça yazılır; 1:1 değildir. PDF tekrar açılır; parça/metin/ölçek doğrulanır.
Font sistem Arial/fallback fontudur; ayrı font dosyası dağıtılmaz. Gerçek
Türkçe karakter/tire geri okuma testi vardır. PDF arka planı sabit beyazdır.

STEP yalnız doğrulanmış **orta yüzey** B-Rep'tir. Düz silindir, konsantrik
koni ve düz/fasetli paneller desteklidir. Kalınlıklı solid, SolidWorks
özellik ağacı veya mesh'ten türetilmiş sahte solid yoktur. Eğik silindir,
dirsek kırpması ve bindirmeli STEP v1'de açıkça kapalıdır. Worker süreç
iptal/süre aşımında sonlandırılır; mevcut dosya üzerine kısmi yayın yapılmaz.

## Kaynaklar ve sınırlamalar

Unfoldo davranış referansı, kullanıcının 5 Kasım 2026 tarihli görev
dosyasındaki herkese açık gözlemlerdir; sunucu algoritmaları veya sayısal
doğruluk iddiaları kullanılmadı. Bu ortamın ağ izinlerinde Unfoldo/yardım
siteleri bulunmadığından canlı site incelemesi yapılmış gibi gösterilmez.
ezdxf'nin kurulu LWPOLYLINE bulge API'si ve OCP'nin kurulu resmi wrapper
imzaları gerçek dosya testleriyle doğrulandı. Başlangıç kaynakları:

- https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html
- https://dev.opencascade.org/
- https://help.solidworks.com/2017/english/SolidWorks/sldworks/c_Bend_Allowance_and_Bend_Deduction.htm

BA bağıntısı `|β_rad| (R_inside+K t)` yalnız açık kullanıcı K ile yardımcı
fonksiyondur. Malzeme akışı, incelme, yaylanma, ömür veya imalat toleransı
doğrulaması yoktur; bunlara onay verilmez. İmalat toleransı kalite kaydında
None'dır. Geometri toleransı/kord/mesh toleransı ayrı tutulur.

Windows EXE'nin bu yeni çekirdek ile canlı çalışması ve SolidWorks
entegrasyonu bu Linux oturumunda test edilmedi. Temel işlev SolidWorks
gerektirmez. Mevcut paketlemede Qt, Shapely ve OCP toplama/lisans altyapısı
vardır; bu görev yeni native bağımlılık eklemez. Canlı Windows kabulü CI ve
gerçek dağıtım ortamında ayrıca yapılmalıdır.

## Sonraki aşamalar — çalışan sayısına dahil değildir

1. Claude: sözleşmeden form, 2D/3D, revizyon kontrollü JobManager ve menü.
2. Eğik silindir/dirsek için doğrulanmış analitik B-Rep yüzey kırpması.
3. Eksantrik/eğik koni, kaçık geçiş ve kalınlıklı tepe/köşe bitiş modelleri.
4. Branşmanda hem dal kurtağzı hem ana boru deliği; Y ve kesişimler.
5. Kanal/oval/prizma/piramit aileleri ve isteğe bağlı büküm tabloları.
6. Bombe/helis yalnız doğrulanmış yaklaşım ve deformasyon metrikleriyle;
   doğrulanana kadar üretim dışa aktarması kapalı kalmalı.
7. Yerel PDF/DXF ölçü çıkarımı ve kullanıcı onayı; AI/OCR ancak ayrı,
   isteğe bağlı sağlayıcı adaptörüyle. Dosya kendiliğinden buluta gönderilmez.

Çalışan referanslar `examples/`, sözleşme `contract_v1.md`, Claude notu
`CLAUDE_HANDOFF.md`, doğrulama paketi `tests/unfolding/` altındadır.

## Doğrulama sonuçları

- **85 yeni çekirdek/kayıt/çıktı testi geçti**; hata ve atlanan test yok.
  Bağımsız sayısal referanslar, yüzey/kenar korunumu, iki ölçü birimi,
  inner/mid/outer, gerçek miter arayüzleri, iptal/cache, bozuk JSON/STEP,
  Türkçe A4/A3 PDF, DXF bulge ve 17° nesting dönüşümü kapsandı.
- **124 mevcut regresyon testi geçti**; hata ve atlanan test yok. Depo
  yapısı, Windows build giriş betiği, paket verileri, mevcut sayfa açılışları,
  nesting/delik geometrisi, dişli hesabı, mil geometrisi ve kayış arayüzü.
- `main.py --self-check` geçti: 18 mevcut sayfa, iki tema ve çözünürlük
  matrisi. Menü entegrasyonu Claude'a ait olduğundan yeni boş sayfa yok.
- Ruff E9/F ve `git diff --check` geçti. Gerçek örnek DXF/PDF/STEP/ZIP
  üretildi; PDF sayfası ayrıca render edilerek görsel olarak incelendi.
- Ortam Python 3.13.5/Linux, Qt 6.10.3/offscreen, gerçek yerel OCP'dir.
  Windows EXE ve canlı SolidWorks kabulü bu sonuçlara dahil değildir.
