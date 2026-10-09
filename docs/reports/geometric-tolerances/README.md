# Geometrik toleranslar ve son program kontrolü

**261 test geçti; 0 başarısız, 0 atlanan. 79 gerçek Tk GUI testi.** Yeni sekme için 10 hesap/içerik ve 11 gerçek GUI testi eklendi; önceki 240 test de tekrar yürütüldü. Sonuçlar Linux sanal ekrandan alınmıştır; gerçek Windows/SolidWorks üretimi bu çalışmaya dahil değildir.

[Word raporu](GOKWORKS_Geometrik_Tolerans_Raporu_2026-10-09.docx), [test çıktısı](test-run.log), [test bazlı sonuçlar ve kaynak hashleri](gui-verification-results.json), [kapsam](coverage.json), [referans karşılaştırması](source-comparison.json), [ekran hashleri](screenshots.json), [Word bütünlüğü](word-report-validation.json).

Word raporunu GitHub dosya sayfasında **Download raw file** ile indirin. Yedi gerçek pencere görüntüsü rapora gömüldü. ZIP CRC ve python-docx içerik geri okuması kontrol edildi; Microsoft Word sayfa görünümü çalıştırılmadı.

## Yeni çalışma alanı

12 güncel ASME özelliği ve iki kaldırılmış eğitim kartı; sembol, tolerans çerçevesi, bölge şeması, açıklama, ölçüm yöntemi, datum ilişkisi ve üretim notu. Türkçe/İngilizce arama, açık/koyu tema, CSV/pano, tercih kalıcılığı ve standart rehberi var. Her iki panel kaydırılabilir; seçilen özellik görünür tutulur.

Silindiriklik t=0,3 mm, iki eş eksenli silindir arasındaki toplam radyal mesafedir; **±0,3 mm değildir**. Konum Ø0,3 mm için radyal pay 0,15 mm'dir. f/m/c/v sınıfından geometrik tolerans atanmaz. Tasarımcı t değerini girer. Ölçülmüş hata karşılaştırması yalnızca hata ≤ t aritmetiğidir; belirsizlikli kalite kabulü veya CMM analizi veya tam ASME model/resim doğrulaması değildir. Normal boyutla ilişkili yüzey formunda ilgili boyut toleransı girilirse t < boyut toleransı kontrol edilir.

FreeCAD-GDT commit **841518cdd74f6a7dad3321d29937c49dc7dc4b1f** ile 14 eski özellik adı eşleştirildi; ASME 2018’de kaldırılmış concentricity/symmetry ile güncel çerçeve üretimi engellendi; ayrı tolerans/datum yapısı incelendi. FreeCAD çalıştırılmadı; kod kopyalanmadı. Birincil kaynak kullanıcının yüklediği ASME PDF belgesidir; kapak/ana metin 2018 baskısıdır. R2024 dosya adında var, içerikte teyit edilmedi. Rule #1 (5.8.1), Rule #2 (5.9.1), şekil/yön/konum/profil/salgı bölümleri incelendi. PDF/figürleri yayımlanmadı. [Ayrıntılı kullanım ve kapsam](../../geometric-tolerances.md).

## Gerçek ekranlar

| Ekran | Görüntü |
| --- | --- |
| Silindiriklik / koyu | [Görüntü](screenshots/gdt-dark.png) |
| Silindiriklik / açık | [Görüntü](screenshots/gdt-light.png) |
| Konum / A-B-C | [Görüntü](screenshots/gdt-position-dark.png) |
| Toplam salgı | [Görüntü](screenshots/gdt-total-runout-dark.png) |
| Ölçüm karşılaştırması | [Görüntü](screenshots/gdt-measurement-dark.png) |
| Kaldırılmış sembol / eğitim | [Görüntü](screenshots/gdt-legacy-dark.png) |
| Küçük pencere 1000×690 | [Görüntü](screenshots/gdt-small-dark.png) |

## Tekrar çalıştırma

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user \
COVERAGE_FILE=/tmp/gokworks-geometric.coverage .venv/bin/python -m coverage run \
  --branch --source=pdf,dxf_dwg,solidworks,main,k_factor,gui,iso_fits,geometric_tolerances \
  docs/report-tools/run_verification.py --output-dir docs/reports/geometric-tolerances
COVERAGE_FILE=/tmp/gokworks-geometric.coverage .venv/bin/python -m coverage json \
  -o docs/reports/geometric-tolerances/coverage.json
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user \
  .venv/bin/python docs/report-tools/capture_gdt_gui.py
.venv/bin/python docs/report-tools/verify_gdt_reference.py --reference /tmp/gokworks-gdt-reference \
  --standard /path/to/ASME-Y14.5-2018-R2024-Dimensioning-and-Tolerancing.pdf
.venv/bin/python docs/report-tools/create_geometric_report.py
```

Kaynak checkout sabit referans commit'inde olmalıdır. Rapor, test sonuçları ve ekran hashleri son kodla eşleşmeden üretilmez. `git_head` commit öncesi ana sürümü, hashler sınanan çalışma ağacını belirtir. Önceki raporlar kendi sürümlerinin tarihsel kanıtları olarak korunur.
