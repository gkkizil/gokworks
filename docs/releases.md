# Geliştirme ve yayın düzeni

| Dal | Amaç | Güncellenme kuralı |
| --- | --- | --- |
| `main` | Uygulamanın güncel geliştirme kodu | Yazılımsal değişiklikler burada yapılır. |
| `release` | Kullanıcılarla paylaşılacak kaynak ve indirme sayfası | Yalnız kullanıcı açıkça yayın istediğinde `main` değişiklikleri aktarılır. |

Varsayılan dal `main` olarak kalır. `main` → `release` otomatik aktarımı yapan
bir iş akışı yoktur. `release` üzerinde özellik geliştirilmez; uygulama
düzeltmeleri önce `main` üzerinde tamamlanır. Yedek depoda işlem yapılmaz.

## Kullanıcıya hangi bağlantı verilir?

- Paylaşım sayfası: <https://github.com/gkkizil/gokworks/tree/release>
- Bu sayfanın **Son başarılı Windows EXE** bağlantısı doğrudan `GOKWORKS.exe`
  indirir. Kullanıcının Git veya Python kurması gerekmez; EXE yanında klasör
  taşınmaz.
- **Code → Download ZIP**, çalıştırılabilir uygulama yerine kaynak kodu indirir.

GitHub görünürlüğü dal bazında ayarlanmaz. Bu depo herkese açıktır; hem `main`
hem `release` görüntülenebilir. Yayın dalı, paylaşılacak sürümü geliştirme
güncellemelerinden ayrı tutar.

## Sonraki sürümü yayınlama

1. Kullanıcı açıkça `main` güncellemelerinin yayın dalına aktarılmasını ister.
   Normal geliştirme veya yalnız `main` için EXE isteği, bu aktarımı başlatmaz.
2. `main` üzerinde istenen değişiklikler ve ilgili testler tamamlanır. Seçilen
   kaynak commit kaydedilir; `release` yalnız bu commit'e kadar, geçmişi
   koruyarak ilerletilir. Yayın dalının kendi derleme kayıtları varsa normal
   birleştirmeyle korunur; geçmiş zorla yeniden yazılmaz.
3. Yeni EXE isteniyorsa **Windows EXE → Run workflow → release** seçilir veya
   `release` dalındaki `packaging/windows-build-request.json` dosyasına yeni
   bir derleme isteği yazılır. Yalnız dalı ilerletmek yeni EXE üretildiği
   anlamına gelmez.
4. Windows testleri, tek dosyalı paket üretimi ve paket açılış kontrolleri
   geçince EXE, kaynak commit'i hedefleyen bir GitHub Release dosyası olarak
   yayımlanır. Büyük EXE dosyası Git geçmişine eklenmez.
5. Yayıncı yalnız derlemenin çalıştığı dalın README indirme bloğunu,
   `packaging/latest-windows.json` ve derleme durumunu günceller. Başarısız
   derleme, son başarılı EXE bağlantısını değiştirmez. Yeni indirme bağlantısı
   oturum açmadan kontrol edilir ve SHA256 değeri paket bilgisiyle karşılaştırılır.
6. Geliştirmeye tekrar `main` üzerinde devam edilir. Sonraki değişiklikler,
   yeni açık yayın isteği gelene kadar `release` dalına taşınmaz.

GitHub Release etiketleri ve dosyaları depo düzeyindedir; yalnız bir dala ait
ayrı bir Releases alanı bulunmaz. Bu nedenle paylaşım sayfası belirli bir
başarılı EXE dosyasına bağlanır. `main` üzerinde başka bir EXE derlenmesi
`release` sayfasının seçtiği dosyayı değiştirmez.

README indirme bloğundaki **Uygulama kodu**, gerçek EXE'nin kaynak sürümüdür.
Dalın güncel commit'iyle aynı olmak zorunda değildir. Yeni kodun derlenmediği
durumda mevcut EXE, yeni kaynak kodu içeriyormuş gibi sunulmaz.

[Paketleme ve Windows kontrolleri](../packaging/README.md)
