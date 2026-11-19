# miha software

Source for [www.mihasoftware.com](https://www.mihasoftware.com/), built with Hugo and served by Cloudflare Workers.

## Local development

Run `./scripts/hugo server --disableFastRender` and open the local URL it prints. The wrapper downloads the exact official Hugo version in `.hugo-version`, verifies its release checksum, and caches the executable under `.cache/`. It supports macOS and Linux and does not install anything globally. No Node, npm, Go, or Sass installation is needed.

## Adding or updating an app

Each current app owns one folder under `content/apps/`. For example, Radio has `_index.md`, `support.md`, and `privacy.md` for English, matching `_index.hr.md`, `support.hr.md`, and `privacy.hr.md` for Croatian, and an `images/` directory. Edit the matching Markdown file when the app changes. URLs follow the content tree, with Croatian under `/hr/`.

To add a fifth app, run:

```sh
./scripts/hugo new content --kind product apps/example-player
```

1. Fill in the six generated Markdown files. The English landing owns the catalogue weight, platform, availability, icon path, and optional `supportemail` override. The footer and the `contact-email` shortcode use the site address by default. Set `params.storeurl` on the English landing when a listing is public, and set `storelabel` in each language. Override `storeurl` on the Croatian landing if the listing has a localized URL.
2. Set `platform` to `appleMobile` or `android` to place the card in its homepage section. Cards keep their catalogue weight within each section. The card shows the translated availability, with an optional localized `availabilitylabel` for custom wording. Put the icon and actual screenshots under `images/`. Set `screenshot` and `screenshotalt` in each landing. Add `screenshotdark` for a matched dark capture. Hugo creates responsive WebP images for both the card and the landing.
3. Preview drafts with `./scripts/hugo server --buildDrafts --disableFastRender`. Remove the `cascade.draft` setting from both landing files when all six pages are ready. Run both validations below. Hugo builds the catalogues, support directories, product navigation, language links, and sitemaps automatically.

The homepage and About also have English and Croatian Markdown files. Interface strings live in `i18n/en.toml` and `i18n/hr.toml`. The archive at `content/apps/archive/` contains the English historical releases. Their explicit public URLs, original files under `static/downloads/` and `static/screenshots/`, and compatibility notes are part of the published site.

Keep legacy page redirects in `static/_redirects`. Four compatibility mounts in `config.toml` serve the original app images at their historical addresses from the bundle sources. New apps need no mount. The site has no RSS feeds.

## Validation

Validation uses Python 3.9+ and Node.js 18+ with npm. On first use, npm fetches the pinned Nu Html Checker, which can download its own Java runtime.

```sh
./scripts/build preview
./scripts/build production
```

Each command rebuilds `public/` and validates the result. Preview excludes analytics. Production applies the page analytics policy. The first run creates `.venv/` and installs the validator dependencies. GitHub Actions and Cloudflare run the same builds.

The Nu Html Checker checks every generated HTML page and stylesheet in `public/`. Errors fail the build. [Nu documentation](https://validator.github.io/validator/)

The Python checker validates HTML parsing, metadata, links, language pairs, both catalogues and support directories, product screenshots, sitemaps, and analytics. `tests/site-contract.json` also protects published URLs, contacts, store links, and original asset checksums. Update those expectations when deliberately changing an existing public integration. Use a Cloudflare preview to verify HTTP redirect status and destination. Hugo's development server does not interpret `_redirects`.

## Publishing

Open a pull request against `master`. GitHub Actions runs both builds and validates them, and Cloudflare builds a private Preview of the branch, reported on the pull request as the **Workers Builds** check. Merging to `master` makes Cloudflare build, validate and deploy the site to `www.mihasoftware.com`. Never commit `public/` or edit generated HTML.

`wrangler.jsonc` describes the Worker `miha-software`: static assets from `public/`, no Worker script, `404.html` for unknown paths, and the route `www.mihasoftware.com/*`. The Worker's own `workers.dev` address is switched off, so production is served only through that route. In the `mihasoftware.com` zone, the `www` and apex DNS records are proxied placeholders with no origin behind them, and a redirect rule sends the apex domain and plain HTTP to `https://www.mihasoftware.com`, keeping the path and query. A route is used instead of a Worker custom domain because Cloudflare will not attach a custom domain to a hostname that already has a DNS record, and removing the record first would have left `www` unresolvable during the move.

The second domain, `miha-software.com`, is its own Cloudflare zone and holds no site. Its apex and `www` records are the same proxied placeholders, and one redirect rule sends every request for either name to `https://www.mihasoftware.com`, keeping the path and query.

The Worker must use these settings under **Settings → Build**: build command `./scripts/build`, deploy command `npx wrangler deploy`, preview command `npx wrangler preview`, production branch `master`, and **Enable Preview Builds** on. Its name must match `name` in `wrangler.jsonc`. No build variables are needed; `scripts/build` reads the branch from `WORKERS_CI_BRANCH`.

Pushes to `master` get the production build. Every other branch gets a Preview: a `test` build without analytics at `<branch>-miha-software` on the account's `workers.dev` subdomain; the check's build log prints the full address. Both builds run the validator, and a failure stops the deployment. Cloudflare Access protects the Previews (the Worker's **Access** tab, previews only), so they need a sign-in; they also send `X-Robots-Tag: noindex`.

The GitHub Actions workflow has read-only repository permissions and never deploys. Monthly Dependabot PRs update its pinned Actions revisions. To update Hugo, change `.hugo-version`, run both validations, and review the Preview before merging.

## Analytics

Cloudflare Web Analytics uses the public beacon identifier in `config.toml`. Current product bundles inherit their analytics exclusion from the Hugo configuration, including both languages and all support and privacy pages. Elsewhere it is included only in production builds and is always excluded by `hugo server`, including when the server uses the production environment. Use the test environment for static previews. Cloudflare automatic injection is disabled.

[Open Web Analytics](https://dash.cloudflare.com/e2ea5e5904a6618a6f0363269c888fdf/web-analytics) to view the `www.mihasoftware.com` site. The service reports visits and pageviews, has six months of accessible history, and does not count custom download events. Browser blockers may suppress measurements. The previous GA4 account and historical data are retained, but this site no longer sends GA4 events.

## Rollback and history

To undo a release, revert its pull request; Cloudflare builds and deploys the revert. For an immediate fix, roll the Worker back to an earlier version under **Deployments** in the Cloudflare dashboard; the next push to `master` replaces it.

This repository started from a snapshot of the private `m1h4/website` repository at commit `8629dfb`, which is archived. GitHub Pages served the site until November 2026, when the repository was still named `m1h4.github.io`; the tag `pre-hugo-migration-2026-11-06` marks the last commit of the generated site from before the move to Hugo.
