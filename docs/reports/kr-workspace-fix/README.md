# K/R COM, ISO geçmeleri ve GUI çalışma alanları

> Eski Tk arayüzü için verilen görsel/rapor komutları tarihîdir. Bu betikler ve
> üretilmiş görseller güncel daldan kaldırılmıştır; yeniden incelemek için
> [temizlik öncesi sürümü](https://github.com/gkkizil/gokworks/tree/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9) kullanın.

10.10.2026 — **289 test geçti, 0 başarısız, 0 atlanan; 93 gerçek Tk GUI testi.**
19 yeni regresyon testi eklendi. Gerçek Windows/SolidWorks 2025 çalıştırılmadı;
K/R COM sınırı davranış test nesneleriyle temsil edildi.

## Değişen davranışlar

- K/R'de dönen çağrılabilir COM nesnesinin varsayılan üyesi yanlışlıkla
  çağrılmıyor. Büküm payının yalnız etkin türü okunuyor/yazılıyor. Manuel
  `t=2 mm, K=0,274, R=2 mm` yazımı, geri okuma, kayıt ve hata sonrası eski
  aktif türün geri yüklenmesi sınandı. Kalınlığı farklı saclar atlanır.
- Hata metni işlem aşamasını ve API üyesini içerir. Ekrandaki HRESULT
  `−2147352573` eski kodda aynı COM davranışıyla yeniden üretildi. Gerçek
  kullanıcının hangi üyede hata aldığı henüz yerel günlükle doğrulanmadı.
- PDF/DXF/K formları solda, sonuçlar sağda tam yüksekliği kullanır. Form
  kaydırması tabloyu küçültmez. K/R tarama/hesap/kayıt seçimi sabit kalır.
  Dar panelde arama ve filtreler iki satıra geçer. ISO/GD&T bağımsızdır.
- ISO hazır listeye delik/mil esası filtresi ve 9 yeni örnek eklendi: toplam
  23 örnek, menülerden 198 çift. Tümü görünümünde iki esas dönüşümlü
  sıralanır. H6/k6, H8/k6, JS7/h6, K7/h6, N7/h6 ve P7/h6 seçilebilir.
- Uzun hazır listeden kısa filtreye geçince eski kaydırma konumunun boş
  alan göstermesi düzeltildi. Seçimler, arama, çapla yeniden gruplama ve
  yeniden açılışta esas filtresini koruma gerçek GUI'de sınandı.
- Manuel sonuçta ayrı H7 ağırlıklı hazır geçme önerisi kaldırıldı. Tam ISO
  eşleşmesi, yakın referans ve eşit uzaklıktaki sınıflar ayrı açıklanır.
  Girilen ölçüler değiştirilmez; geçme türü giriş limitlerinden hesaplanır.

H7 tek başına geçme türü değildir: aynı H7 deliği farklı mil bölgeleriyle
boşluklu, ara veya sıkı geçme verebilir. Önceki hazır liste ara/sıkı örnekleri
ağırlıklı H7 delik esaslı sunduğu için farklı delik seçenekleri görünmüyordu.
Sayısal hesap bütün girdileri H7'ye sabitlemiyordu; liste ve manuel referans
sunumu düzeltildi.

## Bağımsız sayısal kontroller

Ø50'de JS7/h6: −0,0125…+0,0285 mm; K7/h6: −0,018…+0,023 mm;
N7/h6: −0,033…+0,008 mm ara geçme. P7/h6: −0,042…−0,001 mm sıkı geçme.
P7/h6 Ø3'te −0,016…0 mm sıkılık/sınırda temas verir; ara geçme değildir.
H7/p6 Ø3'te ara, Ø50'de sıkı geçmedir.

Manuel Ø50 delik 0…+0,02 ve mil −0,02…0 için boşluk 0…0,04 mm;
en yakın H6/h6 referansı, toplam limit farkı 0,008 mm. Tam ISO eşleşmesi
yoktur. Delik 0…+0,039 → tam H8; 0…+0,062 → tam H9;
−0,0125…+0,0125 → tam JS7. Delik −0,05…0 / mil ±0,1 için
−0,15…+0,10 mm ara geçme; delikte N7/P7 aynı uzaklıktadır.

Sabit GitHub kaynaklarıyla **3.217** tablo kontrolü tekrar yapıldı. Önceden
bilinen F8 ≤3 mm yanlış kaynak satırına ait iki fark kaydedildi;
**0 beklenmeyen fark**. [Kaynaklar ve hashler](iso-source-comparison.json).
Ø50'de 11 delik sınıfının bağımsız sayılarıyla canlı form, rapor ve sınıf
eşleşmesi de kontrol edildi. Resmî ISO sertifikası iddia edilmez.

K/R API üye sözleşmesi [SolidDNA 2023 interop metadata kaydıyla](../k-radius/api-contract.json)
kıyaslandı. pywin32 callable dispatch davranışı [sabit b312 kaynakla](https://github.com/mhammond/pywin32/blob/2a277cb5552756c2b4d42b524dc36d25e0bb6354/com/win32com/client/dynamic.py)
tutarlıdır. Bu kaynaklar gerçek SolidWorks 2025 çalıştırmasının yerine geçmez.

## Kanıtlar ve tekrar çalıştırma

- [Arşiv: Tam test çıktısı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/test-run.log), [test bazlı sonuçlar / kaynak hashleri](gui-verification-results.json).
- [Kapsam ölçümü](coverage.json); kapsam oranı gerçek CAD doğruluğu ölçüsü değildir.
- [Eski COM hatasının yeniden üretimi](dispatch-reproduction.json).
- [Eski H7 önerisi ve eşit uzaklık sunumunun yeniden üretimi](iso-matching-reproduction.json).
- [19 gerçek ekran / dosya hashleri / tablo alan ölçüleri](screenshots.json).
- [Arşiv: Word raporu](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/GOKWORKS_KR_ISO_GUI_Kontrol_2026-10-10.docx), [Word bütünlük kontrolü](word-report-validation.json).

Test kanıtı commit öncesi üretildi: `git_head` başlangıç commitini gösterir;
test edilen uygulama, veri ve test dosyaları `sha256` alanıyla belirlenir.
Bu hashler rapor oluşturulurken mevcut dosyalarla tekrar doğrulandı.

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user \
COVERAGE_FILE=/tmp/gokworks-kr-workspace-final.coverage \
.venv/bin/python -m coverage run --branch \
  --source=pdf,dxf_dwg,solidworks,main,k_factor,gui,iso_fits,geometric_tolerances \
  docs/report-tools/run_verification.py --output-dir docs/reports/kr-workspace-fix
```

1000×690 ve 1366×768 (%100), 1400×900 (%125), 1920×1080 (%150), iki tema,
alt sekmeler, filtreler, sayfa geçişleri ve form kaydırması sınandı. Bu dört
ölçekte PDF/DXF/K tablo yüksekliği en az `180 × ölçek` piksel, sonuç alanı
genişliği en az `300 × ölçek` pikseldir. Gerçek Windows monitör/DPI
kombinasyonları bu Linux testinden ayrı kontrol edilmelidir.

## Güncel gerçek ekranlar

| Ekran | Açık | Koyu |
| --- | --- | --- |
| PDF | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/pdf-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/pdf-dark.png) |
| DXF/DWG | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/dxf-dwg-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/dxf-dwg-dark.png) |
| K/R takım | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/k-factor-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/k-factor-dark.png) |
| K/R manuel | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/k-factor-manual-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/k-factor-manual-dark.png) |
| ISO | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/iso-fits-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/iso-fits-dark.png) |
| ISO mil esaslı | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/iso-fits-shaft-basis-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/iso-fits-shaft-basis-dark.png) |
| GD&T | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/black-theme/screenshots/geometric-tolerances-light.png) | [Arşiv: Görüntü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/black-theme/screenshots/geometric_tolerances-black.png) |

[Arşiv: Manuel ISO H6 referansı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/iso-fits-manual-h6-dark.png) ·
[Arşiv: Manuel ISO tam H8](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/iso-fits-manual-h8-dark.png) ·
[Arşiv: Manuel ISO tablo kontrolü](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/iso-fits-manual-comparison-dark.png) ·
[Arşiv: K/R küçük pencere](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/k-factor-manual-dark-small.png) ·
[Arşiv: DXF küçük pencere](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/reports/kr-workspace-fix/screenshots/dxf-dwg-dark-small.png).

Görseller çalışan Tk uygulamasından alındı; montaj verisi veya gerçek
SolidWorks başarısı gösterilmez. Bulut fontları Windows'tan farklıdır.

## Yerelde kalan kabul kontrolü

Gerçek SolidWorks 2025'te manuel K/R ataması, sac unsurunun K/R geri okuması
ve gerçek DXF/DWG/PDF çıktı geometrisi henüz doğrulanmadı. [Yerel kontrol
ve PyCharm güncelleme adımları](../../local-solidworks-check.md). Kaynak dal
`codex/dxf-dwg-gui-report`; eski ZIP klasörü otomatik güncellenmez.
