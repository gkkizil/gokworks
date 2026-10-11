# SolidWorks 2025 yerel kontrolü

Bulut testleri gerçek Windows/SolidWorks oturumunu çalıştırmaz. Bu kontrol,
bildirilen K/R atama hatasının gerçek montajda giderildiğini doğrulamak içindir.

## Doğru sürümü açma

GitHub dalı: `codex/dxf-dwg-gui-report`. PyCharm'da Git ile açtıysanız bu dala
geçip **Git → Pull** kullanın. ZIP ile açtıysanız aynı dalın güncel ZIP'ini
yeniden indirin; eski klasörü saklayıp yeni klasörü ayrı proje olarak açın.
ZIP klasöründe `git pull` kullanılamaz.

Güncellemeden önce çalışan GOKWORKS penceresini/PyCharm çalışmasını durdurun.
Pull sonrasında `main.py` dosyasını yeniden çalıştırın. Açık eski Python
işlemi, diskte güncellenen kodu kendiliğinden yüklemez. PyCharm Run
Configuration içindeki script yolunun güncel proje klasörüne ait olduğuna
bakın; eski masaüstü ZIP klasörünü çalıştırmayın.

PyCharm'ın projenin kendi `.venv` yorumlayıcısını kullandığını kontrol edin.
Aynı yorumlayıcıya bağımlılıkları kurun:

```powershell
python -m pip install -r requirements.txt
python main.py
```

Pillow, `PIL` importunu sağlar; `PIL` isimli paket kurulmaz. SolidWorks 2025 ve
Python aynı Windows kullanıcı oturumunda çalışmalıdır.

## K/R atama

1. SolidWorks'te aktif ana montajı ve kontrol edeceğiniz parçaları kaydedin.
2. **K FAKTÖR - RADIUS → Manuel K / R**: kalınlık `2`, K `0,274`, R `2` girin.
3. **Montajı tara** ile eşleşen 2 mm sacları ve atlama nedenlerini okuyun.
   Tarama sonuçlarında **Uygulamaya hazır** görünür; bu aşamada K/R yazılmaz.
4. İlk kontrolü **Parça dosyalarını kaydet** işaretlenmeden yapın; **Montaja
   K/R uygula** kullanın. Değişiklik SolidWorks belleğinde uygulanır.
5. Başarılı parçanın doğru konfigürasyonunda SheetMetal unsurunu açın:
   kalınlık 2 mm, K faktörü 0,274, iç R 2 mm, büküm payı türü K faktörü olmalı.
6. Farklı kalınlıklı saclarda değişiklik olmamalı. Alt montajlar dahil sayılar
   raporda görünmeli. Malzeme/gauge tablosuna bağlı, çok gövdeli veya özel
   büküm override'ı olan parçalar için destek sınırlarını rapordan kontrol edin.
   Süpürme flanşında özel yarıçap açıksa işlem yazmadan durmalıdır; varsayılan
   R ve büküm payına bağlıysa uygulanabilir. Türkçe karakterli/büyük harfli
   dosya yolları ve konfigürasyon adları ayrıntılarda özgün haliyle görünmeli.
7. Başarılı sonucu gözle kontrol ettikten sonra SolidWorks'te kaydedin.

Hata durumunda **Günlük**, satıra çift tıklama veya **Rapor kaydet** ile tam
metni alın. Yeni hata metni işlem aşamasını ve ilgili API üyesini içerir;
örneğin `Mevcut K/R ve büküm payı okuma: SolidWorks API · KFactor: ...`.
`128`, `swFileLoadWarning_AlreadyOpen` demektir: belge zaten açık/yüklüdür.
Bu bilgi tek başına atamayı engellemez. Mevcut belge yeniden kullanılmalı ve
işlem sonunda uygulama tarafından yeni açılmış gibi kapatılmamalıdır.
[Enum kaydı](reports/k-radius/api-contract.json) SolidWorks interop
metadata'sından doğrulanmıştır.

**Durum Uygulandı** ve **K/R uygulandı ve geri okumayla doğrulandı** metni,
yazılan K/R'nin SolidWorks'ten tekrar okunup kontrol edildiğini belirtir.
**Önizleme; K/R uygulanmadı** metni, değerlerin yalnız okunduğunu belirtir.
“Montaja K/R uygula” sonrası hâlâ yalnız önizleme görüyorsanız önce çalışan
proje yolunu ve güncel dalı kontrol edin; Günlük ve tam satır ayrıntısını alın.
Tarama sürerken **Tarama bitince K/R uygula** düğmesine basılırsa uygulama
isteği bekletilir; uygun parça bulunan başarılı taramadan sonra başlar.
Durdur/iptal/hata durumunda bekleyen istek uygulanmaz.

## ISO ve GUI kabul kontrolü

- **ISO seçimi → Mil esaslı**: JS7/h6, K7/h6 ve N7/h6 ara geçme örneklerini
  Ø50'de seçin. P7/h6 Ø50'de sıkı olmalı; H7/p6 Ø3'te ara, Ø50'de sıkı olmalı.
- **Manuel kontrol**, Ø50: delik alt 0/üst +0,039 → tam H8;
  alt 0/üst +0,062 → tam H9; −0,0125/+0,0125 → tam JS7.
  Mil alt −0,016/üst 0 → tam h6. Sonuç ve CSV giriş limitlerini korumalı.
- Delik alt 0/üst +0,02 tam H7 değildir: en yakın H6 referansı, üst fark
  +0,004 mm. Delik −0,05/0 ve mil ±0,1 → −0,15…+0,10 mm ara geçme.
- PDF, DXF/DWG ve K/R sayfalarında form solda, sonuçlar sağda tam yüksekliği
  kullanır. Form kaydırılırken tablo küçülmemeli. Açık/koyu tema ve Windows
  ekran ölçeğinde sekme geçişlerini kontrol edin.

## Yerel Codex oturumuna devir

Bilgisayarda Codex CLI kullanılıyorsa proje klasöründen başlatın. Bu belgeyi
ve [düzeltme raporunu](reports/kr-workspace-fix/README.md) okutun. Önce
SolidWorks COM API'sinden aktif belge, unsur ve mevcut değerleri yazma
yapmadan kontrol etmesini isteyin. Bulut sohbetine verilen izin yerel
PyCharm/SolidWorks bağlantısı oluşturmaz; yerel oturum ayrı çalışır.
