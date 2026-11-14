# Pratik hesap — 14 Kasım 2026

Hidrolik bilmeyen kullanıcı için varsayılan giriş artık tek sayfalık **Pratik
hesap**. Pistonun iç çapı, parlak mil çapı ve strok; itme kuvveti, ileri/geri
süreleri ve uçta bekleme girilir. Tam strokla ileri–bekle–geri hareketi kurulur;
bekleme sıfırsa yalnız ileri/geri vardır. Başlangıç konumu sıfırdır. Beklemede
ileri itme kuvveti korunur. Geri çekme yükü başlangıçta sıfırdır ve formda bu
kabul yazılıdır; yük varsa açılır bölümden değiştirilir. Ton-kuvvet ile kütle
karıştırılmaz; kN seçeneği de vardır.

İlk açılışta örnek başlangıç girdileri gösterilir; kullanıcı **Ünite ihtiyacını
hesapla** demeden bunlar proje veya sonuç olarak sunulmaz. Düğme küçük ekranda
da sabit alt çubuktadır. Düzenleme eski sonuçları gizler ve raporu kapatır;
geçerli bilgiler hesaplanınca PDF/Excel yeniden açılır. Hatalı taslak, görünüm
değiştirerek kaybedilemez. Düzenlenmemiş SI değerleri ve kuvvetler korunur.

Sonuçta motor, gereken pompa debisi ve kullanılabilir yağ tankı hacmi öndedir.
Basınç, pompa hacmi, hat ve soğutma ayrıntıları açılır bölümdedir. Kritik
uyarılar görünürdür; soğutma gücü ilgili kritik uyarıda da yazılıdır. Diğer
kontroller ayrıca açılır. Claude'un ünite şeması Pratik hesap ekranında ve
üç adımlı hareket planının sonuç sayfasında doğrudan görünür; açılır bölümde
gizlenmez. Hesaplanan değerler ve elemanlara tıklayarak ilgili ayara gitme
davranışı korunur. Taslak veya hatalı girişte devre görünür kalır, eski sayısal
değerler temizlenir. Şema ölçekli veya üretime hazır hidrolik devre değildir.

Yeni bir hesapta **Pompayı bu harekete göre boyutlandır** açıktır. Kullanıcı
hesaplayınca hesap motorunun ürettiği nominal pompa hacmi adayı projeye uygulanır
ve aynı hesap motoru tekrar çalışır. Bu seçenek kapalıysa mevcut pompa korunur.
Basınç sınırı, regülasyon, verimler, yağ/hat/tank ayarları ve elle seçilmiş motor
kendiliğinden değiştirilmez. Kaydedilmiş basit proje açıldığında pompa seçeneği
kapalı başlar. Debinin karşılanması bütün mühendislik kontrollerinin geçtiği
anlamına gelmez; kritik uyarılar ve senaryo sınırlaması korunur.

Mevcut özel hareket planı sessizce basitleştirilmez. Kısmi strok, rejeneratif
hareket, farklı bekleme kuvveti, karşı basınç, farklı başlangıç konumu veya
birden fazla silindir basit forma indirgenmez. Tek silindirli özel planda
kullanıcı isterse **Yeni basit çevrim oluştur** der; eski hareketler ancak bu
form hesaplandığında değiştirilir. Birden fazla silindir için bu değiştirme
seçeneği yoktur. **Hareket planı (3 adım)** ve **Ayrıntılı ayarlar** erişilebilir
kalır. Eski kolay görünüm tercihi bir kez yeni pratik görünüme taşınır;
sonradan yapılan bilinçli görünüm tercihi ve ayrıntılı görünüm tercihi korunur.

`practical.py` yalnız girişleri mevcut SI modellerine çevirir. Hesap motoru,
formüller, üretim doğrulamaları, `.gwhyd` şeması ve dışa aktarma motoru
değiştirilmemiştir. Yerel doğrulama; analitik silindir debisi karşılaştırması,
çevrim kapanması, birimler, özgün SI hassasiyeti, özel proje koruma, bozuk
girdiler, tercihler, gerçek PDF/proje kaydı, küçük ekranda görünür etiketlerle
tam kullanıcı akışı ve mevcut modül testlerini kapsar. Qt offscreen görüntüler
Linux'ta açık/koyu temada kontrol edilir; Windows doğrulamasını CI yapar.

Yerel sonuç: hidrolik modülünün hesap, kayıt/rapor ve arayüz kapsamındaki
**172 testi geçti**. Yeni pratik ekranın **31 durumu** son düzenlemelerden sonra
ayrıca geçti. Sayfa yükleme/geçiş, bozuk ayarlar ve bütün modüllerin küçük/geniş
pencere başlık kontrollerini içeren 199 testlik ayrı koşu da hatasız tamamlandı;
başarısız test tekrarı kapalıydı. Bu sayılar çakışan testleri içerir, toplanmaz.
Ruff F ve `git diff --check` geçti. Açık/koyu temada 790 ve 1366 piksel
genişliklerde görünüm yakalanıp incelendi; yatay kaydırma yok, hesap düğmesi
ekranda kalıyor, dar görünüm hesap sonrasında sonuç bölümünün başına gidiyor.

Şema görünürlüğü düzeltmesi: Pratik hesap ve üç adımlı sonuç sayfasındaki
şemalar doğrudan görünür. Aynı hesaplanan düğüm değerleri kullanılır; taslakta
yalnız pratik şemanın eski değerleri temizlenir. Fare/klavye ile seçim, tema,
özel proje koruma ve yatay taşma kontrolleri dahil **181 test geçti**; bunun
7 durumu yeni şema regresyonlarıdır. Test tekrarları kapalıdır. Açık/koyu
temada 790/1130/1366/1690 piksel genişlikler ayrıca görsel olarak kontrol edildi.
