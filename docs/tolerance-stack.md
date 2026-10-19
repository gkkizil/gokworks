# Tolerans yığılması · 1D analiz

GOKWORKS → **Mühendislik Hesapları → Tolerans yığılması**.
Mevcut PySide6/Qt Widgets arayüzüne gömülüdür. Ayrı uygulama, ticari eklenti,
bulut API’si, NumPy, OCC veya yeni GUI bağımlılığı gerektirmez.

## Kullanım

1. SolidWorks’te bir `.SLDDRW` açıp **Aktif teknik resmi oku** düğmesini kullanın.
   Alternatif olarak **Dosya seç** ile birden fazla çizim seçip **Ölçüleri tara**
   düğmesine basın. Çizimin önce kaydedilmiş olması gerekir; araç ilk kaydı yapmaz.
2. Soldaki tabloyu arayın/filtreleyin. **Ölçü tablosunu genişlet** bütün sütunlara
   yer açar. Çift tıklama yalnız analiz verisini düzenler. Kaynak çizime değer yazmaz.
3. İlgili ölçüleri `+` veya `−` yönüyle zincire ekleyin. **İlişkiyi düzenle** ile
   başlangıç/bitiş noktalarını, ortak datum/eksen eşlemesini ve gerekli katsayıyı
   açıklayın. Çizim görünümündeki yatay/düşey konum montaj ekseni sayılmaz.
   CAD ölçülerinin ortak fonksiyonel çerçeveye eşlemesi açıkça belirtilmelidir.
4. `Çap` ve `radyüs` kendiliğinden doğrusal terim olmaz. Örneğin çapsal boşluk
   `D−d` için katsayılar `+1/−1`, radyal boşluk `(D−d)/2` için `+0,5/−0,5` olur.
   Açısal ölçüler, referans/BASIC ölçüler, yay/pah ve GD&T bu yolla dönüştürülmez.
5. Analiz ayarlarında kritik boşluğu, zincir uçlarını, kabul sınırlarını,
   yöntemi ve dağılım varsayımlarını belirtin. Boş kabul sınırı sınırsızdır;
   iki sınır da boşsa uygun/uygun değil sonucu üretilmez.
6. Zincirin fonksiyonel ilişkisini doğrulayan kutuyu işaretleyip hesaplayın.
   Her veri değişikliği onayı ve görünür eski sonucu kaldırır. Sıralama/çıkarma
   sonrasında gerçek noktaları düzeltin veya **Noktaları sıraya bağla** ile
   şematik bağlantıyı yeniden kurup ayrıca doğrulayın.
7. Sonuçlar, varsayımlar, kritik ölçüler ve katkı/histogram grafikleri sonuç
   sekmesindedir. PDF/Excel ve panoya aktarım bulunur.
8. **Proje kaydet** sürümlü `.gokstack.json` oluşturur. Açılan projedeki eski
   sonuç yalnız arşivdir; kaynak kontrolü ve yeniden hesaplama gerekir.
   Analiz projeleri kendiliğinden kaydedilmez; uygulamadan çıkmadan kaydedin.

SolidWorks olmadan **Manuel ölçü**, **ISO geçme** ve **Örneği yükle** çalışır.
Manuel giriş, sapma, simetrik ± veya gerçek alt/üst ölçü limiti kabul eder.
Giriş birimleri mm/cm/m/in/µm olabilir; bütün uzunluklar içeride Decimal mm’dir.

## Matematik ve sınırlar

Her girdinin nominali `N`, alt/üst sapmaları `l/u` ve işaretli katsayısı `a`
olsun. Fiziksel limitler `N+l` ve `N+u`’dur. Worst-Case, her terimin iki
uç etkisinin küçüğünü/büyüğünü toplar. Negatif işarette uçlar yer değiştirir.
Asimetrik tolerans nominal çevresinde simetrikleştirilmez.

İstenen örnek otomatik testtedir:

```text
A = 50 ±0,10 mm
B = 20 ±0,05 mm
C = 29,80 ±0,03 mm
K = A − B − C
Nominal 0,20 mm · Worst-Case 0,02 … 0,38 mm
```

RSS, bağımsız girdilerin ortalama ve varyanslarını kullanır:
`μ = Σ(aᵢ μᵢ)`, `σ² = Σ(aᵢ² σᵢ²)`, sonuç bandı `μ ± nσ`.
Varsayılan normal merkez tolerans bandının ortası, giriş σ’sı yarı genişlik/3’tür.
Nominal sonuç ile kaymış dağılım merkezi ayrı gösterilir. Terim bazında normal
merkez/σ ve üçgensel tepe tanımlanabilir. Uniform için `σ = bant/√12`;
üçgensel dağılım kendi gerçek varyansını kullanır. Normal dağılım kesildiğinde
RSS koşullu dağılımın gerçek ortalama/varyansını kullanır.

Monte Carlo 1.000–1.000.000 örnek, seed ve normal/uniform/üçgensel dağılım
destekler. Toplam işlem sınırı örnek sayısı × terim sayısı ≤20.000.000’dur.
Kesilmiş normal dağılım ters CDF ile örneklenir; uçlara kırpılmaz. Kesilmemiş
normal dağılım tolerans dışı örnekler üretebilir. Aynı Python sürümü/girdi/seed
ile sonuçlar tekrarlanır. Örnek minimum/maksimumu tasarımın Worst-Case sınırı
olarak sunulmaz.

Ortalama, örnek standart sapması, yüzdelikler, histogram, uygunluk oranı ve
tahmini PPM hesaplanır. PPM için %95 Wilson aralığı da raporlanır; sıfır gözlenen
hata sıfır gerçek PPM garantisi değildir. Cp/Cpk standart `6σ/3σ` tanımlarıyla
**varsayımsal/simülasyon temelli** olarak gösterilir. Ölçülmüş proses kabiliyeti
iddiası yoktur; sıfır varyansta sonsuz kabiliyet üretilmez.

Worst-Case bant katkısı ve RSS varyans katkısı farklı yüzdelerdir. Aynı fiziksel
ölçünün farklı görünümlerde tekrarı bağımsız terim sayılmaz; çift kullanım hesabı
engeller. Tekrar kullanılan farklı üretim parçaları gerekiyorsa bağımsız fiziksel
ölçüler olarak ayrıca tanımlanmalı, model parametresi tekrarına güvenilmemelidir.
Korelasyon varsa bu sürümde yalnız Worst-Case kullanılabilir.

ISO 286 aktarımı mevcut `iso_fits.rules.limits` ve doğrulanmış tabloları kullanır.
50 H7/h6, 38 H7/k6 ve 25 H7/p6 test edilir. Yeni/rastgele ISO tablosu eklenmedi.
3D STEP/GD&T hesaplanmaz. `tolerance_stack/extensions.py` gelecekte doğrulanmış
yüzey/projeksiyon adaptörleri için ayrı protokol tanımlar; doğrulanmamış
konum, profil, diklik, paralellik, MMR/MMC/LMC formülleri kullanılmaz.

## SolidWorks okuyucusu

`DrawingDoc.GetViews` → tüm sayfalar/görünümler → `GetFirstDisplayDimension5`
→ `GetNext5` ile dolaşılır. `GetDimension2(0)`, `GetSystemValue3`,
`DimensionTolerance.GetMinValue2/GetMaxValue2` ve `Annotation.GetPosition`
kullanılır. Konfigürasyon açıkça belirtilir; API metre/radyanları görüntüdeki
yuvarlanmış metinden bağımsız ele alınır. Çizimdeki görüntü birimi ayrıca kaydedilir.

Kaynak dosya/sayfa/görünüm/model/konfigürasyon, ölçü tam adı, kalıcı anotasyon
referansı, konum ve özgün API veri imzası her kayıtta bulunur. Uygunsa kaynak
anotasyonu SolidWorks’te seçerek vurgulamak mümkündür.

`GetMinValue2/GetMaxValue2` dönüşü tolerans değildir: Int32 durum kodu ve
`VT_BYREF | VT_R8` çıktı ayrı işlenir. Başarısız API kodu hiçbir zaman sıfır
tolerans veya nominal ölçüye çevrilmez. ModelDoc2/DrawingDoc dual arayüzleri
yayımlanmış IID’lerle ayrılır; MakePy/type-info üretimi kullanılmaz.
Çağrılar worker’ın COM apartment’ında yapılır; GUI’ye COM nesnesi taşınmaz.

Simetrik, bilateral, limit, ISO geçme ve API’den gerçekten okunabilen genel
toleranslar desteklenir. `NONE`, BASIC, tek sınırla sonsuz aralık tanımlayan
MIN/MAX, desteklenmeyen/okunamayan toleranslar bilinmiyor kalır. Sonlu tek
taraflı sapma (`+0,05/0` gibi) manuel veya bilateral API verisiyle desteklenir.
Genel/blok tolerans için çizimde gerçek genel tolerans notu ve başarılı sayısal
API değeri gerekir; **ISO 2768 sınıfı tahmin edilmez**. Yalnız nottan tablo
çıkarma yapılmaz. Delik/mil çift gösterimi tek bir ölçüye zorla indirgenmez.
Görünen değer override içeriyorsa otomatik kullanılmaz; manuel inceleme gerekir.

## Revizyon ve çıktı güvenliği

- Dosyalar boyut/mtime ve SHA256 ile kaydedilir. Disk değişiklikleri Qt dosya
  izleyicisiyle eski sonucu kaldırır. Hesap, kopyalama ve rapor/CAD aktarımında
  kullanılan CAD ölçüleri yeniden okunarak değişmiş/silinmiş kimlikler bulunur.
- Kaydedilmemiş SolidWorks düzenlemeleri sürekli arka planda izlenmez; son
  doğrulama tarihi gösterilir ve yeniden kontrol/aktarımda tekrar okunur.
- Çevrimdışı anlık görüntü seçimi açıkça işaretlenir. Disk kontrolü sürer;
  açık SolidWorks oturumu doğrulanamadığı raporlanır ve CAD çıktısı engellenir.
- JSON, PDF, Excel ve yeni native çizim dosyası aynı klasörde geçici dosya
  üzerinden atomik yayımlanır. Yeni dosyada var olan hedefin üzerine yazılmaz;
  rapor/proje diyaloglarında açıkça seçilen yeniden kayıt atomik değişim yapar.
  Atomik yeni yayın için aynı diskte hard-link destekleyen dosya sistemi gerekir
  (örneğin Windows NTFS). Destek yoksa yarım dosya yerine açık hata alınır.
- Yeni native çıktı `SaveAs(Silent | Copy)` ile oluşturulur. Yalnız kopyaya
  GOKWORKS notları eklenir; çizim model bağımlılıkları önce/sonra karşılaştırılır.
  Kaynak dosya kimliği, disk içeriği ve açık değişiklik durumu korunur.
- **Anotasyon ekle · kaydetme**, kaynakta yalnız açık oturum anotasyonları
  oluşturur. Kaynak diske yazılmaz. Üretim ölçüsü/toleransı değiştirilmez.
- **Kaynağa kaydet**, uygulamada ayrı açık onay ister. Kayıt dışı kullanıcı
  değişikliği varsa işlem engellenir. Önce `.gokworks-backups` içinde doğrulanmış
  yedek alınır. Kayıt başarısızsa disk dosyası yedekten geri getirilir; gerekirse
  açık çizimin kaydetmeden yeniden açılması istenir. Bu işlem canlı CAD’de ayrıca
  doğrulanmalıdır.
- Analiz notları, ayrı analiz sayfaları ve opsiyonel L1… notları oluşturulur.
  Var olan üretim ölçüsü/etiketi yeniden adlandırılmaz. Notlar geri okunur;
  üretim ölçüleri önce/sonra karşılaştırılır. Seçim listesi ve önceki sayfa/belge
  geri getirilir. İptal/başarısızlıkta yalnız bu işlemin eklediği nesneler kaldırılır.

## Mimari ve paketleme

`tolerance_stack/`: modeller, zincir doğrulaması, hesap/RSS/Monte Carlo,
COM sözleşmeleri, teknik resim okuyucu/yazıcı, atomik kayıt ve PDF/Excel raporu.
`gui_qt/pages/tolerance_stack.py` mevcut Qt model/view, QThread iş yöneticisi,
tema, vektör sahne ve durum altyapılarını kullanır. `stack_dialogs.py` yalnız
analiz verisini düzenler. Navigasyon sayfayı yeniden oluşturmaz veya COM çağırmaz.

Yeni runtime paketi kurulmaz. PDF mevcut Qt Gui ile, Excel mevcut openpyxl ile
oluşur. `packaging/build_windows.py` mevcut PyInstaller onedir mekanizmasını
korur. Paket açılış kontrolü on modülü, örnek limit hesabını ve gerçek PDF/XLSX
çıktısını kapsar. Referans MIT bildirimleri mevcut lisans paketine eklenir.

## İncelenen kaynaklar ve lisanslar

| Kaynak | İncelenen sürüm | Kullanım / lisans |
|---|---|---|
| [CodeStack](https://github.com/xarial/codestack/tree/master/solidworks-api/document/drawing/export-dimensions) | `0cde3849a184cdbbface61238ef431a6ebb9d530` | Sayfa/görünüm/DisplayDimension API dolaşımı uyarlandı. MIT, ©2025 Xarial Pty Limited; bildirim korundu. |
| [EasyStackup](https://github.com/robertdosa/EasyStackup) | `007cef8b02e2a367bb10b5f37d5064d2fde27462` | İşaretli limitler, asimetrik merkez ve dağılım yaklaşımı incelendi/uyarlandı. MIT, ©2026 github.com/robertdosa. |
| [tolerancing](https://github.com/saurabh-krishnan/tolerancing) | `1d5fc4ad196679d09f86495c900666c58cc73bdb` | Bağımsız momentler, birim ve kabiliyet yaklaşımı incelendi/uyarlandı. MIT, ©2026 saurabh-krishnan. |
| [TolStack](https://github.com/jrstauff2/TolStack) | `0af8a6d9c41843c749ccb04416dde9a616c57426` | STEP yüzey kimliği/normal/projeksiyon yaklaşımı incelendi. Standart lisans dosyası yok; README “Free to use. No restrictions.” diyor. Kaynak kodu kopyalanmadı veya paketlenmedi. |

MIT metinleri `packaging/licenses/tolerance-stack/` içindedir. Dış projeler
runtime bağımlılığı yapılmadı. Ek olarak `angelsix/solidworks-api` deposundaki
2023 interop meta verileriyle enum değerleri, IID’ler ve parametre imzaları
kontrol edildi. DLL’ler uygulamaya kopyalanmadı/dağıtılmadı. Resmî çevrimiçi
SolidWorks yardımına bu ortamdan erişim 403 ile engellendi; başarılı web
doğrulaması gibi raporlanmadı. API sözleşme testleri gerçek SolidWorks testi değildir.

## Çalıştırma ve testler

```bash
python -m pip install -r requirements-dev.txt
python main.py
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_tolerance_stack_*.py
```

Windows’ta `QT_QPA_PLATFORM=offscreen` ayarı normal kullanım için gerekmez.
Gerçek SolidWorks kabul testleri açık kullanıcı oturumunda ayrı, kopya bir
teknik resim üzerinde çalıştırılmalıdır:

```powershell
$env:GOKWORKS_TEST_SLDDRW='C:\test\deneme.SLDDRW'
python -m pytest tests/test_tolerance_stack_live.py -v
$env:GOKWORKS_TEST_WRITE_COPY='1'
python -m pytest tests/test_tolerance_stack_live.py -v
```

İkinci seçenek yalnız ayrı analizli kopya üretir; kaynak üzerine kayıt testi
otomatik açılmaz. Üretim dosyalarını test girdisi yapmayın. Linux testleri saf
hesapları, dosyaları, Qt arayüzünü ve COM double sözleşmelerini doğrular; gerçek
Windows/SolidWorks, kullanıcı çizimi, SaveAs, geri alma ve referans kabulü bu
ortamda çalıştırılmadı. Son test ve görsel kanıtlar `docs/tolerance-stack/` altında.

## Uygulama dosyaları

Yeni iş paketi: `tolerance_stack/{models,chain,calculator,monte_carlo,com,
solidworks_reader,drawing_writer,storage,report,diagram,extensions}.py` ve
`__init__.py`. GUI dosyaları `gui_qt/pages/tolerance_stack.py` ve
`gui_qt/pages/stack_dialogs.py` içindedir. Altı `tests/test_tolerance_stack_*.py`
dosyası saf matematik, rapor/kayıt, COM, CAD yazma ve Qt akışlarını kapsar;
`live` dosyası yalnız gerçek SolidWorks ortamında opt-in çalışır.

Mevcut dosya değişiklikleri: `gui_qt/app.py` navigasyonu, `gui_qt/icons.py`
ikonu, `gui_qt/package_check.py` paket açılış kontrolü,
`packaging/build_windows.py` kullanım notu, `solidworks/connection.py`
opsiyonel ham IDispatch bağlantısı, onun mevcut test dosyası, README ve üçüncü
taraf bildirimleri. Diğer mühendislik hesap motorları değiştirilmedi.
Ham bağlantı seçeneği varsayılan kapalıdır; mevcut çağrıların davranışı korunur.

Referans lisansları, örnek JSON/PDF/Excel ve gerçek Qt ekranları da eklenmiştir.
Tam dosya listesi [changes.json](tolerance-stack/changes.json) içindedir.

## Son doğrulama · 19 Ekim 2026

Tam Linux regresyonu: **615 test, 878 alt senaryo geçti; 2 canlı SolidWorks
testi ortam bulunmadığı için atlandı**. Son ham COM bağlantısı ve etkilenen
katmanların hedefli kontrolü ayrıca **69 test + 5 alt senaryo** geçti.
Bu sayılar birbirine eklenmez; hedefli koşu önceki testlerle örtüşür.
Son kompakt yerleşim düzenlemesi ayrıca 6 tema/çözünürlük senaryosunda geçti;
ölçü ve zincir tabloları okunabilir satır yüksekliğiyle ayrı kaydırılabilir.
131 tam-koşu uyarısı mevcut ezdxf/pyparsing kullanımındandır.

Gerçek Qt açılışı, iki tema ve dört çözünürlük, manuel A−B−C örneği, PDF/XLSX
dosyaları doğrulandı. [Sonuç özeti](tolerance-stack/validation.json) ve
[manuel örnek kanıtı](tolerance-stack/example-validation.json).
Bu adımda yeni Windows EXE üretilmedi; önceki EXE yeni modülü içermez.

### SolidWorks bağlantı düzeltmesi · 19 Ekim 2026

İlk Windows paketinde `pythoncom.CLSIDFromProgID` bulunamadığı için ham
COM bağlantısı başlamıyordu. Bu, SolidWorks'ün kapalı olduğu anlamına gelmez.
pywin32 312'nin `GetActiveObject` uygulaması ProgID metnini doğrudan kabul eder;
bağlantı artık `pythoncom.GetActiveObject("SldWorks.Application")` ve ardından
`QueryInterface(IID_IDispatch)` kullanır. MakePy veya yeni bir SolidWorks
oturumu oluşturulmaz. Sözleşme pywin32'nin
[GetActiveObject / PyWinObject_AsIID](https://github.com/mhammond/pywin32/blob/b312/com/win32com/src/PythonCOM.cpp)
ve [ProgID çözümlemesi](https://github.com/mhammond/pywin32/blob/b312/win32/src/PyIID.cpp)
üzerinden kontrol edildi.

Eski testteki gerçekte bulunmayan sahte fonksiyon kaldırıldı. Tolerans oturumu
artık bağlantı yardımcısını değiştirmeden test edilir; bağlantı hatasında COM
apartment'ının serbest bırakılması da doğrulanır. Gerçek pywin32 modülünü koruyup
yalnız çalışan CAD sunucusunu taklit eden ek test Windows'ta çalışır.
Hedefli Linux kontrolü: **35 test ve 5 alt senaryo geçti; Windows pywin32 testi
atlandı**. Bu kontrol canlı SolidWorks testi değildir. Düzeltme sonrasında
EXE otomatik üretilmedi; önceden indirilmiş paket bu düzeltmeyi içermez.
Sonraki [Windows API kontrolünde](https://github.com/gkkizil/gokworks/actions/runs/39199385108)
gerçek pywin32 modülüyle bağlantı sözleşmesi de geçti. Bu kontrol çalışan CAD
sunucusunu taklit eder; canlı teknik resim okuma başarısı olarak yorumlanmamalıdır.
