# Eski bağımsız K/R denemesi — geliştirme referansı

Bu klasördeki ayrı uygulama kullanımdan kaldırılmıştır. Yeni bağımsız K/R
paketi üretilmez; ayrı EXE derleme/yayımlama iş akışı kaldırılmıştır.
Önceki deneme kaynakları ve geçmiş doğrulama kayıtları referans olarak korunur.

K/R ataması **GOKWORKS → K faktörü / yarıçap → Manuel K / R** içindedir.
[Doğrudan atama motoru](../sheetmetal_parameters.py), ana uygulamanın montaj
işçisi tarafından aynı süreçte çağrılır. C# yardımcı EXE veya .NET gerekmez.
Ana Windows paketine bu eski `standalone` modülleri dahil edilmez.

Kalınlık satırlarına girilen K ve R doğrudan ana Sac-Levha parametrelerine
yazılır; büküm tablosundan değer alınmaz. [Güncel kullanım ve API
algoritması](../../docs/manual-k-radius.md).

Geçmişteki bağımsız paket testleri, güncel GOKWORKS motorunun gerçek SolidWorks
üzerinde doğrulandığı anlamına gelmez. Canlı SolidWorks ataması bu bulut
ortamında henüz doğrulanmamıştır.
