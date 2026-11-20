#!/usr/bin/env python3
"""Validate site content, redirects, app collections, and preserved release assets."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from xml.etree import ElementTree

import html5lib


BASE_URL = "https://www.mihasoftware.com/"
PROJECT = Path(__file__).resolve().parent.parent


def main():
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("directory", type=Path)
    arguments.add_argument("--analytics", choices=["on", "off"], required=True)
    args = arguments.parse_args()
    directory = args.directory.resolve()
    contract = json.loads((PROJECT / "tests/site-contract.json").read_text())
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def destination(path):
        relative = unquote(path).lstrip("/")
        target = directory / relative
        if path.endswith("/") or not relative:
            target /= "index.html"
        elif not target.suffix and (html := target.with_name(target.name + ".html")).is_file():
            target = html  # Cloudflare serves page.html at /page.
        return target

    def public_url(route):
        return urljoin(BASE_URL, route)

    for route in contract["pages"]:
        require(destination(route).is_file(), "Missing page: " + route)
    rules = {}
    for line in (directory / "_redirects").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        source, target, status = line.split()
        require(source not in rules and status == "301", "Invalid redirect: " + line)
        require(destination(target).is_file(), "Missing redirect target: " + target)
        require(not destination(source).is_file(), "Redirect shadows a file: " + source)
        rules[source] = target
    for source, target in contract["redirects"].items():
        require(rules.get(source) == target, "Incorrect permanent redirect: " + source)
    for route in contract.get("retired_pages", []):
        require(not destination(route).exists(), "Retired page remains: " + route)
    for name in contract.get("retired_assets", []) + contract.get("retired_feeds", []):
        require(not (directory / name).exists(), "Retired asset/feed remains: " + name)
    for name, digest in contract["assets_sha256"].items():
        file = directory / name
        require(file.is_file(), "Missing original asset: " + name)
        if file.is_file():
            require(hashlib.sha256(file.read_bytes()).hexdigest() == digest,
                    "Original asset changed: " + name)

    documents = {}
    titles = set()
    for file in sorted(directory.rglob("*.html")):
        name = file.relative_to(directory).as_posix()
        parser = html5lib.HTMLParser(namespaceHTMLElements=False)
        text = file.read_text()
        document = parser.parse(text)
        documents[file] = document
        require(not parser.errors, "Invalid HTML in {}: {}".format(name, parser.errors))
        route = "/" + name.removesuffix("index.html") if name.endswith("index.html") else "/" + name
        locale = "hr" if route.startswith("/hr/") else "en"
        home = "/hr/" if locale == "hr" else "/"
        require(document.get("lang", "").split("-")[0] == locale, "Incorrect HTML language: " + route)
        title = document.find("head/title")
        title_text = "".join(title.itertext()).strip() if title is not None else ""
        require(bool(title_text), "Missing title: " + name)
        require((locale, title_text) not in titles, "Duplicate title: " + name)
        titles.add((locale, title_text))
        metadata = {m.get("name", m.get("property")): m.get("content", "")
                    for m in document.findall("head/meta")}
        require(bool(metadata.get("description", "").strip()), "Missing description: " + name)
        require(bool(metadata.get("og:title")) and bool(metadata.get("og:description")),
                "Missing social metadata: " + name)
        canonical = document.find("head/link[@rel='canonical']")
        require(canonical is not None and canonical.get("href") == public_url(route),
                "Incorrect canonical URL: " + name)
        require(metadata.get("og:url") == public_url(route), "Incorrect social URL: " + name)
        require("https://mihasoftware.com" not in text, "Redirecting hostname in output: " + name)
        require("googletagmanager.com" not in text and "google-analytics.com" not in text,
                "Google Analytics remains in: " + name)
        beacons = document.findall(".//script[@src='https://static.cloudflareinsights.com/beacon.min.js']")
        product = document.find(".//nav[@class='nav subnav']") is not None
        require(len(beacons) == (1 if args.analytics == "on" and not product else 0),
                "Incorrect analytics inclusion: " + name)
        for beacon in beacons:
            try:
                token = json.loads(beacon.get("data-cf-beacon", "")).get("token", "")
                require(bool(re.fullmatch(r"[0-9a-f]{32}", token)), "Invalid beacon token: " + name)
            except (ValueError, AttributeError):
                require(False, "Malformed beacon configuration: " + name)
        navigation = document.find(".//nav[@id='main-navigation']")
        nav_links = navigation.findall(".//a") if navigation is not None else []
        require([a.get("href") for a in nav_links] == [home, home + "posts/", home + "about/"],
                "Incorrect localized navigation: " + name)
        if route.startswith(home + "posts/"):
            expected_current = "page" if route == home + "posts/" else "location"
            current = [(a.get("href"), a.get("aria-current")) for a in nav_links if a.get("aria-current")]
            require(current == [(home + "posts/", expected_current)], "Incorrect current Writing link: " + name)
        alternates = {a.get("hreflang"): a.get("href") for a in document.findall("head/link[@hreflang]")}
        switches = document.findall(".//nav[@class='language-switch']/a")
        if product or route in [home, home + "about/", home + "posts/"]:
            english = route.removeprefix("/hr") if locale == "hr" else route
            pair = {"en": english, "hr": "/hr" + english}
            require(alternates == {lang: public_url(path) for lang, path in pair.items()},
                    "Incorrect alternate languages: " + name)
            require([(a.get("hreflang"), a.get("href")) for a in switches] == list(pair.items()),
                    "Incorrect language switch: " + name)
            require([a.get("hreflang") for a in switches if a.get("aria-current") == "true"] == [locale],
                    "Incorrect selected language: " + name)
        elif route.startswith("/apps/"):
            require(not alternates and not switches, "Unexpected archive translation: " + name)
        require(document.find(".//main[@id='main-content']") is not None, "Missing main landmark: " + name)
        require(len(document.findall(".//h1")) == 1, "Expected one main heading: " + name)
        require(document.find(".//select[@id='appearance']") is not None,
                "Missing appearance preference: " + name)
        require("fonts.googleapis.com" not in text and "maxcdn.bootstrapcdn.com" not in text,
                "External font dependency remains: " + name)
        for image in document.findall(".//img"):
            require(image.get("alt") is not None, "Missing image alternative: " + name)
            require(image.get("width", "").isdigit() and image.get("height", "").isdigit(),
                    "Missing image dimensions: " + name)

    for file, document in documents.items():
        name = file.relative_to(directory).as_posix()
        page_url = urljoin(BASE_URL, name)
        for node in document.iter():
            references = [node.get(attribute) for attribute in ("href", "src") if node.get(attribute)]
            references.extend(candidate.strip().split()[0] for candidate in node.get("srcset", "").split(",")
                              if candidate.strip())
            for value in references:
                url = urlparse(urljoin(page_url, value))
                if url.scheme not in ("http", "https") or url.hostname != "www.mihasoftware.com":
                    continue
                target = destination(url.path)
                require(target.is_file(), "Broken internal reference in {}: {}".format(name, value))
                if url.fragment and target in documents:
                    ids = {element.get("id") for element in documents[target].iter()}
                    require(unquote(url.fragment) in ids,
                            "Missing fragment in {}: {}".format(name, value))

    for name in contract["feeds"]:
        file = directory / name
        require(file.is_file(), "Missing RSS feed: " + name)
        if file.is_file():
            try:
                feed = ElementTree.parse(file)
                require(feed.getroot().tag == "rss", "Not an RSS feed: " + name)
                require(bool(feed.findall("channel/item")), "Empty RSS feed: " + name)
                for link in feed.findall(".//link"):
                    require((link.text or "").startswith(BASE_URL), "Incorrect RSS hostname: " + name)
            except ElementTree.ParseError as error:
                require(False, "Invalid feed {}: {}".format(name, error))

    try:
        sitemap = ElementTree.parse(directory / "sitemap.xml")
        maps = {node.text for node in sitemap.findall("./{*}sitemap/{*}loc")}
        require(maps == {public_url("/en/sitemap.xml"), public_url("/hr/sitemap.xml")},
                "Incorrect language sitemap index")
        for locale in ("en", "hr"):
            tree = ElementTree.parse(directory / locale / "sitemap.xml")
            locations = {node.text for node in tree.findall("./{*}url/{*}loc")}
            expected = set()
            for file in documents:
                path = file.relative_to(directory).as_posix()
                if path.endswith("index.html") and path.startswith("hr/") == (locale == "hr"):
                    expected.add(public_url("/" + path.removesuffix("index.html")))
            require(locations == expected, "Incorrect sitemap pages: " + locale)
    except (OSError, ElementTree.ParseError) as error:
        require(False, "Invalid sitemap: " + str(error))
    robots = directory / "robots.txt"
    require(robots.is_file() and "Sitemap: " + BASE_URL + "sitemap.xml" in robots.read_text(),
            "Missing robots sitemap declaration")
    require(not (directory / "tags").exists() and not (directory / "categories").exists(),
            "Unused taxonomy output remains")
    not_found = documents.get(directory / "404.html")
    require(not_found is not None and not_found.find("head/meta[@content='noindex']") is not None,
            "Missing noindex 404 page")
    check_catalogues(directory, documents, destination, contract, require)
    check_archive(directory, documents, destination, contract, require)

    if errors:
        raise SystemExit("\n".join(errors))
    print("Validated {} HTML pages, {} feeds, and {} unchanged assets; analytics {}.".format(
        len(documents), len(contract["feeds"]), len(contract["assets_sha256"]), args.analytics))


def check_catalogues(directory, documents, destination, contract, require):
    # Discover the catalogue independently from rendered support/privacy pages.
    # Frozen release expectations below protect previously published integrations.
    slugs = set(contract["published_products"])
    for file in documents:
        match = re.fullmatch(r"(?:hr/)?apps/([^/]+)/(?:support|privacy)/index.html",
                             file.relative_to(directory).as_posix())
        if match:
            slugs.add(match[1])
    orders = []
    for locale, home in (("en", "/"), ("hr", "/hr/")):
        roots = {home + "apps/" + slug + "/" for slug in slugs}
        homepage = documents[destination(home)]
        catalogue = homepage.findall(".//a[@class='app-link']")
        supports = documents[destination(home + "about/")].findall(".//ul[@class='support-directory']//a")
        order = [card.get("href") for card in catalogue]
        require(len(order) == len(roots) and set(order) == roots, "Incomplete catalogue: " + home)
        require(sorted(a.get("href") for a in supports) == sorted(url + "support/" for url in order),
                "Support directory differs from catalogue: " + home)
        for slug, product in contract["published_products"].items():
            section = homepage.find(f".//section[@aria-labelledby='{product['platform']}-heading']")
            url = home + "apps/" + slug + "/"
            require(section is not None and section.find(f".//a[@href='{url}']") is not None,
                    "App missing from its platform section: " + url)
        orders.append([url.removeprefix(home) for url in order])
        for card in catalogue:
            root = card.get("href")
            slug = root.strip("/").split("/")[-1]
            release = contract["published_products"].get(slug, {})
            for child in ("", "privacy/", "support/"):
                url = root + child
                page = documents.get(destination(url))
                if page is None:
                    require(False, "Missing product page: " + url)
                    continue
                nav = page.findall(".//nav[@class='nav subnav']//a")
                require([a.get("href") for a in nav] == [root, root + "privacy/", root + "support/"],
                        "Broken product navigation: " + url)
                require([a.get("href") for a in nav if a.get("aria-current") == "page"] == [url],
                        "Incorrect current product link: " + url)
                email = page.find(".//p[@class='fineprint contact-line']/a")
                require(email is not None and email.get("href", "").startswith("mailto:"),
                        "Missing support contact: " + url)
                if release and email is not None:
                    require(email.get("href") == "mailto:" + release["email"], "Changed support contact: " + url)
            landing = documents.get(destination(root))
            if landing is None:
                continue
            shot = landing.find(".//figure[@class='shot']")
            art = card.find(".//div[@class='card-art']")
            for tag, mode in (("img", "light"), ("source", "dark")):
                hero = shot.find(".//" + tag) if shot is not None else None
                thumb = art.find(".//" + tag) if art is not None else None
                if mode == "light" or (release and mode in release[locale]):
                    require(hero is not None, "Missing " + mode + " screenshot: " + root)
                require((hero is None) == (thumb is None), "Screenshot variants differ: " + root)
                if hero is None or thumb is None:
                    continue
                candidates = hero.get("srcset", "")
                require(candidates and candidates == thumb.get("srcset"), "Card/hero mismatch: " + root)
                if mode == "light":
                    require(bool(hero.get("alt", "").strip()), "Missing screenshot description: " + root)
                else:
                    require(hero.get("media") == "(prefers-color-scheme: dark)" and "data-theme-source" in hero.attrib,
                            "Missing theme support: " + root)
                if release:
                    prefix = f"/apps/{slug}/images/{release[locale].get(mode)}_hu_"
                    require(all(item.strip().startswith(prefix) for item in candidates.split(",")),
                            "Incorrect localized capture: " + root)
            if release:
                button = landing.find(".//a[@class='button store-button']")
                require(button is not None and button.get("href") == release[locale]["store"],
                        "Incorrect store link: " + root)
    require(orders[0] == orders[1], "Catalogue order differs by language")


def check_archive(directory, documents, destination, contract, require):
    archive = documents[destination("/apps/archive/")].findall(".//a[@class='app-link']")
    downloads = {}
    for file, page in documents.items():
        button = page.find(".//a[@class='button download-button']")
        if button is not None:
            route = "/" + file.relative_to(directory).as_posix().removesuffix("index.html")
            downloads[route] = button.get("href")
    require(len(archive) == len(downloads) and {a.get("href") for a in archive} == set(downloads),
            "Incorrect archive membership")
    for route, target in contract["downloads"].items():
        require(downloads.get(route) == target, "Changed archive download: " + route)


if __name__ == "__main__":
    main()
