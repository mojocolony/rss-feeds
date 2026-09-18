# Tennis RSS Feeds

Three separate RSS feeds generated hourly:

- **WTA Tennis News** → `feeds/wta.xml`
- **ESPN Tennis** → `feeds/espn-tennis.xml`
- **Sportsnet Tennis** → `feeds/sportsnet-tennis.xml`

They remain separate subscriptions. The repository simply keeps them together so there is only one small system to maintain.

## One-time setup

1. Create a new **public** GitHub repository. A simple name such as `tennis-rss-feeds` works well.
2. Upload all files and folders from this package, preserving the folder structure.
3. In the repository, open **Settings → Pages**.
4. Under **Build and deployment**, choose **Deploy from a branch**.
5. Select branch **main** and folder **/ (root)**, then save.
6. Open **Actions → Update RSS feeds → Run workflow** once to generate the first live feeds.

After GitHub Pages publishes, your three feed URLs will be:

- `https://YOUR-USERNAME.github.io/tennis-rss-feeds/feeds/wta.xml`
- `https://YOUR-USERNAME.github.io/tennis-rss-feeds/feeds/espn-tennis.xml`
- `https://YOUR-USERNAME.github.io/tennis-rss-feeds/feeds/sportsnet-tennis.xml`

Replace `YOUR-USERNAME` if you choose a different GitHub account, and replace `tennis-rss-feeds` if you choose a different repository name.

## How it works

The GitHub Action runs once an hour.

- **ESPN:** reads ESPN's live ATP and WTA JSON news endpoints, combines them, and removes duplicates.
- **WTA:** reads the WTA News index and follows current `/news/...` article links.
- **Sportsnet:** reads the Sportsnet Tennis page and follows only real tennis article URLs, fixing the bad links in Sportsnet's native RSS feed.

The generated XML files are ordinary RSS 2.0 feeds and can be added individually to an RSS reader.

## Notes

Website layouts can change. If WTA or Sportsnet changes its URL structure later, the generator may need a small adjustment. The workflow deliberately fails rather than silently publishing an empty feed.
