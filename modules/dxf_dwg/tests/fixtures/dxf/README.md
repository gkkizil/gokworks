# DXF doğrulama örnekleri

Bu dört dosya `ezdxf==1.4.3` ile yerel olarak oluşturuldu; SolidWorks çıktısı değildir. Kaynak: [mozman/ezdxf v1.4.3](https://github.com/mozman/ezdxf/tree/df5ef277fcc674d77580143212ec63dd981cc2b3).

Her dosyanın model alanında dört LINE ile çizilmiş 120×80 dikdörtgen, (20,20) merkezli 5 yarıçaplı CIRCLE ve (90,30) merkezli 10 yarıçaplı, 0–90° ARC bulunur. R2018 dosyalarında `$INSUNITS=4` (mm) kullanılır; R12 bu başlık değişkenini desteklemez. ASCII/ikili R12 ve R2018 dosyaları aynı altı nesneyi içerir. `readfile()` ve `audit()` ile dördü de sıfır hata/onarım verdi.

Bu örnekler eski/yeni sürümlerin metin ve ikili kodlamasının kabul edildiğini sınar. Bozuk ve kesilmiş dosya testleri geçici dizinde ayrı üretilir. Gerçek parça açınımının ölçülerini veya SolidWorks COM davranışını kanıtlamaz.

Yeniden üretme (proje kökünden, yalnızca örnek dosyaları değiştirmek için):

```python
from pathlib import Path
import ezdxf

folder = Path("tests/fixtures/dxf")
for version, name in (("R12", "r12"), ("R2018", "r2018")):
    for fmt in ("asc", "bin"):
        document = ezdxf.new(version)
        if version != "R12":
            document.units = 4
        model = document.modelspace()
        corners = ((0, 0), (120, 0), (120, 80), (0, 80))
        for start, end in zip(corners, corners[1:] + corners[:1]):
            model.add_line(start, end)
        model.add_circle((20, 20), 5)
        model.add_arc((90, 30), 10, 0, 90)
        document.saveas(folder / f"plate-{name}-{fmt}.dxf", fmt=fmt)
```
