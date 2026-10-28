# Geliştirme ve yayın düzeni

28 Ekim 2026 tarihli kullanıcı talimatıyla kaynak kod, geliştirme ve paylaşım
tek kalıcı dal olan **main** üzerinde toplandı. Ayrı bir `release` dalı yoktur.
Tamamlanmış özellik dalları, içeriklerinin main'e geçtiği doğrulandıktan sonra
kaldırılır. Geçici bir inceleme dalı gerekirse birleştirme sonrasında temizlenir.

## Kullanıcıya hangi bağlantı verilir?

- Kaynak ve paylaşım sayfası: <https://github.com/gkkizil/gokworks/tree/main>
- README'deki **Son başarılı Windows EXE** bağlantısı doğrudan `GOKWORKS.exe` indirir.
- Windows 10/11 x64; Python kurulumu veya EXE yanında ek klasör gerekmez.
- **Code → Download ZIP** çalıştırılabilir uygulama yerine kaynak kodunu indirir.

## Yeni EXE oluşturma

1. Kullanıcının istediği değişiklikler main üzerinde tamamlanır ve test edilir.
2. Kullanıcı EXE istediğinde **Windows EXE → Run workflow → main** seçilir veya
   `packaging/windows-build-request.json` içindeki benzersiz derleme isteği güncellenir.
3. İstenen doğrulama profili, Windows testleri ve gerçek paket açılış kontrolleri
   tamamlanır. Başarısız bir paket son başarılı EXE bağlantısının yerini almaz.
4. Tek EXE GitHub Release dosyası olarak yayımlanır; büyük ikili dosya Git
   geçmişine eklenmez. Yayıncı main'in README indirme bloğunu,
   `packaging/latest-windows.json` ve derleme durumunu günceller.
5. Oturum açmadan indirme bağlantısı kontrol edilir; dosyanın SHA256 değeri
   paket bilgisinde kaydedilir. Güncel kaynak ile EXE'nin kaynak commit'i
   farklıysa mevcut EXE yeni kodu içeriyormuş gibi sunulmaz.

## Geçmiş sürümler ve dal temizliği

Eski GitHub Release etiketleri ve dosyaları korunur. Bir dalın silinmesi eski
EXE dosyasını veya main'in içerdiği geçmişi silmez. Squash ile aktarılmış altı
özellik dalının son dosya ağaçları ilgili main commit'leriyle birebir
karşılaştırıldı; eski release zaten main'in atasıdır.

[Dal başları ve dosya tekilleştirme kaydı](repository-consolidation.md).
[Paketleme ve Windows kontrolleri](../packaging/README.md).
