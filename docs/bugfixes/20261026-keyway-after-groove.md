# Segman sonrasında oluşmayan kama kesimi

Kaynak: `105a4f0766ae372764885a316b423f390fda6512`, dal `main`, çalışma dizini `/workspace/gokworks`.

## Gözlem ve kapsam

Kullanıcının son ekranında segman native kesmesi var; kama yardımcı düzlemi ve
kapsül eskizi var, `KAMA_KANALI_01` Cut unsuru yok. Uygulama native API'nin null
dönüşünü `Native feature failed` olarak bildiriyor. Bu, önceki segman API
hatasından farklı aşamadır. **Gerçek SolidWorks oturumu burada yoktur; null
sonucunun bütün CAD/kernel sebeplerinin kesin olarak bulunduğu iddia edilmez.**

## Uygulanan revizyon

- Kama, mil tabanından dışarı kesilmek yerine `CAP/2+1mm` dış düzleminden
  `DERINLIK+1mm` içeri kör kesilir. Bitiş tam `CAP/2-DERINLIK` olur.
- `FeatureCut4` varsayılan yönü eskiz normalinin tersidir. Her iki düzlem
  yönelimi için içeri kesme hesaplanır; belirsiz/NaN/sonsuz yön reddedilir.
- Eskiz orijininin dış kesme düzlemiyle uyuşması SI metre cinsinden denetlenir.
- `ISketch.CheckFeatureUse(CUTEXTRUDE)` başarılı, açık kontur 0 ve kapalı kontur
  1 olmalıdır. Ardından gerçek eskiz nesnesi 0 işaretiyle tek başına seçilir;
  isim çözümüne ve önceki segman seçimine dayanılmaz.
- Kesme kapsamı ve otomatik gövde seçimi açıktır; öncesinde tek katı gövde
  zorunludur. Yanlış yönde kör deneme veya sahte başarılı sonuç eklenmez.
- Hata artık kesme aşamasını, API'yi, çap/boy/genişlik/derinlik ve normal
  hizalamasını içerir. Başarısız yeni parça açık ve kaydedilmeden bırakılır.
- Sürücü denklemleri korunur: `KESME_Y=CAP/2+1mm`,
  `KESME_BOYU=DERINLIK+1mm`. Yeni yardımcı düzlem
  `KAMA_KANALI_01_KESME_DUZLEMI`; önceki kayıtlı parçalar değiştirilmez.
- Segman yolu ve pah/radyüs sırası değiştirilmedi. JSON `gokworks.shaft` v1,
  operasyon kimlikleri, plan ve Python/STA taşıma sözleşmesi aynı kaldı.

## Testler ve sınırları

Yerel mil paketi: **169 kayıt, 142 geçti, 27 atlandı, 0 hata/başarısızlık**.
Atlamalar 23 lisanslı CAD kabulü ve 4 Windows köprü testidir.
[Arşiv: JUnit](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/bugfixes/20261026-keyway-after-groove-tests.xml).

Host C# 5 / warnings-as-errors ile gerçek 2023 interop ve .NET 4.8
referanslarına karşı derlendi. Test probe'u da host ile birlikte derlendi.
Bu derleme bir CAD işlemi çalıştırmaz.

[Windows STA/köprü](https://github.com/gkkizil/gokworks/actions/runs/40359344689)
başarılıdır: gerçek PowerShell, gerçek arayüz sözleşmelerine proxy,
`CheckFeatureUse` ref sayıları ve seçim ret yolları, iki normal yönünde dıştan
tabana kesme mesafesi, API parametreleri, segman yolu ve başarısız parçayı
koruma. Test proxy'si bir CAD unsuru üretmiş gibi başarı döndürmez.

Son ekranın ölçüleri `reported_groove_keyway` canlı kabulüne eklendi:
Ø30×80, Ø45×65, Ø35×50, Ø25×35; ilk kademede segman; ikinci kademede başlangıç
5, toplam boy 60, genişlik 14, radyal derinlik 5,5 mm. Kapsül sağ omuzda biter;
boy sessizce kısaltılmaz. Gerçek native kesme, hacim, düzenlenebilir ölçüler,
kaydetme ve yeniden açma testi **bu ortamda çalıştırılmadı**.

[Windows BOM/arayüz](https://github.com/gkkizil/gokworks/actions/runs/40359344767):
94 kayıt, 0 hata/başarısızlık, 1 lisanslı CAD atlaması; başarılı.

11 korunan ortak dosyanın hash'leri aynı. Yedek depo ve `release` dalı
kullanılmadı. Windows GUI ve EXE doğrulama sonuçları makine özetine eklenir:
[doğrulama özeti](20261026-keyway-after-groove-checks.json).
