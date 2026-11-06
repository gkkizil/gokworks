# Parametrik Sac Açınımı çekirdeği

GUI, SolidWorks, internet veya LLM bağlantısı gerektirmeyen servis.
Başlangıç sözleşmesi: [contract_v1.md](../../docs/unfolding/contract_v1.md).

Motor 1.1.1 kod denetimi ve düzeltmeleri:
[AUDIT_FIXES.md](../../docs/unfolding/AUDIT_FIXES.md). Eski projeler korunur;
sonuçlar motor sürümüne göre yeniden hesaplanır.

6 Kasım 2026 güncel kapsam: **191 kaynak varyantı / 51 aile / 11 kategori**;
eski yedi API varyantı geriye uyumluluk için korunur. Aşağıdaki yedi satırlı
tablo ilk teslimin kapsamıdır. Güncel hesap/çıktı durumu ve açık kısıtlar için
[genişleme raporu](../../docs/unfolding/EXPANSION_REPORT.md),
[191 satırlı matris](../../docs/unfolding/source_coverage.csv) ve
[GitHub kaynak araştırması](../../docs/unfolding/research/README.md) esas alınır.

```python
from core.unfolding import UnfoldService, UnfoldRequest, ExportOptions
s = UnfoldService()
r = s.calculate(UnfoldRequest(parameters={'diameter': 300., 'height': 200.}))
assert r.status == 'success'
print(r.parts[0].metrics.bounds_mm)  # (0, 0, 942.4777960769379, 200)
s.export(r, ExportOptions('silindir.zip', 'zip', include_step=True))
```

```sh
python -m core.unfolding docs/unfolding/examples/cylinder.json --format dxf --output silindir.dxf
python -m core.unfolding docs/unfolding/examples/cone-frustum.json --format pdf --output koni.pdf
python -m core.unfolding docs/unfolding/examples/cone-frustum.json --format step --output koni.step
python packaging/run_windows_tests.py tests/unfolding
```

Mevcut dosya varsayılan olarak korunur; CLI'da bilinçli üzerine yazmak için
`--overwrite` gerekir. Çok parçalı DXF için `--part-id` seçin veya ZIP üretin.

| Aile / variant_id | Gerçek uygulama | STEP orta yüzey |
|---|---|---|
| cylinder / straight | Analitik dikdörtgen; normal referans dönüşümü | Var |
| cylinder / bevel | Düzlem–silindir kesişimi, kord hatası sınırlı kesim | Kırpma doğrulanmadığı için kapalı |
| cone / full | Analitik daire sektörü | Var |
| cone / frustum | Analitik halkasal sektör; kararlı silindir sınırı | Var |
| rectangular_reducer / centered | 4 ayrı düz trapez panel | Var, ayrı düz B-Rep yüzler |
| rect_to_round / centered_faceted | 4 düz üçgen + 4 fasetli köşe yaması | Var, gerçek düz B-Rep fasetler |
| segmented_elbow / constant_diameter | Serbest toplam açı, N−1 miter birleşimi | Kırpma doğrulanmadığı için kapalı |

STEP yalnız orta yüzeydir, **solid veya düzenlenebilir SolidWorks özellik
ağacı değildir**. STEP, önizleme mesh'inden üretilmez. Bindirmede 2D payı
eklenir; 3D nominal yüzeydir ve STEP kapatılır. Gerçek yetenekler sonuç
`capabilities` alanından alınmalıdır; bağımlılık yoksa ilgili çıktı açılmaz.

Verilen çaplar inner/mid/outer yüzeyinde yorumlanır; normal offset sabit
uç ölçüm düzlemlerinde yapılır. Tam konide t>0 inner/outer tepe bitişi ve
faset geçişin t>0 normal offset'i v1 kapsamında değildir; bu durumlar
reddedilir. Geometrik orta yüzeyden abkant büküm telafisi çıkarımı yapılmaz.
`geometry.bend_allowance` bağımsız, kullanıcı K değeri gerektiren yardımcıdır;
mevcut açınıma gizlice eklenmez.
`bend_profiles.develop_profile/calibrate_k`, ayrıca iç/dış/teğet flanş
boylarını ve ölçülmüş numuneden K hesabını destekler; fitting geometri
akışına veya arayüze otomatik uygulanmaz.

`geometry_tolerance_mm`, kesim `chord_error_mm` ve önizleme `mesh_error_mm`
ayrıdır. Kalınlık sıfır veya yoğunluk eksikse kütle `None` olur. Üretici,
yoğunluk, malzeme fiyatı, evrensel K katsayısı ve imalat toleransı atanmaz.

Projeler `UnfoldProject/ProjectItem` olarak sürümlü JSON kaydedilir. Toplu:

```python
project = s.load_project('docs/unfolding/examples/reference-project.gokunfold.json')
report = s.export_project(project, ExportOptions('tum-parcalar.zip', 'zip'))
assert report.status == 'complete'
```

ZIP manifesti her çıktı için istek/revizyon/imza ve adet taşır. Proje adedi
× öğe adedi × parça adedi bir kez uygulanır. Hatalı öğeler manifestte kalır;
istenen bir PDF/STEP başarısızken başarı taklidi yapılmaz. Çekirdek iptal
edildiğinde son geçerli cache veya mevcut dosya değiştirilmez. STEP ayrı
headless süreçte çalışır; iptal/süre aşımında süreç sonlandırılır.

Arayüz Claude tarafından ayrıca geliştirilecektir; bu değişiklik menüye
çalışmayan ekran eklemez. [Claude notu](../../docs/unfolding/CLAUDE_HANDOFF.md)
ve [teknik rapor](../../docs/unfolding/IMPLEMENTATION.md).
