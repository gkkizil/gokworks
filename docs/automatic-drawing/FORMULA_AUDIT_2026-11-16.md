# Teknik resim modülü — formül doğrulaması

16 Kasım 2026, Europe/Istanbul. Başlangıç revizyonu: `d2421ae`;
dal: `agent/codex`. Bu rapor `modules/automatic_drawing` içindir.

**Teknik resim modülünde 189 test başarılı, canlı SolidWorks gerektiren iki
test atlandı.** Depo yapısı ve paket verileriyle birlikte son komutun sonucu
**196 başarılı / 2 atlanan / 0 başarısız**. Bu görevde 52 yeni test eklendi.
Başlangıçtaki modül sonucu 137 başarılı / 2 atlanandı.

## Bulunan ve düzeltilen hesap sorunları

| Sorun | Yeniden üretim / sonuç | Düzeltme |
| --- | --- | --- |
| Yazıyı geometri gibi ölçekleme | 110 mm kullanılabilir ende 80 mm sabit yazı, 1:1'den 2:1'e geçerken 160 mm varsayılıyor, sığan 2:1 eleniyordu | Her aday ölçek uygulanıp geometri ve yazı sınırları yeniden okunuyor |
| Birleşik kutu merkeziyle izdüşüm hizalama | Ana görünüşün yalnız sağında ölçü olduğunda ana/üst/yan görünüşlerin native konumları farklı eksenlere kayıyordu | Ölçülü kutular native görünüş konumuna göre ifade ediliyor; bağlı görünüşlerin konum eksenleri korunuyor |
| Taşıma sonrası eksik sığma denetimi | Geometri paftaya girerken taşınmayan ölçü yazısı dışarıda kalabiliyor; fit işlemi erken başarılı dönüyordu | Yazı dahil kutular ve anotasyon boşluğu taşıma sonrasında tekrar denetleniyor |
| Yanlış taraftaki izdüşümün kabulü | Bağ ve hizası doğru fakat birinci/üçüncü açıya göre ters tarafta olan üst/yan görünüş denetimden geçiyordu | Konum farkının işareti de doğrulanıyor; `projection_direction` bulgusu eklendi |
| Küçük parçada boyuta bağlı görünüş puanı | Toplam yüzey alanını en az 1 mm² almak, aynı şeklin küçültülmüş halinde yön puanını değiştiriyordu | Alanlar kendi pozitif toplamına bölünüyor; yalnız sıfır toplamda sıfıra bölme önleniyor |
| Otomatik paftanın ilk boyutta durması | 50 mm kenar ve 120 mm antette A4 kullanılabilir yükseklik −10 mm; A3'teki 77 mm alan denenmiyordu | Otomatik seçim boş alan bırakmayan küçük paftayı atlıyor; açıkça seçilmiş A4 değiştirilmeden hata veriyor |
| Farklı konfigürasyondan ölçü okuma | Açınım görünüşünde 125 mm olan ölçü, ana konfigürasyondan 100 mm okunuyordu | Değer ve ölçü kimliği görünüşün kendi `ReferencedConfiguration` bilgisini kullanıyor |

Native sınır testleri kontrollü API kayıt nesneleriyle yapılmıştır. Tablodaki
konfigürasyon ve yerleşim örnekleri gerçek bir SolidWorks kabul oturumunun
yerine geçmez. Kaynak model ölçüsünün değeri veya toleransı yeniden yazılmaz.

## Kontrol edilen bağıntılar

| Hesap | Bağıntı / kontrol |
| --- | --- |
| Metre → mm | `L_mm = 1000 L_m`; görünüş konumu ve ölçü metninin konumu aynı pafta biriminde |
| Radyan → derece | `α_deg = 180 α_rad / π` |
| Model ölçüsü / pafta ölçeği | 12,5 mm ve 60° değerleri 1:10, 1:1 ve 2:1'de aynı kalıyor |
| Kullanılabilir alan | `W_u = W−2m`, `H_u = H−2m−T`; alanın alt köşesi `(m,m+T)` |
| Görünüş geometrisi | İlk planlama: `W_p=sW`, `H_p=sH`; son karar native dış sınırlarla |
| Yerel ölçülü sınır | `B_yerel = B_pafta − IView.Position`; anotasyon boşluğu iki yönde ekleniyor |
| Komşu görünüşler | Pozitif yönde `d = sağ(A)−sol(B)+g`, negatif yönde `d = sol(A)−sağ(B)−g`; düşeyde aynı işlem |
| Grup ortalama | Bütün kutuların birleşiminin merkezi kullanılabilir alanın merkezine taşınıyor; ortak izdüşüm eksenleri birlikte öteleniyor |
| Döndürülmüş metin | `W'=|w cosα|+|h sinα|`, `H'=|w sinα|+|h cosα|`; konum dört köşenin dönüşümünden |
| Görünüş puanı | Kutu projeksiyonu / köşegen² ve yüzey yön katkısı / toplam yüzey alanı boyutsuz; ortak ölçekle değişmiyor |
| BOM | Gerçek örnek adedi, benzersiz çizilecek kaynak adedinden ayrı; mevcut adet ve tablo boyutu testleri de çalıştırıldı |

Yeni geometri matrisi sekiz görünüş grubu × iki izdüşüm yöntemi × 20 sabit
tohumlu örnekten, toplam **320 yerleşimden** oluşur. Kutular, motorun kendi
çakışma/contains yordamları yerine ayrı Shapely dikdörtgenleriyle kontrol
edilir. Pafta sınırı, boşluk ve izdüşüm eksenleri korunur. Bu 320 örnek test
sayısına ayrıca eklenmedi.

Başlangıç regresyon grubundaki 23 testin 10'u hataları yeniden üretti.
Otomatik pafta ve farklı konfigürasyon örnekleri de düzeltme öncesinde ayrı
komutlarla başarısız oldu. Son grupta tüm 52 yeni test başarılıdır.

## API kaynakları

- [ISheet.SetScale](https://help.solidworks.com/2020/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISheet~SetScale.html?format=P&value=): anotasyon konumu ve yazı yüksekliği ayrı bayraklardır. Mevcut çağrı konumu ölçekler, yazı yüksekliğini ölçeklemez.
- [IView.Position](https://help.solidworks.com/2023/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IView~Position.html): native görünüş konumu, eklenmiş ölçülerle oluşturulan birleşik kutunun merkezinden ayrı kullanılır.
- [IDimension.GetSystemValue3](https://help.solidworks.com/2016/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.idimension~getsystemvalue3.html): belirtilen konfigürasyondaki sistem birimli değer okunur.
- [IPartDoc.GetPartBox](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ipartdoc~getpartbox.html): `NoConversion=True` sistem birimlerini korur; model kutusu yaklaşık olup ilk planlama içindir.

Kaynaklara erişim: 16 Kasım 2026. Bunlar belirtilen API sözleşmelerini
destekler; bütün ISO çizim standartlarına uygunluk belgesi değildir.

## Tekrar çalıştırma

Python 3.12 / pytest 9.0.2 / PySide6 6.10.3 / Shapely 2.1.2, Linux offscreen:

```sh
QT_QPA_PLATFORM=offscreen python -m pytest modules/automatic_drawing/tests tests/test_repository_structure.py tests/test_packaged_data_files.py -q --tb=short
```

Son süre yaklaşık 20 saniye. Yeni test dosyasında Ruff, değişen Python
dosyalarında sözdizimi/fatal hata denetimi ve diff boşluk denetimi uygulandı.
ezdxf/pyparsing kaynaklı yedi kullanımdan kaldırma uyarısı test hatası değildir.

## Kapsam ve entegrasyon

Değişiklikler teknik resmin hesap/denetim dosyalarıyla sınırlıdır; UI ve
ortak CAD servisleri değiştirilmedi. `arrange` yordamına isteğe bağlı native
konum girdisi eklendi; eski çağrılar geçerlidir. Sayısal ölçü ve tekrar
kimliğinin veri şekli korunup doğru konfigürasyon anahtarı kullanıldı.

Gerçek SolidWorks'te SLDDRW/PDF üretimi ve performans ölçümü yapılmadı.
Ölçek adaylarının native uygulanması daha fazla rebuild gerektirebilir;
karşılığında sabit yazı boyutuna dayalı yanlış aday elemesi kaldırıldı.
Lider çizgilerinin tüm kesişimleri ve bütün GD&T çerçeveleri bu matematik
denetiminin kapsamı değildir. Görünüş puanı bir seçim sezgisidir; bütün
parçalarda tek doğru imalat görünüşünü kanıtlamaz.

Başlangıçta `origin/main` ile farklar yalnız Claude'un UI ve UI testindeydi.
Hesap dosyalarında örtüşme saptanmadı; bu UI değişikliklerine dokunulmadı.
