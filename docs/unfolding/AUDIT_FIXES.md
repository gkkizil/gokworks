# Sac Açınımı kod denetimi ve düzeltmeler — motor 1.1.1

6 Kasım 2026. Taban `54bb741` (main, PR #29 birleşimi), düzeltme commit'i
`e637031`, görev dalı `agent/codex-unfolding-expansion`.

Denetim, önceki Codex sac açınımı commit'lerinde eklenen/değişen çekirdek,
geometri, şema/katalog, CAD/çıktı, test, paketleme ve belge dosyalarını;
Claude arayüzüyle ortak servis/proje yollarını kapsar. Git/worktree durumu
yeniden incelendi, çalışma tabanı güncel main'e fast-forward edildi.
Başka ajanların worktree'leri ve kullanıcı değişiklikleri değiştirilmedi.
AGENTS.md veya arayüz yerleşimi değiştirilmedi.

## Yeniden üretilen ve düzeltilen hatalar

| Önem | Hata ve somut etkisi | Düzeltme / kanıt |
|---|---|---|
| P1 | Eşit çaplı `cone-frustum-levels`, 3×100 mm örneğinde STEP katlarını z=0'a üst üste koyup toplam yüksekliği 300 yerine 100 mm veriyordu; exporter complete dönebiliyordu | Silindir patch'inin gerçek origin'i ötelenir; bağımsız STEP alan/yüzey/z sınırı testi |
| P1 | Çok ince/uzun üçgen şeritte kareler farkı üzerinden yükseklik hesabı çökerken geçerli görünen açınım alanı yarıya düşüyordu: 0.001×10⁷ mm dikdörtgen 10000 yerine 5000 mm² | Kahan düzenlemeli Heron yüksekliği, daha kararlı izdüşüm ve gerçek üçgen kenar hatasının geometri toleransıyla denetimi |
| P1 | Koni/silindir sınırında mevcut 10 mm bindirmeye ek 5 mm şerit payı mevcut malzemenin içinde kayboluyordu | Ek şerit mevcut bindirmenin dış kenarından başlar; alan `(π·200+15)·300` bağımsız referansıyla doğrulanır |
| P1 | GUI proje çevriminde özel yoğunluk, fiyat birimi, para birimi ve eğri/mesh hassasiyeti sessizce varsayılanlara dönüyordu | DTO ve form gerçek materyali/DevelopmentOptions'u korur; m²/EUR ve sıfır fiyat hesapları, görünür yoğunluk ve para birimi etiketleri test edilir |
| P1 | Sıfır kalınlıklı/fiyatsız kayıt açıldığında önceki parçanın kalınlık/fiyat/malzeme ve hatalı giriş durumu kalabiliyordu | Boş/0 değerler de yüklenir, eski alan hataları temizlenir; kütle None kalır |
| P1 | Açılıp kaydedilen projenin toplam adedi, kodu ve revizyonu kayboluyordu | Proje üst metadatası korunur; toplam 7 ve öğe 3 değerleri ayrı kalır |
| P1 | Kaynak modelden başka şekle geçip geri dönmek kayıtlı kesim/dikiş/pay seçeneklerini sıfırlayabiliyordu | Her form model seçeneklerini orijinal birimiyle saklar ve geri yükler |
| P2 | mm olarak tanımlı pozitif alan minimumu inch değere dönüşümden önce uygulanıyordu; eşdeğer 0.001 mm girdi inch'te reddediliyordu | Uzunluk sınırları normalize mm üzerinde uygulanır; kenar payı üst sınırı da her birimde 100000 mm'dir |
| P2 | Negatif alt kotlu değişken kanalın kenar payı yanlış düzlem normalinde kurulup geçerli geometriyi reddediyordu | Yeniden türetilen normal yerine parçanın gerçek MappingPoint dönüşümü kullanılır |
| P2 | Kaynak konilerin 12/48 yardımcı bölme seçimi değişmiyor, eski sekiz bölmeli çizgiler kullanılıyordu | Seçilen adede göre nominal 2D/3D G çizgileri kurulur; gerçek katlama/mesh adedi değişmez |
| P2 | Aynı sonucu tekrar projeye eklemek veya çoğaltmak aynı request_id'yi kullanıp JSON kaydını engelliyordu | Her yeni proje öğesine benzersiz kimlik; çoğaltmada bağımsız istek kopyası |
| P2 | `catalog/Silindir` kimliği varsayılan DXF/PDF/STEP adında alt klasör yolu oluşturuyordu | Model/proje isimleri mevcut safe_name ile dosya adına dönüştürülür |
| P2 | Gecikmiş eski doğrulama cevabı yeni alan hata mesajını silebiliyordu | Revizyon kontrolü, alan mesajları değiştirilmeden önce yapılır |
| P2 | Bilinen aileye yeni, hesaplanmamış kaynak kimliği eklemek aile algoritmasını otomatik çalışır kabul ettiriyordu | Uygulanmış 191 kimliğin açık listesi ve dispatcher'ın erken reddi; kayıt eklemek hesap yeteneği kazandırmaz |
| P2 | Sonlu ama aşırı büyük büküm girdileri sonsuz allowance/setback içeren sonuç üretebiliyordu | Türetilen büküm değerleri de sonlu olmak zorundadır; hata açık ValueError olarak döner |
| Düşük | `drawing.py` içindeki kullanılmayan fmt importu Ruff F401 oluşturuyordu | İlgisiz çizim davranışı değiştirilmeden import kaldırıldı |

Önceki testler bu kenar durumlarını kapsamıyordu. Yeni testler düzeltme
öncesinde gerçek hataları yeniden üretti. Yeni çekirdek regresyonları
`tests/unfolding/test_audit_regressions.py`, GUI regresyonları
`modules/sheet_unfolding/tests/test_unfold_gui.py` içindedir.

## Doğrulama

Hatalara özel ilk paket 72 testle geçti. Tam modül/GUI regresyonu **902 test,
0 hata, 0 atlama** ile tamamlandı. 33 ayrı test süreci başarılıdır.
**191 modelde 363 DXF, 191 PDF, 191 JSON proje ve 79 STEP orta yüzeyi**
geri okundu; çıktı taraması sıfır hata ve değişmemiş çekirdek hash'iyle
tamamlandı. 950 sıfır uzunluk sınırı denemesinde yakalanmamış istisna yoktur.
19 modüllük kaynak/offscreen açılış kontrolü ve önceki MIT uyarlamasının
128 upstream sayısal karşılaştırması da geçti. Tüm açınım/GUI/test Python
dosyalarında Ruff E9/F ve Git diff denetimi başarılıdır. Kesin kayıtlar
`source_validation.json` içindeki güncel motor/commit, `final_regression_suite`,
`boundary_probe` ve `application_self_check` alanlarında tutulur.

Tam dosya ve JUnit/log kanıtı:
`/workspace/artifacts/unfolding-audit-1.1.1/`. Koni katları ve
dikdörtgen–yuvarlak PDF ilk sayfaları ayrıca görsel incelendi; 191 PDF'in
bütün sayfalarının elle görsel kabulü yapıldığı iddia edilmez.

STEP taraması artık dosyanın kendisiyle tutarlı olmasına ek olarak,
alanı bağımsız nominal 2D parça alanıyla ve montaj kutusunu 3D model
yerleşimiyle karşılaştırır. Sınır kutusu karşılaştırmasında önizlemenin
tanımlı mesh/kord hata bütçesi kullanılır; bu imalat toleransı değildir.
STEP parça adedi tekrar çarpılmaz: bir bombe dilimi quantity=n olsa bile
STEP tek dilimin geometrisidir.

Yeni tekrar üretim:

```sh
QT_QPA_PLATFORM=offscreen python packaging/run_windows_tests.py \
  tests/unfolding modules/sheet_unfolding/tests
QT_QPA_PLATFORM=offscreen python -m tests.unfolding.verify_source_outputs \
  --output /tmp/unfolding-audit-proof
python -m tests.unfolding.verify_boundaries --output /tmp/unfolding-boundaries.json
```

`tests/unfolding/verify_source_outputs.py` her model için ayrıca gerçek
JSON proje kaydet/aç çevrimi ve çıktı hash'i üretir. Kaynak envanteri,
normal örnek girdiler ve 191 kimlik korunmuştur. Güncel kanıt envanterdeki
durumlarla ve [source_coverage.csv](source_coverage.csv) ile eşleştirilir.
Önceki 1.1.0 dosya hash'leri yeni kodun kanıtı gibi sunulmaz.

Sıfır sınırı taraması çökme/istisna dayanımıdır; açık doğrulama veya geometri
hatası da kabul edilen sonuçtur. 950 deneme, 950 ayrı fiziksel doğruluk
onayı veya pytest sayısına eklenecek 950 test olarak yorumlanmaz. Sınır
tarama sürücüsü ve kullanılan çekirdek hash'i sonuç kaydında korunur.

## Değişen uygulama dosyaları

- `geometry.py`, `bend_profiles.py`, `shapes/development.py`: kararlı
  matematik, sonlu çıktı, üçgen kenar hata sınırı.
- `validation.py`, `source_models.py`, `shapes/source_dispatch.py`: birim
  sınırları ve gerçekten uygulanmış kimliklerin denetimi.
- `shapes/source_lofts.py`, `source_extrusions.py`, `source_ducts.py`:
  kat yerleşimi, yardımcı çizgiler ve gerçek kenar payı geometrisi.
- `models.py`: motor 1.1.1. JSON istek/proje şeması v1 kalır; eski motor
  projeleri açılır ve yeniden hesaplanması gerektiği belirtilir.
- `modules/sheet_unfolding/service.py`, `ui.py`: kayıpsız ayar/proje
  taşıma, benzersiz öğeler ve güvenli çıktı adları. `drawing.py`: tek
  kullanılmayan import. Ortak dosya entegrasyonunda bu yeni durum alanları
  ve material/development_options korunmalıdır.

Katalog geometrilerinin üretim onayı, heel/topuk tanımı, üç torus modelinin
kaynak ölçü yorumuyla eşdeğerliği, eksik STEP kırpmaları ve genişletilmiş
görünür seçenek kontrolleri önceki belgelerdeki açık sınırlardır; bu
denetimle tamamlanmış gibi işaretlenmez. Gerçek Windows EXE, SolidWorks ve
ODA kabulü Linux/offscreen testinin yerine konmaz. Ayrı GitHub Windows
doğrulaması normal ajan PR akışında çalışır; başarısız sonuç atlanmaz.
