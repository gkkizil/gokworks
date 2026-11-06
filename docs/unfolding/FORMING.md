# Sac şekillendirme, yaylanma ve abkant telafisi — motor 1.2.0

Bu sürüm gerçek hesap, GUI, proje ve çıktı entegrasyonu içerir. Üretim uygunluk
onayı veya abkant makine programı üretmez. Eski 191 kaynak modelin geometrik
hesapları korunur; aşağıdaki destek sınırları bu modellerin hepsinin mekanik
telafisinin tamamlandığı anlamına gelmez.

## İncelenen yapı ve entegrasyon

- `core/unfolding/models.py`, `validation.py`, `service.py`: değişmez veri,
  mm normalizasyonu, cache, iptal ve başarılı sonuç sözleşmesi.
- `shapes/cylinder.py`, `source_extrusions.py`, `source_bends.py`,
  `development.py`: daire/gerçek oval çevresi, parça/dikiş düzeni, segmentler.
- `source_lofts.py`, `source_formed.py`, `quality.py`: fasetli geçişler,
  bombeler, helezonlar ve mevcut geometrik yaklaşım sınırları.
- `bend_profiles.py`: mevcut lisans bildirimleri korunan BA/BD ve kupon K hesabı.
- `storage.py`, `batch.py`, `exporting.py`, `dxf.py`, `pdf.py`, `cad_process.py`:
  atomik çıktı, miktarlar, proje manifesti, PDF ve nominal STEP sözleşmesi.
- `modules/sheet_unfolding/`: Claude arayüzü, mevcut iş yöneticisi ve servis
  adaptörü kullanıldı. Arayüz yeniden tasarlanmadı.
- `modules/nesting/dwg_import.py` ve `packaging/build_windows.py`: ODA kullanım
  sınırları incelendi; diğer modüllerin davranışları değiştirilmedi. Paketleyici
  zaten `core.unfolding` alt modüllerini topluyor. Yeni bağımlılık eklenmedi.

Yeni mekanik katman `core/unfolding/forming/` altındadır. Matematik Qt ve
SolidWorks'ten bağımsızdır; uzun işler mevcut iş yöneticisinde çalışır.

## Teknik referansların gerçekten incelenmesi

6 Kasım 2026'da aşağıdaki dört sayfanın içeriği HTTP 200 ile okunmuştur.
URL ve SHA-256 kanıtları `research/forming_references.json` içindedir.

1. [Autodesk — Sheet Metal Unfold Reference](https://help.autodesk.com/cloudhelp/2023/ENU/Inventor-Help/files/GUID-7B2525E4-8191-46F2-8CC3-FF422114EAE5.htm):
   nötr eksen, K, BA ve açı türlerinin ayrı tanımlanması. Autodesk K için
   0–1 giriş aralığı tanımlar; bu genel bir malzeme K tablosu değildir.
2. [Autodesk — Bend Tables](https://help.autodesk.com/cloudhelp/2022/ENU/Inventor-Help/files/GUID-27FD9757-5B40-4528-B361-D9BDFDB2EA4D.htm):
   malzeme/kalınlık/yarıçap/açıya bağlı ölçüm hücreleri ve interpolasyon.
   GOKWORKS varsayılanı tam eşleşmedir; açıkça seçilirse eksiksiz hücreler
   arasında bilineer interpolasyon yapılır. Aralık dışında ekstrapolasyon yoktur;
   Autodesk'in varsayılan toleransları buraya aktarılmamıştır.
3. [ANSYS — Calculating Bend Allowances](https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/discovery/Discovery/user_manual/sheetmetal_bendallowances.html):
   K'nın geometrik tanımı, iç/dış gerinim ayrımı ve gerçek proses için tersine
   numune ölçümü gereği. ANSYS'in varsayılan K eğrisi kopyalanmamıştır. Normal
   hava bükümünden farklı K>0.5 girdileri üretim standardı gibi sunulmaz.
4. [SSAB — 20 questions about bending](https://www.ssab.com/en/support/how-to-process/how-to-bend/bending/20-questions):
   kıvırma/abkant ayrımı, elastik geri dönüş, takım, malzeme ve hadde yönü.
   Minimum yarıçaplar SSAB'nin kaliteye özel deneylerine bağlıdır; bu sayfadan
   genel S235/DC01/paslanmaz katsayısı türetilmemiştir.

Bu sayfalar burada kullanılan sayısal yaylanma tahminlerini deneysel olarak
doğrulamaz. Moment/eğrilik modeli aşağıda açıkça türetilen bağımsız modeldir.

## Desteklenen hesaplar

| İşlev | Gerçek destek ve sınır |
|---|---|
| BA, OSSB, BD | Sabit iç yarıçaplı büküm; işaretli dönüş açısı; iç/dış sanal köşe veya teğet boyları ayrı |
| Çoklu büküm | Bağımsız API'de 1–64 büküm; GUI'de tek ve iki bükümlü profil |
| Açınım yöntemi | Açık K, kaynaklı malzeme K, BA tablosu, BD tablosu, ölçülmüş kupondan K |
| Tablo bağlamı | Kalite, kalınlık, yarıçap, açı, proses, takım kimliği, hadde yönü, kaynak |
| Tablo açı türü | `turn` veya `included`; açık açı bir kez dönüş açısına çevrilir |
| Yaylanma | Önce eşleşen üretim ölçümleriyle interpolasyon; ayrıca açık E/akma/pekleşme girdisiyle analitik tahmin |
| Dairesel ve oval borular | Gerçek eğri parçaların nötr eksen uzunluğu değiştirilir; oval düz kenarlar korunur |
| Sabit kesitli segmentli dirsek | Yuvarlak, oval ve yatık oval; gerçek parça adedi ve 3D hedef korunur |
| Koni/redüksiyonlu dirsek/genel loft | Genel K dönüşümü doğrulanmadı: nominal açınım korunur, mekanik telafi `NOT_EVALUATED` |
| Mesh gerinimi | Bire bir 3D/2D eşleme varsa kenar ve alan farkları; plastik gerinim veya incelme değildir |
| Sayısal açınım | Deliksiz, tek sınırlı ve bire bir eşlenmiş yamada kenar enerjisi minimizasyonu; ters üçgen/çakışma reddi |
| Katalog karşılaştırması | Kullanıcının sağladığı kaynaklı ölçüler ve aynı kimlikli noktalar; yazılım/üretim eşdeğerliği iddiası yok |
| DXF | 1:1 mm; nominal, telafili veya karşılaştırma; büküm çizgileri ve tekrar okuma |
| PDF | Türkçe vektör rapor, nominal/telafili boylar, BA/BD, yaylanma, kaynaklar ve sınırlar; çok sayfalı ek |
| DWG | Yalnız kurulu ODA; DXF→DWG→DXF dönüşümünde kontur/alan/boyut/büküm/katman kontrolü |
| STEP | Mevcut gerçek nominal hedef orta yüzey B-Rep; telafili 2D açınım STEP diye sunulmaz |
| SolidWorks | Bu görev SW belgesini değiştirmez; canlı SW testi yapılmadı |

Her prosese aynı model uygulanmaz. Hava bükümü ve kıvırma için saf eğilme
tahmini isteğe bağlıdır. Bottoming/coining/segment birleştirmede analitik
yaylanma uygulanmaz; bağlamı eşleşen üretim ölçümleri gerekir. Tablodaki açık
BA/BD, ait olduğu proseste kullanılabilir; genel proses kapasitesi onayı değildir.

## Formüller ve fiziksel model

`theta` düz sacdan dönüş açısıdır; açık açı `180° - abs(theta)` olarak ayrılır.

```
BA   = abs(theta_rad) * (Ri + K*t)
OSSB = (Ri + t) * tan(abs(theta_rad)/2)
BD   = 2*OSSB - BA
```

Dış sanal köşe boylarından iki dış setback, iç sanal köşe boylarından iki
`Ri*tan(theta/2)` düşülür. Teğet boylarından setback düşülmez. Her bükümün
BA'sı bir kez eklenir; büküm çizgisi kendi nötr eksen yayı ortasındadır.
Komşu setback'leri karşılamayan flanşlar reddedilir.

Geometrik nötr eksen içten `K*t` uzaktadır. Mühendislik gerinimi
`(y-K*t)/(Ri+K*t)` olarak raporlanır. Bu, plastik gerinim, malzeme kopma
sınırı veya hacim korunumuyla çözülen kalınlık değişimi değildir.

Analitik yaylanma için genişliği birim olan dikdörtgen kesitte, izotropik
düzlem gerilme ve sabit kalınlık varsayılır. Kesit ortasına göre simetrik
elastik-plastik/bilineer malzeme kullanılır:

```
c = t/2
ye = min(c, sigma_y/(E*kappa))
M = 2*E*kappa*ye^3/3
    + sigma_y*(1-H/E)*(c^2-ye^2)
    + 2*H*kappa*(c^3-ye^3)/3
I = t^3/12
kappa_final = kappa_loaded - M/(E*I)
```

H, plastik modül değil, gerilme–toplam mühendislik gerinimi eğrisinin teğet
pekleşme modülüdür. İdeal plastik varsayımı için kullanıcı açıkça `H=0` girer.
Hedef nihai eğrilik için yük altı eğrilik bisection ile bulunur. Yay uzunluğu
korunumu ile yük altı dönüş açısı elde edilir. Kapalı kıvrılmış kesitte
uydurma bir 90° makine komutu verilmez; yalnız yerel yük altı yarıçapı tahmini
raporlanır. Açısal kupon verisi silindir kıvırma yarıçapı kalibrasyonu sayılmaz.

K ile hesaplanan ampirik nötr eksen, bu simetrik saf moment modelinin
elastik-plastik kesit çözümüne taşınmış gibi gösterilmez. Bu iki model farklı
yaklaşımlardır; kesim uzunluğu ve açısal geri dönüş ayrı sonuçlardır.

Takım teması, 3D anizotropi, Bauschinger, artık gerilme geçmişi, uzama sınırı,
incelme ve hasar çözülmez. Poisson oranı saklanabilir; düzlem gerilme modelinde
E yerine gizlice `E/(1-nu²)` kullanılmaz. E, akma, H veya kaynak eksikse
sayısal yaylanma sonucu üretilmez. Çekme dayanımı kontrol edilir ve saklanır;
tek başına kopma kriterine dönüştürülmez.

Mesh minimizasyonu `sum((L2D/L3D - 1)^2)` enerjisini iki ankrajla azaltır.
Azalan adım ve üçgen yön kontrolü uygulanır. Sınır geçersizleşirse sonuç
reddedilir. Plastik şekillendirme veya düzgün çift eğrilikli yüzeyin tam
izometrik açınımı değildir. Maksimum 5000 düğüm / 500 adım; servis ayrıntılı
metrik analizi 10000 düğüm / 20000 üçgenle sınırlıdır. İptal denetlenir.

## Veri ve kullanım

Eski v1 proje dosyaları açılmaya devam eder. `UnfoldRequest.forming_options`
opsiyoneldir; boşsa önceki nominal geometri davranışı korunur. Ek alan tüm
giriş imzası/cache/proje/batch akışına dahildir. Bütün `*_mm` alanları her
zaman mm, mekanik değerler MPa, açılar derece; inch yalnız şekil boyları ve
kalınlık için merkezi normalizasyonda çevrilir.

```python
from core.unfolding import UnfoldService, UnfoldRequest, ExportOptions

request = UnfoldRequest(
    shape_id='bent_profile', variant_id='double', thickness=2.,
    parameters=dict(width=100., flange_1=20., flange_2=50., flange_3=20.,
                    bend_1_deg=90., bend_2_deg=-90., radius_1=2., radius_2=2.,
                    length_reference=1),  # 1: dış; 2: iç; 3: teğet
    forming_options=dict(method='k_factor', k_factor=.4))  # açık örnek kullanıcı girdisi
service = UnfoldService()
result = service.calculate(request)
service.export(result, ExportOptions('profil.dxf', 'dxf', development='compensated'))
```

Bu geometrik örnek için nominal açınım 83.42477796076938 mm, telafili
82.79645943005141 mm; büküm çizgileri 18.199114857512853 ve
64.59734457253856 mm'dir. K=0.4 hiçbir kalite için fabrika varsayılanı değildir.

`forming.storage` sürümlü `gokworks.unfolding.forming` JSON profillerini yükler
ve atomik kaydeder. Kaynak, standart, mekanik değerler, takım, BA/BD/kupon
satırları, hadde yönü ve toleranslar düzenlenebilir. Genel kalite isimleri
seçim listesidir; doğrulanmış malzeme özellikleri veritabanı değildir.

GUI'de **Açınım ve üretim telafisi** bölümünü açın. Yöntemi seçin, açık girdileri
girin veya üretim profilini yükleyin. Tablo/kalibrasyon/tolerans bölümü sürümlü
profilin ilgili JSON verilerini düzenler. **Telafi / yaylanma** sekmesi hesap
yöntemini ve hesaplanamayan kontrolleri gösterir. Nominal karşılaştırma
katmanı kapatılabilir. Çıktı seçimi nominal ve telafili konturu ayrı üretir;
karşılaştırma çıktısı CAM kesim programı olarak kullanılmamalıdır.

DXF karşılaştırmada `NOMINAL_OUTER/INNER`, `COMPENSATED_OUTER/INNER` ve
`NOMINAL_BEND`; normal çıktı `CUT_OUTER/INNER`; işaretli profil bükümleri
`BEND_UP/DOWN` katmanındadır. Örnekleme G çizgileri gerçek büküme çevrilmez.
Genel dirseğin her segmenti bir abkant vuruşu sayılmaz.

## Test ve üretim sınırları

Testler bağımsız BA/BD referansları, Simpson yerine bağımsız ince dilimli
gerilme integrasyonu, farklı R/t ve K, üç malzeme senaryosu, üretim bağlamı,
interpolasyon sınırları, geometri/alan, projeler, GUI, DXF ve PDF geri okuma
içerir. DC01/S235/AISI304 testlerinin mekanik sayıları **sentetik test
girdileridir; malzeme sertifikası veya deneysel doğrulama değildir**.

Bu depoda doğrulanmış fiziksel yaylanma ölçüm seti bulunmadığı için yalnız
analitik/sayısal tutarlılık doğrulanmıştır. Gerçek ölçümler profil sözleşmesiyle
eklenebilir. Linux/offscreen sonuçları canlı SolidWorks, ODA veya Windows EXE
kabul testi değildir. Test sayıları ve atlanan kontroller `FORMING_VALIDATION.md`
içinde kayıtlıdır.

Sonraki teknik işler: doğrulanmış atölye ölçümleriyle ayrı doğrulama seti,
konik yüzeylerde yerel proses eşlemesi, delikli mesh optimizasyonu,
çok geçişli kıvırma/sonlu şekil değiştirme, 3D takım çarpışması/büküm sırası ve
makineye özel kapasite adaptörleri. Bu sınırlar başarılmış özellik gibi sunulmaz.
