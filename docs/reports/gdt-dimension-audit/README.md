# GD&T ölçü ve şema denetimi — 09.10.2026

**270 test başarılı; 0 başarısız, 0 atlanan. 84 gerçek Tk GUI testi.** GD&T kapsamında 14 hesap/içerik + 16 GUI testi vardır. Önceki 261 testlik rapor tarihsel kayıt olarak korunur.

[Word raporu](GOKWORKS_GDT_Olcu_Denetimi_2026-10-09.docx), [tam test çıktısı](test-run.log), [test bazlı kanıt ve kaynak hashleri](gui-verification-results.json), [kapsam](coverage.json), [ASME / GitHub eşleştirmesi](source-comparison.json), [eski–yeni gerçek Tk ölçümleri](drawing-before-after.json), [ekran kanıtları](screenshots.json), [Word paket doğrulaması](word-report-validation.json).

## Bulunan sorunlar ve düzeltmeler

| Kontrol | Önce | Güncel |
| --- | --- | --- |
| “45°” açısallık yönü | 29,38637996° | 45°; t oku sınırlara dik ve her iki sınıra temas eder. |
| Konum çap oku / bölge çapı | 0,857142857 | 1; ok tam çapı kapsar. |
| Profil bölgesi | Eğrinin düşey kopyaları; normal genişlik uniform değildi. | Dairesel teorik profil için eş merkezli normal ofsetler; bütün örnek noktalarda genişlik ve eşit dağılım sınandı. |
| Uzun çerçeve değeri | Sabit hücreye sığmıyordu. | Gerçek Canvas yazı sınırından hücre genişliği hesaplanır; iki tema × %100/%125/%150'de sayı hücre ve canvas sınırları içinde. |
| Teknik çerçeve ondalığı | Virgül | ASME 4.3.1/4.3.3: `Ø0.05`, mm altında başta sıfır; Türkçe giriş/açıklama virgülü destekler. |
| Ölçüm alanının anlamı | Genel “toplam hata” etiketi | 12 güncel tür için ayrı ölçüm tanımı; CSV/panoda aynı açıklama; profilde ±t/2 gösterimi. |

Eski–yeni ölçüm yardımcısı eski `870f96c840caf72262d43e41cf51dd8bd67f3efc` sürümünü gerçek Tk'da yeniden çizdirdi. Sayısal ASME kuralları yüklenen belgeye dayanır. Sabit FreeCAD-GDT commit'i 14 ad/çerçeve yapısı için karşılaştırıldı; kaynak uygulama çalıştırılmadı, normatif sayısal doğrulayıcı kabul edilmedi. Yüklenen lisanslı PDF yayımlanmadı.

## Bağımsız sayısal örnekler

- Konum dx=0,015 / dy=0,020 mm: `2 × √(dx²+dy²) = 0,05 mm`; Ø0,05 sınırında.
- Konum radyal 0,03 mm: çap hatası 0,06 mm; Ø0,05 sınırının dışında.
- Merkezlenmiş profil t=0,05 mm: normal sınırlar ±0,025 mm. +0,01 / +0,04 sapmaların max−min farkı 0,03 olsa da eşdeğer merkezlenmiş hata `2 × max(abs(sapma)) = 0,08 mm`; sınır dışında.
- Merkezlenmiş profil −0,025 / +0,025: eşdeğer hata 0,05; sınırda.
- Değerlendirilmiş sınır yarıçapları 24,975 / 25,025 mm: radyal bölge genişliği 0,05 mm. Salgı TIR tekrar ikiyle çarpılmaz.
- Hata 0,050001 / t=0,05: pay −0,000001 mm; Decimal ile sınır dışında, yuvarlayarak kabul edilmez.

Arayüze **önceden değerlendirilmiş geometrik hata** girilir; ham dx/dy, nokta bulutu veya CMM algoritması uygulanmaz. Datumlu profil hizalaması datum sistemini korur; datumsuz profil izin verilen ilişkilendirme sonrası değerlendirilir. Basit 2B konum örneği bütün AME eksenini kanıtlamaz. Normal yüzey şekli için isteğe bağlı `t < boyut toleransı` ilişkisi ayrıca sınanır; MMC zarfı ölçülmez.

## Gerçek ekranlar

[Koyu](screenshots/gdt-dark.png), [açık](screenshots/gdt-light.png), [konum](screenshots/gdt-position-dark.png), [profil](screenshots/gdt-profile-dark.png), [45° açısallık](screenshots/gdt-angularity-dark.png), [uzun çerçeve](screenshots/gdt-long-frame-dark.png), [toplam salgı](screenshots/gdt-total-runout-dark.png), [ölçüm karşılaştırması](screenshots/gdt-measurement-dark.png), [küçük pencere](screenshots/gdt-small-dark.png), [eski sembol engeli](screenshots/gdt-legacy-dark.png).

İki tema × beş boyut/ölçek: 1000×690, 1240×860, 1366×768, 1400×900 (%125), 1920×1080 (%150). Bütün girişlere/düğmelere kaydırarak erişim sınandı. Uygulama 4.627, testler 4.050 fiziksel Python satırı; toplam 8.677. Rapor araçları/veri/bağımlılıklar dahil değildir.

Linux sanal ekranda gerçek Tk kullanıldı. SolidWorks COM üretimi, Windows monitör/DPI sürücüleri ve Microsoft Word sayfa görünümü bu ortamda çalıştırılmadı. Karşılaştırma tam resim/model uygunluğu veya ölçüm belirsizliğiyle kalite kabulü değildir.

## Tekrar çalıştırma

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user COVERAGE_FILE=/tmp/gokworks-gdt-audit.coverage \
  .venv/bin/python -m coverage run --branch \
  --source=pdf,dxf_dwg,solidworks,main,k_factor,gui,iso_fits,geometric_tolerances \
  docs/report-tools/run_verification.py --output-dir docs/reports/gdt-dimension-audit
COVERAGE_FILE=/tmp/gokworks-gdt-audit.coverage .venv/bin/python -m coverage json \
  -o docs/reports/gdt-dimension-audit/coverage.json
DISPLAY=:99 .venv/bin/python docs/report-tools/verify_gdt_drawing_audit.py \
  --output-dir docs/reports/gdt-dimension-audit
DISPLAY=:99 .venv/bin/python docs/report-tools/capture_gdt_gui.py \
  --output-dir docs/reports/gdt-dimension-audit --dimension-audit
.venv/bin/python docs/report-tools/verify_gdt_reference.py \
  --reference /tmp/gokworks-gdt-reference --standard /path/to/ASME-Y14.5-2018-R2024-Dimensioning-and-Tolerancing.pdf \
  --output-dir docs/reports/gdt-dimension-audit
.venv/bin/python docs/report-tools/create_geometric_report.py \
  --output-dir docs/reports/gdt-dimension-audit --dimension-audit
```
