# BOM - ürün ağacı: güncel arayüz ve Excel örneği

> Eski Tk arayüzü için verilen görsel/rapor komutları tarihîdir. Bu betikler ve
> üretilmiş görseller güncel daldan kaldırılmıştır; yeniden incelemek için
> [temizlik öncesi sürümü](https://github.com/gkkizil/gokworks/tree/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9) kullanın.

[Arşiv: Örnek Excel’i indir](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/bom/ORNEK_BOM_URUN_AGACI.xlsx). Bu dosya sentetik bir
ANA-MONTAJ içerir: iki ÖRNEK-M001 örneğinin her birinde P-002 ve bir iç
ÖRNEK-M002 → P-010 dalı vardır. Toplu listede P-002 ve P-010 adetleri 2'şer,
ağaçta iki ayrı ÖRNEK-M001 dalı görünür. Gerçek kullanıcı montajı okunmadı.

| Görünüm | Açık tema | Koyu tema |
| --- | --- | --- |
| Toplu parça listesi | [Arşiv: Görsel](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/bom/screenshots/bom-parts-light.png) | [Arşiv: Görsel](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/bom/screenshots/bom-parts-dark.png) |
| Alt montaj ürün ağacı | [Arşiv: Görsel](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/bom/screenshots/bom-tree-light.png) | [Arşiv: Görsel](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/bom/screenshots/bom-tree-dark.png) |

[Arşiv: Küçük pencere (1000×690)](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/bom/screenshots/bom-tree-dark-small.png) ·
[Arşiv: %125 ölçek](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/bom/screenshots/bom-tree-dark-125pct.png) ·
[Arşiv: Tarama öncesi](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/bom/screenshots/bom-parts-light-empty.png)

Yeni arayüz montaj/konfigürasyon kartı, üç adet özeti, belirgin sekmeler,
arama çubuğu, yeşil alt montaj adları ve tüm dalları açma/kapatma kontrolleri
içerir. Dosya yolu seçili satır paneline taşındı. Küçük pencerede **Ayrıntılar**
düğmesi aynı bilgilere erişim sağlar. Açık ve koyu temalar desteklenir.
Kısa pencerelerde başlık ve adet kartları sıkıştırılarak tabloya daha fazla
alan ayrılır. Ayrıntı penceresindeki kopyalama düğmesi, arka plandaki seçim
değişse bile pencerede gösterilen parçanın yolunu kopyalar. Seçim kaldırılınca
eski ayrıntılar temizlenir; tarama hatası ve iptal üst kartta da belirtilir.

13 Ekim tasarımında lacivert sol menü, ayrı içerik kartları, vurgulu toplam
adet kartı ve bileşen simgeli ayrıntı paneli eklendi. Seçim rengi yalnız
seçili satıra uygulanır; diğer alt montajlar yazı rengiyle ayrılır.
Bu değişiklikte BOM'un yerleşim/ölçek, seçim/dal ve tarama–Excel akışına
yönelik üç arayüz kontrolü geçti. Ortak tasarımın dört arayüz kontrolüyle
birlikte toplam yedi kontrol çalıştırıldı.

Görseller gerçek Tk penceresinden, sentetik montaj verileriyle alındı.
Kaynak ve checksum bilgileri `references.json` ve `screenshots.json` içindedir.

2026-10-12 arayüz değişikliği için yalnız BOM'a özel kontroller çalıştırıldı;
genel test paketi yeniden çalıştırılmadı.

- `test_bom_window`: **9 geçti**. Gerçek Tk penceresinde tarama/Excel akışı,
  önizleme aramasının Excel'i filtrelememesi, seçim/ayrıntılar/yol kopyalama,
  alt montaj dallarını açma/kapatma, boş arama sonucu, sayılar, sayfa önbelleği,
  temalar, küçük pencere, %125 ölçek, iptal ve hatada önceki dosyanın korunması.
  Açık ayrıntı penceresinde seçim değişimi ve gizli sekmeden gelen seçim
  olayları da kontrol edildi.
- Görselleri yeniden üretmek için: `PYTHONPATH=.:tests python docs/report-tools/capture_bom_gui.py`
  (Tk ekranı gerekir; bulutta `DISPLAY=:99`).
- `git diff --check` geçti.
- Windows/SolidWorks 2025'te gerçek montaj kabulü bekleniyor:
  [kullanım ve yerel kontrol](../../bom.md).
