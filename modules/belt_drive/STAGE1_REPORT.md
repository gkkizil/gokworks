# Belt Drive Designer — Aşama 1 teknik teslim raporu

İnceleme/geliştirme: **4 Kasım 2026**. Kaynak tabanı:
`origin/main` = `0513196a3b4acdff858396267a447d57125885b3`.
Görev dalı: `agent/codex-belt-drive-stage1`, Codex worktree'si:
`gokworks-codex`. Bu raporun teslim commit'i Git geçmişinden ve son kullanıcı
yanıtından izlenebilir. Ana worktree `main` dalındaki eski, komitlenmemiş
mil teknik resim taslaklarına dokunulmadı. Claude worktree'si değiştirilmedi.

## 1. İncelenen güncel proje

`gui_qt/app.py`, `workers.py`, `pages.py`, `theme.py`, `components.py`;
`gear_calculator` modelleri/hesabı/geometrisi, `cad.py`, `service.py`,
`serialization.py`, `sprockets/`; `shaft_generator` ve `bridge.py`;
`solidworks/`; `dfm_analyzer` modelleri/kontrolü; `shared/`; `packaging/`;
`.github/workflows/`; `requirements.txt`, `pytest.ini`,
`docs/GOKWORKS_ARCHITECTURE.md` ve `AGENTS.md` incelendi.

Güncel kaynak 17 mevcut Qt sayfası içerir; DFM Analyzer uygulanmış ve menüye
bağlanmıştır. Eski mimari belgesindeki 16 modül ve teknik resimle ilgili bazı
ifadeler tarihsel kalmıştır. Kod esas alındı; bu görevde ortak belge veya
talimat dosyası yeniden yazılmadı. Başlangıçta güncel uzak dal/commit geçmişi
kontrol edilerek görev dalı açıldı; eski sohbet varsayımları kullanılmadı.

## 2. Kullanılan ve korunan altyapı

- Python 3.13; donmuş veri modelleri, ayrı doğrulama/hesap/geometri/JSON
  katmanları. Yeni bağımlılık yok; engine standart kütüphane ile çalışır.
- Dişli modülündeki saf motor ve açık kabiliyet ayrımı örnek alındı.
  Dişli/sprocket kodu yeniden yazılmadı veya private API'sine bağlanılmadı.
- Ortak `JobManager` işlev imzasına uygun Qt'siz iş fabrikası eklendi;
  ayrı/sahte GUI iş yöneticisi yaratılmadı. Sayfa bağlantısı Aşama 2'dir.
- Mevcut OCP, ezdxf, PySide6, C# STA, pywin32 ve PyInstaller korunur;
  yeni motor bunları import etmez. Mevcut DFM davranışı değişmez.

## 3. Mühendislik ve açık kaynak araştırması

İstenen dokuz GitHub kaynağının sabit HEAD'leri, README/lisansları ve uygun
olan hesap/geometri kaynak dosyaları incelendi. MIT: belt-calc, xCAD,
CodeStack; Apache-2.0: CadQuery, build123d; GPLv3 ailesi: FCGear.
PartForge, Pulley Profile Generator ve timing_belt_calculator için kökte
lisans tespit edilmedi. Hiçbirinden uygulama kodu veya ürün tablosu taşınmadı.

Belt-calc'ın incelenen uzunluk yöntemi yaklaşık, kavrama dişi aşağı
yuvarlanmıştır; yeni motor tam teğet/yay uzunluğu ve kesirli kavrama
tahmini kullanır. PartForge ve profil üreticilerindeki veri bulunabilirliği
imalat doğrulaması sayılmadı. CadQuery/build123d mevcut OCP'ye ek zorunlu
bağımlılık yapılmadı. Kaynak kapsamı, güncellik ve teknik uygunluk ayrıntısı
[RESEARCH.md](RESEARCH.md), tam SHA/URL/SHA-256 kaydı
[research/sources.json](research/sources.json) içindedir.

Gates Design Flex Pro, Optibelt CAP, MITCalc, SOLIDWORKS Belt/Chain,
Inventor V-Belt/Synchronous Belt Generator ve SKF araçlarının resmî alanları
bu ortamın ağ politikası nedeniyle erişilemedi. Güncel arayüz ve üretici
yöntemleri için istenen karşılaştırma **tamamlanamadı**; incelenmiş gibi
sunulmaz. Üretici tabloları ve standardın tam metni doğrulanmadığından
kapasite/ömür/imalat profili onayları kapalıdır. Bu, sonraki üretici/CAD
aşamalarının açık teknik gereksinimidir.

## 4. Geliştirilen hesaplar

| İşlev | Uygulama ve doğrulama yaklaşımı |
| --- | --- |
| Oran / çıkış devri | V'de datum çap oranı, triger-senkron kayışta doğrudan tam diş oranı; ideal kaymasız sonuç |
| Adım / bölüm çapı | `Dₚ=z·p/π`; profil/adım/family eşleşmesi zorunlu |
| Güç / tork | Birincil giriş yalnız biri; matematiksel `60000/(2π)` dönüşümü |
| Verim / servis faktörü | Yalnız açık kullanıcı girdisiyle; ideal, η uygulanmış ve tasarım sonuçları ayrı |
| Kayış hızı | mm/rpm → m/s dönüşümü; üretici hız limiti değerlendirilmedi |
| Tam uzunluk / sarılma | İki ortak teğet ve iki gerçek çember yayı; sürücü büyük/küçük/eşit durumları |
| Yaklaşık uzunluk | Klasik açık kayış yaklaşımı ve tam sonuçtan işaretli fark |
| Uzunluktan C | Fiziksel alt sınır ve monoton bisection; eşit çapta analitik çözüm, kalan ve iptal |
| Triger-senkron uzunluk | `Lₚ=N·p`; kesirli teorik N korunur, seçilen N yalnız tam sayı |
| Kavrama tahmini | `z·β/(2π)`, kesin yük taşıyan diş sayısı olarak yuvarlanmaz |
| Etkin kuvvet | `Ft=1000P/v`, toplam `F₁−F₂` farkı; nominal/tasarım ayrı |
| İsteğe bağlı mil bileşkesi | F₀ verilirse sadeleştirilmiş F₁/F₂, eşit kayış paylaşımı ve gerçek kol vektörleri |
| Boyut adayları | Yalnız açık beyan edilen katalog listesi; her aday için C/fark/sarılma/kavrama ve geometrik statü |

Tam bağıntılar, birimler, referans çizgisi ve sınırlar [README.md](README.md)
içindedir. Bu formüller ideal matematik modelidir; ISO veya üretici ürün
sertifikasyonu değildir. Standardın baskısı/doğru profil verisi doğrulanmadan
uygunluk iddiası yapılmaz.

## 5. Mühendislik güven sınırları

- Matematiksel ortak teğet koşulu `C>|R₂−R₁|`; kullanılabilir iki kasnak
  çözümü ayrıca `C>R₁+R₂` gerektirir. Gerçek dış çap/flanş boşluğu açık iştir.
- Hız/çap/ömür/sarılma/kapasite/germe/servis koşulu limitleri için uydurma
  eşik yok. Eksik bilgiler `NOT_EVALUATED`; yanlış girdiler `ERROR` olur.
- F₀ olmadan mil bileşkesi hesaplanmaz. F₀ modeli kütlesiz kayış, sabit
  ortalama germe ve eşit paylaşım varsayar; üretici germe prosedürü değildir.
- Mil bileşkesi yatak reaksiyonu değildir. Katalog boyutu güç onayı değildir.
- HTD, T ve AT aynı adımda birbirine eşdeğer sayılmaz. GT2/GT3 ve Poly-V
  desteklenmediği için reddedilir. V gerçek çıkış devri kayma bilinmeden verilmez.
- Sonuç bayrakları: `geometry_valid=True`, `power_capacity_verified=False`,
  `production_approved=False`, `cad_available=False`. Boyut listesindeki
  adaylar için de güç/imalat onayı verilemez.

## 6. Eklenen dosyalar

| Konum (`modules/belt_drive/` altında) | Amaç |
| --- | --- |
| `__init__.py`, `__main__.py` | Saf Python API ve çalışır JSON CLI |
| `models.py`, `_numbers.py`, `validation.py` | Değişmez sözleşmeler, birim/sayı/giriş kontrolü |
| `calculation.py`, `geometry.py` | Sonuç birleştirme; gerçek çizgi/yay yolu ve mesafeden konum |
| `controller.py` | Ortak iş yöneticisi için iptal edilebilir tek-rapor fabrikası |
| `engineering/__init__.py`, `kinematics.py`, `belt_length.py`, `forces.py`, `belt_selection.py` | Sayısal hesap ve aday seçimi |
| `catalog/__init__.py`, `profiles.py`, `models.py` | Profil kimliği, destek sınırları ve kaynaklı boyut listesi |
| `serialization.py` | Sıkı proje/katalog/sonuç JSON sözleşmeleri |
| `tests/__init__.py`, `test_calculation.py`, `test_geometry_and_forces.py`, `test_catalog.py`, `test_serialization_and_jobs.py` | Bağımsız sayısal/geometrik/kayıt/iptal/CLI testleri |
| `examples/reference_v.json`, `timing_110.json`, `dimension_list.example.json` | Çalışır girişler; sonuncusu açıkça sentetik, üretici ürünü değildir |
| `README.md`, `ARCHITECTURE.md`, `RESEARCH.md`, `STAGE1_REPORT.md`, `research/sources.json` | Kullanım, aşama sözleşmeleri, araştırma kanıtı ve teslim raporu |

**Değiştirilen ortak dosya yoktur.** `requirements.txt`, menü, DFM, dişli,
mil, SolidWorks köprüleri, paketleme, CI ve AGENTS.md aynen korunmuştur.

## 7. Test kanıtları

Yerel ortam Python **3.13.5**, Linux, Qt **6.10.3/offscreen**.

- Yeni modül: **114 test geçti**, başarısız/atlanmış yok.
- Mevcut dişli/sprocket/DFM/mil hesapları, depo yapısı ve tembel sayfa
  yükleme regresyonu: **275 test geçti**, başarısız/atlanmış yok.
- `main.py --self-check`: **passed**, 17 mevcut sayfa; iki tema ve
  çözünürlük matrisi; mevcut CAD denetimlerinin kaynak ortamı kontrolleri.
- Ruff `E9,F821,F822,F823`: geçti. Yeni bağımlılık kurmadan `python -S`
  alt süreç testi bütün API'nin Qt/OCP/COM olmadan çalıştığını doğrular.

Yeni testler: 60 haneli bağımsız Decimal referansından sabitler; ayrı acos
teğet formülü; eşit/ters çaplar; farklı yön/merkezler; teğetlik ve süreklilik;
bağımsız çizgisel örneklemeyle yay toplamı; moment/aksiyon-reaksiyon dengesi;
fiziksel alt sınır; ters çözüm/iterasyon/iptal; nominal ve η/servis ayrımı;
katalogdan var olan boyutlar; bozuk/eksik/çelişkili/sonlu olmayan girdiler;
JSON roundtrip, bilinmeyen şema, duplicate key, limitler; CLI ve iptalde
kısmi sonuç yayımlamama. Test verileri gerçek ürün kapasitesi olarak kullanılmaz.

Referans: 5 kW, 1450 dev/dak, D₁=100/D₂=200/C=400 mm (aynı datum çizgisi).

| Sonuç | Hesap |
| --- | --- |
| Oran / ideal devir | 2 / 725 dev/dak |
| Giriş / ideal çıkış torku | 32.928608916 / 65.857217831 N·m |
| Kayış hızı | 7.592182246 m/s |
| Etkin kuvvet farkı | 658.572178311 N |
| Küçük sarılma açısı | 165.638488437° |
| Tam / yaklaşık uzunluk | 1277.497074475 / 1277.488898038 mm |

Bu testler nominal motora aittir. **Belt CAD henüz uygulanmadığı için
CAD testi veya canlı Windows/SolidWorks testi yapılmadı.** Windows, ODA,
gerçek COM oturumu ve EXE üretimi bu yerel testlerin kapsamı dışındadır.
Mevcut CI'ın yeni teslimi çalıştırması bu yerel sonuçlardan ayrı izlenmelidir.

## 8. Arayüz, CAD ve sonraki kabul koşulları

Bu teslimde yeni menü, Qt sayfası, 2D çizim/animasyon, 3D önizleme, STEP,
DXF, PDF, Excel, SLDPRT veya SLDASM yoktur; çalışan gibi gösterilen boş
düğme/fonksiyon yoktur. Matematiksel yol çizim ve animasyon için hazırdır;
bu, tamamlanmış kullanıcı arayüzü anlamına gelmez.

Sonraki hedef Aşama 2: mevcut Qt tasarım sisteminde form/sonuç/yol görünümü,
karşılıklı dışlayan girişler, doğru yön/hızda kinematik animasyon, gerçek
boyut listesinden seçim, atomik proje aç/kaydet ve JobManager bağlantısı.
Etkileşim/iptal/eski sonuç temizleme ve mevcut sayfa regresyonları eklenmeli.

Aşama 3 için erişilebilir lisanslı üretici kaynakları ve bağımsız örnekler;
Aşama 4 için doğrulanmış kanal/diş profili, gerçek OCP katı ve STEP yeniden
okuma; Aşama 5 için yeni parça oluşturan güvenli STA protokolü ve canlı
Windows/SolidWorks kabul testi gereklidir. Ayrıntılı veri akışı ve ortak
dosya çakışma sınırları [ARCHITECTURE.md](ARCHITECTURE.md) içindedir.
