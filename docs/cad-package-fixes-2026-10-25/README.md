# Pack and Go önizlemesi ve 3D aktarım düzeltmeleri — 25 Ekim 2026

## Pack and Go / İsimlendirme aracı

Ekranda “Dosyalar okundu” yazarken tablonun boş kalması yeniden üretildi.
`NamingPage.prepare_plan`, kaynak satırlarını oluşturmadan önce hedef
klasörün boşluğunu kontrol ediyordu. Dolu, seçilmemiş veya geçersiz bir
hedefte hata olayı satır içermediğinden ilk tarama hiç görüntülenemiyordu.
Sonraki hatalı önizlemelerde önceki kaynağın satırları da kalabiliyordu.

Satırlar artık önce kaynak snapshot'ından oluşturulur. Geçersiz hedefte
de montaj, alt montaj, parça, ortak dosya ve teknik resim kayıtları tutulur.
Geçerli isimlendirme kuralları varsa önerilen adlar gösterilir ve elle
düzenlenebilir. Hedef seçilmemişse veya ad kuralı geçersizse kaynak adları
görünür kalır. Hedef düzeltildiğinde yeniden CAD taraması gerekmez.

Paket oluşturma; boş/yeni hedef, geçerli adlar ve güncel önizleme gerektirir.
Kaynakların veya dolu hedefin üzerine yazılmaz. Yeni API taraması
başarısız olduğunda önceki montaj kaydedilebilir durumda bırakılmaz.
Hata hem önizleme altında hem durum çubuğunda gösterilir.

`GetPackAndGo`, `GetDocumentNames`, `GetDocumentNamesCount`,
`GetDocumentSaveToNames`, `SetDocumentSaveToNames`, `SetSaveToName` ve
`SavePackAndGo` imzaları interop metadata üzerinden tekrar incelendi.
Mevcut BYREF/typed bridge yolu, Pack and Go belge sırası, kaynak sahipliği
ve yeni dosya referanslarını geri okuma kontrolleri korunur. Bu hata için
API listesini dosya sistemi tahminiyle değiştirmek gerekmemiştir.

[Arşiv: Dolu hedefte de görünen gerçek Qt önizlemesi](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/cad-package-fixes-2026-10-25/preview-with-invalid-destination.png)

Görsel sentetik snapshot ile çalışan gerçek Qt ekranıdır; canlı CAD
taramasının veya gerçek montaj paketinin doğrulaması değildir.

## 3D dönüştürücü

`ISldWorks.SetUserPreferenceToggle` **void** döner. Önceki kod `None`
değerini başarısızlık sayıyordu; bu hem aktarımı engelliyor hem de 403
(`swStepExportConfigurationData`) geri yükleme hatasıyla kuyruğu durduruyordu.
Toggle uygulama/geri yükleme artık geri okunan değerle doğrulanır. Sayısal
setter'ların Boolean sonuçları kontrol edilmeye devam eder. Gerçek geri
yükleme uyuşmazlığı hâlâ tüm kuyruğu durdurur; geçici çıktı yayımlanmaz.
STEP, IGES ve STL yolları aynı düzeltmeden yararlanır.

Eksik eski STEP/IGES/Parasolid/ACIS kaynağına bağlı yerel parçalarda,
`IPartDoc.GetBodies2` ile görünür/gizli katı ve yüzey gövdeleri kontrol
edilir; `IBody2.GetType` ve pozitif `GetFaceCount` gerekir. Uygun geometri
varsa mevcut parça geometrisi **uyarılı** olarak aktarılır. Dış kaynağın
güncelliğinin doğrulanmadığı sonuç/raporda açıkça belirtilir.
Boş/mesh/grafik parçalar, bilinmeyen veya eksik native CAD referansları
ve tek dosya montaj aktarımı bu istisnadan yararlanmaz. Kaynak bağlantıları
koparılmaz ve CAD kaynakları kaydedilmez. Bu kontrol geometri bütünlüğü
veya kaynak STEP ile geometrik eşdeğerlik sertifikası değildir.

## Doğrulama

- Yeni ilk 34 regresyonun 23'ü eski kodda başarısızdı; düzeltmeden sonra geçti.
  Sonradan eklenen başarısız yeniden tarama kontrolüyle yeni toplam 35'tir.
- CAD dönüştürücü, isimlendirme ve Qt iş akışları için 342 pytest item toplandı.
  unittest alt durumları dahil JUnit kaydı: 365 kontrol, 0 hata/başarısızlık,
  3 atlanan platform/canlı API kontrolü. Ek yeniden tarama testi ayrıca geçti.
- Önceki Weldments düzeltmesi için 49 API/tarama/graf regresyonu geçti.
- Uygulama öz denetimi: 14 modül, iki tema, çözünürlük matrisi ve yerel
  hesap/rapor kontrolleri geçti. Gerçek Qt önizlemesi görsel olarak incelendi.
- Değişen Python kaynaklarında tanımsız isim kontrolü ve `git diff --check` geçti.

[API metadata kaydı](api-contract.json), [Arşiv: yeni regresyonlar](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/cad-package-fixes-2026-10-25/regressions.xml),
[Arşiv: toplu test kaydı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/cad-package-fixes-2026-10-25/related-tests.xml), [özet](checks.json).
Interop DLL incelemesi referanstır; DLL uygulamaya eklenmedi ve yeni runtime
bağımlılığı yoktur. Buradaki test koşuları Linux/PySide6 offscreen üzerindedir;
betik adındaki `windows` yerel Windows veya SolidWorks çalıştırıldığı anlamına
gelmez. Gerçek Windows/SolidWorks oturumunda montaj paketleme ve sorunlu
ithal parçaların geometrik çıktısı ayrıca denenmelidir.

Yerelde `main` güncellendikten sonra mevcut ortamla `python main.py` çalıştırılır.
Bu kaynak güncellemesi için yeni EXE talebi oluşturulmamıştır.
