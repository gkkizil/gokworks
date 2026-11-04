# DFM Analyzer — Aşama 1 (2B DXF, geometri + lazer kesim)

Menü: **Üretim → DFM · İmalat uygunluğu**.

DXF kesim geometrisini seçilen kural profiline göre kontrol eder. Bulgular,
gerçek çizim koordinatlarında (mm, Y yukarı) geometrinin üzerinde gösterilir.
Kaynak dosya yalnız okunur. Analizden önce ve sonra SHA-256 aynı kalmalıdır.

Bu bir **2B geometri kontrolüdür**; üretime uygunluk onayı veya sertifika
değildir. Paketle gelen lazer profili **doğrulanmamış bir örnek başlangıç
profilidir**. Gerçek sınırlar makineye, lazer gücüne, gaza ve malzemeye
bağlıdır.

## Mimari

| Katman | Dosya | Qt |
|---|---|---|
| Veri modeli, JSON şeması `gokworks.dfm_result` v1 | `models.py` | yok |
| DXF okuyucu (birim, INSERT açma, desteklenmeyen nesne listesi) | `importers/dxf.py` | yok |
| Topoloji (kapalı/açık kontur, dal, kesişim, parça/delik/ada) | `geometry/topology.py` | yok |
| Kural motoru ve kurallar | `rules/base.py`, `rules/geometry.py`, `rules/laser.py` | yok |
| Profiller, şema `gokworks.dfm_profile` v1 | `profiles/` | yok |
| Analiz ve iş fonksiyonu (JobManager) | `controller.py` | yok |
| JSON / CSV rapor | `reporting/` | yok |
| 2B görüntüleyici | `visualization/view.py` | var |
| Sayfa (ayarlar, önizleme, sonuçlar) | `ui.py` | var |

Motor Qt'siz çalışır:

```python
from modules.dfm_analyzer.controller import analyze, profiles
result = analyze('parca.dxf', profiles()['laser_generic'], thickness=2)
```

## Sonuç durumları

- **ERROR / WARNING / INFO**: bulgunun önemi. Profilden değiştirilebilir.
- **PASSED**: kural çalıştı ve bulgu yok.
- **FAILED**: kural çalıştı ve en az bir bulgu var.
- **NOT_EVALUATED**: kural çalıştırılamadı. Örnek nedenler: kalınlık girilmedi,
  desteklenmeyen nesne var, profilde sınır yok. Bu durum hiçbir zaman "geçti"
  olarak gösterilmez.

Bir sınır `max(min_mm, factor_t × t)` olarak hesaplanır. Sınıra tam eşit değer geçer.
Eğriler `Eğri doğruluğu` (varsayılan 0,01 mm) ile düzleştirilir; genişlik
ölçümleri bu kadar sapabilir. Daire delikleri gerçek çapla ölçülür.

## Kurallar

| Kimlik | Kural |
|---|---|
| DFM-GEO-001 | Açık kontur (iki uç ve aralarındaki boşluk işaretlenir) |
| DFM-GEO-002 | Kapatma toleransı içinde köprülenen mikro boşluk |
| DFM-GEO-003 | Dallanan kontur (ikiden fazla uç birleşen düğüm) |
| DFM-GEO-004 | Sıfır uzunluklu nesne |
| DFM-GEO-005 | Çift (üst üste kopya) nesne |
| DFM-GEO-006 | Kısmen çakışan çizgiler (ortak uzunluk) |
| DFM-GEO-007 | Kendini kesen kontur |
| DFM-GEO-008 | Birbirini kesen konturlar |
| DFM-GEO-009 | Boşluk içinde ada (kesimde düşer) |
| DFM-GEO-010 | Çok kısa segment (bilgi) |
| DFM-GEO-011 | Desteklenmeyen nesne → değerlendirilemedi |
| DFM-GEO-012 | Birim/ölçek makullüğü |
| DFM-GEO-013 | Kapalı parça yok |
| DFM-LAS-001 | Minimum delik çapı |
| DFM-LAS-002 | Minimum kanal/boşluk genişliği (en büyük iç teğet daire) |
| DFM-LAS-003 | Delik ile dış kenar arasındaki et |
| DFM-LAS-004 | İki delik arasındaki köprü |
| DFM-LAS-005 | İnce dil/parmak (morfolojik açma) |
| DFM-LAS-006 | Dar kenar çentiği (morfolojik kapama) |
| DFM-LAS-007 | Kalınlık/malzeme profil kapsamında mı |
| DFM-LAS-008 | Parça tabla ölçüsüne sığıyor mu (90° dahil) |

## Kendi profilini oluşturma

1. `profiles/laser_generic.json` dosyasını kopyalayın.
2. `id`, `name` ve `profile_version` değerlerini değiştirin.
3. Değerleri makineniz için doğruladıysanız `"verified": true` yapın.
4. Kural başına yalnız şu anahtarlar kabul edilir: `enabled`, `severity`,
   `min_mm`, `factor_t`, `reference`.

Bilinmeyen kural kimliği, negatif veya sıfır sınır ya da hatalı şema reddedilir.
Dosya sayfadaki **Profil dosyası…** düğmesiyle yüklenir.

## Aşama 1'de olmayanlar

- DWG okuma: DXF'e dönüştürün.
- PDF ve Excel raporu: şu an yalnız JSON ve CSV var.
- SolidWorks sac metal analizi (Aşama 2).
- Abkant/büküm kuralları (Aşama 3).
- Talaşlı imalat (Aşama 4).
- Kerf telafisi, lead-in/out, ısı dağılımı ve takım yolu.
- İç köşe yarıçapı kuralı.
- Serbest açılı tabla yerleşimi (DFM-LAS-008 eksen hizalı sınır kutusu kullanır).
