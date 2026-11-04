# DFM Analyzer — Aşama 1 teknik raporu

Kapsam: 2B DXF kesim geometrisi, geometri hijyeni ve lazer kesim kuralları.
Branch `agent/claude`. Commitler:
- `bc77ecc`: motor
- `35f811c`: arayüz ve menü kaydı
- bu rapor

## A. Proje analizi

Mevcut yapı:
- PySide6 tabanlı.
- Sayfalar `BasePage` üzerinden kurulur ve `PAGE_TYPES` ile ihtiyaç anında yüklenir.
- Uzun işler `JobManager` ile ayrı iş parçacığında çalışır; olaylar `(kind, value)` biçimindedir.
- Dosyalar `shared.files` ile atomik olarak yazılır.
- Tema renkleri `gui_qt.theme.COLORS` içindedir.

Nesting modülündeki DXF açma (`open_dxf`) ve eğri düzleştirme (`flatten_entity`)
yeniden kullanıldı. Yeni ortak kod eklenmedi.

Modül yapısı:

```
modules/dfm_analyzer/
  models.py          bulgu / kural sonucu / analiz sonucu, JSON şeması v1
  importers/dxf.py   birim doğrulama, INSERT açma, desteklenmeyen nesne listesi
  geometry/          topoloji: kapalı/açık kontur, dal, kesişim, parça/delik/ada
  rules/             kural motoru, DFM-GEO-001…013, DFM-LAS-001…008
  profiles/          sürümlü JSON profilleri (gokworks.dfm_profile v1)
  controller.py      analyze(), JobManager iş fonksiyonu
  reporting/         JSON ve CSV
  visualization/     2B görüntüleyici (QGraphicsView)
  ui.py              üç bölmeli sayfa
```

Motor Qt'siz çalışır ve tek başına test edilebilir.

## B. Açık kaynak

Kod kopyalanmadı. Projeler yalnız yöntem ve kapsam referansı olarak incelendi:

| Proje | Lisans | Kullanım |
|---|---|---|
| open-mrp/dfm | Apache-2.0 | Kural kimliği, önem ve profil düzeni (yöntem referansı) |
| OpenNest | MIT | Kontur temizleme yaklaşımı |
| FreeCAD_SheetMetal | LGPL-2.1 | Yalnız Aşama 2 kapsamı için okundu, kod alınmadı |
| xcad, codestack | MIT | Aşama 2 SolidWorks API notları |
| cadquery, build123d | Apache-2.0 | İncelendi, kullanılmadı |

Kullanılan kütüphaneler zaten projede vardı: ezdxf (MIT) ve Shapely (BSD-3).
Yeni bağımlılık yok. GPL veya copyleft kod yok.

## C. Uygulanan

- **DXF okuma**
  - `$INSUNITS` okunur. Yoksa analiz durur ve kullanıcı birim seçer (mm, cm, m, inch).
  - Ölçü/yazı nesneleri ve büküm katmanları (BEND, BUKUM, BÜKÜM) yok sayılır ve notlarda listelenir.
  - Desteklenmeyen nesneler "değerlendirilemedi" olarak raporlanır.
  - Kaynak dosya salt okunur. SHA-256 sonuçta saklanır ve okumadan sonra dosyanın değişmediği denetlenir.
- **Topoloji**
  - Uç birleştirme toleransı 1 µm.
  - Mikro boşluklar yalnız karşılıklı en yakın uçlar arasında köprülenir ve bulgu olarak bildirilir.
  - Delik/ada ayrımı iç içelik derinliğine göre yapılır.
- **Kurallar**
  - 13 geometri ve 8 lazer kuralı.
  - Durumlar: PASSED, FAILED, NOT_EVALUATED. Önemler: ERROR, WARNING, INFO.
  - Sınır `max(min_mm, factor_t × t)`; sınıra eşit değer geçer.
- **Profiller**
  - `geometry_basic`: yalnız geometri kuralları.
  - `laser_generic`: doğrulanmamış örnek; arayüzde ve raporda açıkça işaretlenir.
  - Kullanıcı kendi JSON profilini yükleyebilir. Şema, kural kimliği ve pozitif değer denetlenir.
- **Arayüz** (Üretim → DFM · İmalat uygunluğu)
  - Sol: kaynak, birim, eğri doğruluğu, dışlanan katmanlar, profil, malzeme, kalınlık ve kural seçimi.
  - Orta: gerçek koordinatlarda 2B önizleme. Kırmızı hata, turuncu uyarı, gri bilgi. Tekerlekle yakınlaştırma, sürükleme, çift tıkla sığdırma.
  - Sağ: özet, arama ve önem filtresi, sıralanabilir bulgu tablosu, ayrıntı, kural sonuçları, kapsam ve notlar.
  - Tablodan bulgu seçmek geometriyi vurgular ve yakınlaştırır. İşarete tıklamak tablodaki satırı seçer.
- **İş akışı:** Analiz arka planda çalışır; ilerleme gösterilir ve iş durdurulabilir.
- **Rapor:** JSON (sonuç tekrar açılabilir) ve noktalı virgüllü Türkçe CSV.
- **Paketleme:** Profil JSON dosyaları `build_windows.py` veri listesine eklendi.

## D. Mühendislik doğruluğu

- Daire delikleri gerçek yarıçapla ölçülür.
- Diğer genişlikler en büyük iç teğet daire (Shapely `maximum_inscribed_circle`) ile ölçülür. Hata payı eğri düzleştirme doğruluğu kadardır (varsayılan 0,01 mm) ve her kuralda belirtilir.
- İnce dil ve dar çentik morfolojik açma/kapama ile bulunur. Yaklaşık 50°'den geniş köşeler bulgu sayılmaz; bu bir varsayımdır ve kural açıklamasında yazar.
- Tabla kontrolü eksen hizalı sınır kutusu kullanır (90° döndürme dahil); serbest açılı yerleşim dikkate alınmaz.
- Sınır değerleri bir standarttan gelmez. Örnek profil "≥ 1 × t ve ≥ 1 mm" kullanır ve bu yaygın atölye pratiğidir. Gerçek kullanım için makineye özel doğrulanmış profil gerekir.

## E. Test sonuçları

- **DFM:** 28 test geçti.
  - Geometri, 13 test. Değerler elle hesaplandı:
    - açık kontur boşluğu 50 mm;
    - 0,02 mm mikro boşluk köprüsü;
    - kesişim noktaları (150, 10) ve (150, 40);
    - 20 mm çakışan çizgi;
    - ada;
    - 0,01 mm kısa segment;
    - yay köşeli plaka alanı 5000 − (4 − π)·25;
    - 10⁶ mm koordinatta Ø0,2 mm delik;
    - inch × 25,4 ölçekleme;
    - bozuk ve boş dosya;
    - desteklenmeyen nesne;
    - kaynağın değişmemesi;
    - iptal.
  - Lazer, 12 test. Değerler elle hesaplandı:
    - Ø1,5 / 2,0 / 3,0 deliği 2 mm sınırla karşılaştırma;
    - kenar eti 3 − 2 = 1 mm;
    - köprü 5 − 2 − 2 = 1 mm;
    - 1,5 mm oval kanal;
    - 1,5 mm dil ve 1 mm çentik;
    - dikdörtgen köşelerinin yanlış bulgu üretmemesi;
    - kalınlık yokken 7 kuralın değerlendirilemedi olması;
    - 30 mm kalınlık ve 4000 mm parça;
    - kullanıcı profili ve hatalı profilin reddi;
    - JSON gidiş-dönüş ve CSV.
  - Arayüz, 3 test:
    - menüden açılma ve arka planda analiz;
    - seçilen bulgunun vurgulanıp yakınlaştırılması, işarete tıklayınca satır seçimi;
    - filtreler;
    - JSON/CSV kaydı;
    - birim sorma ve inch;
    - kural seçimi;
    - tema değişimi.
- **Performans:** 2000 delikli plaka 3,26 s.
- **Tam test paketi:** 2553 geçti, 70 atlandı, 0 hata. Başka modülde bozulma yok.
- **Test edilemeyen:** Windows EXE içinde profil dosyalarının paketlenmesi. EXE derlenmedi; kullanıcı istemedikçe derlenmeyecek.

Kabul kriterleri:

| # | Kriter | Durum |
|---|---|---|
| 1 | Uygulama açılır | Geçti (başlangıç testi, 17 modül) |
| 2 | Menüden erişilir | Geçti |
| 3 | DXF açılır | Geçti |
| 4 | Birim doğrulanır veya kullanıcı seçer | Geçti |
| 5 | Gerçek koordinatlarda gösterilir | Geçti |
| 6 | Temel geometri sorunları bulunur | Geçti |
| 7 | Kurallar profil parametresini kullanır | Geçti |
| 8 | Bulgular doğru geometriye bağlı | Geçti |
| 9 | Seçilen bulgu vurgulanır | Geçti |
| 10 | Arayüz donmaz | Geçti (JobManager, iptal) |
| 11 | Kaynak dosya değişmez | Geçti |
| 12 | JSON/CSV dışa aktarım | Geçti |
| 13 | Testler geçer | Geçti |
| 14 | Diğer modüllerde regresyon yok | Geçti |

## F. Sonraki geliştirmeler

Aşama 2'ye kullanıcı Aşama 1'i kabul ettikten sonra geçilecek.

1. PDF ve Excel raporu.
2. İç köşe yarıçapı kuralı; kerf ve lead-in/out uyarıları.
3. Makine üreticisi verisiyle doğrulanmış lazer profilleri.
4. DWG (ODA dönüştürücü üzerinden).
5. Aşama 2: SolidWorks sac metal (büküm yarıçapı, flanş boyu, delik-büküm mesafesi).
6. Aşama 3: abkant/büküm sırası.
7. Aşama 4: talaşlı imalat.
