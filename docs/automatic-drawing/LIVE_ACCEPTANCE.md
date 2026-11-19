# Otomatik Teknik Resim — Gerçek SolidWorks kabul senaryoları

Bu belge, otomatik teknik resim modülünün **gerçek SolidWorks** üzerinde nasıl
kabul edileceğini tanımlar. Kabul betiği:
`modules/automatic_drawing/live_acceptance.py`.

Durum (18 Kasım 2026, **gerçek SolidWorks 2025 SP5, revizyon 33.5.0, Türkçe arayüz**,
Windows 11): 6 senaryo **geçti**, 1 senaryo **kaldı**, 1 senaryo **çalıştırılmadı**.

| # | Senaryo | Sonuç |
|---|---|---|
| 1 | Kademeli mil | geçti |
| 2 | Delikli plaka | geçti (5 delik → 5 merkez işareti, 5 model ölçüsü) |
| 3 | Tek gövdeli sac | geçti (açınım + gövde başlığı) |
| 4 | Çok gövdeli sac | **kaldı**: gövde açınım paftaları bilinçli olarak üretilmez, bkz. `KNOWN_LIMITATIONS.md` |
| 5 | Konfigürasyonlu montaj | geçti (`Konfig-B`, BOM adetleri doğrulandı) |
| 6 | Bastırılmış bileşenli montaj | geçti (bastırılmış bileşen BOM'da sayılmadı) |
| 7 | Eksik referans | geçti (reddedildi, SLDDRW yayımlanmadı) |
| 8 | Firma şablonları | çalıştırılmadı: firma DRWDOT / SLDDRT / BOM şablonu yok |

Aynı senaryolar 19 Kasım 2026'da birleşik kodla (bulut commit'i `ad55ed7` dahil) yeniden
geçti. Antet içeren bir DRWDOT ile mil ve plaka şablonun kendi sayfasında (`template`)
kuruldu ve şablonun anteti korundu.

Arayüzden gerçek SolidWorks'te (19 Kasım 2026, delikli plaka, SolidWorks'te açık belge):

| Yol | Sonuç |
|---|---|
| Masaüstü uygulaması · Üretim → Otomatik Teknik Resim → Aktif dosyayı al → Resimleri oluştur | 18/18 aşama, Uyarılı, SLDDRW + PDF, 5 merkez işareti, 5 ölçü (124,8 sn) |
| SolidWorks eklentisi 2.3.2 (kurulu MSI) · GOKWORKS sekmesi → Otomatik Teknik Resim → Resimleri oluştur | 18/18 aşama, Uyarılı, SLDDRW + PDF, A3 ISO antet, 5 merkez işareti, 5 ölçü (29,6 sn) |

Eklentinin kaynak kopyası, Python'u ve `CommandInProgress` ile kabul senaryoları da masaüstüyle
aynı sonucu verdi. Bir SolidWorks penceresi açıkken ikinci bir SolidWorks örneği başlatılıp
zorla kapatıldığında eklenti işi görünüş oluştururken takıldı; temiz oturumda tekrarlanmadı.

1–7 fixture'ları kullanıcı dosyası değildir; `tools/automatic_drawing/build_live_fixtures.py`
ile API'den sıfırdan üretildi. Varsayılan şablon `Teknik Resim.DRWDOT` (sayfa biçimsiz)
kullanıldı; antet olarak kurulumun `a3 - iso.slddrt` dosyası uygulandı. Modüldeki diğer
testler ham COM taklitleri (fake/mock) kullanır; çağrı sözleşmesini sınar, CAD
doğrulaması değildir. Modülsüz adım adım API denemesi:
`tools/automatic_drawing/sw_drawing_probe.py`.

## Çalıştırma (Windows, lisanslı ve açık SolidWorks)

```bat
set GOKWORKS_DRAWING_LIVE_TEMPLATE=C:\Kabul\sablon\A3.drwdot
set GOKWORKS_LIVE_SHAFT=C:\Kabul\01-mil\kademeli_mil.SLDPRT
rem ... aşağıdaki tablodaki diğer değişkenler
python -m modules.automatic_drawing.live_acceptance --report kabul.json --output C:\Kabul\cikti
```

Ayrıca `pytest modules/automatic_drawing/tests/test_live_solidworks.py -rs`
aynı senaryoları çalıştırır. Eksik senaryo SKIP olur ve nedeni yazılır.

Betik her senaryo için bir rapor satırı yazar:

- **geçti**: Resim üretildi, beklenen kontroller sağlandı ve kaynak klasör değişmedi.
- **kaldı**: Sorunlar `problems` alanında listelenir.
- **çalıştırılmadı**: Fixture, Windows veya SolidWorks oturumu yoktur. Bu durum hiçbir zaman "geçti" sayılmaz.

Betik, raporu yazdıktan sonra üretilen SLDDRW ve PDF dosyalarının bir mühendis
tarafından SolidWorks'te açılıp gözle incelenmesini gerektirir. Otomatik
kontroller resim kalitesini (ölçü yerleşimi, okunabilirlik, standart uygunluğu)
onaylamaz.

## Kaynak dosya güvenliği

- Her fixture **kendi klasöründe** durmalıdır. Montajın bileşenleri de aynı klasörde veya alt klasörlerinde olmalıdır.
- Betik, klasördeki her dosyanın SHA256 değerini çalıştırmadan önce ve sonra karşılaştırır. Bir dosya değişirse, resim sonucu ne olursa olsun senaryo **kaldı** olur.
- Çıktı klasörünü (`--output`) fixture klasörlerinin dışında seçin.
- Kullanıcının gerçek projeleri fixture olarak kullanılmamalıdır. Kopyalarla çalışın; modül kaynak modeli kaydetmez, ama kabul bunu da sınar.

## Fixture listesi

| # | Senaryo | Ortam değişkeni | Hazırlanacak fixture | Otomatik kontrol |
|---|---|---|---|---|
| 1 | Kademeli mil | `GOKWORKS_LIVE_SHAFT` | Tek gövde, en az 3 çap kademesi, 1 pah, 1 kama kanalı; kaydedilmiş ve tam yeniden oluşturulmuş SLDPRT | Sınıf `shaft`; SLDDRW + PDF; pafta kaydı |
| 2 | Delikli plaka | `GOKWORKS_LIVE_HOLED_PLATE` | 100×50×10 plaka, 4 adet Ø8 geçme deliği, 1 adet M6 Hole Wizard dişli delik, 1 havşa | Sınıf `plate`/`block`; merkez işaretleri istenir; SLDDRW + PDF |
| 3 | Tek gövdeli sac | `GOKWORKS_LIVE_SHEET` | 2 mm, 2 büküm, FlatPattern bastırılmamış, açınım konfigürasyonu hazır | 1 sac gövdesi; açınım görünüşü |
| 4 | Çok gövdeli sac | `GOKWORKS_LIVE_MULTIBODY_SHEET` | En az 2 sac gövdesi, farklı kalınlık; her gövde için mevcut açınım konfigürasyonu, güncel Cut List | Her gövde için ayrı açınım paftası |
| 5 | Konfigürasyonlu montaj | `GOKWORKS_LIVE_ASSEMBLY` + `GOKWORKS_LIVE_ASSEMBLY_CONFIGURATION` | En az 2 konfigürasyon; seçilen konfigürasyonda farklı bileşen adedi | Montaj okunur; istenen konfigürasyon kullanılır; BOM tablosu |
| 6 | Bastırılmış bileşenli montaj | `GOKWORKS_LIVE_SUPPRESSED_ASSEMBLY` | Etkin konfigürasyonda en az 1 bastırılmış bileşen | Bastırılmış bileşen ağaçta; BOM tablosu (adet elle kontrol edilir) |
| 7 | Eksik referans | `GOKWORKS_LIVE_MISSING_REFERENCE` | Bir bileşen dosyası silinmiş / yeniden adlandırılmış montaj kopyası | Durum `FAIL`, gerekçe bildirilir, **SLDDRW yayımlanmaz** |
| 8 | Firma şablonları | `GOKWORKS_LIVE_COMPANY_SOURCE`, `GOKWORKS_LIVE_COMPANY_DRWDOT`, `GOKWORKS_LIVE_COMPANY_SLDDRT`, `GOKWORKS_LIVE_COMPANY_BOM` | Firmanın gerçek DRWDOT, SLDDRT ve BOM şablonu + bir montaj | Şablonlarla SLDDRW + PDF; BOM tablosu (antet alanları elle kontrol edilir) |

Ortak şablon: 1–7 numaralı senaryolar `GOKWORKS_DRAWING_LIVE_TEMPLATE` ile verilen DRWDOT'u kullanır.

## Elle incelenecekler (rapora eklenmeli)

- Ölçülerin okunabilirliği, çakışma, eksik imalat ölçüsü.
- Delik / diş / havşa açıklamaları. Bunlar model ölçüsü olarak gelir; otomatik tanıma kapsamı sınırlıdır, bkz. `KNOWN_LIMITATIONS.md`.
- Büküm çizgileri ve büküm notları.
- BOM adetleri: Bastırılmış bileşen sayılmamalıdır.
- Firma antetindeki özellik bağlantıları.
