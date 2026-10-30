"""Load each Qt workbench once on demand; keep the public mapping interface."""

from collections.abc import Mapping


class PageRegistry(Mapping):
    def __init__(self, factories, create):
        self._factories = dict(factories)
        self._loaded = {}
        self._create = create

    def __getitem__(self, key):
        if key not in self._loaded:
            factory = self._factories[key]  # Unknown keys retain normal KeyError semantics.
            self._loaded[key] = self._create(key, factory)
        return self._loaded[key]

    def __iter__(self):
        return iter(self._factories)

    def __len__(self):
        return len(self._factories)

    def __contains__(self, key):
        return key in self._factories

    def loaded_values(self):
        return tuple(self._loaded.values())

    def peek(self, key, default=None):
        """Inspect lifecycle state without constructing a hidden workbench."""
        return self._loaded.get(key, default)
