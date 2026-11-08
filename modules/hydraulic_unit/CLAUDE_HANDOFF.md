# Claude — Hidrolik Ünite arayüz entegrasyonu

Kullanıcı arayüzü sana bıraktı. Codex yalnız çekirdek, servis, kayıt, rapor,
test ve örnek proje ekledi. `gui_qt/app.py`, tema, bileşenler ve mevcut ekranlar
değiştirilmedi. Bu teslimde `ui.py` veya menü kaydı yoktur.

## Sayfa kaydı

`modules/hydraulic_unit/ui.py` içinde `HydraulicPage(BasePage)` oluştur.
Repo yapısal testi sayfa sınıfının bu gerçek dosyada olmasını bekler; `ui/`
paketinin içinden alias sınıf getirme. Aynı modülde `tests/test_ui.py` ekle.
`gui_qt/app.py`:

```python
# PAGE_TYPES
'hydraulic_unit': ('modules.hydraulic_unit.ui', 'HydraulicPage'),
# MODULES
('hydraulic_unit', 'Hidrolik Ünite Hesaplayıcı', 'MÜHENDİSLİK HESAPLARI'),
```

PyInstaller hook'u kayıttan otomatik toplar. Yeni ağır bağımlılık veya ortak
tema/iş yöneticisi refactor'u gerekmez. QtCharts mevcut PySide6 paketindedir.

## Tek doğru hesap kaynağı

```python
from modules.hydraulic_unit.core.models import *
from modules.hydraulic_unit.core.service import calculate_project
from modules.hydraulic_unit.service import describe, calculate
from modules.hydraulic_unit.core.validation import InputError

project = Project()              # dört fazlı, başlangıca dönen pres örneği
metadata = describe()            # sürüm 1: varsayılanlar, türler, SI birimleri, seçenekler
result = calculate_project(project)  # raporlara bu ProjectResult verilir
dto = calculate(project)         # JSON'a uygun sonuç + label/value/unit/formula satırları
```

İngilizce alanlar sabit API kimlikleridir; Türkçe etiketleri UI'da göster.
`describe().models` alan varsayılanlarını **SI** verir. `type` açıklama içindir;
güvenilir yükleme için `serialization.loads` kullan, type metnini eval etme.
Sabit hesapları UI'da tekrar yazma; `core` altındaki bağımsız API'leri kullan.

- `cylinder.calculate_cylinder(Cylinder, CylinderOperatingPoint)`: alan/oran,
  kuvvet, gerekli basınç, hız/debi/süre, ters nominal çap/mil ve Euler sonuçları.
- `pump_motor.pump_for_type(kind, **overrides)`: kaynağı örnek pompa tip katsayıları.
  `pump_flow`, `required_displacement`, `pump_torque`, `available_flow`, `select_motor`
  fonksiyonları bağımsız sekme hesabı için kullanılabilir.
- `piping.oil_for_grade` örnek yağ eğrisi verir. Gerçek ν40/ν100 ve kaynak
  girilebilsin. `recommended_velocity(role, pressure)` yalnız başlangıç önerisi;
  kullanıcı değerlerini her hesapta otomatik ezme.
- `tank_thermal.thermal_result`, `accumulator.accumulator_result` bağımsızdır.

Önemli SI dönüşümleri: mm→m, bar/psi→Pa, kN→N, rpm→rad/s,
L/min/ABD gpm→m³/s, cm³/dev→m³/dev, °C→K, cSt→m²/s.
`units.convert(value, source, target)` kullan. `density` kg/m³,
`heat_transfer` W/(m²K), `exponent` ve verimler boyutsuzdur.

## Çevrim sözleşmesi ve hatalar

Silindir `id` ve faz `cylinder_id` ile bağlanır. İleri hareketler `extend` veya
`regenerate`, geri `retract`, bekleme `hold`, boşta `idle` kimliklidir.
Her silindirin `initial_position` değeri vardır. Faz strokları **toplanır**;
uç konumlar `PhaseResult.start_position/end_position` içindedir.

Harekette `speed` veya `duration` değerlerinden biri None olmalıdır.
Beklemede/boştada speed=None, duration>0. Boşta force=0.
Basınçta bekleme itme yönündeki statik yüke aittir; farklı yönlü bekleme
şeması varmış gibi davranma. `stroke` hareket dışındaki fazlarda kullanılmaz.

`InputError.field` alan/faz kimliğidir; her geçersiz alanı `invalid=true`
ve tooltip ile göster. Fazlar `phases.N...`, yükleyici hataları `project...`
öneki taşıyabilir. Bağımsız silindir fonksiyonları bore/rod gibi yerel adlar verir.
Sonuç ve rapor düğmelerini geçersiz girdide temizle/kapat; eski sonucu gösterme.

`result.issues`: code, message, field, severity (`info/warning/critical`).
`result.feasible` tam mühendislik/ürün onayı değildir. `cycle.demand_met=False`
veya `thermal.status='scenario_only'` değerini görünür tut. Bekleme ideal kaçak
sıfırla hesaplanıyorsa bu varsayımı gizleme. `None` nominal seçim değeri,
"serinin dışında/değerlendirilmedi" demektir; sıfır değildir.

Grafikler `cycle.phases` içindeki duration, pressure (ihtiyaç), flow (ihtiyaç),
shaft_power değerlerinden kümülatif zamanda basamak eğrisi olarak çizilmeli.
`supply_pressure/flow` ile gerekli basınç/debiyi birbirinin yerine kullanma.
Mil gücü elektrik şebekesinden çekilen güç değildir. `rows[].formula` tooltip'e uygundur.

## Kayıt ve rapor

`serialization.save(project,path)`, `load(path)`; schema
`gokworks.hydraulic_unit`, version=1, units=SI, uzantı `.gwhyd`.
Kayıt/yükleme çekirdeği doğrular; kritik tasarım uyarısı içeren projeler
kaydedilebilir. Bozuk/yeni sürüm/tekrarlı alan/sonlu olmayan değer reddedilir.

`report.export.export_excel/export_json(project,result,path,stop=...)` mevcut
JobManager işi içinde çağrılabilir. Başarıdan önce dosya geri okunur; hata veya
iptalde önceki dosya korunur. Dosya üzerine yazma onayını dosya iletişim kutusunda
al. Kullanıcı yolunu iş sürerken sabit tut. Sonuç girdi parmak iziyle kontrol edilir.

PDF için `create_pdf_job(project,result,path,parent=page)` **ana Qt iş parçacığında**
çağrılmalı. Widget oluşturmaz; QTimer ile sayfa başına ilerler:

```python
job = create_pdf_job(project,result,path,parent=self)
job.progress.connect(self.set_pdf_progress)   # (sayfa, toplam)
job.finished.connect(self.pdf_finished)       # dosya yolu
job.failed.connect(self.pdf_failed)           # hata/iptal açıklaması
self.pdf_job = job                           # ömrünü işlem sonuna kadar koru
job.start()
# Durdur/sayfa kapanışı: job.cancel(); sonra deleteLater()
```

Üç rapor grafiği otomatik eklenir. Senkron `export_pdf` CLI/test içindir;
QThread içinden çağırma. Genel iş kilidini korumak gerekiyorsa mevcut
JobManager worker'ı PDF başlangıcını queued sinyalle GUI'ye iletsin ve bir
threading.Event üzerinden sonucu/iptali beklesin. Worker'da Qt metin/grafik
boyama çalıştırma. Kapanışta devam eden PDF işini cancel et; eski hedef korunur.

## Kabul ve sınırlar

300 ms debounce, tema tokenları, yedi sekme ve formül tooltip'leri kullanıcı
talebidir. UI'ı yeniden tasarlamadan ortak bileşenlere uyarla. Örnek dosya:
`examples/ornek_pres_unitesi.gwhyd` (250 mm yaklaşma, 50 mm presleme,
bekleme, 300 mm geri dönüş). Örnek sabit pompa devresinde soğutucu ihtiyacını
ve fazla debi kayıplarını bilerek görünür kılar; üretim reçetesi değildir.

Çekirdek test komutu: `python -m pytest tests/hydraulic_unit -q`.
UI tamamlanınca kendi pytest-qt testlerini, mevcut gezinme/paketleme
testlerini ve Windows açılışını doğrula. Bu teslim canlı Windows/SolidWorks
testi yapıldığı anlamına gelmez. CAD veya SolidWorks bağlantısı bu modülün kapsamı değildir.
