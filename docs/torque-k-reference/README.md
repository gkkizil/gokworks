# Hızlı tork hesabı — görünür K rehberi

K girişinin altında, ek bir yardım bölümünü açmadan görünen küçük bir yüzey
rehberi bulunur: çok iyi yağlanmış yüzeyler, hafif yağlı/kuru çelik ve yüksek
sürtünme için yaklaşık başvuru değerleri gösterilir.

Tablo hesap girdisini değiştirmez. Kuru bağlantıda 0,20 ve hafif yağlı
bağlantıda 0,15 varsayımı; manuel K girişi, sıfırlama ve hesap formülü korunur.
Değerler standarttan alınmış evrensel yüzey sabitleri olarak sunulmaz.
Çinko/diğer kaplamalarda gerçek K, kaplama ve yağlayıcıya göre değişir;
paslı/kirli bağlantıya tablodan K atanmaması açıklanır.

[Arşiv: Koyu tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/torque-k-reference/dark.png) · [Arşiv: Açık tema](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/torque-k-reference/light.png) · [Arşiv: Küçük pencere](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/torque-k-reference/minimum.png).
Görüntüler çalışan PySide6 arayüzünden Linux / Qt offscreen ortamında alınmıştır.
Küçük pencerede form kaydırılabilir; tork/ön yük özeti üstte kalır.

Qt testleri rehberin açık/koyu temada görünmesini, manuel K değerini
değiştirmemesini ve mevcut hesap/kopyalama/kesit davranışlarını kontrol eder.
