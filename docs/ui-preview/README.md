# Güncel arayüz

**Mühendislik hesapları → Cıvata hesabı**. [Hesap ve kapsam](../bolt-calculator.md) · [Açık tema](../reports/bolt/screenshots/tension-light.png) · [Koyu tema](../reports/bolt/screenshots/combined-dark.png).

13 Ekim 2026. Product Design ile mevcut masaüstü arayüzü revize edildi.
Yedi çalışma alanı ortak başlık, simge, işlem alanı ve daha yumuşak kartlar
kullanır. Açık temada beyaz ve açık mavi yüzeyler, koyu temada katmanlı
lacivert yüzeyler vardır. Ana düğmeler, seçimler ve başarılı sonuçlar mavi
tonlarındadır. Menü seçimi 140 ms içinde yumuşakça değişir; içerik
hemen kullanılabilir. Görseller çalışan Tk uygulamasından alındı;
SolidWorks bağlantısı veya gerçek CAD çıktısı içermez.

- Temayla uyumlu sol menü, pencere kenarlarından ayrılmış yuvarlak bir paneldir.
- Her sayfanın başlığı simgesiyle gösterilir; işlem düğmeleri aynı bölgede durur.
- PDF/DXF klasör seçimleri numaralandırıldı; seçenekler ayrı başlıkta toplandı.
- Sayaçlar, başlıklar ve tablo satırları daha okunaklı hale getirildi.
- BOM'da toplam adet vurgulandı; seçili satır diğer alt montajlardan ayrıldı.
- Seçili BOM bileşeninin türü ayrıntı panelinde simgeyle gösterilir.
- Dar K/R alanında sayaç simgeleri kaldırılarak başlıklara yer açıldı.
- Ortak düğmelerin sert kenarlıkları kaldırıldı; giriş ve seçim alanları birleştirildi.
- K/R sekmeleri sadeleştirildi. Geçersiz giriş ilgili formda gösterilir;
  işlem hatasında günlük açılır ve **Günlüğü kopyala** düğmesi kullanılabilir.
- K/R'de BA ve numune ölçü alanları yalnız **BA ölçümü** seçildiğinde açılır.
  Yöntemler arasında geçişte ölçüler korunur. Hesap özeti ayrı bir karttadır.
- Manuel K/R ekranında tarama ve atama adımları iki kısa bilgi kartıyla anlatılır.
- EXE yalnız kullanıcı isteğiyle oluşturulur; otomatik derleme kapatıldı.

| Çalışma alanı | Açık tema | Koyu tema |
| --- | --- | --- |
| PDF | [Görüntü](screenshots/pdf-light.png) | [Görüntü](screenshots/pdf-dark.png) |
| DXF / DWG | [Görüntü](screenshots/dxf-dwg-light.png) | [Görüntü](screenshots/dxf-dwg-dark.png) |
| K/R · Takım | [Görüntü](screenshots/k-factor-light.png) | [Görüntü](screenshots/k-factor-dark.png) |
| K/R · Manuel | [Görüntü](screenshots/k-factor-manual-light.png) | [Görüntü](screenshots/k-factor-manual-dark.png) |
| K/R · BA ölçümü | [Görüntü](screenshots/k-factor-calibration-light.png) | [Görüntü](screenshots/k-factor-calibration-dark.png) |
| ISO geçmeleri | [Görüntü](screenshots/iso-fits-light.png) | [Görüntü](screenshots/iso-fits-dark.png) |
| Geometrik toleranslar | [Görüntü](screenshots/geometric-tolerances-light.png) | [Görüntü](screenshots/geometric-tolerances-dark.png) |
| BOM · Parça listesi | [Görüntü](../reports/bom/screenshots/bom-parts-light.png) | [Görüntü](../reports/bom/screenshots/bom-parts-dark.png) |
| BOM · ürün ağacı | [Görüntü](../reports/bom/screenshots/bom-tree-light.png) | [Görüntü](../reports/bom/screenshots/bom-tree-dark.png) |

## Açık tema · ISO geçmeleri

![ISO geçmeleri, açık tema](screenshots/iso-fits-light.png)

## Koyu tema · DXF / DWG

![DXF / DWG, koyu tema](screenshots/dxf-dwg-dark.png)

## BOM · ürün ağacı

![BOM, koyu tema](../reports/bom/screenshots/bom-tree-dark.png)

## Manuel K/R

![Kalınlığa göre manuel atama](screenshots/k-factor-manual-dark.png)

## Geometrik toleranslar

![Geometrik toleranslar](screenshots/geometric-tolerances-dark.png)

[1000 × 690 DXF ekranı](screenshots/dxf-dwg-dark-small.png) · [1000 × 690 manuel K/R](screenshots/k-factor-manual-dark-small.png).

Görüntülerin dosya özetleri ve çekim bilgileri [screenshots.json](screenshots.json) içindedir. Yeniden üretmek için çalışan sanal ekranda `docs/report-tools/capture_workspaces.py --output-dir docs/ui-preview` kullanılır. Bulutun Python 3.13 / Tk 8.6 ortamı düzgün kenarlı yazı görüntülemesi sağlar; Windows uygulaması Segoe UI kullanır.

Bu revizyonda **8 hedefli kontrol geçti**: farklı pencere/DPI yerleşimleri,
metin/zemin kontrastı, hızlı menü seçimi, BOM ve cıvata ekranı, K/R alanlarının
erişilebilirliği, ölçüm değerlerinin korunması ve tarama–uygulama akışı.
21 genel ekran, 7 BOM ve 3 cıvata ekranı yenilendi. Genel test paketi
çalıştırılmadı. [Kontrol çıktısı](product-design-checks.log).

Mavi/lacivert tema güncellemesinde metin kontrastı ve önbellekte tutulan
sayfaların tema/tablo renklerinin yenilenmesi için **2 hedefli kontrol
geçti**. Menü metninin açık temadaki kontrastı artırıldı. 31 ekran güncel
paletle yeniden çekildi; hesaplama testleri ve EXE derlemesi çalıştırılmadı.
[Tema kontrol çıktısı](blue-theme-checks.log).

K/R kontrollerinde alt COM nesnelerinin çıkış parametreleri düzeltildi;
programın kendi konfigürasyon değişikliği önceden kaydedilmemiş düzenleme
sayılmıyor. Windows/SolidWorks üzerinde kullanıcının montajı henüz
doğrulanmadı. [K/R düzeltmesinin kapsamı](../manual-k-radius.md#13-ekim-2026-çağrı-ve-hata-görünürlüğü-düzeltmesi).

[Türkçe metin denetimi ve doğrulama kayıtları](../reports/language-review/README.md).
