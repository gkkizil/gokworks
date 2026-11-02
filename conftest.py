"""Test-wide defaults shared by Linux and native Windows runs."""

import os

# Tests measure geometry and grab windows right after navigation. Keep page
# transitions off so results do not depend on animation timing; the dedicated
# transition tests opt in explicitly.
os.environ.setdefault('GOKWORKS_PAGE_TRANSITIONS', '0')
