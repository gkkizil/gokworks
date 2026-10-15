# Kaynak ve telif ön incelemesi

[Excel listesini indir](GOKWORKS_Kaynak_ve_Telif_Listesi_2026-10-15.xlsx).

15 Ekim 2026, Europe/Istanbul. İncelenen uygulama sürümü:
`5a5d0a3` (`codex/dxf-dwg-gui-report`).

Excel yedi sayfadan oluşur:

- **Özet:** kapsam, durumların anlamı ve sayfa bağlantıları.
- **Kaynaklar:** 45 proje, standart, belge veya görsel kaynağı; kullanım biçimi,
  lisans kanıtı, sürüm, yerel kanıt ve yapılması gerekenler.
- **Bağımlılıklar:** 22 paket, araç veya alt bileşen kaydı. Linux ortamındaki
  sürümler, Windows için sabitlenen sürümlerden ayrı belirtilir.
- **Malzeme Verileri:** 39 malzemenin yoğunluğu, kaynağı ve kart/dosya lisansı.
- **Dolaylı Kaynaklar:** malzeme kartlarının işaret ettiği, özgün metni ayrıca
  okunmuş sayılmayan yayın ve site bağlantıları.
- **Tüm Bağlantılar:** mevcut takipli metin/DOCX dosyalarında kayıtlı 110 bağlantı
  ve bulundukları dosyalar. İç proje/build bağlantıları ayrıca işaretlidir.
- **Dağıtım Kontrolü:** bildirim eksikleri, belirsizlikler ve izlenecek adımlar.

## Durumların anlamı

- **YOK:** belgelenen mevcut kullanımda somut telif/lisans sorunu tespit edilmedi.
  Kaynağın telifsiz veya her kullanımının serbest olduğu anlamına gelmez.
- **VAR:** belirtilen lisans bildirimi/paketleme açığı tespit edildi. Kesinleşmiş
  telif ihlali kararı değil, dağıtım öncesi ele alınacak somut bulgudur.
- **BELİRSİZ:** lisans, hak sahipliği, veri/derleme hakkı veya dağıtım koşulu
  yeterli kanıtla doğrulanamadı; otomatik olarak “yok” yazılmadı.

Önemli bulgu: EXE betiği `ISOFITS-LICENSE.txt` için açık bir ekleme adımı veya
üçüncü taraf bildirimlerini toplama adımı içermiyor. Gerçek Windows EXE/ZIP
içeriği açılıp incelenmedi; gömülü paketlerin hiçbir lisans taşımadığı iddia edilmez.

FreeCAD kartları tek bir lisansla işaretlenmedi: plastik kartlarında
CC-BY-3.0/CC-BY-SA-4.0, metal kartlarında LGPL sürümleri bulunuyor. Fontların
gömülü metadata alanları da incelendi. CustomTkinter'ın metadata lisans beyanı
ile gerçek LICENSE dosyası farklı olduğundan gerçek MIT metni esas alındı.

Bir GPL/LGPL deposunu okumak, formül incelemek veya tekil fiziksel olguyu
kullanmak, uygulamayı otomatik olarak aynı lisansa bağlamaz. Öte yandan kod,
font, figür, tablo derlemesi ve dağıtılan kütüphanenin koşulları ayrı incelenir.
Bu liste hukuki uygunluk veya hak sahipliği garantisi değildir.

## Kanıt ve sınırlar

[Makine tarafından okunabilir kayıtlar](source-audit.json), Excel ile aynı
değerlendirmeleri, kaynak commitini, sabit sürüm lisans URL'lerini ve SHA-256
kanıtlarını içerir. 28 GitHub projesinin yaygın lisans dosyaları tarandı;
19 projenin lisans metni okundu. Diğerleri için lisansın kesinlikle bulunmadığı
iddia edilmez. Malzeme kartları ve paket/font kayıtları ayrıca incelendi.

Mevcut depoda kayıtlı kaynaklar listelenmiştir. Kayıt dışı eski araştırmalar,
ilk commit öncesindeki içeriklerin bütün kökenleri, bağımsız kod benzerliği
incelemesi ve gerçek Windows paketinin tam SBOM'u kapsam dışındadır.

Bu çalışma uygulama kodunu veya lisans politikasını değiştirmez. EXE üretilmedi,
genel uygulama testleri çalıştırılmadı. Oluşturulan XLSX yeniden açılarak yedi
sayfa, kayıt sayıları, filtreler, tablo yapıları ve formül içermemesi doğrulandı.
