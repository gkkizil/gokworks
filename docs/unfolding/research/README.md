# Sac açınımı depoları: sabit kaynaklar ve seçim

6 Kasım 2026. Yalnız sac açınımı, kazan/kanal parçası açınımı ve bükümlü
sacın açılmasıyla ilgili sekiz depo çekildi. Genel CAD, nesting veya
papercraft motoru bu taramaya katılmadı. Ayrı checkout'lar
`/workspace/research/sheet-unfolding/` altındadır; uygulamaya sekiz depo
veya ikinci bir hesap motoru gömülmedi.

Commit, tarih, incelenen dosyaların SHA-256'ları, gerçek lisans metni/header
ayrımları ve kullanım kararı [references.json](references.json) içindedir.
GitHub API bu ortamda 403 verdi; izinli GitHub HTML araması ve HTTPS Git
clone çalıştı. Tarihler sabitlenen commit'in tarihidir, bakım garantisi değildir.

| Depo | Gerçek kapsam | Karar |
|---|---|---|
| [FreeCAD SheetMetal](https://github.com/shaise/FreeCAD_SheetMetal) | Düzlem/silindir yüzlerinin komşuluk grafiği, spanning tree, UV açma, K tabloları | İncelendi; FreeCAD/Part/TechDraw/NetworkX motoru taşınmadı |
| [YouCanNotUnfold](https://github.com/alexneufeld/YouCanNotUnfold) | Yeni FreeCAD unfolder'ının deneysel kaynağı; upstream'e entegre edilmiş | Ayrı bağımsız katalog motoru sayılmadı; kopyalanmadı |
| [SheetMetalCone](https://github.com/quirxi/SheetMetalCone) | Inkscape koni/kesik koni SVG açınımı | Analitik yöntem karşılaştırıldı; inkex çalışma bağımlılığı eklenmedi |
| [sheet_ufo](https://github.com/ulrich1a/sheet_ufo) | Eski FreeCAD yüz ağacı ve lazer profili | Kaynak header GPL-2.0-or-later; kod alınmadı |
| [Desarrolla](https://github.com/neferpi/desarrolla) | Dört fitting: silindir, koni, dirsek, kare–yuvarlak MVP | MIT; kritik kenar koruma kontrolünden sonra geometri alınmadı |
| [Gusset](https://github.com/Bas-Automation-Services/gusset) | Özellik tabanlı sac katı/B-Rep, büküm tabloları, relief/clash | MPL-2.0; Rust/OpenGeometry ayrı motor, mevcut 191 modele takılabilir bir alternatif değil |
| [unfolding_of_sheet_metal](https://github.com/IgorAgarkov/unfolding_of_sheet_metal) | Sabit ölçülü tek dikdörtgen–yuvarlak betiği | Lisans izni doğrulanamadı; kod alınmadı/çalıştırılmadı |
| [sheet-metal-unfold](https://github.com/hermes98761234/sheet-metal-unfold) | Flanş ölçü türleri, büküm bölgeleri, numuneden K kalibrasyonu | **MIT matematik yordamları Python'a uyarlandı** |

## Alınan gerçek katkı

`src/lib/bend.ts`, commit
`2ad13f96ba83fb0e20a7b0c7f3bc201b8ef1b540` temelinde
`core/unfolding/bend_profiles.py` eklendi. Telif ve MIT metni
`packaging/licenses/unfolding/sheet-metal-unfold-MIT.txt` altında korunur ve
mevcut lisans paketleme mekanizmasıyla dağıtılır.

- İç/dış sanal keskin köşeye kadar ölçü ile teğetten teğete düz boy ayrılır.
- Büküm payı, iç/dış setback, deduction, gerçek düz boy ve büküm bölgesi
  ortasındaki çizgi konumu hesaplanır.
- Her bükümün kendi R/K değeri ve işaretli dönüş açısı olabilir.
- Ölçülmüş tek büküm numunesinden K geri bulunur; uygunsuz ölçüm makul
  görünen bir katsayıya kırpılmaz.
- Python uyarlaması değişmez sonuçlar, sonlu sayı/tür denetimi ve komşu
  bükümlere yetmeyen flanşın açık hatayla reddedilmesini ekler.

```python
from core.unfolding.bend_profiles import BendInput, develop_profile, calibrate_k

r = develop_profile((20, 50, 20),
    (BendInput(90, 2, .4), BendInput(-90, 2, .4)),
    2, dimension_reference='outside')
assert abs(r.flat_length_mm - 82.79645943005141) < 1e-9
k = calibrate_k(40, 60, 96.67842872136355, 90, 3, 1.5)  # 0.41
```

Bu, bağımsız bir **1D bükümlü flanş hesabıdır**. Mevcut fitting'lerin geometrik
orta yüzeyine otomatik K/abkant telafisi eklemez; arayüz düğmesi veya serbest
B-Rep açma özelliği sunmaz. Malzeme K tablosu, varsayılan dayanım ve V kalıp
seçim sezgileri aktarılmadı. Tek numune farklı malzeme/kalınlık/takım için
proses doğrulaması değildir. Kullanıcı K'sı açık girdidir.

## Sayısal karşılaştırma ve reddedilen yöntemler

[comparison_results.json](comparison_results.json) ve tekrar üretilebilir
[verify_upstream.py](verify_upstream.py) gerçek yordamları kontrol eder:

1. MIT uyarlamasında sabit tohumlu 128 farklı profil, iç/dış/teğet boy ve
   karışık yön: açınım boyu ve büküm çizgilerindeki en büyük fark
   `2.274e-13 mm`. Ayrıca 25 Python testi, bağımsız sabit sayısal örnekler,
   birim ölçekleme, imkânsız flanş ve hatalı numune davranışını doğrular.
2. Desarrolla, S=1200, D=500, H=700, 24 bölme örneğinde üreteç boylarını
   yaklaşık korur; ancak ürettiği 2D/3D üçgenlerin komşu köşegeninde en büyük
   fark `304.962 mm` olur. Kare çevresini zorla düz taban üzerine yerleştiren
   yöntem, gerçek üçgen kenarlarının tümünü korumaz. GOKWORKS'ün mevcut gerçek
   uzunluk üçgen/fan yöntemi korundu. Bu sonuç tüm Desarrolla işlevlerinin
   incelendiği veya bütün girdilerde aynı hatanın oluştuğu iddiası değildir.
3. Sabit FreeCAD sürümünün **yalnız skaler `get_k_factor` yordamı** izole
   çalıştırıldı: (1,.38), (3,.43), (99,.5) tablosunda R/t=5 için `.48`
   döndürürken parça doğrusal referans `.43145833333333333` olur. Bu yordam
   alınmadı. FreeCAD'in tamamı veya canlı CAD akışı test edilmiş sayılmaz.
4. SheetMetalCone'da çaplar eşitken koni hesabının paydası sıfırlanır;
   GOKWORKS'ün mevcut açık silindir limiti korunur. Lisanssız betikte erken
   0.001 koordinat yuvarlaması ve sabit K görüldü; yeniden kullanım yapılmadı.

Tekrar üretim: `references.json` içindeki depoları belirtilen checkout
adlarıyla çekin ve **kayıtlı commit'e** geçin; sonra:

```sh
PYTHONPATH=. python docs/unfolding/research/verify_upstream.py \
  --research-root /workspace/research/sheet-unfolding \
  --output /tmp/unfolding-research.json
python -m pytest tests/unfolding/test_bend_profiles.py
```

Python 3.13 ve Node 24 kullanıldı. Node yalnız araştırma karşılaştırması
içindir; GOKWORKS çalışma bağımlılığı değildir. FreeCAD GUI/CAD, Inkscape ve
Gusset'in tam upstream test paketleri çalıştırılmadı. Araştırmada indirilen
kodlardan yalnız belirtilen MIT yordamının uyarlaması uygulamaya alındı.
