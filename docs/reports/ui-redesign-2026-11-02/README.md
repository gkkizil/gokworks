# Arayüz yenileme raporu — 2 Kasım 2026

Kapsam: PySide6 6.10 / Qt Widgets arayüzünün merkezi bir tasarım sistemiyle
yeniden düzenlenmesi. Hesap motorları, CAD/COM kodu ve iş mantığı
değiştirilmedi. Tasarım dili: [UI_DESIGN_SYSTEM.md](../../UI_DESIGN_SYSTEM.md).

## 1. Keşif bulguları (önce)

- Tema tek QSS dosyasındaydı, ancak modüller kendi renklerini de kodluyordu:
  DXF önizlemesi `#ffffff`/`#f8f8f8`, tolerans/ISO/cıvata diyagramları kendi
  paletleri, Nesting'in ayrı stil sayfası.
- Koyu temada beyaz önizleme alanları; ondalık ayırıcı tutarsız (dişli
  `2.0000`, diğerleri `1,5`); bozuk görünen spinbox okları.
- Tablo başlıkları kimi yerde ortalı, kimi yerde sola dayalıydı. DXF tablosunda
  başlıklar kesiliyordu. Hata satırlarının tamamı kırmızıya boyanıyordu.
- Sol menünün altında dört ayrı kontrol vardı. Tolerans yığılmasında tam
  genişlik buton sıraları; Nesting menülerinde ok işareti metnin üstüne
  biniyordu.
- Durum çubuğunda CAD bağlantısı görsel olarak ayırt edilmiyordu.
- 1366×768 @%150'de en küçük pencere (820×560) ekrandan büyüktü.

## 2. Tasarım sistemi

`gui_qt/theme.py`: koyu (varsayılan) ve açık token setleri. Mevcut anahtarlar
korundu; `border_strong`, `hover`, `on_accent`, `focus`, `success` ve `grid`
eklendi. Tipografi ve boşluk ölçeği, 26 px satır yüksekliği; birincil,
ikincil, yıkıcı ve düz butonlar; giriş, spinbox, tablo, sekme, durum çubuğu
ve dock stilleri tanımlandı. Fusion üzerine sadeleştirilmiş temizle simgesi
eklendi.

`gui_qt/components.py`: `button(primary/destructive/flat)`, `separator()`,
`section_header()`, `StableScrollArea`; tablolar sola hizalı başlık ve
ızgarasız. Sayısal alanlar sağa hizalı ve temizle simgesiz.

## 3. Ekranlar

| Alan | Değişiklik |
| --- | --- |
| Kabuk | Kompakt logo satırı, düz alt bağlantılar, sayfa başlığı ayırıcısı, durum çubuğunda SolidWorks bağlantı noktası (gri/yeşil/kırmızı), ekrana uyan en küçük pencere |
| Nesting | Düz menü çubuğu (Dosya, Düzenle, Yerleşim, Görünüm, Rapor); token'lı tuval (sac sınırı, kullanılabilir alan, delikler, seçim yalnız vurgu renginde); kompakt parça/sac listeleri; çizim altında sonuç şeridi (plaka, kullanım %, fire m²/kg, maliyet); tek satırlık sonuç tablosu başlıkları |
| PDF / DXF / 3D / BOM / İsimlendirme | Kaynak, Çıktı ve Seçenekler sırası; yan yana kompakt komutlar; renkli durum hücresi ve başarı/hata sayacı; DXF tablosunda başlığa göre ölçülen sütunlar; DXF 3D/açınım önizlemesi tema zemininde ve tema değişince yeniden boyanır |
| Ortak hesap ekranı | Başlık sonucu (20 px), özet, ayırıcı, diyagram hiyerarşisi; kart yerine düz paneller; diyagramların boş bant bırakmaması |
| Dişli | Türkçe yerel ayarlı sayı alanları (`2`, `1,5`), sade tablolar, nötr ikinci dişli rengi |
| Tolerans yığılması | Kompakt zincir araç çubuğu (ipuçlu), tek birincil komut, düz paneller |
| Parametrik mil | Mantıksal gruplar (Parça, kademe/kanal/kenar/diş/delik seçimi, Eklenen işlemler, Üretim kontrolü); virgüllü sayılar; 1366×768'de önizleme ile tablo birlikte |
| Diyagramlar | Cıvata, ağırlık, ISO (iki çizim), geometrik tolerans, tolerans yığılması ve profil çubuk planı tema token'larından renk alır; geometri aynı |

## 4. Bulunan ve düzeltilen hata

`QScrollArea` içindeki sarmalanan etiketler, bazı pencere genişliklerinde
kaydırma çubuğu ve içerik yüksekliği arasında sonsuz yeniden boyutlandırma
döngüsüne giriyordu (92.000+ yığın çerçevesi, ISO geçme ekranında segfault).
Eski düzende bu genişliklere tesadüfen denk gelinmiyordu. `StableScrollArea`
iç içe yeniden boyutlandırmayı keser. Test: `tests/test_scroll_stability.py`.

## 5. Doğrulama

- Ekran görüntüleri (Linux, Qt offscreen, DejaVu Sans): 16 sayfa, iki tema;
  1366×768, 1440×900, 1920×1080, 820×560; `QT_SCALE_FACTOR` 1 / 1,25 / 1,5.
  Sayfa komutlarının görünür alanda kaldığı ayrıca kontrol edildi.
- Windows'ta Segoe UI, gerçek %125/%150 ölçek ve canlı SolidWorks ile
  görsel kontrol **yapılmadı**.
- Tam test takımı sonucu commit mesajında verilmiştir.

## 6. Kalanlar

- (Giderildi, 3 Kasım) Sayı alanı (`NumberSpinBox`), `pane()`,
  `StatusDelegate` ve `AdaptiveRow` `gui_qt/components.py` dosyasına taşındı;
  eski içe aktarma yolları çalışmaya devam eder.
- Ağırlık formu tek `ValueForm` olduğu için malzeme ve kesit grupları
  ayrılmadı.
- Nesting sayfa içi durum satırı, ana durum çubuğuyla kısmen tekrar ediyor
  (testler bu satıra bağlı).
- `shared/theme.py` eski Tk renklerini içeriyor; iki test hâlâ import ediyor.
