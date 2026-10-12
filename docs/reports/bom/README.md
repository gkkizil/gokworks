# BOM-ÜRÜN AĞACI örneği ve doğrulaması

[Örnek Excel’i indir](ORNEK_BOM_URUN_AGACI.xlsx). Bu dosya sentetik bir
ANA-MONTAJ içerir: iki ÖRNEK-M001 örneğinin her birinde P-002 ve bir iç
ÖRNEK-M002 → P-010 dalı vardır. Toplu listede P-002 ve P-010 adetleri 2'şer,
ağaçta iki ayrı ÖRNEK-M001 dalı görünür. Gerçek kullanıcı montajı okunmadı.

| Görünüm | Açık tema | Koyu tema |
| --- | --- | --- |
| Toplu parça listesi | [Görsel](screenshots/bom-parts-light.png) | [Görsel](screenshots/bom-parts-dark.png) |
| Alt montaj ürün ağacı | [Görsel](screenshots/bom-tree-light.png) | [Görsel](screenshots/bom-tree-dark.png) |

Görseller gerçek Tk penceresinden, sentetik montaj verileriyle alındı.
Kaynak ve checksum bilgileri `references.json` ve `screenshots.json` içindedir.

- Tam regresyon: **374 geçti**, 0 başarısız, 0 hata, 0 atlanan; 175.079 saniye.
- BOM ve menü hedefli doğrulaması: **28 geçti**.
- Dosya + konfigürasyon birleştirme, doğal ad sırası, tekrarlanan/iç içe alt
  montajlar, bastırma/BOM dışı filtreleri, iptal ve hatada tam sonuç koşulu
  test edildi. Excel, openpyxl ile yeniden açılarak sayısal adetler, sıra,
  üst/alt ilişkileri, girintiler ve satır grupları kontrol edildi.
- Gerçek Tk testlerinde tarama/Excel düğmeleri, arama, sekme durumu, temalar,
  küçük pencere, %125 ölçek, iptal ve işlem sürerken kapanış doğrulandı.
- Bağımlılık kontrolü, kaynak derleme ve `git diff --check` geçti.
- Windows/SolidWorks 2025'te gerçek montaj kabulü bekleniyor:
  [kullanım ve yerel kontrol](../../bom.md).
