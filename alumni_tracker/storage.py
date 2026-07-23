from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Manifest static storage that degrades gracefully before collectstatic.

    Templates reference static assets via ``{% static %}``. The default manifest
    storage raises if an asset isn't in the collectstatic manifest (or can't be
    hashed because ``STATIC_ROOT`` hasn't been populated yet). That breaks page
    rendering during tests, which run with DEBUG=False and no collected static.

    Here we return the plain filename in those cases instead of raising. In
    production, run ``collectstatic`` and hashed, cache-busted names work as usual.
    """

    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            # File not present in STATIC_ROOT yet (e.g. during tests) — fall
            # back to the un-hashed name so {% static %} still resolves.
            return name
