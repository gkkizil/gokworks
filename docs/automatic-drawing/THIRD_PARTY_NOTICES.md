# Araştırılan kaynaklar ve lisanslar

Araştırma tarihi: 15 Kasım 2026.

Yeni modüle aşağıdaki depolardan kaynak kodu kopyalanmadı veya
FreeCAD binary / runtime bağımlılığı eklenmedi. Görünüş / yerleşim ve
SolidWorks kullanım yaklaşımları incelenip uygulamaya uygun kod bağımsız
geliştirildi. Mevcut GOKWORKS COM yardımcılarının mevcut lisans bildirimleri
korunur.

| Kaynak | İncelenen lisans / telif | Uygulama kararı |
|---|---|---|
| andrewbartels1/SolidworksMCP-python | MIT; Copyright (c) 2025 ESPO Corporation | Yöntem araştırması; MCP veya kaynak kodu eklenmedi |
| BLAZE-TAN/sw-drawings | MIT; Copyright (c) 2019 Paine-Zeng | Dosyalar doğrulandı; sorunlu örnek çağrılar kopyalanmadı |
| xarial/codestack | MIT; Copyright (c) 2025 Xarial Pty Limited | API örnekleri araştırıldı; mevcut proje bildirimleri korundu |
| xarial/xcad | MIT; Copyright (c) 2025 Xarial Pty Limited | Dual interface / görünüş yaklaşımı araştırıldı; .NET eklenmedi |
| kilwizac/solidworks-automate-drawing | İncelenen ağaçta lisans dosyası bulunmadı | Algoritma fikri araştırıldı; kod alınmadı |
| RylanLN/SolidWorks-Automation-Tool | İncelenen ağaçta lisans dosyası bulunmadı | Toplu işlem yaklaşımı araştırıldı; kod alınmadı |
| FreeCAD TechDraw DrawProjGroup.cpp | Dosya başlığı: GNU Library GPL v2 veya sonrası; Luke Parry / Joe Dowsett | Yalnız algoritma araştırması; kod / bağlantı / backend eklenmedi |

Kaynak dosyalar ve sabit referanslar [araştırma raporunda](RESEARCH.md).
Bu belge söz konusu depoların kodunun yeniden dağıtımı anlamına gelmez.

PDF önizlemesi mevcut PySide6 6.10.3 içindeki Qt PDF / PDF Widgets
modüllerini kullanır. Qt’nin bu sürümdeki kaynak başlığında LGPL-3.0-only
seçeneği doğrulandı. Kod değiştirilmedi. Eşleşen PDFium snapshot’ının
lisansı
[QtPdf-PDFium-LICENSE.txt](../../packaging/licenses/automatic-drawing/QtPdf-PDFium-LICENSE.txt)
ile, diğer bileşen bildirimleri aynı klasörde korunur.
[Kaynak kaydı](../../packaging/licenses/automatic-drawing/QtPdf-NOTICE.txt) ve
[tam kaynak URL’leri](../../packaging/licenses/automatic-drawing/source-inventory.json)
paketlemeye dahil edildi.
