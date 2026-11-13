# DXF/DWG kapsamlı test — 13 Kasım 2026

Kaynak başlangıcı: `a1d402b9033f2f11d55956e16d308a30752ee42c`.
Bu rapor yeni kodun yerel doğrulamasıdır; eski EXE'nin yenilendiği veya kullanıcının
SolidWorks parçasının canlı okunduğu anlamına gelmez. Arayüz değiştirilmedi.

## Sonuç

- 857 test düğümü: **849 geçti, 8 atlandı**, 0 hata/çökme, 0 yeniden deneme.
- DXF/DWG paketinin kendi payı: 458 test, 452 geçti, 6 atlandı.
- 44 unittest alt kontrolü de geçti. Testler 42 ayrı süreçte çalıştı.
- Yeni 27 regresyon senaryosu eklendi. Önceden geçen testlere eklenen olumsuz
  örnekler üç açığı yeniden üretti; düzeltmelerden sonra geçtiler.
- Altı üretim dosyasında satır/dal kapsamı birlikte %89; bu, SolidWorks
  uyumluluk oranı veya bütün olası CAD dosyalarının doğrulanması değildir.
- EXE derlenmedi. Windows entegrasyonu başladıktan sonra çalışmaya devam edilmez.

## Denenen kapsam

| Alan | Kontrol |
| --- | --- |
| Tarama ve liste | Etkin parça/montaj, klasör, alt montaj, fiziksel örnek adetleri, gizli/lightweight bileşen, gerçek konfigürasyon ve Cut List eşleşmesi; kontrollü COM. |
| Çok gövdeli sac | Kalıcı gövde/Flat-Pattern kimliği, mekanik gövdeyi dışlama, seçili alt küme, `ORHAN-01/02/03`, aynı adlı farklı kaynaklar ve konfigürasyonlar. |
| Otomatik kayıt | Ham/sarılmış IDispatch karışımı, ek kaynak belge, SaveReferenced ile sonradan kirlenen montaj, salt okunur/adsız belge, Save3 hatası ve uyarısı, güvenli konfigürasyona dönüş. |
| Önizleme | Seçim değişimi, eski yanıtı reddetme, aşamalı açınım, cache/revizyon, 3B ağ/delikler, hata, iptal, kapatma ve yeniden deneme; gerçek Qt, COM kısmı kontrollü. |
| Çıktı | DXF, DWG ve birlikte aktarım; özgün dosyayı koruyan atomik yayın, dosya çakışması, kısmi başarı, geçici dosya temizliği ve kayıt/geri alma hatasında kuyruk durması. |
| Geometri | ASCII/ikili R12, R2000, R2018 DXF; gerçek dosya okuma/audit, sonlu koordinat, mükerrer kesim, eğriler, BLOCK, büküm katmanı ve boş kesim. |
| Arayüz akışı | Seçim/gruplama/filtreler, seçeneklerin aktarılması, sonuç listesi, kaynak listesi ve önizleme yaşam döngüsü; Linux Qt offscreen. |
| Bağımlılar | Ortak CAD dönüştürücü, profil kesim ve abkant SolidWorks okuyucusunun ilgili regresyonları. |

## Düzeltilen açıklar

1. **Eski kalınlık/malzeme ile dosya yayımlanması:** Save3 veya native aktarım,
   Cut List bilgilerini ilk kuyruk kontrolünden sonra değiştirebiliyordu. Üretim
   envanterinden gelen gövde, dosya yayımlanmadan önce tekrar doğrulanıyor.
   Değişen kimlik/kalınlık/malzeme eski adla yayımlanmıyor. Önizlemenin yalnız
   geometri kimliği taşıyan geçici istekleri bu üretim metadata kontrolüne sokulmadı.
2. **Yalnızca açıklama içeren DXF:** TEXT, POINT veya boş BLOCK taşıyan dosya,
   modelspace boş olmadığı için kabul edilebiliyordu. Kesim çizgisi/eğrisi yoksa
   çıktı reddediliyor; mevcut hedefin üzerine yazılmıyor. Kontrol eski klasör
   aktarımı dahil bütün DXF yayın yollarına uygulandı. Geçerli geometri yanında
   açıklama bulunması kabul edilmeye devam ediyor.
3. **Kapatma başarısızken başarılı sonuç:** Eski klasör yolunda CloseDoc istisnası
   yalnız not ediliyor, sessizce açık kalan pencere de denetlenmiyordu. Artık
   kuyruk duruyor, önceden yayımlanan çıktı kısmi sonuç/sayaçlarla korunuyor.
   Montajın hâlâ kullandığı, penceresi kapanmış referans bellekte kalabiliyor.
   Kapatılmış belge işaretçisi tekrar okunmuyor.

## Gerçek dosya matrisi

Sabit seed `20261113`: 180 üretilmiş ASCII/ikili DXF geçerli bulundu ve dosya
baytları değişmedi. 96 kesilmiş DXF reddedildi. Ayrı 12 örnekte gerçek LibreDWG
0.13.3 ile R2000 DWG yazıldı; GOKWORKS DWG okuyucusuyla geri okunan bir kapalı
kontur ve bir deliğin sınırları/net alanı bağımsız analitik değerle karşılaştırıldı.
Kaynak DXF/DWG dosyalarının baytları korundu. Dosya matrisinin süresi yaklaşık
4 saniyedir; canlı SolidWorks aktarım performans ölçümü değildir.

LibreDWG'nin tam metadata içeren ham DXF geri çıktısında geçersiz handle/
tekrarlanan handle sorunu görüldü. Geometri karşılaştırması programın mevcut
DWG import temizleme yoluyla yapıldı; ham dönüştürücü çıktısı kusursuz sayılmadı
ve dönüştürücü motoru bu görevde değiştirilmedi.

## Doğrulanamayanlar

8 atlama: 5 lisanslı/açık SolidWorks ve açıkça seçilmiş test kopyası isteyen
senaryo; 3 Windows COM/yerel pencere/ekran testi. Kullanıcının ağ klasöründeki
SLDPRT/SLDASM dosyaları, gerçek Save3 ve ExportToDWG2 bu makinede çalıştırılmadı.

Üretim DWG doğrulaması dosya başlığı seviyesindedir. 12 R2000 geri okuma örneği;
bütün DWG sürümlerinin, kesilmiş/bozuk ikili DWG'lerin veya SolidWorks'ün ürettiği
bütün dosyaların tam içerik doğrulaması anlamına gelmez. DXF geometri denetimi de
tam CAM, bütün kendini kesmeler veya tezgâh güvenliği sertifikası değildir.

## Kanıt ve tekrar

[Sayılar, kapsam ve kaynak SHA-256 değerleri](dxf-dwg-audit-20261113.json).
Ham JUnit/log, kapsama ve stres dosyaları çalışma ortamında
`/workspace/work/dxf-dwg-module-audit/` altında saklandı. Kapsama aracı üretim
bağımlılıklarına eklenmedi. Yerel çalıştırmada Qt platformu `offscreen`, test
runner'ının `MAX_RETRIED_BATCHES` değeri `0` olarak kullanıldı.

```sh
python packaging/run_windows_tests.py modules/dxf_dwg/tests modules/cad_converter/tests modules/profile_cutting/tests modules/press_brake/tests/test_solidworks.py 'tests/test_compact_workspaces_gui.py::test_visible_transfer_options_are_used_and_retained[dxf_dwg]' 'tests/test_compact_workspaces_gui.py::test_source_inventory_selection_filters_and_clear_share_the_export_model[dxf_dwg]'
```
