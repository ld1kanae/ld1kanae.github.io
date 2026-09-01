# DruMaster Ranking Backend

Cloudflare Workers + D1 backend for DruMaster online rankings.

## API

### `GET /health`
Checks Worker and D1 connectivity.

### `POST /v1/plays`
Registers one completed play. `playId` is idempotent: sending the same play more than once does not create duplicate ranking records.

Ranked plays must have:

- `autoPlay: false`
- `noScore: false`
- score from `0` through `1,000,000`
- non-negative judgement counts
- `noteCount === perfect + great + good + miss`
- `maxCombo <= noteCount` when max combo is present

The response contains the player's current best score position when available:

```json
{
  "ok": true,
  "accepted": true,
  "duplicate": false,
  "personalBest": true,
  "rank": 27,
  "totalPlayers": 1538
}
```

### `GET /v1/leaderboards/:songId/:chartId`

Query parameters:

- `rankingVersion` (default `1`)
- `limit` (1-100, default 50)
- `offset` (default 0)

Only each player's best play is returned. Ordering is score descending, then earliest server receipt time, then play ID for deterministic tie-breaking.

Example:

```text
/v1/leaderboards/nanairo/default?rankingVersion=1&limit=50
```

### `GET /v1/players/:playerId/best`

Required query parameter:

- `songId`

Optional:

- `chartId` (default `default`)
- `rankingVersion` (default `1`)

## Create the Cloudflare resources

Requires a Cloudflare account and Wrangler login/API token.

```bash
cd DruMaster-Backend
npm install
npx wrangler login
npm run d1:create
```

`wrangler d1 create drumaster-ranking` prints the new D1 database ID. Put that ID into `wrangler.jsonc` in place of:

```text
REPLACE_WITH_D1_DATABASE_ID
```

Apply the schema:

```bash
npm run d1:migrate:remote
```

Deploy the Worker:

```bash
npm run deploy
```

Wrangler then prints a URL similar to:

```text
https://drumaster-ranking-api.<account-subdomain>.workers.dev
```

Verify it:

```text
GET https://<worker-url>/health
```

Expected response:

```json
{
  "ok": true,
  "service": "drumaster-ranking-api",
  "database": true
}
```

## Connect the current DruMaster PC app

The PC app ranking client stores its endpoint in local storage. Once the Worker URL is known, set it from the app's WebView developer console (temporary setup mechanism):

```js
DruMasterRanking.setEndpoint('https://drumaster-ranking-api.<account-subdomain>.workers.dev')
```

Pending offline plays are retained in IndexedDB and will automatically retry after the endpoint is configured and connectivity is available.

Before public release, the endpoint should be baked into the PC package configuration instead of requiring this console command.

## Data model

- `players`: stable local player UUID + current display name
- `plays`: immutable ranked play records
- each ranking is scoped by `song_id + chart_id + ranking_version`
- each player contributes only their best score to leaderboard queries
- `played_at_client` is stored separately from trusted `received_at_server`

## Security model

This first public-ranking implementation rejects structurally impossible or disallowed results, but it cannot fully prevent a modified client from fabricating a plausible score. For stronger anti-cheat later, add server-known chart metadata and/or online verified-play sessions. Offline scores are intentionally supported, so they should remain an unverified ranking class if a verified ranking is introduced later.
