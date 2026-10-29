# Weldments ve profil kesim entegrasyonu

22 Ekim 2026 · `main` · Mevcut PySide6/Qt Widgets mimarisi.

GOKWORKS’e **Profil kesim optimizasyonu** sayfası eklendi: aktif/dosyadan
Weldments taraması, düzeltilebilir Cut List, inceleme/hariç filtreleri,
tekrar güvenli aktarım ve stok boyu/testere payıyla 1D kesim planı.
[Kullanım, matematik ve doğrulama sınırları](../modules/profile_cutting/README.md).

Güncel yerel `main` incelendiğinde önceden 1D profil optimizasyon modülü
bulunmadı. Yeni modül bu eksik iş akışını tamamlar. Mevcut sac nesting,
PDF/DXF, BOM, K/R, tolerans ve diğer hesap motorları yeniden yazılmadı.
Yedek depo ve `release` dalı bu işin kapsamı dışındadır.

## Eklenen dosyalar

| Konum | İşlev |
| --- | --- |
| `modules/profile_cutting/models.py` | Kaynak, Cut List, body/occurrence kimliği, durum, kesim listesi ve tekrar aktarım kontrolü |
| `properties.py` | Düzenlenebilir case-insensitive mapping, evaluated değer, birim ve kesit kontrolü |
| `solidworks.py` | Mevcut raw COM oturumunun STA adaptörü; Get6 ve BodyFolder API’leri |
| `scanner.py` | Recursive montaj, konfigürasyon, miktar, Cut List ve geometri doğrulaması |
| `geometry.py` | İki uç düzlemi ve doğrusal prizma kontrolü; AABB kullanılmaz |
| `optimizer.py` | Best-fit, sınırlı exact arama, Decimal stok dengesi ve bağımsız plan kontrolü |
| `storage.py` | Sürümlü atomik JSON proje ve kaynak/ham property içeren CSV raporu |
| `ui.py`, `dialogs.py` | Mevcut Qt sayfası, editörler, property mapping ve manuel doğrulama |
| `tests/` | Matematik, scanner, COM contract/doubles, Qt workflow ve opt-in gerçek SolidWorks |
| `README.md`, `__init__.py` | Kullanım ve paket |
| `docs/profile-cutting/` | Pinlenmiş kaynak/lisans araştırması, API metadata, gerçek Qt görüntüleri ve test kaydı |

## Değişen ortak dosyalar

- `gui_qt/app.py`, `icons.py`: mevcut navigasyonda 14. modül ve yerel vektör ikon.
- `gui_qt/package_check.py`: dağıtım içinde profil transferi, tekrar kontrolü,
  miktar/grup dengesi, kesim şeması ve JSON/CSV döngüsünün COM’suz kontrolü.
- `packaging/build_windows.py`: mevcut tek EXE paket bilgisinde profil/Weldments
  gereksinimi. Normal Python importlarıyla paketlenir; yeni DLL, eklenti veya
  ticari servis eklenmedi.
- `README.md`, `modules/README.md`, `docs/repository-structure.md`,
  `docs/THIRD_PARTY_NOTICES.md`: modül, kullanım ve kaynak kaydı.

## Araştırma ve lisans

- Xarial CodeStack `0cde3849a184cdbbface61238ef431a6ebb9d530`: MIT.
  Read-all-properties Get6 sözleşmesi ve component Cut List yaklaşımı incelendi.
  Mevcut `packaging/licenses/tolerance-stack/CodeStack-MIT.txt` bildirimi korunur.
- SimonRafferty/Solidworks_Macros `05abb6c72c5b9b787e828b95d905d47c20365600`:
  Weldment Cut List README iş akışı incelendi; açık lisans doğrulanamadı.
  Binary SWP çalıştırılmadı, uygulamaya kod veya binary kopyalanmadı.
- edgarev/SolidWorks-Macros `8c88d59144fe1567c36a7b47a08261fb178682ab`: GPL-3.0.
  README/property yaklaşımı incelendi. GPL makro kodu veya binary kullanılmadı.
- Python kodu GOKWORKS için yazıldı. Yeni çalışma bağımlılığı yoktur.

Resmî 2025 API web sayfalarına erişim bu ortamda HTTP 403 ile engellendi.
Get6, BodyFolder, yüzey/face ve persistent-reference imzaları ayrıca
SolidWorks.Interop.sldworks 32.1.0 (2024 SP1) metadata’sından okundu.
DLL dağıtıma eklenmez; çalışma zamanında kurulu SolidWorks swconst TLB’si
kullanılır. [URL, commit, lisans ve SHA256 kayıtları](profile-cutting/references.json).

## Doğrulama ve gerçek ortam sınırı

[Arşiv: Modül JUnit kaydı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/profile-cutting/module-tests.xml) ve
[14 modüllü uygulama öz denetimi](profile-cutting/selfcheck.json) bu ortamda
çalıştırıldı. Çalışma ortamı Linux/Qt offscreen’dır. Gerçek SolidWorks
kurulumu bulunmadığı için canlı CAD testi atlandı; başarılı sayılmaz.
Toplu regresyon sonucu ve son dosya SHA256’ları `profile-cutting/checks.json`
dosyasında kaydedilir.

Son modül çalıştırması **64 geçti / 1 canlı test atlandı**. Uygulamanın tam
regresyonunda **1117 test ve 878 alt test geçti / 9 platform veya opt-in testi
atlandı**; hata yoktur. Son tarayıcı/aktarım iyileştirmeleri ayrıca modülün
tam test grubuyla yeniden kontrol edildi. Bağımsız subset-DP hesaplamasına
karşı [100 deterministik optimizasyon örneği](profile-cutting/oracle-check.json)
de uyuştu. [Arşiv: Ham regresyon JUnit kaydı](https://github.com/gkkizil/gokworks/blob/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9/docs/profile-cutting/regression-tests.xml).

UI gerçek Qt widget/worker/tablolarıyla test edilir; CAD sınırında doubles
kullanılır. Senaryolar: tek/çok gövdeli Weldment, farklı boy/kesit, 5 montaj
örneği, recursive adet çarpımı, farklı konfigürasyonlar, suppressed/lightweight,
eksik LENGTH, miktar çelişkisi, 45° kesim, tekrar/değişmiş aktarım, atomik
proje/rapor, kesim payları ve iptal. Tarama sırasında navigasyon ve küçük
pencere davranışı da kontrol edilir.

Kesit standardının tam geometri doğrulaması, üretici malzeme sertifikası,
gönye ortak kesim/CAM yönleri, kavis/cope/özel trim otomasyonu, çok stok boyu
ve sınırlı envanter desteklenmez. Gerçek SolidWorks’te test kopyalarıyla
özellik isimleri, display birimleri, özel geometri ve referans konfigürasyonlar
entegrasyon testiyle doğrulanmalıdır. [Canlı test talimatı](../modules/profile_cutting/README.md#dosyalar-ve-doğrulama).
