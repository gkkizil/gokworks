# ISO geçmeleri — görsel kontrol, 16 Ekim 2026

final result: passed

## Kapsam ve kaynak

Kullanıcının iki ekran görüntüsü ve son yönlendirmesi esas alındı: mevcut
sekme/paneller korunacak, yalnız ISO seçimi sadeleşecek; manuel tolerans ekranı
değişmeyecek. İlk referansın yeşil rengi yerine uygulamanın mevcut mavi/lacivert
teması korundu. Bu çalışma masaüstü Tk uygulamasında yapıldı; web prototipi değildir.

Kaynak uygulama: `181e5bf`; başlangıç görüntüsü
`/workspace/.cloud-setup/iso-minimal/iso-before.png`. Tam karşılaştırma:
[Arşiv: önce/sonra](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/iso-minimal-comparison.png); uygulama görüntüleri:
[Arşiv: koyu](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/iso-minimal-dark.png),
[Arşiv: açık](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/screenshots/iso-minimal-light.png).

Görünüm 1440×900 piksel, ölçek 1; karşılaştırma 2880×900 pikselde iki eşit
görünüm içerir. Durum: Ø50 H7/s6, Orta değer, montaj kesiti. Kullanıcı referansları
farklı pencere boyutundadır; 1:1 piksel kopyası hedeflenmedi. Mevcut uygulama
görünümüyle aynı durum ve ölçekte karşılaştırıldı.

## Sonuç

- Yazı tipi ve hiyerarşi: uygulamanın mevcut fontları korundu; nominal çap,
  sınıflar, sonuç ve iki fark değeri okunuyor. Kaynaklar/CSV ve ölçü sınırları erişilebilir.
- Boşluk ve yerleşim: kesit üste alındı, sonuç daha kısa kartta; filtre açıklamaları
  açılır bölüme taşındı. Görünüm ve üç örnek seçimi aynı işlevlerle görünür kaldı.
- Renkler: mevcut açık/koyu mavi token'lar; sıkılık ve çakışma mevcut kırmızı
  token ile, geometrik boşluk aynı hesaplardan çiziliyor.
- Görsel kalite: teknik kesit canlı hesap verisinden çiziliyor; nominal etiket ile
  gerçek örnek çapları ayrılıyor. Logo ve manuel kesit kaynağı korunuyor.
- Metin ve içerik: ISO seçimindeki tekrarlanan Cmin/Cmax açıklaması kısaldı.
  Manuel uyum ve ISO karşılaştırma metinleri aynı kaldı. Isıtma/pres kararı eklenmedi.

Manuel görünüm için açık ve koyu tema başlangıç/son pikselleri birebir aynı;
[SHA256 ve fark kaydı](test-results/iso-minimal.json). Yakın incelemede kesit
etiketleri, örnek değişimi, minimum/maksimum değerler ve manuel sonuç panelleri
kontrol edildi. Çözümlenmemiş P0/P1/P2 görsel bulgu yok.

17 ilgili GUI kontrolü geçti: örnekler/iki görünüm, geçersiz girdi, filtreler,
manuel değerlerin korunması, menü ön yüklemesi, detaylı manuel kesit ve
1000×690–1920×1080 ile %100/%125/%150 ölçekleri. Tüm test paketi çalıştırılmadı.
Manuel test yardımcısında mevcut kuyruklu menü geçişinin bitmesi bekleniyor;
bu düzeltme uygulamanın manuel davranışını değiştirmiyor.

Kontrol Linux/Xvfb üzerinde gerçek Tk pencereleriyle yapıldı. Windows font
görünümü bu görsel karşılaştırmanın kapsamı dışındadır.
