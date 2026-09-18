# RSS Feeds

Custom RSS feeds for websites with missing, broken, or outdated feeds.

Each feed is kept separate so it can be subscribed to individually in any RSS reader.

## Feeds

### WTA Tennis News
`feeds/wta.xml`

### ESPN Tennis
`feeds/espn-tennis.xml`

### Sportsnet Tennis
`feeds/sportsnet-tennis.xml`

## How it works

The feeds are regenerated automatically with GitHub Actions.

- ESPN Tennis uses ESPN's live tennis news data.
- WTA Tennis News is generated from the current WTA news page.
- Sportsnet Tennis is generated from the current Sportsnet tennis page and uses the correct individual article links.

## Feed URLs

Once GitHub Pages is enabled, the feeds are available at:

`https://mojocolony.github.io/rss-feeds/feeds/wta.xml`

`https://mojocolony.github.io/rss-feeds/feeds/espn-tennis.xml`

`https://mojocolony.github.io/rss-feeds/feeds/sportsnet-tennis.xml`

Additional feeds can be added to this repository over time.

## Files

- `generate_feeds.py` — generates the RSS feeds
- `.github/workflows/update-feeds.yml` — automatically refreshes the feeds
- `feeds/` — contains the generated RSS files
- `.nojekyll` — tells GitHub Pages to serve the files directly
