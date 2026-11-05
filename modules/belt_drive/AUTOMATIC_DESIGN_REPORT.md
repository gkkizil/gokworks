# Otomatik kayış–kasnak tasarımı — backend teslimi

**5 Kasım 2026.** Güncel taban `origin/main`:
`f69ef60` (Aşama 1, PR #20 ile main'e alınmış). Görev dalı:
`agent/codex-belt-drive-automatic`. Çalışma alanı `gokworks-codex`.
Teslim commit'i son yanıtta/Git geçmişindedir.

Kullanıcının son kapsam düzeltmesi uygulandı: **arayüz geliştirilmedi**.
Menü, ana uygulama, DFM, dişli, mil, SolidWorks, paketleme ve CI kodu
değiştirilmedi. Değişiklikler yalnız `modules/belt_drive/` içindedir.
Türkçe açıklamalarda **triger-senkron kayış** kullanılır; `timing` API/JSON
kimliği korunur. Ana worktree'deki eski kullanıcı değişikliklerine ve
Claude alanına dokunulmadı.

## Gerçekleşen durum

| Alan | Durum |
| --- | --- |
| Otomatik kombinasyon, C/uzunluk/devir filtreleri, sıralama, iptal | Kodlandı ve bağımsız test edildi |
| Ürün/kaynak/rating modelleri, normalize JSON/CSV, v2/v1 projeler | Kodlandı ve test edildi |
| Açık beyan edilen tablo aritmetiği, enterpolasyon, adet/genişlik karşılaştırması | Kodlandı; **gerçek üretici yöntemiyle doğrulanmadı**, PROVISIONAL |
| Tosyalı PDF adaptörü ve 342 sayısal kasnak kaydı | Gerçek kullanıcı PDF'sinden çıkarıldı, matematiksel/veri kontrolleri yapıldı; güncellik/menşe/resmî revizyon bağımsız doğrulanmadı |
| Gates/Optibelt kaynak kimlik adaptörleri | Yerel normalize sözleşme için kodlandı; üretici özel veri biçimi veya kapalı yazılım adaptörü değildir |
| Gerçek Gates kayıtları / güç tabloları | **0 / 0**; resmî alanlara erişim politikası nedeniyle getirilemedi |
| Gerçek Optibelt kayıtları / güç tabloları | **0 / 0**; aynı erişim engeli |
| Doğrulanmış üretici kapasitesi / otomatik servis faktörü | Uygulanmadı; veri ve referans hesap eksik, sonuç NOT_EVALUATED |
| Diğer yerli üreticiler | Veri eklenmedi; üretici/distribütör kimliği ve resmî kaynak doğrulaması gerekir |
| GUI, PDF/Excel sunumu, animasyon, CAD/SolidWorks | Bu teslimin dışında; çalışan gibi gösterilen düğme/özellik yok |

Hiçbir tasarım için tam mühendislik uygunluğu verilmez. `OFFICIAL_VERIFIED`
yazan bir JSON, kaynak veya kapasiteyi resmî doğrulanmış yapamaz. Bu sürümde
bağımsız incelenmiş üretici veri seti/yöntemi olmadığından
`manufacturer_verified=False`, `engineering_approved=False` kalır.

## İncelenen kod ve korunan sözleşmeler

Mevcut `models.py`, `calculation.py`, `validation.py`, `belt_selection.py`,
`belt_length.py`, katalog modelleri/profilleri, `serialization.py`,
`controller.py`, README, mimari ve 114 Aşama 1 testi yeniden okundu.
`AGENTS.md`, Git durumu/geçmişi/worktree'ler ve güncel uzak main incelendi.
Ortak JobManager, mevcut menü/paketleme ve kaynak/atomik dosya davranışları
kontrol edildi; başka modülün özel API'sine yeni bağımlılık eklenmedi.

`calculate`, `nearest_catalog_candidates`, eski `LengthCatalog` ve v1
nominal JSON davranışı aynıdır. Doğrulanmış tam teğet/yay uzunluğu ve
monoton ters çözüm yeniden kullanıldı; ikinci bir matematik motoru yazılmadı.
Eski dosyalardaki Türkçe terimler dışında nominal formüller değiştirilmedi.

## Tasarım algoritması ve matematik

1. `DesignRequest` motor/hedef, aile/profil, mod, sınırlar, koşullar,
   öncelik ve hesap bütçesini sıkı biçimde doğrular.
2. Gerçek kayıtlar üretici, seri, profil ve açık uyumluluk kimliğiyle
   indekslenir. Farklı üretici/seriler aynı adım nedeniyle birleştirilmez.
3. Kayıtlı sürücü/sürülen çiftleri taranır. `i=z₂/z₁` veya `D₂/D₁`,
   `n₂=n₁/i`, `Δn=n₂−n_target`, `%error=100|Δn|/n_target` hesaplanır.
4. Devir/çap/diş filtresi kayış döngüsünden önce uygulanır. C sınırlarının
   karşılığı olan tam geometrik uzunluk aralığı erken eleme sağlar.
5. Yalnız kayıttaki kayış uzunluğu kullanılır: V için **Ld**, triger-senkron
   için **N×p**. Li/La dönüşümü veya yeni stok uzunluğu/diş sayısı üretilmez.
6. Mevcut bisection ile gerçek C çözülür. Referans daireleri ve biliniyorsa
   gerçek dış gövde boşluğu; genişlik, kanal/adet, üretici adına beyan edilen
   minimum/hız ve kurulum koşulları kontrol edilir. Eksik bilgi onay değildir.
7. Beyan edilmiş kapasite aritmetiği varsa uygulanır. Yetersiz bilinen
   kapasite sert rettir; diğer eksik kontroller doğrulanmamış grupta kalır.
8. Sert retlerden sonra deterministik sıralama yapılır. Devir, referans
   alanı, adet, kapasite oranı, C hedefine yakınlık ve açık ağırlıklar
   desteklenir. Eksik ölçütler sıfır maliyet sayılmaz. Fiyat/stok veya gerçek
   mil yükü uydurulmaz. Kimlikler sabit bağlayıcı sıralama anahtarıdır.

Modlar: `auto` (sonlu katalogdaki bütün kayıtlar), `fixed` (C hedefi ve açık
tolerans) ve `range` (C min/max). Varsayılanlar gizli fiziksel tasarım
sınırları değildir. İş bütçesi ve dönen sonuç sayısı ayrı sınırlardır.
Kapsam, ret nedenleri, iptal ve eksik arama açık raporlanır. Bir çiftin
sayısal hatası diğer uygun çiftleri durdurmaz; bozuk katalog sözleşmesi
arama başlamadan reddedilir.

V'de hız/devir idealdir; kayma bilinmez. Triger-senkron model diş atlama,
elastisite veya dinamik çözüm değildir. Genel sarılma, Ft ve ideal tork
sonuçları Aşama 1'deki birim/referans çizgisiyle aynıdır.

## Kapasite katmanının kesin sınırı

`declared_additive_corrected_v1` açık, deneysel bir sözleşmedir. Bir
üreticinin onaylı yöntemi olarak tanıtılmaz. V için `(base+additional)`
üzerine açık wrap/length; triger-senkron için mesh/length/width faktörleri
uygulanır. Küçük kasnağın **kendi devri** kullanılır. Boyut/rpm tablosunda
yalnız açıkça izin verilmiş bilinear, düzeltmede doğrusal enterpolasyon
yapılır; ekstrapolasyon yoktur. Eksik terim/katsayı varsayılmaz.

Servis faktörü açık verilirse `P_design=P×K`; aksi halde tasarım gücü ve
kapasite kıyası değerlendirilmez. Günlük saat ve yük karakteristiği kaydedilir;
doğrulanmış servis tablosu olmadan bu koşullardan katsayı türetilmez.
V'de `ceil(P_design/P_per_belt)` yalnız bu beyan edilen yöntem kapsamında
hesaplanır. Triger-senkron genişlikler yalnız listelenen gerçek SKU'lardır.
Kapasite oranı `P_available/P_design`, bütün tasarımın emniyet katsayısı değildir.

Üreticiye özgü toplamsal/çarpımsal kurallar, oran düzeltmeleri, gerçek
tablo/ömür/genişlik/germe yöntemleri ayrıca doğrulanmalıdır. Deneysel
tablodan PROVISIONAL sayı çıkması Gates/Optibelt kapasite onayı değildir.

## Tosyalı kaynağı ve katalog veri kalitesi

Kullanıcı PDF'si: `a9f64a62-521a-4208-9747-49cd8338d91a.pdf`.
SHA-256: `8399b6b5a123573e99e8a982afd6c7c1504e160edc845d6fc6218812461d689c`.
151 sayfa. Kapakta TOS/Tosyalı ve `www.tosyalimakina.com` bulunur.
Kaynak yayımlayan şirket adı belgeden okunmuştur; üretim menşei veya
“en büyük üretici” iddiası bağımsız doğrulanmış değildir.

Metadata 2013 oluşturma / 2023 değiştirme tarihi taşır; resmî baskı/revizyon
belirlenemedi. Kaynak `USER_SUPPLIED` ve içerik özetiyle tanımlanır;
resmî/güncel kaynakmış gibi yükseltilmez. Her ürün kaynağında PDF sayfası ve
okunan basılı sayfa numarası vardır. 20, 21 ve 30. sayfalar görsel olarak da
karşılaştırıldı. Poppler metin çıkarımı bağımsız matematik ve sütun
kontrolleriyle denetlendi.

| İşlem | Adet |
| --- | ---: |
| Tanınan metrik profil satırı | 522 |
| Kabul edilen pilot kasnak kaydı | 342 |
| Karantinaya alınan kayıt | 146 |
| Kapsam dışı burçlu tablo satırı | 34 |

Kabul edilen dağılım: HTD_3M **60**, HTD_5M **108**, HTD_8M **67**, AT5 **41**,
AT10 **66**. T5/T10'daki çelişkili Dp değerleri aktarılmadı. 144 kayıt
`z×p/π` ile basılı Dp'nin 0.01 mm yuvarlama kontrolünde çelişir; iki kayıtta
hücre sayısı belirsizdir. Örneğin 10 dişli T5 için basılı 16.05 mm,
`10×5/π=15.915494309... mm` ile uyuşmaz. Kayıt kendiliğinden düzeltilmez.
0.006 mm denetim eşiği bir üretim toleransı değildir.

F, nominal kayış genişliği, L, flanş/diş dış çapı ve pilot delik ayrıdır.
Pilot delik bitmiş delik sayılmaz. Basılı Dp, kinematikte tam `z×p/π`
değerinin yerine konulmaz. Kayış SKU/standart uzunluk veya güç tablosu
bu kasnak tablolarından icat edilmedi. Diğer V seçim grafikleri
triger-senkron kapasitesi yerine kullanılmadı.

Sayısal boyutlar ve karantina denetimi repoda bulunur. Tam PDF, çizimler,
logo veya tam metin dağıtılmaz. Tam PDF/katalog yeniden dağıtım lisansı
tespit edilmiş değildir; yalnız talep edilen teknik ürün olguları ve
kaynak/denetim metadatası kullanıldı.

## Referans ve test kanıtları

- **188 modül testi geçti**: eski 114 Aşama 1 testi + yeni 74 test.
- **275 mevcut regresyon geçti**, hata/atlanmış yok: dişli/sprocket,
  DFM, mil modelleri/standartları, depo yapısı ve tembel sayfa yükleme.
- Ana uygulama `--self-check`: **passed**, mevcut **17 sayfa**.
- Ruff `E9,F`: geçti. Python `-S` ile bütün yeni backend Qt/OCP/COM/numpy
  olmadan import edilip çalıştırıldı. Yeni zorunlu bağımlılık yok.

Yerel ortam Python 3.13.5/Linux; uygulama kontrolü Qt 6.10.3/offscreen.
Windows/SolidWorks/ODA/EXE veya canlı üretici yazılımı testi değildir.
Bu görevde yeni CAD veya SolidWorks çağrısı eklenmedi.

Bağımsız referanslar: 1450→700 hedefte sentetik **28/58** çifti nominal
700 rpm verir; katalogda 58 yoksa üretilmez. Gerçek Tosyalı verisinde
%2 toleransla **32 kasnak çifti** bulunur; ilk **12/25** alternatifi
**696 rpm**, **%0.57142857** sapmadır. Bunlar `complete_drive=False`;
kayış/gerçek C/güç onayı yoktur.

188 test; sabit C=400 mm referansı, ters çözüm, eşit/ters çaplar, devir ve
boyut sınırları, eksik koşullar, kaynak/seri/ürün kimliği, CSV/JSON bozukluğu,
enterpolasyon ve tablo sınırları, ekstrapolasyon yasağı, gerekli adet,
genişlik, wrap düzeltmesi, eksik/eski kaynak, iptal, sıralama, kapsam,
eski v1 proje, katalog özeti ve CLI kontrollerini kapsar. Kapasite test
tabloları açıkça sentetiktir; üretici referans sonucu sayılmaz.

Yerel tek ölçümde 6,400 çift + 1,558 kayış boyutu değerlendirildi;
1,512 geometrik/doğrulanmamış aday **0.229 s** civarında bulundu. İlk 25
sonuç döndü; arama tam, çıktı sınırlı olarak raporlandı. Gerçek Tosyalı
6,580 çift taraması **0.006 s** civarındadır. Bunlar bu ortama ait
gözlemlerdir; başka donanım için performans garantisi değildir.

## Dosyalar ve teslim sınırı

Yeni dosyalar: `design_models.py`, `design_search.py`, `design_ranking.py`,
`design_pairs.py`, `design_serialization.py`, `design_cli.py`;
`catalog/products.py`, `rating_models.py`, `importers.py`, `manufacturers.py`,
`tosyali.py`, `data/tosyali-user-pdf.json`, `data/tosyali-import-audit.json`;
`engineering/ratings.py`; iki otomatik tasarım örneği; üç yeni test dosyası
ve sentetik fixture yardımcıları; bu teslim raporu.

Mevcut dosyalar: `controller.py` ortak iş yöneticisi protokolüyle yeni iş
fabrikası için genişletildi. README, ARCHITECTURE, RESEARCH güncellendi.
`validation.py`, `catalog/models.py` ve tarihsel STAGE1_REPORT yalnız
Türkçe terminoloji bakımından güncellendi. Ortak dosya/API değişikliği yoktur.

Sonraki teknik gereksinimler: erişilebilir ve kullanım koşulları incelenmiş
Gates/Optibelt kaynakları; Tosyalı'nın güncel revizyonu ve çelişen Dp
hücrelerinin üretici teyidi; gerçek kayış SKU/uzunlukları; üreticiye özgü
servis/rating/germe yöntemleri ve yayımlanmış bağımsız örnek hesapları.
Üreticiler arası uyumluluk ayrı kanıt olmadan açılmamalıdır. GUI ve
PDF/Excel/CAD entegrasyonu ayrı kullanıcı görevidir.
