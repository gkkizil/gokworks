# GOKWORKS arayüz tasarım sistemi

GOKWORKS bir mühendislik aracıdır. Arayüz; hız, okunabilir teknik veri ve
tutarlılık için tasarlanır. Kaynak kod: `gui_qt/theme.py` (token'lar ve QSS),
`gui_qt/components.py` (ortak bileşenler), `gui_qt/workspace.py` (sol menü),
`gui_qt/app.py` (ana pencere, durum çubuğu, özellik paneli).

## 1. İlkeler

1. **Bilgi yoğunluğu önce gelir.** Kompakt satırlar (26 px), dar boşluklar,
   tablo ve özellik paneli tercih edilir. Büyük kartlar, büyük başlıklar ve
   dekoratif boşluk kullanılmaz.
2. **Düz yüzeyler, ince çizgiler.** Bölgeler gölge veya iç içe kartla değil,
   1 px ayırıcıyla (`separator()`) ve yüzey tonu farkıyla ayrılır. Köşe
   yarıçapı denetimlerde 3 px, panellerde 2 px, tablolarda 0'dır.
3. **Tek vurgu rengi.** Mavi `accent` yalnız birincil komut, seçili öğe,
   odak ve etkin sekme için kullanılır. Durum renkleri (`success`,
   `warning`, `danger`) yalnız anlam taşıdığında kullanılır.
4. **Ölçü her zaman birimiyle.** Etiket biçimi `Ad · birim`
   (`Kalınlık · mm`). Sayılar sağa hizalanır; ondalık ayırıcı virgüldür
   (`QLocale('tr_TR')`).
5. **Hareket en aza indirilir.** Tek animasyon, modüller arası geçişte
   yaklaşık 150 ms süren sade solmadır (`gui_qt/transitions.py`). Dekoratif
   animasyon ve süs kullanılmaz. Yalnız işlevsel ikonlar kullanılır.

## 2. Renk token'ları

`COLORS[appearance][anahtar]`; `appearance` = `dark` (varsayılan) veya
`light`. Anahtarlar kamuya açık API'dir: yeniden adlandırmayın, yalnız ekleyin.

| Token | Koyu | Açık | Kullanım |
| --- | --- | --- | --- |
| `bg` | `#1E1F22` | `#EDEEF0` | Çalışma alanı zemini, alternatif satır |
| `sidebar` | `#18191B` | `#E4E6E9` | Sol menü, durum çubuğu, dock başlığı |
| `panel` | `#25262A` | `#FFFFFF` | Paneller, tablolar, menüler |
| `input` | `#2C2E33` | `#FFFFFF` | Düzenlenebilir alan, ikincil buton |
| `canvas` | `#1A1B1E` | `#F7F8F9` | Çizim/önizleme yüzeyi |
| `grid` | `#2A2C31` | `#E3E6EA` | Çizim ızgarası |
| `border` | `#3A3C42` | `#CDD1D6` | 1 px ayırıcı ve çerçeve |
| `border_strong` | `#4C4F57` | `#AEB4BC` | Hover çerçevesi, tablo başlık alt çizgisi |
| `hover` | `#30333A` | `#E6E9ED` | Üzerine gelme |
| `selected` | `#233A5C` | `#D8E5F7` | Seçili satır/öğe |
| `text` | `#E3E5E8` | `#1F2328` | Birincil metin |
| `muted` | `#9DA2AB` | `#5B636E` | Etiket, açıklama, pasif ikon |
| `accent` / `focus` | `#4C9DFF` | `#1767C6` | Birincil komut, odak, etkin sekme |
| `on_accent` | `#0B1626` | `#FFFFFF` | Vurgu zeminindeki metin/ikon |
| `success` | `#56C08D` | `#1E7A4C` | Başarılı, bağlı |
| `warning` | `#E2B04A` | `#8A5D00` | Uyarı |
| `danger` | `#F07A7A` | `#B8323E` | Hata, yıkıcı komut |

Çizim yapan bileşenler (önizleme, diyagram, nesting tuvali) arka planı
`canvas`, yardımcı çizgileri `grid`/`muted`, seçimi `accent` ile çizer ve
`theme_changed()` içinde yeniden boyanır. Sabit `#ffffff` gibi değerler
kullanılmaz.

## 3. Tipografi ve ölçüler

- Yazı tipi: Segoe UI (Windows). Linux test ortamında DejaVu Sans.
- Boyutlar (`FONT_SIZES`, mantıksal px): açıklama 11, gövde 12,
  bölüm başlığı 12 yarı kalın, sayfa başlığı 15 yarı kalın, ana sonuç 20.
- Kalın yazı yalnız sayfa/bölüm başlığı, seçili menü öğesi ve birincil buton
  içindir.
- Boşluk ölçeği (`SPACING`): 2, 4, 6, 8, 12, 16 px. Sayfa kenar boşluğu
  12/8 px, bölümler arası 8 px, form satırı 6–8 px.
- `ROW_HEIGHT` = 26 px; denetim yüksekliği yaklaşık 24–26 px.
- DPI: Qt `PassThrough` ölçekleme kullanır. Sabit piksel konumlandırma
  kullanılmaz; layout, splitter ve scroll alanı kullanılır.
  En küçük pencere 820 × 560'tır.

## 4. Ortak bileşenler

| Bileşen | API | Not |
| --- | --- | --- |
| Buton | `button(text, cb, primary=, destructive=, flat=)` | Sayfa başına tek birincil komut |
| Sayfa komutu | `BasePage.action(title, cb, primary=)` | Başlık satırının sağında, ikonlu |
| Ayırıcı | `separator(vertical=False)` | Kart yerine bölge ayırma |
| Bölüm başlığı | `section_header(title, *widgets)` | Sol başlık, sağda küçük komutlar |
| Düz grup | `pane(title, rule=False)` | Kart yerine çerçevesiz başlıklı grup; hesap ekranları |
| Panel | `card(title)` | Yalnız gerçekten ayrı bir grup gerektiğinde |
| Sayı alanı | `NumberSpinBox(decimals)` | Virgüllü, sağa hizalı, gereksiz sıfırsız; `turkish_locale()` |
| Uyarlanır satır | `AdaptiveRow(*widgets)` | Dar sütunda alt alta, genişte yan yana komutlar |
| Durum hücresi | `StatusDelegate(appearance)` | Yalnız durum hücresini anlam rengiyle boyar |
| Form | `ValueForm.text/combo/check/path` | Değerleri ayarlara otomatik kaydeder |
| Dosya alanı | `PathPicker` / `ValueForm.path` | Dar sütunda `stack_fields()` |
| Tablo | `configure_view(view)` | Sola hizalı başlık, ızgarasız, sıralanabilir |
| Sonuç listesi | `ResultsPanel` | Arama, durum filtresi, CSV, günlük |
| Boş durum | `ViewEmptyState` | Tablonun üstünde, filtre temizleme |
| Ayrıntı/hata | `show_details(parent, title, text)` | Kopyalanabilir metin |
| Açılır bölüm | `Disclosure(title, widget)` | Değerleri korur |
| Kaydırma | `scroll(widget)` → `StableScrollArea` | Sarmalanan metinde döngüye girmez |
| İş | `context.jobs.start(owner, operation)` | GUI iş parçacığında COM yok |

Metin rolleri: `label(text, role)`; `role` ∈ `title`, `subtitle`, `section`,
`muted`, `result`, `error`, `warning`, `success`.

## 5. Ana pencere düzeni

```
┌ sol menü (232/64 px) ┬ başlık: ad + açıklama ············ komutlar ┬ ÖZELLİKLER ┐
│ logo · ‹             ├─────────────────────────────────────────────┤ (dock,     │
│ Araç bul… Ctrl+K     │ modül çalışma alanı (splitter'lı)           │  ≥1320 px) │
│ GRUP · n             │                                             │            │
│  ▸ modül             │                                             │            │
│ tema                 │                                             │            │
│ Ayarlar Hakkında İlt.│                                             │            │
├──────────────────────┴─────────────────────────────────────────────┴────────────┤
│ durum metni ············ ilerleme · ● SolidWorks · Bağlantıyı kontrol et       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

Durum çubuğundaki nokta: gri = kontrol edilmedi, yeşil = bağlı,
kırmızı = bağlantı yok. Kısayollar: `Ctrl+K` araç ara, `Ctrl+B` menüyü daralt,
`Ctrl+,` ayarlar, `Ctrl+F` liste araması.

## 6. Yeni modül kuralları

1. Sayfa `BasePage`'den türer. Başlık kısa bir ad, açıklama tek cümle olur.
   Komutlar `action()` ile eklenir; tek birincil komut kullanılır.
2. Renk, yazı boyutu ve boşluk için `gui_qt.theme` token'larını kullanın.
   Modül içinde `setStyleSheet` ile yeni renk tanımlamayın. Gerekirse
   `theme.py` içine yeni token ekleyin.
3. Veri girişi `ValueForm` ile yapılır, sayısal alanlar sağa hizalı ve
   birimli olur. Hatalı giriş, alanın yanında veya durum çubuğunda Türkçe
   ve eyleme dönük bir mesajla bildirilir; uygulama kapanmaz.
4. Liste ve sonuçlar `QTableView` + `TableModel` + `configure_view` ile
   gösterilir. Büyük veri için model/proxy kullanılır, `QTableWidget`
   kullanılmaz.
5. Çizim alanları `canvas` zemini kullanır ve tema değişince yeniden boyanır.
6. Uzun veya CAD işleri `JobManager` üzerinden çalışır. İlerleme
   `progressChanged`, durum `set_status` ile bildirilir. Durdur komutu
   sunulur.
7. Dar pencerede (820 px) komutlar kesilmemelidir; testler
   `tests/test_compact_workspaces_gui.py` ile denetler.

## 7. Sayfa geçişi

- `PageTransition`, yeni sayfanın üstüne `bg` renginde, fareyi engellemeyen
  bir katman koyar ve 150 ms'de (OutCubic) saydamlaştırır. Sayfa bileşenleri
  efekt içine alınmaz; OpenGL önizlemeleri ve odak etkilenmez.
- Saat, yeni sayfa ilk kez çizildikten sonra başlar; ilk kez açılan ağır
  sayfalarda solma kaybolmaz.
- Aynı sayfaya geçişte, ekransız (`offscreen`) test platformunda ve
  **Ayarlar → Sayfa geçişlerinde yumuşak geçiş** kapalıyken çalışmaz.
  Tercih `page_transitions` ayarında saklanır.
- Sol menü ve durum çubuğu sabit kalır; sayfa başlığı dahil yalnız çalışma
  alanı geçiş yapar.
