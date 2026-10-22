# 3D Dönüştürücü

GOKWORKS → **Aktarım ve Montaj → 3D Dönüştürücü**. PySide6 ekranı mevcut
`JobManager` ve iki sütunlu aktarım alanını kullanır. CAD çağrıları tek STA
iş parçacığında yapılır; arayüze yalnız basit veri/sinyaller gönderilir.

## Kullanım

1. Sol üstteki **Kaynak dosyaları → Dosyaları seç…** ile çoklu dosya seçin
   veya **Kaynak klasörü seç…** ile klasör ekleyin. Bu düğmeler ayarlar
   kaydırılsa da görünür kalır. Sürükle/bırak da desteklenir.
   Alt klasör taraması varsayılan açıktır. Aynı fiziksel dosya tek kez eklenir;
   SLDDRW dosyaları bu araca alınmaz.
2. Altındaki **Çıktı ve formatlar** bölümünde çıktı klasörünü ve bir veya
   birden fazla formatı seçin. Kaynak seçimi çıktı klasörünü değiştirmez;
   son seçilen kaynak klasörü ayrı hatırlanır. Her format kendi
   klasöründedir: STEP_AP203, STEP_AP214, STEP_AP242, PARASOLID_XT,
   PARASOLID_XB, IGES, STL_BINARY, STL_ASCII. Yalnız seçilenler oluşturulur.
3. Aktif/bütün/seçilen konfigürasyonları seçin. **Konfigürasyonları oku** ile
   adları alın; seçilen modunda işaretleyin veya adları noktalı virgülle yazın.
   Bir modelde seçilen ad yoksa o model için açık hata raporlanır.
4. Montajı tek dosya veya benzersiz bileşen dosyası/konfigürasyonu başına ayrı
   aktarın. İkinci modda alt montajların kendilerini de ayrıca aktarabilirsiniz;
   parçalar her durumda alt seviyelerden bulunur.
5. **Aktarımı başlat**. **Durdur**, devam eden COM çağrısını zorla kesmez; çağrı
   bitince geçici dosya silinir, durum geri alınır, sonraki işe geçilmez.
6. Sağdaki dosya/sonuç/günlük sekmelerini inceleyin. **Rapor** ile CSV/XLSX
   kaydedin. **Temizle**, hem kuyruğu hem sonuç/günlüğü temizler; işler sürerken
   kaynak değiştirme ve temizleme kapalıdır.

## Formatlar ve koşullar

- AP203/AP214: `swStepAP` kaydedilir, değiştirilip geri okunur ve aktarım
  sonunda doğrulanarak geri yüklenir. AP204 yoktur.
- AP242: `IModelDocExtension.PublishSTEP242File(Path)`; MBD lisansı yoksa
  başarısız sonuç gösterilir. `swStepAP=242` varsayılmaz. PMI bütünlüğü
  doğrulanmış değildir; normal STEP katı geometri aktarımından farklı bir
  MBD yayınlama yoludur.
- Parasolid X_T/X_B: gerçek malzeme geometrisini taşıyan text/binary çıktılar.
  Parça/montaj gövde sayısı burada sadeleştirilmez.
- STL: binary/ASCII ayrı hedeflerdir. Varsayılan mm, ayrıca inch; kaba/yüksek
  SolidWorks ön ayarları, orta = 0,1 mm / 15° özel ayar, kullanıcı özel ayarı.
  API sapması metreye, açı radyana çevrilir. Montaj gövdeleri tek STL'dedir;
  montaj ağacı ve B-Rep/parametrik geçmiş STL içinde korunmaz.

## Kaynak ve oturum güvenliği

Kaynak dosyalar kaydedilmez, yeniden adlandırılmaz veya silinmez. Araç kendi
açtığı modelleri sessiz/salt okunur açar ve yalnız bunları kapatır. Önceden
açık modeller kapatılmaz; konfigürasyon/seçim listesi, önceki aktif belge ve
değiştirilen STEP/STL/IGES tercihlerinin geri yüklemesi doğrulanır. Geri
yükleme başarısız olursa işlem durur ve açık hata gösterilir.

Her hedef önce aynı klasörde benzersiz geçici dosyaya yazılır; format
doğrulanınca atomik yayımlanır. Mevcut çıktılar varsayılan atlanır. Üzerine
yazma açıksa hatalı geçici çıktı mevcut doğru dosyanın yerini almaz.
Konfigürasyon/format klasörleri, temizlenen Windows adları ve gerektiğinde
kaynak/konfigürasyon kimliği sonekleri isim çakışmasını önler.

Tek dosya montaj aktarımında eksik/çözümlenemeyen referanslar engellenir.
Bileşen modunda okunabilir lightweight dosyalar ayrı açılır; bastırılmışlar
atlanan olarak raporlanır. Sanal parçalar bağımsız aktarım için önce
SolidWorks'te haricî dosyaya kaydedilmelidir. Eksik dosya, geçersiz referans
konfigürasyonu ve kimlik uyuşmazlıkları dosya bazında hatadır.

## Kod ve testler

- `formats.py`, `models.py`, `scanner.py`, `naming.py`: saf veri/dosya katmanı.
- `api.py`: COM yaşam döngüsü, kurulu swconst TLB, oturum/tercih koruması.
- `exporter.py`: sıra, konfigürasyon, tekilleştirme, iptal ve atomik çıktı.
- `validation.py`: STEP protokol/sonlandırma, IGES kayıt/sayaçları,
  STL tür/üçgen/koordinatlar, Parasolid başlık/şema/text-binary kontrolleri.
- `report.py`: atomik CSV ve XLSX; `ui.py`: uygulama içi ekran.

Yapısal kontrol tam geometrik eşdeğerlik, watertight mesh veya üretim
uygunluğu sertifikası değildir. Parasolid kontrolü tam kernel okuyucusu
değildir. Montaj yapısının korunması hedef format/çeviriciyle sınırlıdır.

```bash
QT_QPA_PLATFORM=offscreen python -m pytest modules/cad_converter/tests
python main.py
```

Gerçek SolidWorks testi Windows'ta isteğe bağlıdır:
`GOKWORKS_CAD_LIVE_SOURCE` bir test SLDPRT/SLDASM kopyasının mutlak yolu,
`GOKWORKS_CAD_LIVE_FORMATS` virgülle ayrılmış format anahtarları olmalıdır.
Varsayılan format step214'tür. Kullanıcı SolidWorks'ü önceden açmalıdır.
Çıktılar testin geçici klasörüne yazılır; bu test Linux'ta çalışmış sayılmaz.

[Uygulama/araştırma raporu](../../docs/CAD_CONVERTER_IMPLEMENTATION.md).
