"""Public application identity and accurate source/build revision metadata."""
import json
from pathlib import Path
import re
import sys

AUTHOR = 'Orhan Gökkızıl'
GITHUB_URL = 'https://github.com/gkkizil/gokworks'
EMAIL = 'orhangokkizilwork@gmail.com'
LINKEDIN_URL = 'https://www.linkedin.com/in/orhan-g%C3%B6kk%C4%B1z%C4%B1l/'
COPYRIGHT = '© 2026 Orhan Gökkızıl — GOKWORKS.'
DISCLAIMER = ('GOKWORKS, mühendislik ve teknik tasarım süreçlerini kolaylaştırmak amacıyla geliştirilmiş '
              'ücretsiz ve açık kaynaklı bir yazılımdır. Yazılım herhangi bir garanti verilmeden sunulmaktadır. '
              'Hesaplamaların, teknik verilerin ve oluşturulan CAD çıktılarının doğruluğunun kontrol edilmesi '
              'kullanıcının sorumluluğundadır. Yazılımın kullanımından kaynaklanabilecek doğrudan veya dolaylı '
              'zararlardan geliştirici sorumlu tutulamaz.')
ROOT = Path(__file__).resolve().parents[1]


def source_revision(root=ROOT):
    """Read Git metadata without starting a process or requiring Git on PATH."""
    try:
        root=Path(root);git=root/'.git'
        if git.is_file():
            marker=git.read_text(encoding='utf-8').strip()
            if not marker.startswith('gitdir: '):return None
            git=root/marker[8:]
        value=(git/'HEAD').read_text(encoding='utf-8').strip()
        if value.startswith('ref: '):
            ref=value[5:];common=git
            if (git/'commondir').is_file():common=git/(git/'commondir').read_text(encoding='utf-8').strip()
            path=common/ref
            if path.is_file():value=path.read_text(encoding='utf-8').strip()
            else:
                value=next((line.split()[0] for line in (common/'packed-refs').read_text(encoding='utf-8').splitlines()
                            if not line.startswith(('#','^')) and line.split()[1:]==[ref]),'')
        return value if re.fullmatch(r'[0-9a-fA-F]{40,64}',value) else None
    except (OSError,UnicodeError):return None


def version_text():
    if getattr(sys,'frozen',False):
        try:
            info=json.loads((ROOT/'build/application-info.json').read_text(encoding='utf-8'))
            revision=info.get('revision') if isinstance(info,dict) else None
            if isinstance(revision,str) and re.fullmatch(r'[0-9a-fA-F]{40,64}',revision):
                return 'Derleme revizyonu '+revision[:8]
        except (OSError,ValueError):pass
        return 'Paket sürüm bilgisi bulunamadı'
    revision=source_revision()
    return 'Kaynak revizyonu '+revision[:8] if revision else 'Kaynak dağıtımı'
