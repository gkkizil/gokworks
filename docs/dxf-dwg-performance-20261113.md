# DXF/DWG aktarımındaki performans gerilemesi — 13 Kasım 2026

`d783669`, `fad46f5` ve `755b4cc` sürümleri karşılaştırıldı. Otomatik kayıt
ve üretim doğrulamasındaki tekrarlar azaltıldı; arayüz ve yerel DWG motoru
değiştirilmedi.

## Gerilemenin kaynağı

- `fad46f5`, seçili gövde aktarımına otomatik kayıt eklerken aynı kaynak için
  iç içe kayıt taramaları eklemişti. Temiz belgelerin de dosya yolu her defasında
  okunuyordu. Geçici çıktı konfigürasyonu, asıl konfigürasyona dönülmeden hemen
  önce ayrıca kaydediliyordu.
- `755b4cc`, kayıt/aktarım sırasında değişebilen kalınlık ve malzemeyi kontrol
  etmek için her çıktı biçiminden sonra bütün unsur ağacını tekrar tarıyordu.
  DXF+DWG için gövde başına bir tam tarama üçe çıkmıştı.
- DXF denetimi ile geometri kontrolü aynı dosyayı ayrı ayrı okuyordu. Bu tekrar
  seçili aktarımda önceki sürümlerde de vardı; yeni gerilemenin tamamı buna
  atfedilmiyor.

## Düzeltme

İlk gövde doğrulaması tam yapılır. Sonraki biçimlerde modelin güncelleme sayacı,
rebuild durumu, konfigürasyonu, güncel gövde kimliği, FlatPattern sahipliği ve
Cut List üyeliği doğrulanır. Kalınlık ve malzeme her seferinde yerel API'den
yeniden okunur; değişmeyen sayaç bu değerlerin önbelleğe alınmasına izin vermez.
Belirsizlikte tam taramaya dönülür. FlatPattern tanım erişimi kapandıktan sonra
gövde nesneleri yeniden alınır.

Otomatik kayıt, iş başlangıcında, her yerel çıktı işleminden önce ve ilk
konfigürasyona dönüldükten sonra korunur. İç içe tekrarlar kaldırılmıştır.
İç aktarım kendi açtığı belgeyi kapatacaksa önce kaydetmeye devam eder.
Temiz belgeler kayıt taramasında dosya yolu sorgulanmadan elenir.

Denetlenmiş DXF belgesi geometri kontrolüne aktarılır; yeniden okunmaz.
Envanterde dosya revizyonu gövde başına yerine belge başına okunur.

## Ölçüm

Kontrollü COM sınırı ve test nesneleri kullanıldı. Her eski sürüm ayrı süreçte
`git show` ile kendi exporter/sheetmetal kodundan yüklendi. Sayaçlar envanter
sonrasında başlatıldı. Ham ölçüm özeti aynı dizindeki JSON dosyasındadır.

20 gövde, 100 başka açık belge, DXF+DWG; yerel aktarım belgeleri temiz bırakıyor:

| İşlem sayısı | d783669 | fad46f5 | 755b4cc | Düzeltme |
| --- | ---: | ---: | ---: | ---: |
| Tam gövde/unsur taraması | 20 | 20 | 60 | 20 |
| Tümünü Kaydet taraması | 0 | 121 | 121 | 61 |
| Yerel GetPathName çağrısı | 202 | 12.684 | 12.724 | 222 |
| Başarılı gövde | 20 | 20 | 20 | 20 |

8 gövde, 30 başka açık belge, DXF+DWG; konfigürasyon A→B→A, yerel aktarım
kaynağı değiştiriyor ve kaynak kaydı üst montajı değiştiriyor:

| İşlem sayısı | fad46f5 | 755b4cc | Düzeltme |
| --- | ---: | ---: | ---: |
| Tam gövde/unsur taraması | 8 | 24 | 8 |
| Tümünü Kaydet taraması | 49 | 49 | 25 |
| Yerel Save3 çağrısı | 64 | 64 | 48 |
| Başarılı gövde | 8 | 8 | 8 |

Bu ortamda canlı SolidWorks, kullanıcının modelleri ve ağ paylaşımı yoktur.
Bu sayılar gereksiz işlemlerin kaldırıldığını gösterir; gerçek uygulamada
saniye veya hızlanma katsayısı taahhüdü değildir.

## Doğrulama

Yeni performans regresyonları; tek/iki biçim çağrı bütçesi, temiz belgelerde yol
okumama, tek DXF okuması, ortak envanter revizyonu, ilk konfigürasyonun tek son
kaydı, değişmiş/bilinmeyen sayaçta geri dönüş, yeniden adlandırma, rebuild,
yanlış sahiplik, yinelenmiş gövde kimliği ve eski IBody2 nesnelerini kapsar.
Mevcut salt okunur belge, kayıt hatası, iptal, üretim verisi değişimi, kaynak
durumu geri alma ve kısmi çıktı koruma testleri de çalıştırılır.

Sonuç: Linux/Python 3.13.5, Qt offscreen altında 875 test toplandı;
867 geçti, 8 atlandı, hata yok. Sınırlı süreç çalıştırıcısı
`packaging/run_windows_tests.py::run_tests` ile 42 ayrı süreç kullanıldı;
başarısız grubu tekrar çalıştırma kapalıydı (`MAX_RETRIED_BATCHES=0`). Kapsam:
DXF/DWG, ortak CAD dönüştürücü, profil kesim testleri, abkant SolidWorks
adaptörü ve DXF/DWG'nin iki kompakt arayüz aktarım testi. Yeni performans
regresyonları 17 durum içerir. Ruff F ve `git diff --check` geçti.
Bu sonuç Windows/SolidWorks testi olarak sunulmuyor; Windows doğrulaması
GitHub entegrasyonuna bırakılır.

API dayanağı: [IModelDoc2.GetUpdateStamp](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~GetUpdateStamp.html).
Özellik/konfigürasyon adı değişimleri sayacı artırmayabildiği için adlar ayrıca
doğrulanır ve eski adla bulunamayan unsurda tam taramaya dönülür.
