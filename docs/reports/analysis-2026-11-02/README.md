# GOKWORKS teknik analiz raporu — 2 Kasım 2026

Dal: `claude/gokworks-analysis-fixes-vcwvdk`, başlangıç `98d94a6`.
Çalışma dizini temiz başladı. Yıkıcı Git komutu kullanılmadı. Kullanıcı CAD
dosyalarına dokunulmadı. Gerçek SolidWorks/Windows ortamı bu çalışmada
**kullanılamadı**; CAD yolları yalnız mevcut sahte (mock) testlerle denetlendi.

## 1. Proje özeti

GOKWORKS, PySide6/Qt Widgets ile yazılmış, 16 sayfalık bir masaüstü
uygulamasıdır. Her özellik `modules/<ad>/` altında Qt'siz bir hesap/CAD motoru
ve ayrı bir `ui.py` sayfasından oluşur. Sayfalar ilk açılışta oluşturulur.
Uzun işler `gui_qt/workers.py` içindeki `JobManager` ile tek bir `QThread`
üzerinde, sırayla çalışır. PDF aktarımı ve dişli OCP işleri aynı EXE'nin ayrı
süreçlerinde çalışır. Mil oluşturma ve Pack and Go, SolidWorks interop
DLL'leriyle derlenen C# STA köprüleri kullanır. Ayrıntılar:
[GOKWORKS_ARCHITECTURE.md](../../GOKWORKS_ARCHITECTURE.md).

## 2. Modül envanteri

| Modül | Durum | Not |
| --- | --- | --- |
| PDF, DXF/DWG, 3D Dönüştürücü, BOM, İsimlendirme | Uygulanmış | SolidWorks COM gerektirir; mock testleri geçiyor, canlı testler atlandı |
| K faktörü / yarıçap | Uygulanmış | Hesap saf Python; montaja atama COM ile |
| ISO geçme, geometrik tolerans, tolerans yığılması | Uygulanmış | ISO 286 tablosu nm tamsayı |
| Cıvata, hızlı tork, ağırlık | Uygulanmış | Statik/yaklaşık modeller açıkça belirtilmiş |
| Nesting · sac maliyeti | Uygulanmış | NFP sezgisel arama + bağımsız doğrulayıcı; optimum iddiası yok |
| Profil kesim | Uygulanmış | 1D best-fit + sınırlı tam arama |
| Parametrik mil | Uygulanmış | Geometri + C# köprüsüyle katı model; mukavemet hesabı yok |
| Dişli / zincir dişli | Uygulanmış | Sıfır kaydırmalı dış düz evolvent; OCP ile STEP/DXF |
| Otomatik teknik resim ve ölçülendirme, genel parametrik parça | **Yok** | Öneri listesinde |

## 3. Bulgular

Bağımsız olarak kontrol edilen formüller (hatasız bulundu): ağırlık kesit
alanları (boru πt(d−t), altıgen √3/2·s², kutu 2t(b+h−2t), I/U/T profiller);
ISO 898-1 Sp/Rp0,2 değerleri ve As = π/4(d−0,9382P)²; BA = θ(R+Kt),
BD = 2(R+t)tan(θ/2) − BA; kesilmiş normal ve üçgensel dağılım momentleri;
dişli kavrama yolu, girişim koşulu, Ft = 2000T/d, T = 60000P/(2πn);
ISO 286 sınıf aralığı seçimi; nesting kütle/maliyet korunumu.

Hatalı girdi taraması: ağırlık, cıvata, tork, K faktörü ve ISO geçme
motorlarına boş, metin, NaN, ±inf, 1e400, bool, liste ve negatif değerler
verildi. `ValueError` dışında hiçbir istisna oluşmadı.

Ruff (F, B, PLE) taraması: tanımsız ad veya sözdizimi hatası yok.
B023 uyarıları, döngü içinde hemen çağrılan kapanışlar; F841 uyarıları ise COM
referanslarını bilinçli olarak bırakan atamalardır. Bunlar hata sayılmadı.

| Kimlik | Öncelik | Dosya / fonksiyon | Kök neden |
| --- | --- | --- | --- |
| N01 | P2 | `gui_qt/workers.py` · `EventSink.put` | Olaylar ancak 64 olaya ulaşınca veya **bir sonraki** `put` 16 ms sonra gelirse iletiliyordu. Motor `("current", parça)` yazıp uzun bir COM çağrısına girdiğinde, bu mesaj çağrı bitene kadar arayüze ulaşmıyordu. Sink oluşturulduktan sonraki ilk 16 ms içinde gelen olaylar da bekliyordu. Bu yüzden durum ve ilerleme bilgisi bir adım geriden geliyordu. Bulgu, test ile yeniden üretildi: 0,5 s içinde 0 olay iletildi. |
| N02 | P3 | `modules/bolt_torque/rules.py` · `STRENGTHS['8.8']`, `LARGE_88` | ISO 898-1'de 8.8 sınıfının akma özelliği `Rp0,2` olarak tanımlıdır, `ReL` değildir. Sayısal değerler (640/660 MPa) doğruydu; yalnız arayüzde ve kopyalanan sonuçta gösterilen sembol yanlıştı. |

## 4. Düzeltilen hatalar

- **N01** — `gui_qt/workers.py`: `EventSink` kilitli hale getirildi. İlk
  bekleyen olay için en geç 16 ms sonra çalışan tek bir zamanlayıcı kurulur.
  64 olay ve 16 ms paketleme sınırları korunur. `close()` yeni eklendi:
  `JobWorker.run` sonunda kalan olayları iletir ve zamanlayıcıyı iptal eder.
  Böylece `deleteLater` sonrasında sinyal yayımlanmaz. Olay sırası korunur.
  Qt bağlantısı zaten `QueuedConnection` olduğu için yayın, işçi dışındaki
  iş parçacığından güvenle yapılır.
- **N02** — `modules/bolt_torque/rules.py` içinde sembol ve açıklama
  `Rp0,2` yapıldı. Bunlara bağlı test beklentisi
  (`modules/bolt_torque/tests/test_bolt_torque.py`), test yorumu
  (`tests/test_audit_engineering_oracles.py`) ve `docs/bolt-torque.md`
  tablosu güncellendi. Hesaplanan ön yük ve tork değerleri değişmedi.

Değiştirilen ve eklenen dosyalar:
`gui_qt/workers.py`, `modules/bolt_torque/rules.py`,
`modules/bolt_torque/tests/test_bolt_torque.py`,
`tests/test_audit_engineering_oracles.py`, `docs/bolt-torque.md`,
yeni `tests/test_event_sink.py`, yeni `docs/GOKWORKS_ARCHITECTURE.md`,
yeni `docs/reports/analysis-2026-11-02/README.md`.

## 5. İyileştirmeler

- GUI yanıt verebilirliği: uzun CAD çağrılarından önce gönderilen durum ve
  ilerleme mesajları artık en geç yaklaşık 16 ms içinde görünür.
- Mimari dokümantasyon: gerçek modül envanteri, iş/süreç modeli, COM kuralları
  ve yeni modül kuralları tek belgede toplandı.
- Büyük refactor yapılmadı. Yeni bağımlılık eklenmedi. Arayüz ve modül adları
  korundu.

## 6. Test sonuçları (Linux, Python 3.13.18, Qt offscreen)

| Çalıştırma | Sonuç |
| --- | --- |
| Değişiklik öncesi tam takım | 2281 geçti, 66 atlandı, 0 başarısız (888 alt senaryo) |
| `tests/test_event_sink.py` (yeni, 3 test) | Eski kodla 3 başarısız, yeni kodla 3 geçti |
| Değişiklik sonrası tam takım | 2284 geçti, 66 atlandı, 0 başarısız (888 alt senaryo, 495 s) |
| `main.py --self-check` | `passed`: 16 sayfa, 2 tema, 4 çözünürlük, 25 kontrol |

Atlanan 66 test Windows, pywin32, PowerShell veya lisanslı ve açık
SolidWorks gerektirir. Bu testler **doğrulanmış sayılmamalıdır**.

## 7. Kalan sorunlar

- Bütün SolidWorks COM/C# köprüsü yolları (PDF, DXF/DWG, 3D, BOM, Pack and Go,
  K/R atama, mil, tolerans yığılması okuma/yazma) gerçek SolidWorks üzerinde
  yeniden doğrulanmalıdır. Bu oturumda doğrulanmadı.
- `EventSink` düzeltmesinin Windows EXE içindeki davranışı, Windows CI testleri
  (`packaging/run_windows_tests.py`) ile ayrıca görülmelidir.
- Pyright tip denetimi borcu sürüyor (önceki denetimdeki A09 maddesi).
- 4.8/5.8 sınıfları için tork modülü 320/400 MPa nominal değerlerini kullanır.
  ISO 898-1'de bu sınıfların özelliği tam boy cıvatada `Rpf`'dir (min 340/420).
  Mevcut seçim muhafazakârdır ve kodda belgelenmiştir; değiştirilmedi. Etiket
  doğrulaması için standardın güncel metni kontrol edilmelidir.

## 8. Geliştirme önerileri

1. Mil modülüne DIN 743 / basit burulma-eğilme mukavemet kontrolü (ayrı motor,
   mevcut geometri modelini kullanarak).
2. Dişli modülüne ISO 6336 yöntem B'ye dayalı diş dibi/yüzey basıncı ön
   kontrolü. Kapsam ve sürüm açıkça belirtilmeli.
3. Nesting için kesim sırası/takım yolu ön izlemesi ve büyük gerçek müşteri
   DXF kümeleriyle performans ölçümü.
4. SolidWorks çizim otomasyonu: şablonla teknik resim oluşturma ve standart
   görünüş yerleşimi (yeni modül; canlı test altyapısıyla birlikte).
5. Kademeli tip denetimi: önce saf motorlar (`modules/*/rules.py`, nesting,
   profil kesim) için Pyright'ı CI'da zorunlu yapmak.
