# Dişli CAD motoru bildirimleri

OCP/proxy 8.0.1.1.0 bağlayıcıları Apache-2.0'dır. Dinamik OCCT 8.0.1 çekirdeği
LGPL-2.1 ve OCCT istisnası kapsamındadır; ilgili tam metinler bu klasördedir.
Kaynak: https://github.com/Open-Cascade-SAS/OCCT/tree/V8_0_1 ve
https://github.com/CadQuery/OCP . OCP wheel üretimi:
https://github.com/CadQuery/ocp-build-system .

`native/` Windows wheel'de görülen görüntü kodeklerinin bildirimlerini içerir.
FreeImage için FreeImage Public License 1.0, LibRaw için LGPL-2.1, zstd için
BSD seçeneği esas alınır. Diğer kodekler için ilgili MIT/BSD/IJG/zlib/libpng/
Apache/0BSD bildirimleri korunur. FreeType FTL metni üst lisans klasöründedir.
Microsoft MSVC çalışma zamanı DLL'leri Microsoft yeniden dağıtım koşullarına
tabidir; bunlar Apache veya LGPL olarak yeniden etiketlenmez.

Metinlerin kaynak bağlantıları ve SHA256 değerleri
`modules/gear_calculator/research/native-notices.json` içindedir. Sürüm ve
koşullar gerçek kullanılan wheel/DLL paketiyle birlikte kontrol edilmelidir.
LGPL kitaplığının değiştirilmiş sürümleri dağıtılırsa kaynak/değişiklik ve ilgili
kurulum bilgileri sağlanmalı; alıcıların kitaplık değiştirme ve hata ayıklama
hakları kısıtlanmamalıdır. Uygulama kaynakları bu kitaplıklara statik bağlanmaz.

`GOKWORKS_CAD_DIR`, uyumlu `OCP/`, `cadquery_ocp_proxy/` ve
`cadquery_ocp_novtk.libs/` içeren dizinden değiştirilmiş dinamik kitaplıkları
yüklemeyi sağlar. Yerel STEP işlemleri de bu seçimi devralır. Normal kullanıcı
çalıştırması için bu değişkenin ayarlanması gerekmez.
