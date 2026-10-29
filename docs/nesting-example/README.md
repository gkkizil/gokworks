# Gerçek DXF ile uçtan uca örnek

Bu klasördeki parçalar `docs/report-tools/capture_nesting.py` ile gerçek
DXF geometrisi olarak oluşturuldu, uygulamanın DXF okuyucusuyla içe alındı
ve normal GOKWORKS NFP motoruyla yerleştirildi. Ekrana veya rapora yerleşim
sonucu elle yazılmadı.

- `input/`: içbükey L, delikli levha ve yaylı/delikli üç kaynak DXF.
- `Ornek.goknest.json`: geometrileri gömülü 22 parçalık taşınabilir proje.
- `DXF/`: doğrulanmış bir levha ve kesim/kerf notları.
- `checks.json`: çalıştırmanın sayısal özeti.

Üretilen ekran görüntüleri ve PDF/Excel çıktıları güncel dalda tutulmaz.
Gerektiğinde [örneği üreten Qt betiği](../report-tools/capture_nesting.py)
ile yeniden oluşturulabilir. DXF girdileri ve gömülü proje, uygulama ve
testlerin kullandığı gerçek örnekler olarak korunur.

600×400×2 mm S235JR, 7850 kg/m³, 45 TL/kg:
brüt **3,768 kg**, net yaklaşık **2,11533 kg**, fire **1,65267 kg**,
verim **%56,1394**, malzeme bedeli **169,56 TL**.
Bu bir yazılım doğrulama örneğidir; CAM takım yolu programı değildir.
