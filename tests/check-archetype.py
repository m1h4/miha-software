"""Exercise the documented product-authoring workflow in a disposable site."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory() as directory:
        site = Path(directory)
        for name in ("content", "archetypes", "i18n", "static", "themes"):
            shutil.copytree(PROJECT / name, site / name)
        shutil.copy(PROJECT / "config.toml", site)

        def hugo(*args):
            subprocess.run([PROJECT / "scripts/hugo", *args, "--source", site], check=True)

        hugo("new", "content", "--kind", "product", "apps/example-player")
        bundle = site / "content/apps/example-player"
        assert len(list(bundle.glob("*.md"))) == 6
        hugo("--environment", "production", "--panicOnWarning")
        output = site / "public"
        for locale in ("", "hr/"):
            assert not (output / locale / "apps/example-player").exists()

        for landing in bundle.glob("_index*.md"):
            landing.write_text(landing.read_text().replace("  draft: true", "  draft: false"))
        images = bundle / "images"
        images.mkdir()
        sample = site / "themes/m1h4/static/icons/android-icon-192x192.png"
        for name in ("icon.png", "en-light.png", "hr-light.png"):
            shutil.copy(sample, images / name)

        hugo("--environment", "production", "--minify", "--panicOnWarning")
        for locale in ("", "hr/"):
            for child in ("", "privacy", "support"):
                assert (output / locale / "apps/example-player" / child / "index.html").is_file()
        subprocess.run([sys.executable, PROJECT / "scripts/check-site.py", output,
                        "--analytics", "on"], check=True)


if __name__ == "__main__":
    main()
