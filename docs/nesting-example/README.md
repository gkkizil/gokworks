# Gerçek DXF ile uçtan uca örnek

Bu klasördeki parçalar `docs/report-tools/capture_nesting.py` ile gerçek
DXF geometrisi olarak oluşturuldu, uygulamanın DXF okuyucusuyla içe alındı
ve normal GOKWORKS NFP motoruyla yerleştirildi. Ekrana veya rapora yerleşim
sonucu elle yazılmadı.

- `input/`: içbükey L, delikli levha ve yaylı/delikli üç kaynak DXF.
- `Ornek.goknest.json`: geometrileri gömülü 22 parçalık taşınabilir proje.
- `DXF/`: doğrulanmış bir levha ve kesim/kerf notları.
- `Nesting.xlsx`, `Nesting.pdf`: gerçek hesap tablosu ve levha çizimi.
- `nesting-dark-1440.png`, `nesting-light-1440.png`, `nesting-dark-1024.png`:
  entegre arayüzün iki tema/genişlik düzeni.
- `checks.json`: çalıştırmanın sayısal özeti.

600×400×2 mm S235JR, 7850 kg/m³, 45 TL/kg:
brüt **3,768 kg**, net yaklaşık **2,11533 kg**, fire **1,65267 kg**,
verim **%56,1394**, malzeme bedeli **169,56 TL**.
Bu bir yazılım doğrulama örneğidir; CAM takım yolu programı değildir.
