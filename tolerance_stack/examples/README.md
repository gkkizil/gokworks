# A − B − C örnek analizi

Bu dosyalar gerçek Qt uygulaması ve yerel hesap/rapor motorlarıyla üretildi.
CAD dosyası veya canlı SolidWorks kaynağı kullanılmadı.

- `A-B-C.gokstack.json`: GOKWORKS → Tolerans yığılması → Proje aç.
- `A-B-C.xlsx`: sonuçlar, bütün zincir, katkılar ve MC histogramı.
- `A-B-C.pdf`: Unicode PDF analiz raporu.

A=50±0,10; B=20±0,05; C=29,80±0,03 mm. K=A−B−C.
Nominal **0,20 mm**, Worst-Case **0,02…0,38 mm**.
Örnekte kesilmemiş normal dağılım, 50.000 örnek ve seed=42 kullanılır.
JSON açılırken arşiv sonucu güncel kabul edilmez; zinciri doğrulayıp hesaplayın.
Cp/Cpk ve PPM değerleri varsayımsal/simülasyon temellidir.
