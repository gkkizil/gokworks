# GOKWORKS modülleri

Her özellik bu klasörde kendi Python paketi altında bulunur. Bir özelliği
geliştirmek için hesaplama/CAD kodu, `ui.py` arayüzü, `tests/` testleri ve
varsa `examples/` örnekleri aynı klasördedir. Hesap motorları arayüzü başlatmaz.

| Uygulamadaki modül | Klasör | Arayüz |
| --- | --- | --- |
| PDF aktarımı | [pdf](pdf) | [ui.py](pdf/ui.py) |
| DXF / DWG | [dxf_dwg](dxf_dwg) | [ui.py](dxf_dwg/ui.py) |
| BOM · Ürün ağacı | [bom](bom) | [ui.py](bom/ui.py) |
| İsimlendirme / Pack and Go | [naming](naming) | [ui.py](naming/ui.py) |
| K faktörü / yarıçap | [k_factor](k_factor) | [ui.py](k_factor/ui.py) |
| ISO geçme toleransları | [iso_fits](iso_fits) | [ui.py](iso_fits/ui.py) |
| Geometrik toleranslar | [geometric_tolerances](geometric_tolerances) | [ui.py](geometric_tolerances/ui.py) |
| Tolerans yığılması | [tolerance_stack](tolerance_stack) | [ui.py](tolerance_stack/ui.py) |
| Cıvata hesabı | [bolt](bolt) | [ui.py](bolt/ui.py) |
| Hızlı tork hesabı | [bolt_torque](bolt_torque) | [ui.py](bolt_torque/ui.py) |
| Ağırlık hesabı | [weight](weight) | [ui.py](weight/ui.py) |
| Nesting · Sac maliyeti | [nesting](nesting) | [ui.py](nesting/ui.py) |

Örnek düzen:

```text
modules/bolt_torque/
├── __init__.py
├── README.md
├── rules.py       # Arayüzden bağımsız hesap
├── ui.py          # Qt ekranı
├── diagram.py     # Modüle ait kesit çizimi
├── examples/      # Görseller ve örnek çıktılar
└── tests/         # Sayısal ve arayüz testleri
```

Tek modülü test etmek için depo kökünde:

```bash
python -m pytest modules/bolt_torque/tests
```

Tüm uygulama: `python main.py`. Tüm testler: `python -m pytest`.
[Ortak altyapı ve taşıma rehberi](../docs/repository-structure.md).
