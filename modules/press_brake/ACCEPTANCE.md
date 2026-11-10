# İlk sürüm kabul kaydı — 10 Kasım 2026

Ortam: Linux, Python 3.13.5, PySide6 6.10.3, OCP 8.0.1.1,
Shapely 2.1.2, ezdxf 1.4.3. Qt offscreen ve gerçek OCCT katıları kullanıldı.
Canlı Windows/SolidWorks veya paketlenmiş Windows EXE testi yapılmadı.

## Sonuçlar

| Kontrol | Sonuç |
| --- | --- |
| `pytest modules/press_brake/tests` | **50 başarılı**: geometri, kinematik, hareket, DXF, katalog, SW sözleşmesi, kartlı seçici ve normal Qt sayfası |
| Lazy kayıt, depo yapısı ve Windows paketleyici/test koşucu sözleşmeleri | **26 başarılı** |
| Mevcut K/R parametreleri, DXF önizleme kaynağı/geometrisi, açınım profilleri, CI raporu | **129 başarılı**, 3 alt test başarılı |
| Ortak arayüz kontrolleri, kabuk geri bildirimi, ayarlar/bağlantı | **19 başarılı**, 1 platforma bağlı atlanan, 5 alt test başarılı |
| `python main.py --self-check ...` | **passed**, 22 modül, iki tema, çözünürlük matrisi; yeni abkant işçisi gerçek katı süpürmesi ve PDF oluşturdu |
| Sözdizimi, Ruff F kuralları ve `git diff --check` | **başarılı** |

Normal `main.main()` girişinden, gerçek Qt olay döngüsüyle ayrıca:

1. Üretim → Abkant Simülasyonu açıldı; özgün U parçası yüklendi.
2. İki bükümün sırası `B02 → B01` yapıldı.
3. Üst bıçak düğmesinden **görsel kart kütüphanesi** açıldı, `DEMO-WIDE`
   aranıp seçildi. Alt kalıp kartından `DEMO-2V / V24` seçildi.
4. Her adımda 131 ara katı konum kontrol edildi. İkinci adımın **yaklaşma**
   fazında, yaklaşık **0°** aktif dönüşte `F2 ↔ punch:DEMO-WIDE:1` bulundu.
   Oynatma ilk çarpışmada durdu; sahnede konum kırmızı işaretlendi.
5. Açık/koyu ekranlar ve üst/alt kart katalogları yakalandı. İki sayfalık
   `GOKWORKS-Abkant-U-Demo.pdf` oluşturulup sayfa görüntüsü ve çıkarılan metni
   incelendi. V24, yön, segmentler, ilk çift/faz/açı ve kapsam raporda doğrulandı.
6. Akış 50,68 saniyede bitti; iş sırasında Qt zamanlayıcısı 1.256 kez çalıştı.
   Bu, katı hesabının GUI olay döngüsünü kilitlemediğinin gözlemidir.

Dört kenarlı 2 mm delikli kutu için **tam üç fazlı 524 katı poz** ayrıca kontrol
edildi. Etkin boya uygun `DEMO-NARROW` segmentleriyle kontrol edilen konumlarda
çarpışma yok; dört adımlık PDF oluştu. Geniş bıçakla bilinen kutu çarpışması
gerçek katı testinde ayrıca üretildi. Delikler ve köşe rahatlatmaları korundu.
Kutunun tam hesap süresi bu ortamda yaklaşık 104 saniyeydi.

## Kanıtların kapsamı

- L: 120° iç açı / 60° dönüş, iki yön, 2 mm normal kalınlığı ve nominal hacim.
- U: iki sırada farklı ara dönüşüm, aynı nominal son geometri; bağlı alt ağaç taşınması.
- Büküm bandını kesen delik: ±30°/±60°'de geçerli, kapalı, delikli katı.
- Ara hareket: iki uç poz açıkken ortadaki gerçek katı çarpışması bulunur;
  yakın konumlarda aralık sıklaşır; oynatma hızından bağımsızdır.
- Temas: normal demo uç/omuz temasında yanlış alarm yok; tüm aktif flanş
  muaf değil, başka flanş yerel temas maskesinden de yararlanamaz.
- DXF: analitik yay ve tam daire hacimleri, gerçek delik, çok kesit seçimi,
  birim kontrolü, açık kesit reddi; ölçülendirme patlatılıp takım kenarına katılmaz.
- Katalog: parça açmadan DXF kart eklenmesi mevcut kullanıcı kartlarını korur;
  hat yükünün boş değeri bilinmiyor kalır. Demo/üretici varlıkları kopyalanmaz.
- Görsel seçici: üst/alt ayrı, kod/üretici araması, kalıcı favoriler, değişen sütun
  düzeni, büyük kesit/çalışma referansı, V ve segmentin birlikte atanması, iptal.
- SW doubles: aktif konfigürasyon, metre/radyan sınırı, kalıcı kimlik ve yeniden
  adlandırma; başarı/hata/iptalde seçim/unsur durumu ve dosya korunması; çok gövde,
  eksik R, eski rebuild ve eşleşmeyen büküm yüzü gerekçeli ret.

Ayrık örnekleme sürekli çarpışmasızlık kanıtı değildir. Tezgâh, arka dayama,
yeniden tutuş/çevirme geçişi ve çıkarma rotası modellenmedi; föyde kapsam dışıdır.
Eksik takım/tutucu veya arayüz eşleşmesi başarılı kontrol olarak gösterilmez.
Geometrik hava bükümü gerçek tezgâh kurulumu ya da üretim uygunluğu onayı değildir.

Çalışma alanı kanıt klasörü: `/workspace/work/press-brake/`. Kullanıcı DXF'si,
referans video, üretici ekranları veya katalog varlıkları kaynak depoya eklenmedi.
