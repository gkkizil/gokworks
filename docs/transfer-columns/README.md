# Aktarım ve Montaj — iki sütunlu çalışma alanı

PDF, DXF/DWG, BOM ve İsimlendirme aynı yerleşimi kullanır. Kaynak seçimi ve
ayarlar solda, sonuçlar sağda tam yükseklikte bulunur. İşlem düğmeleri sol
sütunun altında sabittir; ayarları kaydırmak düğmeleri ekran dışına çıkarmaz.

- PDF/DXF: klasör seçimi, görünür aktarım seçenekleri ve kaynak dosya listesi
  solda; dosya durumları, arama, rapor ve günlük sağda.
- BOM: kaynak montajın parça ağacı solda; seçilen parçanın adet/ağırlık bilgileri
  veya seçilen montajın ağacı sağda.
- İsimlendirme: kaynak/hedef, montaj seçimi ve adlandırma kuralları solda;
  mevcut/yeni dosya adlarının önizlemesi sağda.
- Ayırıcı sürüklenebilir. Küçük pencerede sonuçlara en az 320 piksel ayrılır;
  pencere büyütüldüğünde kullanıcının seçtiği sütun genişliği geri gelir.
- Kaynak dosya listesi mevcut sonuç modeliyle çalışır. Sol listeden seçim,
  sağdaki ilgili satırı gösterir; gizleyen bir sonuç filtresi varsa kaldırılır.
  `Temizle`, kaynak envanterini ve sonuç/günlük verilerini birlikte sıfırlar.
  İşlem sürerken temizleme kapalı kalır.

## Ekran görüntüleri

Görüntüler çalışan PySide6 arayüzünden Linux / Qt offscreen ortamında alınmıştır.
Dosya adları, montaj ve sonuç kayıtları örnek veridir. Görseller canlı SolidWorks
aktarımı veya gerçek bir CAD dosyası üzerinde test yapıldığını göstermez.

| Ekran | Geniş pencere | Küçük pencere |
| --- | --- | --- |
| PDF | [Arşiv: 1440 × 900](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/transfer-columns/pdf-dark-1440.png) | [Arşiv: 820 × 560](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/transfer-columns/pdf-dark-820.png) |
| DXF/DWG | [Arşiv: 1440 × 900](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/transfer-columns/dxf_dwg-dark-1440.png) | Otomatik geometri testine dahil |
| BOM | [Arşiv: 1440 × 900](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/transfer-columns/bom-dark-1440.png) | [Arşiv: 820 × 560](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/transfer-columns/bom-dark-820.png) |
| İsimlendirme | [Arşiv: 1440 × 900](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/transfer-columns/naming-dark-1440.png) | [Arşiv: 820 × 560](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/transfer-columns/naming-dark-820.png) |

[Arşiv: Açık tema PDF](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/transfer-columns/pdf-light-1440.png) · [Görüntü ölçümleri](capture.json)

## Doğrulama

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q \
  tests/test_compact_workspaces_gui.py tests/test_qt_workflows.py
QT_QPA_PLATFORM=offscreen python main.py --self-check /tmp/gokworks-selfcheck.json
```

Yeni kontroller iki sütunun konumunu, taşmayı, işlem düğmelerinin görünürlüğünü,
ayırıcı genişliğinin korunmasını, kaynak/sonuç seçimini, filtreleri ve temizlemeyi
gerçek Qt modelleri ve olaylarıyla sınar. Mevcut Qt regresyonları diğer modüllerin
gezintisini, temalarını, ayarlarını, iş akışlarını ve yerel çıktıları da kapsar.

Sonuç: **156 test geçti**; 12 modüllü uygulama öz denetimi de iki tema ve dört
çözünürlükte geçti. [Test özeti](checks.json) · [Uygulama öz denetimi](selfcheck.json)

SolidWorks COM okuma/aktarma ve Pack and Go motorları değiştirilmemiştir. Canlı
SolidWorks ile Windows entegrasyon testi bu Linux oturumunda çalıştırılmadı.
