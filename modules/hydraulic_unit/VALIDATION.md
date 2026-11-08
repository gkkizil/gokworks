# Hidrolik altyapı doğrulaması — 8 Kasım 2026

Çalışma dalı: `agent/codex`. Taban: `f981cb9` (güncel main kontrolüyle).
Arayüz ve menü kaydı kullanıcı talimatıyla Claude'a bırakıldı.

## Sonuçlar

- Hidrolik modülü: 70 test geçti.
- Saf mevcut motor importu, mevcut sayfa açılışı, PyInstaller kayıt hook'u,
  paket veri dosyaları ve ISO/dişli sayısal regresyonları dahil birleşik
  koşu: **114 geçti, 56 alt test geçti**.
- Ruff E9/F63/F7/F82/F401: geçti. Git whitespace kontrolü: geçti.
- `main.py --self-check`: Linux Qt offscreen ortamında geçti; mevcut
  19 modül, iki tema ve dört çözünürlük kontrol edildi. Bu listede hidrolik
  ekranı yoktur; henüz UI entegrasyonu yapılmadı.
- Dört fazlı örnekten proje/JSON/Excel ve dört sayfalık A4 PDF üretildi.
  Excel/JSON geri okundu. PDF metni, Türkçe karakterler ve çok sayfalılık
  test edildi; ilk sayfa ve üç grafiği bir arada gösteren son sayfa ayrıca
  render edilip görsel olarak incelendi.
- PDF sayfalama düzeltmesi: belge gerçek A4 kullanılabilir sayfa boyutunu
  bilir; grafikler ayrı bir sayfada toplanır. Metin kontrolü fonttaki fi
  ligatürünü Unicode NFKC ile normalize eder.

Ortam: Python 3.13.5, PySide6/Qt 6.10.3, openpyxl 3.1.5; mevcut bağımlılıklar.
Canlı Windows, SolidWorks, pompa deney düzeneği veya motor üretici testi
yapılmadı. Windows CI sonucu bu yerel doğrulama kaydına dahil değildir.

## Bağımsız mühendislik kontrolleri

22.04 L/min pompa debisi; 6.9019608 kW mil gücü ve 7.5 kW nominal motor;
10.803408 mm teorik hat çapı; 49.875925 kN silindir kuvveti. Bunlara ek:

- Karşı basınç içeren ters çap/kuvvet eşdeğerliği ve rejeneratif dış besleme.
- Euler uç bağlantıları ve sıfır yükte tanımsız emniyet oranı.
- Moment × açısal hız ile pompa mil gücü eşitliği.
- Sabit güç p–Q zarfı ve kompansatör/emniyet valfi sınırları.
- Laminer kayıp için bağımsız Hagen–Poiseuille bağıntısı, geçiş/türbülans sınırları.
- Walther uç noktaları ve Boyle n=1 akümülatör limiti (mutlak basınç).
- Ardışık fiziksel konum, strok taşması, başlangıca dönüş ve çoklu silindir.
- Faz süreleri, bağımsız RMS, toplam mil enerjisi eksi kuvvet × mesafe.
- Sabit pompa bekleme ısısı ve emniyet valfi debisinin ortak tank dönüşüne eklenmesi.
- Karşılanamayan ihtiyacın hızını değiştirmeme ve ısıyı scenario_only etiketleme.
- Sıkı JSON şeması, yanlış türler, sonlu olmayan sayılar, formül enjeksiyonuna
  karşı Excel hücrelerini metin yazma, eski sonuçla raporu reddetme.
- İptalde mevcut dosyayı koruma, sayfa başına PDF işi ve tek terminal sinyali.

## Tekrar çalıştırma

```sh
python -m pytest tests/hydraulic_unit -q
python -m modules.hydraulic_unit examples/ornek_pres_unitesi.gwhyd --json sonuc.json --excel sonuc.xlsx --pdf sonuc.pdf
python main.py --self-check hydraulic-startup.json
```

Linux ekranı yoksa Qt komutlarına `QT_QPA_PLATFORM=offscreen` eklenir.
Görsel/çıktı kanıtları bu koşuda `/tmp/hydraulic-example.*` ve
`/tmp/hydraulic-app-startup.json` altında üretildi; dağıtım kaynağı olarak
commit'e ikili rapor eklenmedi. Yeniden üretilebilir örnek proje repo içindedir.

Sınırlar ve kaynakların doğrulama durumu README'de; UI sözleşmesi
CLAUDE_HANDOFF.md içindedir. Bu testler üretici veya imalat onayı değildir.
