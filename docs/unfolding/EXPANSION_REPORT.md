# Sac Açınımı genişlemesi: hesap, çıktı ve GitHub kaynakları

6 Kasım 2026. Görev dalı `agent/codex-unfolding-expansion`; geometri
uygulaması `11c279c`. Bu rapor kayıtlı kimlik sayısını imalata uygun model
sayısı olarak kullanmaz. **191 kaynak varyantının her biri için normal
hesap ve çıktı örneği doğrulandı; kaynağın bütün özellikleriyle eşdeğerlik
ve üretim onayı verilmedi.** Açık eksikler aşağıdadır.

## Kapsam ve kanıt

| Ayrı ölçülen kapsam | Sonuç |
|---|---:|
| Kaynak kimliği / aile / kategori | 191 / 51 / 11 |
| Kaynak ölçü alanı / kesim kümesi | 1136 / 53 |
| Yalnız kayıtlı/planned kalan hesap kimliği | 0 |
| Geçerli hesap örneği ve geçersiz girdi testi olan kaynak kimliği | 191 |
| Geri okunan 1:1 mm DXF | 363 dosya, 191 model |
| Metni geri okunan ve ilk sayfası render edilen PDF | 191 |
| Geri okunan gerçek OCCT STEP orta yüzeyi | 79 |
| Doğrulanmış STEP solid | 0 |
| JSON proje kaydet/aç turu | 191 |
| Özgün DXF ve adetleriyle nesting adaptörü | 191 |
| Kaynakla tam özellik eşdeğerliği / üretim onayı | Doğrulanmadı |

191 satırın tamamı: [source_coverage.csv](source_coverage.csv).
Kaynak kimliği, iç kimlik, yöntem, hesap/2D/3D/DXF/PDF/STEP/nesting,
testler, uygulama dosyaları ve kısıtlar ayrı sütunlardadır.
[unfoldo_inventory.json](unfoldo_inventory.json) kaynak alanlarını ve
uygulama durumunu; [source_validation.json](source_validation.json) her
modelin isteğini, çıktı hash'lerini ve ölçüm/geri okuma kanıtını taşır.
Tekrar üretilebilir örnekler [examples/source_models.json](examples/source_models.json)+içindedir. Tam dosyalar ve PNG'ler çalışma ortamında
`/workspace/artifacts/unfolding-expansion-final/` altında korunur.

Kaynak envanterinin HTTP/canonical/h1/sitemap doğrulaması kullanıcı tarafından
5 Kasım'da sağlanmıştır. Unfoldo hesap motoru/CAD dosyaları elde edilmedi.
Kaynağın 184 referans metadatası bir GOKWORKS kabul sayısı değildir. Dört
yayımlanmamış başlık sayılmaz. Önceki 5 aile / 7 API varyantı eski projeleri
açmak için korunur; yeni 191 sayısına eklenmez.

## Mevcut altyapı ve mimari

Taban `60bef56`, Claude arayüz PR #28 birleşimidir; ilk çekirdek PR #27 de
bu geçmiştedir. Güncel `AGENTS.md`, worktree/dal durumu, `core/unfolding`,
`modules/sheet_unfolding`, Qt iş yöneticisi, nesting veri modeli, CAD süreç
sınırı, paketleme ve agent integration akışı incelendi. Başka worktree'nin
kullanıcı/ajan değişiklikleri alınmadı veya sıfırlanmadı.

Python 3.13; mevcut PySide6/Qt Widgets, ezdxf, Shapely/GEOS ve OCP/OCCT
yeniden kullanılır. GUI, LLM, SolidWorks veya internet olmadan hesap yapılır.
Yeni çalışma bağımlılığı yoktur. Matematik GUI'den ayrıdır; CAD işi iptal ve
süre aşımı destekleyen ayrı süreçtedir. Sonuçlar/istekler değişmez veri
modelleridir. UI/çıktı aynı sonuç snapshot'ını kullanır; eski revizyon/hash
ve iptal kontrolleri korunur.

`UnfoldRequest` şema v1'e geriye uyumlu `model_options` eklendi. Kaynak
kimlikleri değişmeden korunur; `shape_id=unfoldo/<aile>`,
`variant_id=<source_id>`. Registry'nin gerçek hesap tanımları 51 aileyi
dinamik sağlar. Açı/adet/ayrık seçenek birim dönüşümüne girmez; W/w gibi
alanların harf farkı korunur. Katalog örnek girdileri fiziksel geçerlilik
garantisi değildir. Dokuz normal örnekte gereken farklı girdiler ayrı
`source_default_overrides` kaydıyla açıklanır; kaynak varsayılanları silinmez.

## Gerçek hesap yöntemleri

| Yöntem sınıfı | Model | Uygulama |
|---|---:|---|
| Analitik açılabilir | 28 | Dikdörtgen/halka dilimi, prizma/piramit ve düzlemsel kanal levhaları |
| Örneklenmiş açılabilir | 114 | Analitik düzlem/kuadrik kesişim; gerçek silindir/koni/oval yay koordinatında açma |
| Gerçek uzunluk fasetleri | 42 | Doğru kesit eşlemesi ve gerçek 3D üçgen kenarlarıyla açma |
| Şekillendirme yaklaşımı | 7 | Bombe dilimi, farklı helezon yüzeyleri veya deforme halka; deformasyon kısıtlarıyla |

Silindir `x=rθ` ile açılır; orta çap inner/mid/outer için D+t / D / D−t
olur. D=200, H=300, t=0 örneğinde genişlik
628.3185307179587 mm'dir. Oval iki yarım daire+düz kenarlıdır; elips ayrı
parametrik profildir. Prizmada gerçek çokgen kenarları kullanılır.

Konsantrik konide eğik boy `s=hypot(H,R-r)`, sektör yarıçapları
`sR/(R-r)` ve `sr/(R-r)`, açı `2π(R-r)/s`; alan `π(R+r)s`'dir.
Eşit çapta açık silindir limiti vardır. Tepe yüksekliği/açı alternatifleri
aynı fiziksel çözüm girdilerine dönüştürülür. Eğik/düzlem/çatı kesimleri ve
katlar gerçek ayrı geometrilerdir. Yağmur haznesinin arka sacı duvar
kesişiminden ayrıca çıkarılır.

Geçişlerde ortak dış normal ve düz yüz eşlemesi köşeleri korur. Düz kenar
bir üst noktaya eşlendiğinde gerçek üçgen fan kurulur. Konturu zorla düz
tabana yerleştirme veya bütün profilleri genel silindire indirgeme yapılmaz.
Üst/taban eğimi, X/Y offset, köşe yarıçapı, level ve köşegen geometriye katılır.
Faset yönteminde gerçek üçgen kenarları korunması düzgün, çift eğrilikli
yüzeyin gerinimsiz açılacağı anlamına gelmez.

Segmentli dirsek ve gönye dirsek ayrı çözülür. Segmentli dirsekte iki uç
yarım segmenttir; n−1 ortak düzlem vardır. Oval yönleri/redüksiyon/uzatma,
S ve çok düzlemli S ayrı girdilerle gerçek parçaları üretir. Boru–koni
gönyesinde uyumlu kuadriklerin düzlemsel elips şartı kullanılır.

Branşman üreteci ana silindir/koni kuadriğine yerleştirilir, ikinci derece
kesişim çözülür. Kol kurtağzı ve ana gövde deliği aynı 3D kesişimle ayrı
üretilir. Çoklu kollarda komşu yüzeyler ayrıca kırpar. Uyumlu gövdeli
pantolon konilerinde `F=|P|²−R²−β²` ve ağırlıklı doğrusal ayırıcı düzlemler,
parçalar arasında gerçek ortak dikiş sağlar. Dirseğe giren boruda torus
kesişimi sayısal kökle ve bağımsız yüzey artığıyla denetlenir.

Kanallar gerçek kapak/duvar yollarıdır; 4/5/6 plaka ve paylar gerçek parça
adetlerini/kenarlarını değiştirir. `lap_top` duvarın iki uzun kenar flanşı,
`lap_left` iki uç bindirmesidir; kapaklar bbox büyütmesiyle şişirilmez.

Bombe crown/knuckle/etek ve üst delik ayrı hesaplanır. Açınım bir dilimdir,
adedi n'dir. Helezonlar ayrı yüzeyler ve son kısmi tur üretebilir. Deforme
halka dış kenarı eşleştirir, gerekli iç kenar uzamasını raporlar. Bunlar
pres/çekme, gerinim kapasitesi veya yaylanma çözümü değildir.

Yöntemlerin ayrıntıları ve ölçü yorumları [SOURCE_MODELS.md](SOURCE_MODELS.md)+içindedir. Bu geometri formülleri bir DIN/EN üretim standardı sertifikası
veya Unfoldo ile sayısal eşdeğerlik iddiası değildir.

## Çıktı doğrulaması

DXF 1:1 mm, kapalı geçerli konturlar ve gerçek delikler üretir. Analitik
yaylar korunur; bağımsız DXF bulge integraliyle alan/kesim boyu tekrar
ölçüldü. CUT/BEND/SEAM/ANNOTATION sözleşmeleri korundu. Yeni katlama
çizgilerinde işaretli yön hesaplanmadığı için nötr `BEND` kullanılır.
Yardımcı 12/24/36/48/72/96 çizgi seçimi adaptif eğri toleransından ayrıdır.
Ölçülen örnekleme artığı üretim hata sertifikası değildir; 0.005 mm
üretim doğruluğu iddia edilmez.

191 PDF'in tüm sayfa metni geri okundu; ilk sayfa render edildi, seçili
sayfalar görsel incelendi. Türkçe, parça adları/adetleri ve yaklaşım
uyarıları korunur; PDF sayfaya sığar ve 1:1 değildir. Bütün PDF sayfalarının
insan tarafından tek tek görsel kabulü yapılmış sayılmaz.

79 STEP, gerçek analitik veya açıkça fasetli OCCT **surface B-Rep** içerir.
Dosya yeniden açılarak alan, sınır kutusu ve yüzey sayısı denetlenir.
STL mesh'i sahte STEP solid'e çevrilmez. Doğrulanmış analitik kırpma yoksa
STEP kapalıdır. 112 modelde bu örnek için STEP yoktur; kimlikleri matriste
tek tek `unavailable` olarak bulunur. Yerel SolidWorks özellik ağacı/SLDPRT
veya SLDASM bu çalışmada üretilmedi.

Proje kayıt/adet, toplu ZIP/PDF, kısmi hata manifesti, iptal/süre aşımı ve
mevcut dosyayı koruma regresyonları devam eder. Nesting adaptörünün özgün
DXF ve adet aktarımı 191 örnekte denetlendi; 191 bağımsız optimize nesting
işinin çalıştırıldığı iddia edilmez.

## GitHub depolarından alınan katkı

Kullanıcının ek talebiyle yalnız bu konuya odaklanan **sekiz GitHub deposu**
çekildi ve incelendi. Tam tablo, lisans/commit/dosya hash'leri,
tekrar üretilebilir karşılaştırma ve reddetme gerekçeleri
[research/README.md](research/README.md) içindedir.

MIT `sheet-metal-unfold` büküm matematiği `bend_profiles.py` içine
uyarlandı: açık iç/dış/teğet boylar, büküm payı/deduction/çizgi konumu ve
ölçülmüş numuneden K geri hesabı. 128 upstream karşılaştırması ve 25
bağımsız Python testi geçti. Genel K tabloları/kalıp sezgileri alınmadı.
Bu yardımcı backend'de bağımsızdır; 191 fitting'e otomatik uygulanmaz ve
arayüz kontrolüne bağlanmış sayılmaz. MIT metni lisans paketinde korunur.
GPL/LGPL/MPL veya lisanssız dış motor kodu bu çalışmada alınmadı.

## Testler ve kanıtın sürümü

`11c279c` sabit geometri sürümünde **851 test geçti**, hata/atlama yok.
Bağımsız sabit formüller, tüm model normal/yanlış örnekleri, bütün 1136
alanın etkisi, birimler, kesim parçaları, ortak 3D dikişler ve mevcut GUI
regresyonları içerilir. Ayrıca 191 model çıktı taraması sıfır hata ile bitti.
`source_validation.json` bu sürümün birleşik kaynak hash'ini ve dosya
hash'lerini saklar. Sonradan eklenen bağımsız `bend_profiles.py` bu
geometri kanıtının kapsamına geriye dönük eklenmemiştir; kendi test ve
upstream karşılaştırma kaydı vardır.

MIT yardımcı ve güncel envanter/kanıt metadatasından sonra bütün açınım
ve GUI regresyonları tekrar çalıştırıldı: **876 test geçti; 0 hata, 0 atlama**.
31 ayrı test sürecinin hepsi başarılıdır. JUnit/log hash'leri
`source_validation.json.final_regression_suite` içinde saklanır. Ek
üçüncü taraf skaler karşılaştırma sayısı 128'dir; pytest sayısına eklenmez.
Değişen Python dosyalarında Ruff E9/F ve `git diff --check` geçti. Geniş
tarama, değişmemiş Claude `drawing.py` dosyasında önceden bulunan kullanılmayan
`fmt` importunu da gösterdi; ilgisiz arayüz dosyası değiştirilmedi.

```sh
QT_QPA_PLATFORM=offscreen python packaging/run_windows_tests.py \
  tests/unfolding modules/sheet_unfolding/tests
QT_QPA_PLATFORM=offscreen python -m tests.unfolding.verify_source_outputs \
  --output /tmp/unfolding-output-proof
```

Python 3.13.5/Linux, PySide6 6.10.3, ezdxf 1.4.3, Shapely 2.1.2,
cadquery-ocp-novtk 8.0.1.1.0 kullanıldı. Betiğin adındaki `windows` gerçek
Windows testi anlamına gelmez: burada ayrı Linux/offscreen test süreçleri
çalıştı. Canlı Windows/SolidWorks/ODA/EXE ve FreeCAD/Inkscape/Gusset'in
tam uygulama testleri yapılmadı.

Kaynak dağıtımında `main.py --self-check` ayrıca başarılıdır: 19 modül,
iki tema, çözünürlük matrisi, mevcut dişli CAD/çıktı, nesting/rapor ve
lisans arşivi kontrolleri geçti. Bu Linux/offscreen açılışı Windows EXE
veya canlı COM kabulü değildir. Kanıt `application_self_check` alanındadır.

## Eksik özelliklerin açık kimlikleri

- `pipe-to-pipe-angle-branch`: `heel=true` için sayısal tanım yok;
  özellik açık hatayla reddedilir. Normal kol hesabı çalışır.
- `pipe-to-bend-concentric`, `pipe-to-bend-offset`, `pipe-to-bend-angled`:
  torus temas geometrisi doğrulandı, ancak kaynağın E/Z/X/A ölçü yorumu
  teknik çizimiyle eşdeğerlik doğrulanmadı.
- `mitred-elbow-double-outside`: dış H/X'ten D çıkarma yorumu kaynak
  ölçü çizimiyle ayrıca doğrulanmalı.
- 42 faset geçiş ve 7 şekillendirme yaklaşımında düzgün yüzeyin
  gerinimsiz açınım/imalat kabulü yoktur. Bütün kimlikler matriste yöntem
  ve kısıtlarıyla ayrı listelenir.
- Koni/silindir/oval/prizma dışındaki birçok ailede yalnız mid girdisi
  desteklenir; ana gövde/kol için iki bağımsız cidar ve ölçü yüzeyi yoktur.
- İmzalı katlama yönü, genel kerf, kaynak toleransı, malzeme şekillendirme
  davranışı, otomatik takım seçimi ve üretim onayı değerlendirilmedi.
- Claude ekranında modele özgü yeni kesim/pay/bölme/numara seçicileri
  ayrıca tamamlanmalı. Dinamik 191 model metadatası ve DTO/proje/birim
  koruması hazırdır; yeni seçiciler çalışan arayüz diye sunulmaz.

Bu nedenle **“Unfoldo'nun bütün özellikleri eksiksiz tamamlandı” denmez**.
Eksiksiz kayıt+hesap örnekleri ve doğrulanmış uygun çıktılar ile kaynak
özellik/parite/proses onayı birbirinden ayrılır.

## Değişen dosyalar ve sonraki adım

Yeni ana dosyalar `source_models.py`, `shapes/development.py`,
`support_profiles.py`, `source_dispatch.py`, `source_extrusions.py`,
`source_lofts.py`, `source_planes.py`, `source_bends.py`,
`source_intersections.py`, `source_complex.py`, `source_ducts.py`,
`source_formed.py`, bağımsız `bend_profiles.py`; envanter/örnek/kanıt/matris,
araştırma/lisans ve kaynak model testleridir. Her modelin somut uygulama
dosyası envanterde bulunur.

Ortak çekirdek sözleşmesi, validation/registry/service, geometry/CAD/DXF/PDF
ve exporter yalnız gerekli genişleme için değişti. UI ortak dosyaları
`modules/sheet_unfolding/service.py` (dinamik şema/DTO), `numbers.py`
(yöntem etiketleri), `ui.py` (model seçeneklerini proje/birim çevriminde
koruma); `packaging/build_windows.py` envanter JSON paketlemesidir.
Tema/menü/ekran yerleşimi yeniden tasarlanmadı. Bu dosyalarda başka ajan
çalışırsa DTO ve model seçenekleri alanlarında entegrasyon dikkat gerektirir.
Diğer modüller, ana worktree ve AGENTS.md değiştirilmedi.

Sonraki iş sırası: kaynak teknik çizimleriyle beş açık ölçü/topuk yorumunu
çözmek; Claude'un görünür seçenek kontrollerini tamamlamak; eksik analitik
kırpılmış STEP yüzeylerini doğrulamak; gerekli ailelerde normal offset'i ve
imalat modeli kabulünü eklemek; gerçek Windows/EXE/SolidWorks kabulü.
[CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md) dosya/alan bazlı sözleşmeyi verir.
Teslim normal ajan PR/Windows doğrulama akışını izler; main'e doğrudan
push veya başarısız testi atlama yapılmaz.
