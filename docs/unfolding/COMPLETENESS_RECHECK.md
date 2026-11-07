# Kaynak katalog kapsam kontrolü ve katı STEP — 7 Kasım 2026

Güncel kaynak karşılaştırması ve çıktı kanıtı bu dosya, `live_source_audit.json`
ve `source_coverage.csv` ile birlikte okunmalıdır. Eski genişleme raporundaki
79 STEP **yüzey** sayısı bu sürümün katı desteğini ifade etmez.

## Canlı kaynak kontrolü

Kaynak katalog ana sayfasındaki bütün “daha fazla” ve aile varyant listeleri tarayıcıda
açıldı. **191 model bağlantısının tamamı** GOKWORKS envanteriyle eşleşti.
191 model sayfasının her biri HTTP 200, canonical, h1 ve sitemap ile ayrıca
denetlendi. Sonuç: 51 aile, 11 kategori, 1.136 ölçü alanı, 382 kesim/dikiş
seçeneği. Eksik kaynak kimliği bulunmadı. Boş/yayımlanmamış kategori başlıkları
model diye sayılmadı.

Kaynak metadatasında `rectangle-to-cone-angle-branch.Hr` varsayılanı 200'den
250 mm'ye değişmişti; alan sıralamasında L ve Z de yer değiştirmişti. Kayıt
güncellendi; önceki değer ve tarih `source.live_recheck` içinde korunur.
Çalışan örnekler kaynak varsayılanlarından ayrı, açık parametreli örneklerdir.

Tekrar çalıştırma (internet gerektirir; otomatik pytest ağ kullanmaz):

```sh
python -m tests.unfolding.audit_live_source --output /tmp/live-source-audit.json
```

Bu incelemede yalnız yayımlanmış form/katalog bilgileri ve normal tarayıcı
görünümü kullanıldı. Kaynak kataloğun hesap motoru, ücretli dosyaları, görselleri
veya üçüncü taraf algoritma kodu projeye aktarılmadı.

## Düzeltilen görünür eksikler

- Belirli varyantın adını arayıp aileyi seçmek ilk varyantı açıyordu. Artık
  eşleşen varyant açılır; aynı aile zaten seçiliyken tıklamak da çalışır.
- Tam model adları, kaynak kimlikleri ve Türkçe İ/ı ile aksansız arama desteklenir.
- Aile kartları varyant sayısını gösterir. 51 aile kartı, 191 ayrı hesap
  varyantının tek seçeneğe indirgenmesi anlamına gelmez.
- Eğik/çatı kesimli boruların, oval kesitlerin, konik segmentlerin ve delikli
  branşmanların CAD tanımları tamamlandı. Teğet düz ve dairesel kesitler gerçek
  düzlem/silindir; koniler gerçek konik yüzeyler; eğik koniler rasyonel dairesel
  kesitli B-spline yüzeylerle tanımlanır. Kesim sınırları toleranslı örneklenir.

## STEP artık katı modeldir

Arayüzdeki **STEP (katı model)** düğmesi ve `ExportOptions(format='step')`
varsayılanı pozitif sac kalınlığıyla kapalı katı B-Rep üretir. Kalınlık sıfırsa
katı dışa aktarım kapalıdır. Başarısız katı işleminde yüzey dosyasına dönülmez.

```python
from core.unfolding import UnfoldService, UnfoldRequest, ExportOptions

s = UnfoldService()
r = s.calculate(UnfoldRequest(
    parameters={'diameter': 200., 'height': 300.}, thickness=2.))
out = s.export(r, ExportOptions('silindir.step', 'step'))
assert out.status == 'complete', out.errors
```

- Boyutlar normalize edilmiş nominal orta yüzeye aittir; katı bu yüzeyin iki
  yanında t/2 kalınlıkla oluşturulur. İç/dış girdi referansı yalnız şemada
  doğrulanmış modellerde seçilebilir.
- Analitik yüzeyler normal offset ve gerçek yan yüzlerle kapatılır. Tam
  konide iç/dış paralel konilerin kendi tepe noktalarıyla kapanması kullanılır;
  bu nedenle nominal orta yüzey tepe yüksekliği katının en üst ölçüsü değildir.
- **Açıkça fasetli malzeme** modellerinde incident yüzlerin paralel düzlemleri
  kesiştirilir. Eğri yelpazelerinde fazla sayıda düzlem aynı köşeyi
  kısıtlayabilir; ölçülen normal offset sapması `min(0.001 mm, 0.001×t)`
  sınırını aşarsa işlem reddedilir. Ulaşılan değer STEP başlığına da yazılır.
  Bağlantısız/non-manifold parça reddedilir. Bu sınır, düzgün yüzeyin
  gerinimsiz açınımı veya sertifikalı imalat toleransı iddiası
  değildir. Fasetli tasarım fasetli katı olarak kalır.
- `mesh_3d` yalnız ekrandaki önizlemedir. Katı üretimi bu ağı okumaz; bağımsız
  `SurfacePatch` malzeme geometrisini kullanır. STL dosyası STEP'e çevrilmez.
- Seçilen her tekil fiziksel parça ayrı katı gövdedir. Tekrarlı kesim adetleri
  STEP'te kendiliğinden çoğaltılmaz; bombe dilimi gibi çıktılarda adet ayrıca
  proje/PDF/DXF bilgisidir. Bu çıktı parametrik SolidWorks özellik ağacı değildir.

CAD işi mevcut ayrı süreçte çalışır. Kapanma, B-Rep geçerliliği, pozitif hacim,
beklenen gövde sayısı ve bağımsız açık yüz kalmaması kontrol edilir. Yazılan
STEP yeniden okunur; hacim, alan ve sınır kutusu ilk geometriyle karşılaştırılır.
Süre aşımı, iptal veya doğrulama hatasında mevcut kullanıcı dosyası korunur.

API'deki açık `step_kind='surface'` seçeneği eski teşhis/test sözleşmesi için
korunur; arayüz bunu sunmaz ve katı başarısızken otomatik kullanmaz.

## Kabul kanıtı ve sınırlar

`source_validation.json` güncel kod özeti, parametreler, çıktı hash'leri, dosya
geri okumaları, katı hacimleri ve hataları içerir. `complete` doğrulama koşusunun
tamamlanmasıdır; kaynakla tam özellik eşdeğerliği veya imalat onayı değildir.
191 satırlı `source_coverage.csv` hesap, 2D, 3D, DXF/PDF, katı STEP ve nesting
adaptörünü ayrı gösterir.

7 Kasım 2026 son doğrulama sonuçları:

| Kontrol | Sonuç |
|---|---:|
| Modül ve arayüz regresyonları | 1.061 geçti, 1 atlandı |
| Son katalog/arayüz boyut ve seçim kontrolü | 42 geçti |
| Model hesabı ve DXF geri okuma | 191 / 191 |
| PDF metni ve ilk sayfa render'i | 191 / 191 |
| JSON proje çevrimi ve nesting adaptörü | 191 / 191 |
| Kapalı, pozitif hacimli katı STEP geri okuma | 190 / 191 |
| Toplu çıktı doğrulama hatası | 0 |

Atlanan test, ortamda canlı ODA File Converter bulunmamasıdır. Canlı Windows,
SolidWorks ve ODA denemesi yapılmadı. `rectangle-to-round-angled-top` katı CAD
kabulünde **0,5 mm**, diğer örneklerde **2 mm** kullanıldı. Bu modelin 2 mm
katı isteği ayrıca reddetme testiyle doğrulandı; kalınlık otomatik azaltılmaz.
Tek STEP istisnası aşağıda açıklanan `helix-deformed` modelidir. Dolayısıyla
bu tablo “bütün kaynak özellikleri tamamlandı” anlamına gelmez.

Kesim/dikiş seçeneklerinin 382 kombinasyonu hesap testlerinden geçer.
Silindir ve delikli eğik koninin PDF ilk sayfaları ayrıca görsel olarak
incelendi. Katalog arayüzünde varyant sayılarının kesilmeden görünmesi gerçek
Qt ekran görüntüsüyle kontrol edildi.

Bağımsız CAD referansları arasında silindirin pi×(Ro²−Ri²)×H hacmi, gerçek
mil boşluğu, branşman deliğinin açık kalması, iki yarımın ayrı katı olması,
dört kanal plakasının toplam hacmi ve paralel çokgenlerle prizma duvar hacmi
bulunur. Önizleme ağını silen test de aynı CAD sonucunu doğrular.

Kapanmamış kapsam **model kaydı eksikliğiyle karıştırılmamalıdır**:

- `helix-deformed`: 2D halka şekillendirme taslağı hesaplanır; hedef deforme
  helezonun doğrulanmış CAD tanımı yoktur. Katı/yüzey STEP açılmaz.
- `pipe-to-pipe-angle-branch`: kaynaktaki topuk kutusu vardır. Tarayıcıdaki
  açıklama oturan branşmanda daha dik etkin kesim açısından söz eder; sayısal
  tanım doğrulanmadığından `heel=true` çalışıyor diye gösterilmez.
- Şeması yalnız `mid` sunan modellerde iç/dış normal offset henüz yoktur.
  `meanOnly` modellerde keyfî iç/dış dönüşüm uygulanmaz.
- `mitred-elbow-double-outside` dıştan eksene H/X dönüşümü ve üç `pipe-to-bend-*`
  modelinin kaynak E/Z/X/A ölçü yorumları tam kaynak eşdeğerliğiyle doğrulanmadı.
- Bombe, helezon ve geçişlerde açıklanan fasetleme/şekillendirme yaklaşımları
  korunur. Katı gövde bulunması dayanım, gerinim, proses veya imalat onayı vermez.
- Nesting **adaptörü** kontrol edilir; bütün modellerle tam yerleşim
  optimizasyonu, canlı SolidWorks ve ODA kabulü bu Linux koşusunda yapılmaz.

Bu nedenle `source_full_feature_parity` ve `production_approved` bayrakları
yalnız model kaydı veya katı dosya oluştu diye true yapılmaz.
Kısıtlanan kaynak kimlikleri tek tek [remaining_limits.json](remaining_limits.json)
içindedir; yalnız `mid` kabul eden 169 model listesi de bu dosyada bulunur.

## Değişen dosyalar

| Dosya grubu | Amaç |
|---|---|
| `core/unfolding/models.py`, `service.py`, `exporting.py` | 1.3.0 sürümü, katı çıktı varsayılanı, girdiye bağlı CAD uygunluğu ve hata sözleşmesi |
| `cad.py`, `cad_process.py`, yeni `solid_cad.py`, `solid_facets.py` | Gerçek B-Rep, ayrı süreç, normal kalınlık, adaptif hacim integrasyonu ve geri okuma |
| `shapes/development.py`, yeni `surface_patches.py` | Bağımsız kesit eğrileri ve analitik kırpılmış CAD tanımları |
| `shapes/cylinder.py`, `source_extrusions.py`, `source_bends.py`, `source_intersections.py`, `source_planes.py`, `source_complex.py` | Boru, oval, dirsek, koni ve branşmanların mevcut geometriyi kullanan CAD bağlantıları |
| `modules/sheet_unfolding/service.py`, `ui.py` ve UI testleri | Doğru varyant araması, görünür varyant sayısı, katı STEP düğmesi ve uygunluk gerekçesi |
| `tests/unfolding/test_solid_step.py`, `test_trimmed_step.py`, `audit_live_source.py` | Yeni katı/analitik yüzey ve canlı katalog kontrolleri |
| `tests/unfolding/test_native_outputs.py`, `test_batch_and_worker.py`, `test_audit_regressions.py`, `test_source_gui_contract.py`, `verify_source_outputs.py` | Var olan doğrulamaların yeni sözleşmeyle sürdürülmesi |
| `docs/unfolding/` envanter, örnek, kapsam, doğrulama, rapor ve devir dosyaları; `core/unfolding/README.md` | Güncel kaynak, yeniden üretilebilir kanıt ve ajan bağlamı |

## Entegrasyon

Çalışma `agent/codex-catalogue-completeness` dalında, güncel `origin/main`
`ae921e9` tabanında yapıldı. Diğer worktree'ler korunur. Ortak arayüzde yalnız
arama/varyant seçimi, varyant sayısı, STEP etiketi ve sonuç yetenek bağlantısı
değişti; Claude'un sayfa düzeni ve iş yöneticisi korunur.

Yeni CAD dosyaları `core.unfolding` altındadır. Mevcut PyInstaller
`--collect-submodules core.unfolding` ve OCP hook'u bunları kapsar; yeni pip
bağımlılığı eklenmedi. Otomatik ajan entegrasyonu `agent/codex` PR'ını sabit
head/main birleşiminde Windows testlerinden geçirir; başarısız doğrulama veya
çakışma atlanmaz.
