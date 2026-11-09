# Akıllı Parça Bölme — teslim ve kabul raporu

9 Kasım 2026. Geliştirme commit'i `27ed739`, dal `agent/codex`.
[PR #48](https://github.com/gkkizil/gokworks/pull/48). Windows doğrulaması teslim
anında sürüyor; main birleşmesi veya yeni EXE yayımlandığı iddia edilmez.

## 1. Oluşturulan dosyalar

`modules/smart_splitting/` altında:

| Dosya | Sorumluluk |
| --- | --- |
| `__init__.py`, `models.py` | Paket, parametreler, segment/aday sonuçları ve bütçeler |
| `analysis.py` | DXF, kaynak/kontur/delik ve merkez analizi |
| `validation.py` | Bağımsız alan, simetrik fark, çakışma, genişlik/et kontrolleri |
| `splitter.py` | Eşit/akıllı radyal bölme ve aday üretimi |
| `optimizer.py` | Gerçek NFP değerlendirmesi ve aday sıralaması |
| `adapter.py` | Part/Sheet/Options adaptörü ve korumalı aktarım |
| `dxf_export.py` | Atomik, yeniden okunarak doğrulanan DXF ve JSON raporu |
| `canvas.py`, `ui.py` | Native önizleme ve çalışma ekranı |
| `tests/__init__.py`, `test_geometry.py`, `test_optimizer.py`, `test_workbench.py` | 33 geometri/optimizasyon/Qt testi |
| `README.md`, `RESEARCH.md`, `DELIVERY.md` | Kullanım, araştırma/lisans ve teslim kaydı |
| `examples/D1800_ORNEK.zip` | Kaynak, segment çıktıları, taşınabilir Nesting planı, ham ölçümler ve ekran görüntüleri |

## 2. Değiştirilen dosyalar

- `gui_qt/app.py`: mevcut PAGE_TYPES/MODULES sayfa kaydı.
- `gui_qt/workspace.py`: mevcut Üretim menüsünde Nesting'in hemen altına ekleme.
- `gui_qt/icons.py`: radyal bölme ikonu.
- `tests/test_lazy_pages_gui.py`: sabit 20 yerine kayıt sayısını kullanma.

Diğer menü sırası, Nesting motoru/veri şeması, DWG okuyucusu ve ODA/LibreDWG
dönüşüm dosyaları bu geliştirmede değiştirilmedi.

## 3. Algoritmalar

Eşit mod `360/n` derecelik sektörlerle gerçek kaynak poligonunu kırpar. Kontur
duyarlı mod her ışının çevresinde ±%33 dilim açısına kadar deterministik yerel
tarama yapar; delik/slot yaklaşması ve yasaklı bölgeler sert kısıttır. Merkezdeki
bore birleştirme sınırıdır; diğer iç konturlar kritiktir. Açılar asimetrik olabilir.
Detaylı profilde otomatik merkezin X yönünde ±%2 kayması da denenir; özel merkez sabittir.

Her nominal segment tek ve geçerli Polygon olmalıdır. Sabit sayı, alan toplamı,
kaynakla birleşimin simetrik farkı ve çiftler arası çakışma bağımsız denetlenir.
Alan eşiği `max(1e-6 mm², kaynak alanı × 1e-9)`; CAD eğri yaklaşım toleransı ayrıdır.
Geçersiz, sığmayan, yinelenen, kısmi veya GEOS/NFP topoloji hatalı aday gerekçesiyle
elenir. Doğrulanmış tam sonuç yoksa çözüm üretilmez.

Sıralama: geçerlilik/imalat ön kontrolü → tam yerleşim → levha sayısı → brüt
alan → en büyük bağlantılı serbest bölge toplamı → fire → birleşim uzunluğu.
Serbest bölge metriği garantili dikdörtgen artık stok değildir. Sonuç **bulunan
en iyi çözüm**dür; global minimum iddiası yoktur.

## 4. Kütüphaneler ve araştırma

Yeni bağımlılık yok. Mevcut Shapely 2.1.2/GEOS, ezdxf 1.4.3 ve PySide6 6.10.3
kullanılır. Saf geometri API'si Qt/SolidWorks istemez.
OpenNest DrawingSplitter/AutoSplitCalculator/SplitByCount/FitToPlate kaynakları,
Shapely/Clipper2 boolean-offset yaklaşımları, ezdxf ve SheetNest NFP+GA incelendi.
Ayrı native/Rust motor bağlanmadı ve kod kopyalanmadı. Lisanslar, sabit araştırma
commitleri ve kararlar [RESEARCH.md](RESEARCH.md) içindedir.

## 5. Mevcut Nesting ile entegrasyon

Segmentler bağımsız Part nesnelerine, levha Sheet'e, ayarlar Options'a çevrilir;
mevcut NFP aynen çağrılır. Adet, kalınlık, malzeme, kimlik, kaynak izi, geometri
ve hata payları korunur. Örneğin 5 orijinal × 6 segment = 30 kesim parçası.
Aktarım kopya projede doğrulanır; başka parçalar, stoklar, dosya geçmişi ve
maliyetler silinmez. Kaynak kimliği notlarıyla tekrar aktarımda yalnız o kaynağın
önceki segmentleri yenilenir; bu koruma `.goknest.json` kaydından sonra da çalışır.
Yeni levha stoğa eklenir; mevcut levhalar da Nesting tarafından kullanılabilir.

## 6. Menü ve GUI

**Üretim → Nesting · Sac maliyeti → Akıllı Parça Bölme**. Ayrı sayfalar mevcut
PageRegistry ile kalıcıdır. Sayfa değiştirmek kaynak/sonucu sıfırlamaz. DXF,
hesap/NFP ve dışa aktarma mevcut JobManager üzerinde çalışır. İlerleme ve Durdur
vardır; iptalde yalnız daha önce doğrulanmış tam yerleşim korunabilir.
Önizlemede konturlar, delikler, renkli segmentler, ID'ler ve birleşim çizgileri
görünür; zoom, pan, Sığdır ve orijinal/bölünmüş geçişi vardır. Kaynak/sonuç,
geçersiz girdi veya parametre değişikliğinde eski çıktı kullanımına izin vermez.

## 7. Test sonuçları

- Geniş regresyon: **429 geçti, 1 atlandı**. Nesting, yeni modül, navigasyon,
  tembel yükleme, kompakt ekranlar, depo yapısı ve tüm sayfalarda hatalı girdi taraması.
- Son ek kontroller dahil yeni modül: **33 geçti**. Bu küme öncekiyle örtüşür;
  sayılar farklı test sayısı gibi toplanmamalıdır.
- Güncel Claude `e4ad137` / main `934fca0` ile geçici birleşik ağaçta:
  **384 geçti, 1 atlandı**. Gerçek LibreDWG entegrasyonu dosyaları bu kopyaya dahildir.
  Canlı worktree veya dallar elle birleştirilmedi; dosya çakışması çıkmadı.
- Uygulama self-check: **21 modül**, açık/koyu tema ve dört çözünürlük geçti.
- 1366×900 koyu, 1024×700 açık gerçek Qt görüntüleri incelendi.
- Sözdizimi ve Git whitespace kontrolleri geçti.

Ø1000/4, Ø1800/6, Ø1200/Ø600 halka/8, delikler, slot, asimetri/5, delikten geçen
kesim, açık/self-intersection, mm/inch, export/reimport, minimum genişlik/et,
imkânsız sayı, yasaklı bölge, adet, kaynak boşluğu/pay, iptal, atomik çıktı ve
GEOS aday reddi test edildi. Windows/SolidWorks/fiziksel üretim bu Linux sonuçlarına dahil değildir.

## 8. Performans ve gerçek karşılaştırma

Örnek: Ø1800, altı delik, altı segment, 1500×3000 levha, bir orijinal,
0,05 mm eğri toleransı ve 5 mm yaklaşma. Bu Linux oturumunda gözlenen:

| Profil | Aday | Toplam süre | Levha | Yerleşen segment |
| --- | ---: | ---: | ---: | ---: |
| Hızlı | 3 | 4,23 s | 1 | 6 |
| Dengeli | 7 | 18,74 s | 1 | 6 |
| Detaylı | 13 | 57,22 s | 1 | 6 |

NFP arama bütçeleri 3×2, 7×3 ve 13×5 saniyedir; toplam duvar saati garantisi
değildir. Geometri/çıktı ve kesilemeyen tek GEOS işlemi ek süre alabilir.
Ölçümler ortam yüküne bağlıdır. Detaylı koşuda bir gerçek topoloji hatası üreten
aday elendi; başka doğrulanmış tam aday seçildi. Ham kayıtlar ZIP'tedir.

Dört segmentli Ø1800 karşılaştırmasında eşit başlangıç **1 levha / 4,5 m² /
%43,455 fire**, denenmiş bir alternatif **2 levha / 9 m² / %71,728** verdi;
başlangıç korundu. Bu örnekte iyileşme oluşmadı. Altı delikli örnekte pozitif
yaklaşma nedeniyle eşit başlangıç uygulanamazken kontur duyarlı adaylar bir levhaya sığdı.

## 9. DXF geometrileri

LINE, ARC, CIRCLE, LWPOLYLINE/bulge, POLYLINE, SPLINE için bölme→export→reimport
testleri geçti. Mevcut okuyucunun ELLIPSE ve blok/birim desteği de kullanılır.
Kaynak dosya değişmez. Tam kalan CIRCLE doğal CIRCLE olarak korunabilir;
kesilmiş yay/spline/elips giriş toleransıyla kapalı LWPOLYLINE çıkarılır.
Genel analitik ARC/bulge yeniden kurma bu sürümde yoktur.

OUTER_CONTOUR/INNER_CONTOUR gerçek kesimdir. Birleşim kenarı dış konturdadır;
SPLIT_EDGE üzerinde yinelenerek çift kesim yapılmaz. REFERENCE kesim dışıdır.
Birleşik DXF segmentleri yan yana koyar; optimize plaka DXF'si Nesting'den çıkarılır.
Her dosya kapalı kontur, alan, konum ve mm birimiyle yeniden okunarak doğrulanır.

## 10. İmalat kapsamı

Minimum genişlik, minimum döndürülmüş dikdörtgenin kısa kenarıdır. Minimum et
ön kontrolü erozyonda bağlantı ve delik mesafeleridir; tüm yerel uç kalınlığını
sertifikalandırmaz. Yasaklı bölgeler GUI'de kutu, Python API'sinde Polygon'dur.
Kaynak boşluğu birleşim kenarlarından malzeme çıkarır; işleme payı komşu nominal
malzemeye genişletir ve dış kaynak sınırını aşmaz. İkisi aynı anda uygulanmaz.
Nominal/imalat alanları ayrıdır. Kerf kontura uygulanmaz; CAM telafisi gerekir.
JSON'daki kerf alan tahmini ortak hattın fiziksel kesimi varsayımı içindir.
Birleştirme yöntemi metadata'dır; kaynak ağzı veya bağlantı elemanı tasarlanmaz.

## 11. Desteklenmeyenler ve sınırlar

Serbest kesim ağı, otomatik segment sayısı, adacıklı MultiPolygon kaynak,
analitik kesilmiş ARC/bulge geri kurma, yerel et sertifikasyonu, kaynak ağzı/
bağlantı otomasyonu ve yapısal/kaynak mukavemeti onayı yoktur. Radyal arama
her kontur için çözüm bulmayabilir; sayı değiştirilmez veya sahte çözüm üretilmez.
Doğrudan dosya seçimi DXF'tir; Nesting'de DWG'den okunmuş parça kopyalanabilir.
Özel malzemeler için bölme ekranında mevcut katalogdan seçim gerekir.
2–64 segment ve 10000 toplam örnek sınırı vardır. İptal tek GEOS işleminde
anlık olmayabilir. Kullanıcının kendi CAD dosyası ve fiziksel üretim test edilmedi.

## 12. Uçtan uca sonuç ve örnek paket

Üretilmiş gerçek altı delikli Ø1800 DXF ile Qt uygulamasında istenen akış geçti:
yükleme → altı segment → 1500×3000 aday karşılaştırması → ayrı/birleşik DXF →
yeniden okuma → Nesting'e aktarım → normal Nesting hesabı. Önceden var olan
bir parça korunarak toplam yedi parçanın yerleşimi de doğrulandı.

[Örnek paket](examples/D1800_ORNEK.zip): orijinal DXF, altı ayrı/birleşik DXF,
JSON raporu, gömülü geometri taşıyan `.goknest.json` planı, ölçüm JSON'ları ve
iki Qt görüntüsü. Ekran görüntüleri 0,2 mm'lik ayrı UI kabul koşusundandır;
paketteki DXF/proje 0,05 mm toleranslı koşudandır. Örnekler fiziksel imalat onayı değildir.
