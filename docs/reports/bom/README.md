# BOM - Ürün ağacı: güncel arayüz ve Excel örneği

[Örnek Excel’i indir](ORNEK_BOM_URUN_AGACI.xlsx). Bu dosya sentetik bir
ANA-MONTAJ içerir: iki ÖRNEK-M001 örneğinin her birinde P-002 ve bir iç
ÖRNEK-M002 → P-010 dalı vardır. Toplu listede P-002 ve P-010 adetleri 2'şer,
ağaçta iki ayrı ÖRNEK-M001 dalı görünür. Gerçek kullanıcı montajı okunmadı.

| Görünüm | Açık tema | Koyu tema |
| --- | --- | --- |
| Toplu parça listesi | [Görsel](screenshots/bom-parts-light.png) | [Görsel](screenshots/bom-parts-dark.png) |
| Alt montaj ürün ağacı | [Görsel](screenshots/bom-tree-light.png) | [Görsel](screenshots/bom-tree-dark.png) |

[Küçük pencere (1000×690)](screenshots/bom-tree-dark-small.png) ·
[%125 ölçek](screenshots/bom-tree-dark-125pct.png) ·
[Tarama öncesi](screenshots/bom-parts-light-empty.png)

Yeni arayüz montaj/konfigürasyon kartı, üç adet özeti, belirgin sekmeler,
arama çubuğu, yeşil alt montaj satırları ve tüm dalları açma/kapatma kontrolleri
içerir. Dosya yolu seçili satır paneline taşındı. Küçük pencerede **Ayrıntılar**
düğmesi aynı bilgilere erişim sağlar. Açık ve koyu temalar desteklenir.

Görseller gerçek Tk penceresinden, sentetik montaj verileriyle alındı.
Kaynak ve checksum bilgileri `references.json` ve `screenshots.json` içindedir.

2026-10-12 arayüz değişikliği için yalnız BOM'a özel kontroller çalıştırıldı;
genel test paketi yeniden çalıştırılmadı.

- `test_bom_window`: **8 geçti**. Gerçek Tk penceresinde tarama/Excel akışı,
  önizleme aramasının Excel'i filtrelememesi, seçim/ayrıntılar/yol kopyalama,
  alt montaj dallarını açma/kapatma, boş arama sonucu, sayılar, sayfa önbelleği,
  temalar, küçük pencere, %125 ölçek, iptal ve hatada önceki dosyanın korunması.
- Görselleri yeniden üretmek için: `PYTHONPATH=.:tests python docs/report-tools/capture_bom_gui.py`
  (Tk ekranı gerekir; bulutta `DISPLAY=:99`).
- `git diff --check` geçti.
- Windows/SolidWorks 2025'te gerçek montaj kabulü bekleniyor:
  [kullanım ve yerel kontrol](../../bom.md).
