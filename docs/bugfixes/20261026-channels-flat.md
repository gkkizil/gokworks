# 26 Ekim 2026 · Kanal, çift pah ve açınım hata düzeltmeleri

Kapsam: kullanıcının bildirdiği segman eskizi sonrası kesme hatası, kama
taban/orijin hatası, aynı kademeye sol/sağ pah ekleme ve DXF/DWG açınım
önizlemesindeki `PyIDispatch.ActiveDoc` hatası. Geliştirme `main` üzerindedir.

## Değişiklikler

- `modules/shaft_generator/interop/ShaftHost.cs`: kama taban konumu mm'den
  metreye çevrilir. Ø30 / 3 mm örneğinde dönüşüme 12 yerine 0,012 m girer.
  Segman eskizi ve construction ekseni isim çözümlemesi yerine kendi native
  nesneleriyle seçilir; işaretler 0/16 ve seçim adetleri doğrulanır. Kesme
  başarısızsa yeni parça kapatılmaz/kaydedilmez, inceleme için açık kalır.
  Başarısız JSON'a geriye uyumlu `partial_document` alanı eklenir.
- `modules/shaft_generator/ui.py`: pah/radyüs ekledikten sonra form yeni
  kayıt modunda kalır. Diğer kenarı seçmek önceki operasyonu taşımaz. Listede
  Sol/Sağ ve mm ölçüsü görünür. Aynı kenara yinelenen kayıt eklenmez; gerçek
  geometrik çakışma denetimleri korunur. Listeden seçilen mevcut kayıt canlı
  olarak düzenlenmeye devam eder.
- `modules/dxf_dwg/exporter.py`: ham `PyIDispatch` da `DumbDispatch` ile
  sarılır. Önizleme ve eski exporter aynı bağlantıyı kullanır; yeni SolidWorks
  örneği başlatılmaz. BYREF, çıktı yayımlama ve belge geri yükleme değişmez.

Testler `modules/shaft_generator/tests/{test_channel_selection.py,
native/ChannelProbe.cs,test_ui.py,test_live.py}` ve
`modules/dxf_dwg/tests/{test_dxf_dwg.py,test_preview_source.py}` içindedir.
İki modülün README dosyaları güncellendi. Windows shaft bridge iş akışı
`main` üzerindeki mil değişikliklerinde de çalışır ve yeni native proxy
testini içerir; bu iş akışı EXE derlemez/yayınlamaz.

## Doğrulama

- İlgili iki modülün Linux koşusu: **358 JUnit kaydı, 0 hata, 24 atlama**.
  [Arşiv: JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261026-channels-flat-tests.xml). Qt testleri offscreen, COM sınırı
  test çiftiyle çalışır. Native Windows ve lisanslı CAD atlamaları başarı
  sayılmaz. Örtüşen hedefli koşuların sayıları bu toplama eklenmez.
- Gerçek SOLIDWORKS 2023 interop / .NET Framework 4.8 referanslarıyla host ve
  native test fixture'ı C# 5 / warnings-as-errors ile derlendi. Bu Linux
  derlemesi COM sunucusu veya Windows kabulü değildir.
- Üretimde kullanılan `KeywayFloorMetres` yordamı .NET 8 altında Ø10, Ø30 ve
  Ø100 örneklerinde doğrudan çalıştırıldı; metre sonuçları bağımsız sabit
  değerlerle karşılaştırıldı.
- Açınım regresyonu `export_one_part` yordamını mock'lamaz: ham dispatch
  üzerinden gerçek Python exporter akışına girer, geçici DXF'yi yazıp okur,
  dosyayı temizler, önceki aktif belgeyi ve mevcut DWG'yi korur. CAD sunucusu
  test çiftidir. Bu, kullanıcıdaki ham COM sınırı hatasını kapsar.
- Yeni Qt regresyonu sol ve sağ pah/radyüsün ayrı tutulmasını, liste
  etiketlerini, yinelenen kenarın reddini ve mevcut kayıt düzenlemesini kapsar.
- Ruff F821/F822/F823 ve `git diff --check` geçti. Ortak 11 dosyanın içerikleri
  [aynen korunmuştur](20261026-protected-check.json).
- Windows PowerShell 5.1 / STA kontrolü de
  [`4a74a28` kaynak sürümünde geçti](https://github.com/gkkizil/gokworks/actions/runs/40319360525):
  gerçek host derlemesi, kayıtlı sınıf/ROT bağlantı testi, kesme API argüman ve
  hacim denetimleri, yeni eksen/eskiz seçimleri, metre dönüşümü ve kısmi
  belgeyi koruma testi. Bu testler SolidWorks uygulamasını çalıştırmaz.
  [Windows kontrol kaydı](20261026-windows-channel-checks.json).
  İlk iki Windows denemesinde yeni test yardımcısı PowerShell'in `GetType`
  adaptörüne takıldı; test proxy'leri C# içinde tutularak düzeltildi. Son
  başarılı koşu önceki başarısız denemelerin yerine geçen doğrulamadır.

## Gerçek CAD kabulü ve sınırlar

Lisanslı SOLIDWORKS bu ortamda yok. Segman kesiminin CAD çekirdeğindeki
başarısı, kama kesiminin hacmi ve çift pahın native sonucu gerçek oturumda
henüz doğrulanmadı. `test_live.py` içinde tek/çift segman, kama, sıfır ofset
ve iki uç pahı için ayrı kabul senaryoları bulunur. Çift pah için silindirden
çıkarılan hacim bağımsız analitik formülle denetlenir.

```powershell
python -m pytest modules/shaft_generator/tests modules/dxf_dwg/tests
$env:GOKWORKS_SHAFT_LIVE='1'
python -m pytest modules/shaft_generator/tests/test_live.py -v
```

Canlı testler yalnız yeni test parçaları oluşturur; geçerli varsayılan Part
şablonu ve açık/lisanslı SOLIDWORKS gerekir. Hata halinde kısmi test parçası
açık bırakılır. Önceki EXE bu kaynak düzeltmelerini içermez; bu görev için
yeni EXE yayımlama isteği oluşturulmadı. `release`, yedek depo, ortak bağlantı,
worker ve paketleme betiği değiştirilmedi. Önceki başka ajan çalışmaları
üzerine yazılmadı; mil değişiklikleri bu dört yeni hata bildirimi kapsamındadır.
