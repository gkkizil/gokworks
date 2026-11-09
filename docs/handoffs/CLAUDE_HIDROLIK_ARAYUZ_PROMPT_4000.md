GOKWORKS Hidrolik Ünite Hesaplayıcı arayüzünü profesyonel ve kullanıcı dostu hâle getir. Öncelik, teknik uzmanlığı sınırlı bir kişinin rahatça kullanabileceği kaliteli bir masaüstü arayüzüdür. Mevcut uygulamada çalış; yalnız öneri veya örnek ekran hazırlamakla yetinme.

ÖNCE İNCELE
AGENTS.md, Git durumu, main/ajan dalları ve modules/hydraulic_unit/ kodunu oku. Ekranı çalıştırıp mevcut görünümü incele. Kullanıcı ve diğer ajan değişikliklerini koru; reset/clean/force push yapma. Çalışma dalı agent/claude olsun.

Codex'in son kolay kullanım çalışması 2c32410 commit'iyle agent/codex dalına gönderildi. Önce bu değişiklikleri incele ve koru. Farklı bir ortamdaysan dalın güncelliğini doğrula.

ARAYÜZ KALİTESİ
- GOKWORKS tema ve bileşenlerine uy. Düzenli hizalama, tutarlı yazı boyutları ve boşluklarla belirgin görsel hiyerarşi kur.
- Başlangıç, veri girişi, sonuç ve sonraki işlem kolayca bulunabilsin.
- Sıkışık formları, kesilen değerleri ve gereksiz boşlukları düzelt. Önemli sonuçları öne çıkar.
- Renkleri seçim/durum/önem için kullan. İkonları metinle destekle; aşırı dekorasyon, yoğun renk ve gereksiz kartlar kullanma.
- Yerleşimi gerektiğinde yeniden düzenle; diğer modüllerin tasarımını değiştirme.

KOLAY KULLANIM
Varsayılan akış: Ölçüler → Hareketler → Sonuç ve rapor.
- Her adımın amacı ve sonraki işlem görünür olsun.
- Piston çapı, mil çapı ve stroku açıklayan anlaşılır çizim kullan. Piston çapıyla gövde dış çapını karıştırma.
- “Ne kadar yol alsın?”, “Kaç saniye sürsün?”, “Gerekli itme/çekme kuvveti nedir?” gibi açık etiketler kullan.
- Birimler, örnekler ve kısa terim açıklamaları alan yanında bulunsun. Bilginin etiketten/teknik resimden/üreticiden nereden alınacağını belirt.
- Hız/süre ve kN/ton-kuvvet geçişlerini güvenilir yap; kuvveti kütleyle karıştırma.
- Teknik seçenekleri Ayrıntılı ayarlar altında tut. Görünüm geçişinde değer veya yarım giriş kaybolmasın. Karmaşık projelerden silindir/faz silme.

SONUÇ VE HATA DENEYİMİ
- Motor, pompa debisi, basınç, hat iç çapı, tank ve soğutucu ihtiyacını değer+birim+kısa açıklamayla göster.
- İhtiyaç, mevcut kapasite ve nominal öneri ayırt edilsin. Grafiklerin eksen/birimleri okunabilir olsun.
- Uyarı hem sorunu hem yapılabilecek işlemi açıklasın; ilgili alana yönlendirsin. Kritik uyarıları kolay görünümde de göster.
- Yalnız renge güvenme. Geçersiz girdiyi işaretle; eski sonuçla rapor alınmasını engelle. Hesaplanıyor/başarılı/iptal/hata durumları tutarlı olsun.
- Örnek değerleri ve varsayımları belirt. Kullanıcı girdisini sessizce değiştirme; sonucu üretici/imalat onayı gibi sunma.

TEKNİK SINIRLAR
Sadece PySide6 kullan; yeni ağır bağımlılık ekleme. Hesap çekirdeği, formüller, .gwhyd sözleşmesi ve PDF/Excel/JSON işlevlerini koru. Görünen düğmeler gerçek işlevlere bağlı olsun; uygulanmamış özelliği çalışıyor gibi gösterme.

DOĞRULA VE TESLİM ET
Açık/koyu tema ve 1024×700, 1366×768, 1920×1080 boyutlarını kontrol et. Önce/sonra ekran görüntülerini alıp gerçekten açarak hizalama, okunabilirlik ve kesilmeleri incele. Klavye/odak sırası, hata düzeltme, birim/görünüm geçişi, kayıt ve rapor akışlarını test et. İlgili regresyonları çalıştır; görsel kusurları düzelt.

Kararları sen ver. Sonunda değişen dosyaları, ekran görüntülerini, testleri, commit/dal bilgisini ve eksikleri bildir. Kabul ölçütü: Hidrolik uzmanı olmayan kişi temel hesabı yardım almadan tamamlayabilsin; arayüz profesyonel bir mühendislik uygulaması kadar tutarlı ve özenli olsun.